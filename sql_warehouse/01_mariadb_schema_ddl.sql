-- ============================================================================
-- DATA WAREHOUSE DESIGN & IMPLEMENTATION: MARIADB STAR SCHEMA DDL
-- Project: Student Academic Performance, Attendance & Engagement Data Warehouse
-- Target DBMS: MariaDB 10.5+ / MySQL 8.0+ (InnoDB Engine, UTF8MB4)
-- ============================================================================

CREATE DATABASE IF NOT EXISTS student_academic_dw
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE student_academic_dw;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS Fact_Student_Subject_Performance;
DROP TABLE IF EXISTS Dim_Student;
DROP TABLE IF EXISTS Dim_Subject;
DROP TABLE IF EXISTS Dim_Date;
DROP TABLE IF EXISTS Dim_Risk_Category;
SET FOREIGN_KEY_CHECKS = 1;

-- 1. DIMENSION TABLE: Dim_Student
CREATE TABLE Dim_Student (
    student_key       INT AUTO_INCREMENT PRIMARY KEY,
    student_id        VARCHAR(50) NOT NULL,
    gender            VARCHAR(20),
    age               INT,
    grade_level       VARCHAR(30),
    section           VARCHAR(30),
    enrollment_status VARCHAR(30) DEFAULT 'Active',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_student_id UNIQUE (student_id)
) ENGINE=InnoDB;

-- 2. DIMENSION TABLE: Dim_Subject
CREATE TABLE Dim_Subject (
    subject_key       INT AUTO_INCREMENT PRIMARY KEY,
    subject_name      VARCHAR(100) NOT NULL,
    department        VARCHAR(100) DEFAULT 'General Academics',
    CONSTRAINT uq_dim_subject_name UNIQUE (subject_name)
) ENGINE=InnoDB;

-- 3. DIMENSION TABLE: Dim_Date
CREATE TABLE Dim_Date (
    date_key          INT PRIMARY KEY, -- YYYYMMDD format
    full_date         DATE NOT NULL,
    year_num          INT NOT NULL,
    quarter_num       INT NOT NULL,
    month_num         INT NOT NULL,
    month_name        VARCHAR(20) NOT NULL,
    day_of_week       VARCHAR(20) NOT NULL,
    CONSTRAINT uq_dim_full_date UNIQUE (full_date)
) ENGINE=InnoDB;

-- 4. DIMENSION TABLE: Dim_Risk_Category
CREATE TABLE Dim_Risk_Category (
    risk_key          INT PRIMARY KEY,
    risk_code         TINYINT NOT NULL, -- 1 = At-Risk (<80), 0 = Not At-Risk (>=80)
    risk_label        VARCHAR(50) NOT NULL,
    threshold_rule    VARCHAR(100) NOT NULL,
    CONSTRAINT uq_dim_risk_code UNIQUE (risk_code)
) ENGINE=InnoDB;

-- 5. FACT TABLE: Fact_Student_Subject_Performance
-- Grain: One record per Student per Subject exam evaluation
CREATE TABLE Fact_Student_Subject_Performance (
    fact_id              INT AUTO_INCREMENT PRIMARY KEY,
    student_key          INT NOT NULL,
    subject_key          INT NOT NULL,
    date_key             INT NULL,
    risk_key             INT NOT NULL,

    -- Quantitative Measures
    exam_score           DECIMAL(6, 2) NOT NULL,
    below80_flag         TINYINT(1) NOT NULL,
    att_total_sessions   INT DEFAULT 0,
    att_present_count    INT DEFAULT 0,
    att_absent_count     INT DEFAULT 0,
    att_late_count       INT DEFAULT 0,
    attendance_rate      DECIMAL(5, 4) NULL,
    absence_rate         DECIMAL(5, 4) NULL,
    hw_total_count       INT DEFAULT 0,
    hw_mean_completion   DECIMAL(6, 2) NULL,
    hw_missing_rate      DECIMAL(5, 4) NULL,
    hw_late_rate         DECIMAL(5, 4) NULL,
    parent_comm_count    INT DEFAULT 0,
    last_updated         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints & Foreign Keys
    CONSTRAINT chk_exam_score CHECK (exam_score >= 0),
    CONSTRAINT chk_below80_flag CHECK (below80_flag IN (0, 1)),
    CONSTRAINT uq_fact_student_subject UNIQUE (student_key, subject_key),
    CONSTRAINT fk_fact_student FOREIGN KEY (student_key) REFERENCES Dim_Student(student_key) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_fact_subject FOREIGN KEY (subject_key) REFERENCES Dim_Subject(subject_key) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_fact_date    FOREIGN KEY (date_key)    REFERENCES Dim_Date(date_key)       ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_fact_risk    FOREIGN KEY (risk_key)    REFERENCES Dim_Risk_Category(risk_key) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Analytical Indexes for Star Schema Joins & Slice-and-Dice
CREATE INDEX idx_fact_student ON Fact_Student_Subject_Performance(student_key);
CREATE INDEX idx_fact_subject ON Fact_Student_Subject_Performance(subject_key);
CREATE INDEX idx_fact_risk    ON Fact_Student_Subject_Performance(risk_key);
CREATE INDEX idx_fact_date    ON Fact_Student_Subject_Performance(date_key);
