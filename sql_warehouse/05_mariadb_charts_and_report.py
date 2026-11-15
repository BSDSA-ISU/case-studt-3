"""
05_mariadb_charts_and_report.py
Connects directly to MariaDB (`student_academic_dw`), runs all analytical queries,
prints formatted results, and generates `mariadb_dw_visual_summaries.png`.
"""

import mysql.connector
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",  # <-- Match your MariaDB password
    "database": "student_academic_dw",
}

sns.set_theme(style="whitegrid")
conn = mysql.connector.connect(**DB_CONFIG)

kpi_df = pd.read_sql(
    """SELECT 
        COUNT(DISTINCT student_key) AS students,
        COUNT(fact_id) AS evaluations,
        ROUND(AVG(exam_score), 2) AS avg_score,
        ROUND(AVG(attendance_rate)*100, 1) AS avg_att,
        ROUND(AVG(below80_flag)*100, 1) AS risk_rate
       FROM Fact_Student_Subject_Performance""",
    conn,
)

subj_df = pd.read_sql(
    """SELECT sub.subject_name,
              ROUND(AVG(f.exam_score), 2) AS avg_score,
              ROUND(AVG(f.below80_flag)*100, 2) AS below80_risk_pct
       FROM Fact_Student_Subject_Performance f
       JOIN Dim_Subject sub ON f.subject_key = sub.subject_key
       GROUP BY sub.subject_name
       ORDER BY below80_risk_pct DESC""",
    conn,
)

hw_df = pd.read_sql(
    """SELECT 
        CASE 
            WHEN hw_mean_completion >= 90 THEN '1. >=90%'
            WHEN hw_mean_completion >= 75 THEN '2. 75-89%'
            WHEN hw_mean_completion >= 60 THEN '3. 60-74%'
            ELSE '4. <60%'
        END AS hw_tier,
        ROUND(AVG(exam_score), 2) AS avg_score,
        ROUND(AVG(below80_flag)*100, 2) AS below80_risk_pct
       FROM Fact_Student_Subject_Performance
       WHERE hw_mean_completion IS NOT NULL
       GROUP BY hw_tier
       ORDER BY hw_tier""",
    conn,
)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

sns.barplot(data=subj_df, x="subject_name", y="below80_risk_pct", palette="Blues_d", ax=axes[0])
axes[0].set_title("Chart 1: Academic Risk Rate (% Below 80) by Subject")
axes[0].set_ylabel("At-Risk Rate (%)")
axes[0].set_xlabel("Subject")
axes[0].tick_params(axis="x", rotation=25)

sns.barplot(data=hw_df, x="hw_tier", y="avg_score", color="#2b5c8f", ax=axes[1])
axes[1].set_title("Chart 2: Average Exam Score by Homework Completion Tier")
axes[1].set_ylabel("Average Exam Score")
axes[1].set_xlabel("Homework Completion Tier")

plt.suptitle(
    f"MariaDB DW KPIs | Students: {kpi_df['students'][0]:,} | Evaluations: {kpi_df['evaluations'][0]:,} | "
    f"Avg Score: {kpi_df['avg_score'][0]} | Avg Attendance: {kpi_df['avg_att'][0]}% | At-Risk Rate: {kpi_df['risk_rate'][0]}%",
    fontsize=11, fontweight="bold", y=1.03,
)
plt.tight_layout()
plt.savefig("mariadb_dw_visual_summaries.png", dpi=200, bbox_inches="tight")
print("Saved -> mariadb_dw_visual_summaries.png")
conn.close()
