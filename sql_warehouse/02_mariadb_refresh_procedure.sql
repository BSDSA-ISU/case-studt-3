-- ============================================================================
-- MARIADB STORED PROCEDURE: INCREMENTAL UPSERT / REFRESH PROCEDURE
-- Satisfies Section II Step 5 ("At least one data updating, reloading, or refresh procedure")
-- ============================================================================

USE student_academic_dw;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_refresh_student_performance $$

CREATE PROCEDURE sp_refresh_student_performance(
    IN p_student_id       VARCHAR(50),
    IN p_subject_name     VARCHAR(100),
    IN p_exam_date        DATE,
    IN p_exam_score       DECIMAL(6,2),
    IN p_att_sessions     INT,
    IN p_att_present      INT,
    IN p_att_absent       INT,
    IN p_att_late         INT,
    IN p_hw_count         INT,
    IN p_hw_mean_comp     DECIMAL(6,2),
    IN p_hw_missing_rate  DECIMAL(5,4),
    IN p_hw_late_rate     DECIMAL(5,4),
    IN p_comm_count       INT
)
BEGIN
    DECLARE v_student_key INT;
    DECLARE v_subject_key INT;
    DECLARE v_date_key    INT DEFAULT NULL;
    DECLARE v_risk_flag   TINYINT(1);
    DECLARE v_att_rate    DECIMAL(5,4) DEFAULT NULL;
    DECLARE v_abs_rate    DECIMAL(5,4) DEFAULT NULL;

    -- 1. Ensure Dimension Keys Exist (Late-Arriving Dimension Handling)
    INSERT IGNORE INTO Dim_Student (student_id) VALUES (p_student_id);
    SELECT student_key INTO v_student_key FROM Dim_Student WHERE student_id = p_student_id;

    INSERT IGNORE INTO Dim_Subject (subject_name) VALUES (p_subject_name);
    SELECT subject_key INTO v_subject_key FROM Dim_Subject WHERE subject_name = p_subject_name;

    IF p_exam_date IS NOT NULL THEN
        SET v_date_key = CAST(DATE_FORMAT(p_exam_date, '%Y%m%d') AS UNSIGNED);
        INSERT IGNORE INTO Dim_Date (date_key, full_date, year_num, quarter_num, month_num, month_name, day_of_week)
        VALUES (
            v_date_key,
            p_exam_date,
            YEAR(p_exam_date),
            QUARTER(p_exam_date),
            MONTH(p_exam_date),
            MONTHNAME(p_exam_date),
            DAYNAME(p_exam_date)
        );
    END IF;

    -- 2. Derive Business Rules & Rates
    SET v_risk_flag = IF(p_exam_score < 80, 1, 0);
    IF p_att_sessions > 0 THEN
        SET v_att_rate = ROUND(p_att_present / p_att_sessions, 4);
        SET v_abs_rate = ROUND(p_att_absent / p_att_sessions, 4);
    END IF;

    -- 3. Upsert into Fact Table (Insert new or update existing student-subject evaluation)
    INSERT INTO Fact_Student_Subject_Performance (
        student_key, subject_key, date_key, risk_key,
        exam_score, below80_flag, att_total_sessions, att_present_count,
        att_absent_count, att_late_count, attendance_rate, absence_rate,
        hw_total_count, hw_mean_completion, hw_missing_rate, hw_late_rate,
        parent_comm_count
    ) VALUES (
        v_student_key, v_subject_key, v_date_key, v_risk_flag,
        p_exam_score, v_risk_flag, p_att_sessions, p_att_present,
        p_att_absent, p_att_late, v_att_rate, v_abs_rate,
        p_hw_count, p_hw_mean_comp, p_hw_missing_rate, p_hw_late_rate,
        p_comm_count
    )
    ON DUPLICATE KEY UPDATE
        date_key           = VALUES(date_key),
        risk_key           = VALUES(risk_key),
        exam_score         = VALUES(exam_score),
        below80_flag       = VALUES(below80_flag),
        att_total_sessions = VALUES(att_total_sessions),
        att_present_count  = VALUES(att_present_count),
        att_absent_count   = VALUES(att_absent_count),
        att_late_count     = VALUES(att_late_count),
        attendance_rate    = VALUES(attendance_rate),
        absence_rate       = VALUES(absence_rate),
        hw_total_count     = VALUES(hw_total_count),
        hw_mean_completion = VALUES(hw_mean_completion),
        hw_missing_rate    = VALUES(hw_missing_rate),
        hw_late_rate       = VALUES(hw_late_rate),
        parent_comm_count  = VALUES(parent_comm_count),
        last_updated       = CURRENT_TIMESTAMP;
END $$

DELIMITER ;
