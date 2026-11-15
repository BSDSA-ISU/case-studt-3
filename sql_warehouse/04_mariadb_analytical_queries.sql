-- ============================================================================
-- MARIADB ANALYTICAL SQL QUERIES (OLAP & BUSINESS INTELLIGENCE)
-- Database: student_academic_dw
-- ============================================================================

USE student_academic_dw;

-- KPI SUMMARY: Executive Warehouse Metrics
SELECT 
    COUNT(DISTINCT f.student_key)          AS total_unique_students,
    COUNT(f.fact_id)                       AS total_subject_evaluations,
    ROUND(AVG(f.exam_score), 2)            AS overall_avg_exam_score,
    ROUND(AVG(f.attendance_rate) * 100, 2) AS overall_avg_attendance_pct,
    ROUND(AVG(f.hw_mean_completion), 2)    AS overall_avg_hw_completion_pct,
    SUM(f.below80_flag)                    AS total_at_risk_enrollments,
    ROUND(AVG(f.below80_flag) * 100, 2)    AS at_risk_rate_pct
FROM Fact_Student_Subject_Performance f;

-- FINDING 1: Subject-Level Risk & Score Distribution
SELECT 
    sub.subject_name,
    COUNT(f.fact_id)                       AS total_students,
    ROUND(AVG(f.exam_score), 2)            AS avg_exam_score,
    MIN(f.exam_score)                      AS min_score,
    MAX(f.exam_score)                      AS max_score,
    SUM(f.below80_flag)                    AS at_risk_count,
    ROUND(AVG(f.below80_flag) * 100, 2)    AS below80_risk_pct
FROM Fact_Student_Subject_Performance f
INNER JOIN Dim_Subject sub ON f.subject_key = sub.subject_key
GROUP BY sub.subject_name
ORDER BY below80_risk_pct DESC;

-- FINDING 2: Behavioral Profile Comparison (At-Risk vs. Not At-Risk)
SELECT 
    r.risk_label,
    COUNT(f.fact_id)                       AS evaluation_count,
    ROUND(AVG(f.exam_score), 2)            AS avg_exam_score,
    ROUND(AVG(f.attendance_rate) * 100, 2) AS avg_attendance_pct,
    ROUND(AVG(f.absence_rate) * 100, 2)    AS avg_absence_pct,
    ROUND(AVG(f.hw_mean_completion), 2)    AS avg_hw_completion_pct,
    ROUND(AVG(f.hw_missing_rate) * 100, 2) AS avg_missing_hw_pct,
    ROUND(AVG(f.parent_comm_count), 2)     AS avg_parent_communications
FROM Fact_Student_Subject_Performance f
INNER JOIN Dim_Risk_Category r ON f.risk_key = r.risk_key
GROUP BY r.risk_label
ORDER BY avg_exam_score DESC;

-- FINDING 3: Attendance Rate Tiers vs. Exam Performance
SELECT 
    CASE 
        WHEN f.attendance_rate >= 0.90 THEN '1. High Attendance (>=90%)'
        WHEN f.attendance_rate >= 0.80 THEN '2. Moderate Attendance (80-89%)'
        WHEN f.attendance_rate >= 0.70 THEN '3. Low Attendance (70-79%)'
        ELSE '4. Critical Chronically Absent (<70%)'
    END AS attendance_tier,
    COUNT(f.fact_id)                       AS student_subjects,
    ROUND(AVG(f.exam_score), 2)            AS avg_exam_score,
    ROUND(AVG(f.below80_flag) * 100, 2)    AS below80_risk_pct
FROM Fact_Student_Subject_Performance f
WHERE f.attendance_rate IS NOT NULL
GROUP BY attendance_tier
ORDER BY attendance_tier;

-- FINDING 4: Homework Completion Tiers vs. Exam Performance
SELECT 
    CASE 
        WHEN f.hw_mean_completion >= 90 THEN '1. Exemplary (>=90%)'
        WHEN f.hw_mean_completion >= 75 THEN '2. Satisfactory (75-89%)'
        WHEN f.hw_mean_completion >= 60 THEN '3. Partial (60-74%)'
        ELSE '4. Deficient (<60%)'
    END AS homework_tier,
    COUNT(f.fact_id)                       AS student_subjects,
    ROUND(AVG(f.exam_score), 2)            AS avg_exam_score,
    ROUND(AVG(f.below80_flag) * 100, 2)    AS below80_risk_pct
FROM Fact_Student_Subject_Performance f
WHERE f.hw_mean_completion IS NOT NULL
GROUP BY homework_tier
ORDER BY homework_tier;

-- FINDING 5: Parent-Teacher Communication Frequency vs. Academic Risk
SELECT 
    CASE 
        WHEN f.parent_comm_count = 0 THEN '0 Contacts'
        WHEN f.parent_comm_count BETWEEN 1 AND 2 THEN '1-2 Contacts'
        WHEN f.parent_comm_count BETWEEN 3 AND 4 THEN '3-4 Contacts'
        ELSE '5+ Contacts'
    END AS communication_frequency,
    COUNT(f.fact_id)                       AS student_subjects,
    ROUND(AVG(f.exam_score), 2)            AS avg_exam_score,
    ROUND(AVG(f.below80_flag) * 100, 2)    AS below80_risk_pct
FROM Fact_Student_Subject_Performance f
GROUP BY communication_frequency
ORDER BY communication_frequency;

-- FINDING 6: Multi-Subject At-Risk Student Intervention Roster
SELECT 
    s.student_id,
    s.gender,
    s.grade_level,
    COUNT(f.fact_id)                       AS subjects_taken,
    SUM(f.below80_flag)                    AS subjects_below_80,
    ROUND(AVG(f.exam_score), 2)            AS overall_avg_score,
    ROUND(AVG(f.attendance_rate) * 100, 2) AS avg_attendance_pct,
    ROUND(AVG(f.hw_mean_completion), 2)    AS avg_hw_completion_pct
FROM Fact_Student_Subject_Performance f
INNER JOIN Dim_Student s ON f.student_key = s.student_key
GROUP BY s.student_id, s.gender, s.grade_level
HAVING SUM(f.below80_flag) >= 2
ORDER BY subjects_below_80 DESC, overall_avg_score ASC
LIMIT 20;

-- DEMO TEST: Call Incremental Refresh Stored Procedure (`sp_refresh_student_performance`)
-- CALL sp_refresh_student_performance('STU_TEST_001', 'Mathematics', '2026-11-14', 76.50, 20, 15, 4, 1, 10, 72.00, 0.2000, 0.1000, 2);
