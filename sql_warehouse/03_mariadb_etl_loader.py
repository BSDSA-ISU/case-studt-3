"""
03_mariadb_etl_loader.py
Connects to local MariaDB server (`student_academic_dw`), creates the Star Schema
(`01_mariadb_schema_ddl.sql`), and imports your ALREADY-CLEANED Power BI datasets
directly from `./clean-powerbi/` (auto-detecting `./cleaned_data_for_powerbi/` if needed):
  - bi_dim_student.csv
  - bi_dim_subject.csv
  - bi_fact_student_subject_performance.csv
  - bi_clean_attendance.csv
  - bi_clean_homework.csv
  - bi_clean_communications.csv

Prerequisites:
    pip install pandas numpy mysql-connector-python
"""

import os
import numpy as np
import pandas as pd
import mysql.connector

# --- UPDATE YOUR MARIADB CREDENTIALS HERE ---
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "ali",
    "password": "toshinoukyouko",
    "database": "student_academic_dw"
    }
DB_NAME = "student_academic_dw"

# Automatically resolve your cleaned Power BI folder
CLEAN_DIR = "./clean-powerbi/"
if not os.path.isdir(CLEAN_DIR) and os.path.isdir("./cleaned_data_for_powerbi/"):
    CLEAN_DIR = "./cleaned_data_for_powerbi/"


def find_col(df, candidates):
    lower_map = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    for c in df.columns:
        for cand in candidates:
            if cand.lower() in c.lower():
                return c
    return None


def load_clean_powerbi_csvs():
    print(f"[1/4] Reading cleaned Power BI CSVs from `{CLEAN_DIR}`...")
    dim_student = pd.read_csv(os.path.join(CLEAN_DIR, "bi_dim_student.csv"))
    dim_subject = pd.read_csv(os.path.join(CLEAN_DIR, "bi_dim_subject.csv"))
    fact_df = pd.read_csv(os.path.join(CLEAN_DIR, "bi_fact_student_subject_performance.csv"))

    # Also verify the 3 cleaned operational detail tables exist & log their row counts
    clean_att = pd.read_csv(os.path.join(CLEAN_DIR, "bi_clean_attendance.csv"))
    clean_hw = pd.read_csv(os.path.join(CLEAN_DIR, "bi_clean_homework.csv"))
    clean_comm = pd.read_csv(os.path.join(CLEAN_DIR, "bi_clean_communications.csv"))

    print(f"  - bi_dim_student.csv                    : {len(dim_student):,} rows")
    print(f"  - bi_dim_subject.csv                    : {len(dim_subject):,} rows")
    print(f"  - bi_fact_student_subject_performance   : {len(fact_df):,} rows")
    print(f"  - bi_clean_attendance.csv               : {len(clean_att):,} rows")
    print(f"  - bi_clean_homework.csv                 : {len(clean_hw):,} rows")
    print(f"  - bi_clean_communications.csv           : {len(clean_comm):,} rows")

    # Standardize string nulls on dim_student
    dim_student = dim_student.drop_duplicates(subset=["Student_ID"]).copy()
    for col in dim_student.select_dtypes(include="object").columns:
        if col != "Student_ID":
            dim_student[col] = dim_student[col].fillna("Unknown").astype(str).str.strip()

    # Safety check: ensure no '%' or negative values remain in fact_df
    score_col = find_col(fact_df, ["Exam_Score", "exam_score_clean", "Score", "Grade"])
    date_col = find_col(fact_df, ["Exam_Date", "exam_date_clean", "Date"])
    hw_mean_col = find_col(fact_df, ["hw_mean_completion", "perf_hw_completion_pct", "Homework_Completion_%"])

    fact_df[score_col] = pd.to_numeric(fact_df[score_col], errors="coerce")
    if hw_mean_col:
        fact_df[hw_mean_col] = (
            fact_df[hw_mean_col].astype(str).str.replace("%", "", regex=False).str.strip()
        )
        fact_df[hw_mean_col] = pd.to_numeric(fact_df[hw_mean_col], errors="coerce").clip(lower=0, upper=100)

    fact_df["exam_score_clean"] = fact_df[score_col]
    fact_df["exam_date_clean"] = pd.to_datetime(fact_df[date_col], errors="coerce") if date_col else pd.NaT
    fact_df["hw_mean_clean"] = fact_df[hw_mean_col] if hw_mean_col else np.nan
    fact_df["below80_clean"] = (
        fact_df["below80"].astype(int)
        if "below80" in fact_df.columns
        else (fact_df["exam_score_clean"] < 80).astype(int)
    )

    return dim_student, dim_subject, fact_df, clean_att, clean_hw, clean_comm


def run_ddl_file(cursor, path):
    with open(path, "r", encoding="utf-8") as f:
        sql_text = f.read()
    cleaned = "\n".join(line for line in sql_text.splitlines() if not line.strip().startswith("--"))
    for stmt in cleaned.split(";"):
        stmt = stmt.strip()
        if stmt:
            cursor.execute(stmt)


def load_into_mariadb(dim_student, dim_subject, fact_df, clean_att, clean_hw, clean_comm):
    print("[2/4] Connecting to MariaDB and initializing Star Schema...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    ddl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "01_mariadb_schema_ddl.sql")
    run_ddl_file(cursor, ddl_path)
    conn.commit()
    cursor.execute(f"USE {DB_NAME}")

    # 1. Load Dim_Risk_Category
    cursor.executemany(
        "INSERT IGNORE INTO Dim_Risk_Category (risk_key, risk_code, risk_label, threshold_rule) VALUES (%s, %s, %s, %s)",
        [
            (0, 0, "Not At-Risk (>= 80)", "Exam_Score >= 80"),
            (1, 1, "At-Risk (< 80)", "Exam_Score < 80"),
        ],
    )

    # 2. Load Dim_Subject from bi_dim_subject.csv
    subj_col = find_col(dim_subject, ["Subject", "subject_name"])
    subjects = [(str(s).strip(),) for s in dim_subject[subj_col].dropna().unique()]
    cursor.executemany("INSERT IGNORE INTO Dim_Subject (subject_name) VALUES (%s)", subjects)

    # 3. Load Dim_Student from bi_dim_student.csv
    gender_col = find_col(dim_student, ["Gender", "Sex"])
    age_col = find_col(dim_student, ["Age"])
    grade_col = find_col(dim_student, ["Grade_Level", "Grade", "Year_Level"])
    sec_col = find_col(dim_student, ["Section", "Class"])

    student_rows = []
    for _, r in dim_student.iterrows():
        student_rows.append((
            str(r["Student_ID"]).strip(),
            str(r[gender_col]) if gender_col else "Unknown",
            int(float(r[age_col])) if age_col and pd.notnull(r[age_col]) else None,
            str(r[grade_col]) if grade_col else "Unknown",
            str(r[sec_col]) if sec_col else "Unknown",
        ))
    cursor.executemany(
        "INSERT IGNORE INTO Dim_Student (student_id, gender, age, grade_level, section) VALUES (%s, %s, %s, %s, %s)",
        student_rows,
    )

    # 4. Load Dim_Date from cleaned exam dates
    valid_dates = pd.to_datetime(fact_df["exam_date_clean"].dropna().unique())
    date_rows = []
    for d in valid_dates:
        ts = pd.Timestamp(d)
        date_rows.append((
            int(ts.strftime("%Y%m%d")),
            ts.strftime("%Y-%m-%d"),
            int(ts.year),
            int(ts.quarter),
            int(ts.month),
            ts.strftime("%B"),
            ts.strftime("%A"),
        ))
    cursor.executemany(
        """INSERT IGNORE INTO Dim_Date
           (date_key, full_date, year_num, quarter_num, month_num, month_name, day_of_week)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        date_rows,
    )
    conn.commit()

    # Lookup surrogate keys
    cursor.execute("SELECT student_id, student_key FROM Dim_Student")
    student_map = dict(cursor.fetchall())
    cursor.execute("SELECT subject_name, subject_key FROM Dim_Subject")
    subject_map = dict(cursor.fetchall())

    # 5. Load Fact_Student_Subject_Performance from bi_fact_student_subject_performance.csv
    comm_col = find_col(fact_df, ["comm_total_count", "parent_comm_count"])
    fact_rows = []
    for _, r in fact_df.iterrows():
        s_key = student_map.get(str(r["Student_ID"]).strip())
        sub_key = subject_map.get(str(r["Subject"]).strip())
        if not s_key or not sub_key:
            continue
        d_key = int(pd.Timestamp(r["exam_date_clean"]).strftime("%Y%m%d")) if pd.notnull(r["exam_date_clean"]) else None
        fact_rows.append((
            s_key,
            sub_key,
            d_key,
            int(r["below80_clean"]),
            float(r["exam_score_clean"]),
            int(r["below80_clean"]),
            int(r["att_total_sessions"]) if "att_total_sessions" in r and pd.notnull(r["att_total_sessions"]) else 0,
            int(r["att_present_count"]) if "att_present_count" in r and pd.notnull(r["att_present_count"]) else 0,
            int(r["att_absent_count"]) if "att_absent_count" in r and pd.notnull(r["att_absent_count"]) else 0,
            int(r["att_late_count"]) if "att_late_count" in r and pd.notnull(r["att_late_count"]) else 0,
            round(float(r["attendance_rate"]), 4) if "attendance_rate" in r and pd.notnull(r["attendance_rate"]) else None,
            round(float(r["absence_rate"]), 4) if "absence_rate" in r and pd.notnull(r["absence_rate"]) else None,
            int(r["hw_count"]) if "hw_count" in r and pd.notnull(r["hw_count"]) else 0,
            round(float(r["hw_mean_clean"]), 2) if pd.notnull(r["hw_mean_clean"]) else None,
            round(float(r["hw_missing_rate"]), 4) if "hw_missing_rate" in r and pd.notnull(r["hw_missing_rate"]) else None,
            round(float(r["hw_late_rate"]), 4) if "hw_late_rate" in r and pd.notnull(r["hw_late_rate"]) else None,
            int(r[comm_col]) if comm_col and pd.notnull(r[comm_col]) else 0,
        ))

    insert_sql = """
        INSERT INTO Fact_Student_Subject_Performance (
            student_key, subject_key, date_key, risk_key,
            exam_score, below80_flag, att_total_sessions, att_present_count,
            att_absent_count, att_late_count, attendance_rate, absence_rate,
            hw_total_count, hw_mean_completion, hw_missing_rate, hw_late_rate,
            parent_comm_count
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            date_key = VALUES(date_key),
            risk_key = VALUES(risk_key),
            exam_score = VALUES(exam_score),
            below80_flag = VALUES(below80_flag),
            att_total_sessions = VALUES(att_total_sessions),
            att_present_count = VALUES(att_present_count),
            att_absent_count = VALUES(att_absent_count),
            att_late_count = VALUES(att_late_count),
            attendance_rate = VALUES(attendance_rate),
            absence_rate = VALUES(absence_rate),
            hw_total_count = VALUES(hw_total_count),
            hw_mean_completion = VALUES(hw_mean_completion),
            hw_missing_rate = VALUES(hw_missing_rate),
            hw_late_rate = VALUES(hw_late_rate),
            parent_comm_count = VALUES(parent_comm_count)
    """
    cursor.executemany(insert_sql, fact_rows)

    # 6. Also create & load cleaned staging/detail tables (`Stg_Clean_Attendance`, `Stg_Clean_Homework`, `Stg_Clean_Communications`)
    #    so every single cleaned CSV in clean-powerbi/ is directly queryable inside MariaDB!
    print("[3/4] Loading cleaned detail tables (`bi_clean_attendance`, `bi_clean_homework`, `bi_clean_communications`)...")
    cursor.execute("DROP TABLE IF EXISTS Stg_Clean_Attendance")
    cursor.execute("""
        CREATE TABLE Stg_Clean_Attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id VARCHAR(50),
            subject_name VARCHAR(100),
            att_date VARCHAR(30),
            attendance_status VARCHAR(50),
            INDEX idx_stg_att_stu (student_id, subject_name)
        ) ENGINE=InnoDB
    """)
    att_date_col = find_col(clean_att, ["Date", "Attendance_Date"])
    att_stat_col = find_col(clean_att, ["Attendance_Status", "Status"])
    att_rows = list(zip(
        clean_att["Student_ID"].astype(str),
        clean_att["Subject"].astype(str),
        clean_att[att_date_col].astype(str) if att_date_col else [""] * len(clean_att),
        clean_att[att_stat_col].astype(str) if att_stat_col else [""] * len(clean_att),
    ))
    for i in range(0, len(att_rows), 25000):
        cursor.executemany(
            "INSERT INTO Stg_Clean_Attendance (student_id, subject_name, att_date, attendance_status) VALUES (%s, %s, %s, %s)",
            att_rows[i:i+25000],
        )

    cursor.execute("DROP TABLE IF EXISTS Stg_Clean_Homework")
    cursor.execute("""
        CREATE TABLE Stg_Clean_Homework (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id VARCHAR(50),
            subject_name VARCHAR(100),
            due_date VARCHAR(30),
            completion_pct DECIMAL(6, 2),
            homework_status VARCHAR(50),
            INDEX idx_stg_hw_stu (student_id, subject_name)
        ) ENGINE=InnoDB
    """)
    hw_date_col = find_col(clean_hw, ["Due_Date", "Date", "Submission_Date"])
    hw_comp_col = find_col(clean_hw, ["Homework_Completion_%", "Completion_%", "Completion"])
    hw_stat_col = find_col(clean_hw, ["Homework Status", "Homework_Status", "Status"])
    hw_comp_vals = (
        pd.to_numeric(clean_hw[hw_comp_col].astype(str).str.replace("%", "", regex=False).str.strip(), errors="coerce")
        .clip(lower=0, upper=100)
        if hw_comp_col else pd.Series([None] * len(clean_hw))
    )
    hw_rows = [
        (
            str(sid),
            str(subj),
            str(dt) if pd.notnull(dt) else None,
            round(float(comp), 2) if pd.notnull(comp) else None,
            str(st) if pd.notnull(st) else None,
        )
        for sid, subj, dt, comp, st in zip(
            clean_hw["Student_ID"],
            clean_hw["Subject"],
            clean_hw[hw_date_col] if hw_date_col else [None] * len(clean_hw),
            hw_comp_vals,
            clean_hw[hw_stat_col] if hw_stat_col else [None] * len(clean_hw),
        )
    ]
    for i in range(0, len(hw_rows), 25000):
        cursor.executemany(
            "INSERT INTO Stg_Clean_Homework (student_id, subject_name, due_date, completion_pct, homework_status) VALUES (%s, %s, %s, %s, %s)",
            hw_rows[i:i+25000],
        )

    cursor.execute("DROP TABLE IF EXISTS Stg_Clean_Communications")
    cursor.execute("""
        CREATE TABLE Stg_Clean_Communications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id VARCHAR(50),
            comm_date VARCHAR(30),
            comm_type VARCHAR(100),
            INDEX idx_stg_comm_stu (student_id)
        ) ENGINE=InnoDB
    """)
    c_date_col = find_col(clean_comm, ["Date", "Communication_Date", "Contact_Date"])
    c_type_col = find_col(clean_comm, ["Type", "Communication_Type", "Method", "Channel", "Reason"])
    comm_rows = [
        (
            str(sid),
            str(dt) if pd.notnull(dt) else None,
            str(tp) if pd.notnull(tp) else None,
        )
        for sid, dt, tp in zip(
            clean_comm["Student_ID"],
            clean_comm[c_date_col] if c_date_col else [None] * len(clean_comm),
            clean_comm[c_type_col] if c_type_col else [None] * len(clean_comm),
        )
    ]
    for i in range(0, len(comm_rows), 25000):
        cursor.executemany(
            "INSERT INTO Stg_Clean_Communications (student_id, comm_date, comm_type) VALUES (%s, %s, %s)",
            comm_rows[i:i+25000],
        )

    conn.commit()
    return conn, cursor


def validate_mariadb(cursor):
    print("[4/4] Validating MariaDB Star Schema & Cleaned Staging Tables...")
    tables = [
        "Dim_Student",
        "Dim_Subject",
        "Dim_Date",
        "Dim_Risk_Category",
        "Fact_Student_Subject_Performance",
        "Stg_Clean_Attendance",
        "Stg_Clean_Homework",
        "Stg_Clean_Communications",
    ]
    for tbl in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
        print(f"  - {tbl:<34}: {cursor.fetchone()[0]:,} rows")

    cursor.execute("SELECT COUNT(*) FROM Fact_Student_Subject_Performance")
    fact_total = cursor.fetchone()[0]
    assert fact_total >= 2000, f"Fact table count ({fact_total}) is below 2,000 minimum!"

    cursor.execute("SELECT MIN(hw_mean_completion), MAX(hw_mean_completion) FROM Fact_Student_Subject_Performance")
    min_hw, max_hw = cursor.fetchone()
    print(f"  [PASS] Clean homework completion range in MariaDB: [{min_hw}, {max_hw}]")


if __name__ == "__main__":
    d_stu, d_sub, f_df, c_att, c_hw, c_comm = load_clean_powerbi_csvs()
    connection, cur = load_into_mariadb(d_stu, d_sub, f_df, c_att, c_hw, c_comm)
    validate_mariadb(cur)
    cur.close()
    connection.close()
    print("\nDone! All 6 cleaned CSVs from `clean-powerbi/` are now loaded in MariaDB (`student_academic_dw`).")
