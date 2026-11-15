# Student Academic Performance, Engagement & Risk Analytics
**Integrated Data Warehousing, Machine Learning & Business Intelligence Presentation**

---

## Slide 1: Title Slide
* **Title:** Student Academic Performance & Early Risk Analytics: An Integrated Data Warehouse, Machine Learning, and BI Approach
* **Subtitle:** Case Study on Multi-Source Educational Data (`student_academic_dw`)
* **Presenters:** [Insert Group Members' Names]
* **Course / Date:** DSA 312 | November 2026

---

## Slide 2: Introduction
* **Context:** Schools collect massive daily operational records across attendance, homework submissions, exams, and parent-teacher communications—yet these tables remain siloed and unstandardized.
* **The Challenge:**
  * Raw records contain duplicate session logs, mixed string formats (`"80%"`), and impossible out-of-range anomalies (`-5` completion).
  * Without unified integration, educators only identify struggling students (`Exam_Score < 80`) *after* final exams are graded.
* **Our Solution:** Build a centralized **MariaDB Star Schema Data Warehouse**, train **leakage-free Machine Learning classifiers** to evaluate early risk predictability, and deploy an interactive **Power BI Dashboard** for proactive advisor intervention.

---

## Slide 3: Project Objectives
1. **Data Integration & Warehousing:** Clean and consolidate **498,396 raw operational records** across **12,156 students** into a normalized **MariaDB Star Schema** (`student_academic_dw`) at the `(Student_ID, Subject)` grain.
2. **Exploratory & BI Analytics:** Uncover subject-level risk patterns, attendance/homework engagement distributions, and parent-teacher communication trends via interactive **Power BI** dashboards.
3. **Predictive Risk Modeling:** Develop and compare **Logistic Regression**, **Random Forest**, and **Gradient Boosting** models using strict `Student_ID`-grouped splitting to predict whether a student will score below 80 (`below80 = 1`) without data leakage.
4. **Actionable Decision Support:** Translate model diagnostics and warehouse KPIs into practical early-warning guidelines for school administrators and advisors.

---

## Slide 4: Methodology — End-to-End Pipeline & ETL
* **5 Operational Source Tables (498,396 Raw Rows):**
  * `students.csv` (12,156) | `performance.csv` (36,468) | `homework.csv` (60,780) | `attendance.csv` (364,680) | `teacher_parent_communication.csv` (24,312)
* **Automated ETL & Remediation:**
  * Deduplicated composite attendance keys `(Student_ID, Subject, Date)`.
  * Stripped `%` symbols and winsorized (clipped) out-of-range homework values (`-5`) to valid `[0, 100]`.
  * Assigned `0` for students with no recorded parent outreach (`comm_total_count`).
* **Star Schema Warehouse (`student_academic_dw`):**
  * **Fact Table:** `Fact_Student_Subject_Performance` ($N = 28,736$ clean analytical evaluations)
  * **Dimensions:** `Dim_Student`, `Dim_Subject`, `Dim_Date`, `Dim_Risk_Category`

---

## Slide 5: Methodology — Leakage-Free ML Design
* **Target Definition:** Binary classification `below80` (`1` = At-Risk if `Exam_Score < 80`, `0` = Not At-Risk).
* **Leakage Prevention:**
  * Excluded `Exam_Score`, `Student_ID`, personal text, and raw dates from predictor features.
  * Used **`GroupShuffleSplit` (80% Train / 20% Test)** grouped by `Student_ID` (**0 shared students** across splits) and **5-Fold `StratifiedGroupKFold`** for validation.
  * Fitted `SimpleImputer`, `StandardScaler`, and `OneHotEncoder` strictly on training folds only.
* **Models Evaluated (`random_state=42`):**
  * **Logistic Regression** (`class_weight='balanced'`) — Interpretable linear baseline
  * **Random Forest** (`n_estimators=100`, `max_depth=8`, `balanced`) — Non-linear ensemble
  * **Gradient Boosting** (`n_estimators=100`, `learning_rate=0.05`, `max_depth=3`) — Sequential boosted trees

---

## Slide 6: Results & Discussion — Model Performance
* **Primary Metrics:** **ROC-AUC** (threshold-independent ranking) and **F1-Score** (positive class: `below80 = 1`).

| Model | Split | Accuracy | Precision | Recall | F1-Score | ROC-AUC |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Logistic Regression** | 5-Fold Val | 0.5061 | 0.5700 | 0.4992 | 0.5321 | **0.5085** |
| **Logistic Regression** | **Test (20%)** | 0.5027 | 0.5677 | 0.4952 | 0.5290 | **0.5044** |
| **Random Forest** | 5-Fold Val | 0.5104 | 0.5696 | 0.5333 | 0.5506 | 0.5086 |
| **Random Forest** | **Test (20%)** | 0.5006 | 0.5627 | 0.5129 | 0.5366 | 0.4987 |
| **Gradient Boosting** | 5-Fold Val | 0.5608 | 0.5625 | 0.9876 | 0.7168 | 0.5099 |
| **Gradient Boosting** | **Test (20%)** | **0.5612** | 0.5629 | **0.9919** | **0.7183** | 0.4987 |

* **Key Analytical Finding:**
  * All models exhibit **near-random ROC-AUC (~0.50)**, proving that aggregate attendance and homework logs alone carry weak predictive signal for exam scores in this dataset.
  * **Gradient Boosting** achieved `0.7183` F1 by defaulting to the majority class (`below80 = 1`, `99.19%` recall), whereas **Logistic Regression** (`0.5044` Test AUC) provided the best calibrated ranking across classes.

---

## Slide 7: Results & Discussion — Error & Feature Analysis
* **Confusion Matrix (Logistic Regression on Held-Out Test, $N = 5,709$):**
  * **True Positives (`TP = 1,594`):** At-risk students correctly flagged.
  * **True Negatives (`TN = 1,276`):** Passing students correctly cleared.
  * **False Negatives (`FN = 1,625`):** Missed struggling students (maintained good attendance/homework but scored $< 80$ on exams).
  * **False Positives (`FP = 1,214`):** False alarms (low homework/attendance logs but scored $\ge 80$).
* **Top Predictive Features & Tuning:**
  * Subject-level attendance (`att_present_count`, `attendance_rate`) and homework completion (`perf_hw_completion_pct`, `hw_mean_completion`) ranked highest, while `Gender` and `comm_total_count` had minimal weight.
  * Hyperparameter tuning (`Config B`: `n_estimators=100`, `lr=0.05`, `max_depth=3`) achieved the best cross-validated ROC-AUC (`0.5099 ± 0.0006`) without overfitting.

---

## Slide 8: Business Intelligence (BI) Dashboard Overview
*(Groupmate Note: Place full-screen screenshot of your Power BI Report / Star Schema view here)*

* **Power BI Star Schema Data Model:**
  * Connected `bi_fact_student_subject_performance` (`28,736` rows) with `bi_dim_student` (`12,156` students), `bi_dim_subject` (`6` subjects), and cleaned detail tables (`bi_clean_attendance`, `bi_clean_homework`, `bi_clean_communications`).
* **Core Dashboard Visuals & KPIs:**
  1. **Executive KPI Cards:** Total Unique Students (`12,156`), Total Subject Evaluations (`28,736`), Overall At-Risk Rate (`~56.4%` below 80), Average Attendance Rate, and Average Homework Completion %.
  2. **Subject Risk Breakdown:** Bar/column comparison of `below80` risk rates and mean exam scores across all 6 subjects.
  3. **Engagement & Communication Slicers:** Interactive filtering by `Grade_Level`, `Section`, `Gender`, and `Subject` to drill down into multi-subject at-risk student rosters.

---

## Slide 9: Recommendations & Conclusion
* **Conclusion:**
  * Successfully built an automated, leakage-free **MariaDB + Python + Power BI** analytics pipeline.
  * Honest grouped evaluation demonstrated that routine attendance and homework summaries alone are insufficient (`Test ROC-AUC = 0.5044`) for automated high-stakes student classification.
* **Three Actionable Recommendations:**
  1. **Capture Formative Academic Signals:** Log quiz scores, midterm grades, and LMS submission timestamps to boost predictive signal beyond attendance counts.
  2. **Enforce Database Ingestion Constraints:** Maintain `CHECK` rules and stored procedures (`sp_refresh_student_performance`) in MariaDB to block negative percentages and duplicate keys at entry.
  3. **Human-in-the-Loop BI Screening:** Use the Power BI dashboard for descriptive monitoring and advisor outreach rather than automated punitive labeling.