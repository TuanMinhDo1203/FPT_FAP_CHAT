# Mẫu file: cloud_data_setup.py
# Mục đích: Triển khai pipeline 3NF chuẩn hoá dữ liệu FAP lên Aiven PostgreSQL

import pandas as pd
import pymysql
import os
import logging
from dotenv import load_dotenv
import shutil
from sqlalchemy import create_engine

# Thiết lập logging cơ bản
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

class CloudManager:
    def __init__(self, csv_paths: dict, db_config: dict):
        self.csv_paths = csv_paths
        try:
            self.conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **db_config)
            self.cursor = self.conn.cursor()
            # Tạo SQLAlchemy engine cho pandas
            user = db_config["user"]
            password = db_config["password"]
            host = db_config["host"]
            port = db_config["port"]
            db = db_config["db"]
            self.engine = create_engine(f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4")
            logging.info("Connected to Aiven PostgreSQL (and SQLAlchemy engine)")
        except Exception as e:
            logging.error(f"Failed to connect to DB: {e}")
            raise
        self.changed_records = {
            "students": [],
            "attendance": [],
            "grades": [],
            "courses": []
        }

    def drop_tables(self):
        queries = [
            "DROP TABLE IF EXISTS students",
            "DROP TABLE IF EXISTS courses",
            "DROP TABLE IF EXISTS grades",
            "DROP TABLE IF EXISTS attendance"
        ]
        try:
            for query in queries:
                self.cursor.execute(query)
            self.conn.commit()
        except Exception as e:
            logging.error(f"drop_tables: {e}")

    def create_tables(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS students (
            full_name VARCHAR(128),
            date_of_birth VARCHAR(32),
            gender VARCHAR(16),
            id_card_number VARCHAR(64),
            home_address VARCHAR(512),
            phone_number VARCHAR(32),
            email_address VARCHAR(128),
            id_date_of_issue VARCHAR(32),
            id_place_of_issue VARCHAR(128),
            parent_full_name VARCHAR(128),
            parent_phone_number VARCHAR(32),
            parent_address VARCHAR(512),
            parent_email VARCHAR(128),
            parent_job VARCHAR(128),
            parent_workplace VARCHAR(128),
            roll_number VARCHAR(32) PRIMARY KEY,
            old_roll_number VARCHAR(32),
            member_code VARCHAR(32),
            enrollment_date VARCHAR(32),
            study_mode VARCHAR(64),
            current_status VARCHAR(128),
            current_term_number VARCHAR(16),
            major VARCHAR(128),
            curriculum VARCHAR(128),
            capstone_project VARCHAR(128),
            main_class VARCHAR(64),
            specialization VARCHAR(128),
            account_balance VARCHAR(128),
            previous_major VARCHAR(128),
            decision_graduate_check VARCHAR(128),
            is_full_time_student VARCHAR(20),
            full_time_confirmed_date VARCHAR(32),
            is_scholarship_student VARCHAR(8),
            valid_study_period VARCHAR(64),
            training_type VARCHAR(64),
            decision_dropout VARCHAR(128),
            decision_transfer_campus VARCHAR(128),
            decision_academic_leave VARCHAR(128),
            decision_graduation VARCHAR(128),
            decision_rejoin VARCHAR(128),
            destination_after_study VARCHAR(128),
            start_term VARCHAR(32)
        )
            """,
                """
            CREATE TABLE IF NOT EXISTS attendance (
            student_id VARCHAR(32),
            term VARCHAR(32),
            course_name VARCHAR(128),
            course_code VARCHAR(32),
            no INT,
            date VARCHAR(32),
            slot VARCHAR(32),
            room VARCHAR(64),
            lecturer VARCHAR(64),
            `group` VARCHAR(64),  
            status VARCHAR(32),
            comment TEXT,
            PRIMARY KEY (student_id, course_code, date, slot)
        )
            """,
            """
            CREATE TABLE IF NOT EXISTS courses (
            term VARCHAR(32),
            course_name VARCHAR(128),
            course_code VARCHAR(32),
            avg_score FLOAT,
            status VARCHAR(32),
            summary TEXT,
            PRIMARY KEY (course_code, term)
        )

            """,
            """
            CREATE TABLE IF NOT EXISTS grades (
            student_id VARCHAR(32),
            term VARCHAR(32),
            course_name VARCHAR(128),
            course_code VARCHAR(32),
            category VARCHAR(64),
            item VARCHAR(64),
            weight VARCHAR(16),
            value VARCHAR(16),
            PRIMARY KEY (student_id, course_code, item)
        )
            """
        ]
        try:
            for query in queries:
                self.cursor.execute(query)
            self.conn.commit()
        except Exception as e:
            logging.error(f"create_tables: {e}")

    def load_dataframes(self):
        try:
            self.df_students = pd.read_csv(self.csv_paths["student_profile"])
            self.df_attendance = pd.read_csv(self.csv_paths["attendance_reports"])
            self.df_grades = pd.read_csv(self.csv_paths["grade_details"])
            self.df_courses = pd.read_csv(self.csv_paths["course_summaries"])
        except Exception as e:
            logging.error(f"load_dataframes: {e}")
            raise

    def sync_table(self, table_name: str, df: pd.DataFrame, keys: list):
        # === Lưu checkpoint trước khi lọc header ===
        checkpoint_dir = os.path.join(os.path.dirname(self.csv_paths[list(self.csv_paths.keys())[0]]), "checkpoints")
        os.makedirs(checkpoint_dir, exist_ok=True)
        df.to_csv(os.path.join(checkpoint_dir, f"checkpoint_{table_name}_before_upload.csv"), index=False, encoding="utf-8-sig")
        # Loại bỏ các dòng là header lặp lại (an toàn)
        if len(keys) > 0:
            mask = ~((df[keys] == pd.Series(keys, index=keys)).all(axis=1))
            df = df[mask]
        columns = list(df.columns)
        rows = df.to_dict(orient="records")
        updates = 0
        inserts = 0
        try:
            for record in rows:
                clean_record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
                where_clause = " AND ".join([f"`{k}` = %s" for k in keys])
                select_query = f"SELECT * FROM `{table_name}` WHERE {where_clause}"
                self.cursor.execute(select_query, [clean_record[k] for k in keys])
                existing = self.cursor.fetchone()

                escaped_columns = [f"`{col}`" for col in columns]
                if existing:
                    update_query = f"UPDATE `{table_name}` SET {', '.join([f'{col} = %s' for col in escaped_columns])} WHERE {where_clause}"
                    self.cursor.execute(
                        update_query,
                        [clean_record[c] for c in columns] + [clean_record[k] for k in keys]
                    )
                    updates += 1
                    self.changed_records[table_name].append(clean_record)
                else:
                    placeholders = ", ".join(["%s"] * len(columns))
                    insert_query = f"INSERT INTO `{table_name}` ({', '.join(escaped_columns)}) VALUES ({placeholders})"
                    self.cursor.execute(insert_query, [clean_record[c] for c in columns])
                    inserts += 1
                    self.changed_records[table_name].append(clean_record)
            logging.info(f"⬆️ Synced {table_name} - New: {inserts}, Updated: {updates}")
            self.conn.commit()
        except Exception as e:
            logging.error(f"sync_table ({table_name}): {e}")

    def sync_all(self):
        try:
            self.sync_table("students", self.df_students, ["roll_number"])
            self.sync_table("attendance", self.df_attendance, ["student_id", "course_code", "date"])
            self.sync_table("grades", self.df_grades, ["student_id", "course_code", "item"])
            self.sync_table("courses", self.df_courses, ["course_code", "term"])
        except Exception as e:
            logging.error(f"sync_all: {e}")

    def get_changed_records(self, table_name: str):
        try:
            return self.changed_records.get(table_name, [])
        except Exception as e:
            logging.error(f"get_changed_records: {e}")
            return []

    def get_student_df(self, user_id):
        try:
            sql = "SELECT * FROM students WHERE roll_number = %s"
            self.cursor.execute(sql, (user_id,))
            rows = self.cursor.fetchall()
            return pd.DataFrame(list(rows))
        except Exception as e:
            logging.error(f"get_student_df: {e}")
            return pd.DataFrame()

    def get_attendance_df(self, user_id):
        try:
            sql = "SELECT * FROM attendance WHERE student_id = %s"
            self.cursor.execute(sql, (user_id,))
            rows = self.cursor.fetchall()
            return pd.DataFrame(list(rows))
        except Exception as e:
            logging.error(f"get_attendance_df: {e}")
            return pd.DataFrame()

    def get_grades_df(self, user_id):
        try:
            sql = "SELECT * FROM grades WHERE student_id = %s"
            self.cursor.execute(sql, (user_id,))
            rows = self.cursor.fetchall()
            return pd.DataFrame(list(rows))
        except Exception as e:
            logging.error(f"get_grades_df: {e}")
            return pd.DataFrame()

    def get_courses_df(self, user_id):
        try:
            sql = "SELECT DISTINCT c.* FROM courses c JOIN grades g ON c.course_code = g.course_code AND c.term = g.term WHERE g.student_id = %s UNION SELECT DISTINCT c.* FROM courses c JOIN attendance a ON c.course_code = a.course_code AND c.term = a.term WHERE a.student_id = %s"
            self.cursor.execute(sql, (user_id, user_id))
            rows = self.cursor.fetchall()
            return pd.DataFrame(list(rows))
        except Exception as e:
            logging.error(f"get_courses_df: {e}")
            return pd.DataFrame()

    def get_all_courses_df(self):
        try:
            sql = "SELECT * FROM courses"
            self.cursor.execute(sql)
            rows = self.cursor.fetchall()
            return pd.DataFrame(list(rows))
        except Exception as e:
            logging.error(f"get_all_courses_df: {e}")
            return pd.DataFrame()

    def download_dataframes(self):
        """
        Download all tables from cloud and save to local CSVs (overwriting current CSVs in self.csv_paths).
        """
        try:
            checkpoint_dir = os.path.join(os.path.dirname(self.csv_paths[list(self.csv_paths.keys())[0]]), "checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)
            table_map = {
                "students": "student_profile",
                "attendance": "attendance_reports",
                "grades": "grade_details",
                "courses": "course_summaries"
            }
            for table, csv_key in table_map.items():
                df = pd.read_sql(f'SELECT * FROM {table}', self.engine)
                csv_path = self.csv_paths[csv_key]
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                # Lưu checkpoint
                df.to_csv(os.path.join(checkpoint_dir, f"checkpoint_{table}_after_download.csv"), index=False, encoding="utf-8-sig")
                # Đọc lại file vừa ghi để xác nhận
                df_check = pd.read_csv(csv_path)
                if df.shape != df_check.shape:
                    raise RuntimeError(f"❌ Lỗi: Số dòng/cột khi ghi file {csv_path} không khớp với dữ liệu cloud!")
            logging.info("\n✅ Đã tải và xác nhận toàn bộ bảng từ cloud về local CSVs!")
        except Exception as e:
            logging.error(f"download_dataframes: {e}")
            raise

    def clean_csv_nan_to_placeholder(self, csv_path, placeholder="unknown"):
        """
        Clean CSV file by replacing NaN, None, empty values with placeholder
        and remove empty lines to prevent cloud upload errors.
        """
        try:
            df = pd.read_csv(csv_path)
            
            # Replace various forms of null/empty values
            df = df.replace([None, 'None', 'null', 'NULL', ''], placeholder)
            df = df.fillna(placeholder)
            
            # Remove completely empty rows
            df = df.dropna(how='all')
            
            # Clean up any remaining problematic values
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).replace(['nan', 'NaN', 'NAN'], placeholder)
            
            # Save with proper encoding
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            logging.info(f"🧹 Cleaned {csv_path}")
        except Exception as e:
            logging.error(f"clean_csv_nan_to_placeholder ({csv_path}): {e}")

    def clean_all_csvs(self):
        """
        Clean all CSV files before cloud operations.
        """
        for csv_path in self.csv_paths.values():
            self.clean_csv_nan_to_placeholder(csv_path)

if __name__ == "__main__":
    load_dotenv()
    # Đọc config từ biến môi trường hoặc .env
    csv_paths = {
        "student_profile": os.environ.get("CSV_STUDENT_PROFILE", "./data/student_profile.csv"),
        "attendance_reports": os.environ.get("CSV_ATTENDANCE_REPORTS", "./data/attendance_reports.csv"),
        "grade_details": os.environ.get("CSV_GRADE_DETAILS", "./data/grade_details.csv"),
        "course_summaries": os.environ.get("CSV_COURSE_SUMMARIES", "./data/course_summaries.csv")
    }
    db_config = {
        "host": os.environ.get("MYSQL_HOST", "localhost"),
        "port": int(os.environ.get("MYSQL_PORT", 19116)),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "db": os.environ.get("MYSQL_DB", "test"),
        "charset": "utf8mb4"
    }
    print("[INFO] Đang sử dụng cấu hình:")
    print("CSV paths:", csv_paths)
    print("DB config:", {k: v if k != 'password' else '***' for k, v in db_config.items()})

    manager = CloudManager(csv_paths, db_config)
    # XÓA SẠCH TOÀN BỘ DỮ LIỆU TRÊN CLOUD
    try:
        for table in ["students", "attendance", "grades", "courses"]:
            # manager.cursor.execute(f"DELETE FROM {table}")
            # manager.conn.commit()
            logging.info(f"Đã xóa sạch bảng {table}")
            # In ra số lượng dòng trong bảng
            logging.info(f"Số lượng dòng trong bảng {table}: {manager.cursor.rowcount}")
    except Exception as e:
        logging.error(f"Lỗi khi xóa dữ liệu cloud: {e}")

    # TEST: Tải từng bảng về DataFrame và in ra trạng thái thực tế
    for table in ["students", "attendance", "grades", "courses"]:
        try:
            df = pd.read_sql(f'SELECT * FROM {table}', manager.conn)
            logging.info(f"\n===== {table.upper()} =====")
            logging.info(f"Shape: {df.shape}")
            logging.info(df.head())
        except Exception as e:
            logging.error(f"Lỗi khi đọc bảng {table}: {e}")

    # manager.create_tables()
    # manager.load_dataframes()
    # manager.sync_all()

    # changed_attendance = manager.get_changed_records("attendance")
    # logging.info(f"🔁 Attendance changed: {len(changed_attendance)}")
