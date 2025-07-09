import pymysql
from typing import Dict, List, Optional
from datetime import datetime
from config import DB_CONFIG

class DatabaseManager:
    def __init__(self):
        """Initialize database connection"""
        self.connection = None
        self.connection_params = DB_CONFIG

    def create_tables(self):
        """Create all necessary database tables if they don't exist"""
        try:
            with self.connection.cursor() as cursor:
                # Create students table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id VARCHAR(10) PRIMARY KEY,
                    full_name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                )
                """)

                # Create courses table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS courses (
                    course_code VARCHAR(20) PRIMARY KEY,
                    course_name VARCHAR(100) NOT NULL,
                    credits INT NOT NULL,
                    department VARCHAR(50),
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Create applications table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id VARCHAR(10) NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    process_note TEXT,
                    file VARCHAR(255),
                    status VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
                """)

                # Create transactions table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id VARCHAR(10) NOT NULL,
                    receipt_no VARCHAR(50) NOT NULL,
                    receipt_date DATE NOT NULL,
                    fee_type VARCHAR(50) NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    input_by VARCHAR(50) NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
                """)

            self.connection.commit()
            print("All tables created successfully!")
        except Exception as e:
            print(f"Error creating tables: {e}")
            raise

    def connect(self):
        """Create database connection"""
        try:
            self.connection = pymysql.connect(
                **self.connection_params,
                charset="utf8mb4",
                connect_timeout=10,
                cursorclass=pymysql.cursors.DictCursor
            )
            print("Connected to database successfully!")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("Database connection closed.")

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()

    # Student related methods
    def get_student(self, student_id: str) -> Optional[Dict]:
        """Get student information by ID"""
        try:
            with self.connection.cursor() as cursor:
                sql = "SELECT * FROM students WHERE student_id = %s"
                cursor.execute(sql, (student_id,))
                return cursor.fetchone()
        except Exception as e:
            print(f"Error getting student: {e}")
            return None

    def add_student(self, student_id: str, full_name: str, email: str, class_name: str) -> bool:
        """Add a new student"""
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT INTO students (student_id, full_name, email, Class)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(sql, (student_id, full_name, email, class_name))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error adding student: {e}")
            return False

    def bulk_add_students(self, students_data: List[Dict]) -> bool:
        """Bulk insert students"""
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT IGNORE INTO students (student_id, full_name, email, Class)
                VALUES (%s, %s, %s, %s)
                """
                values = [(s['student_id'], s['full_name'], s['email'], s['class']) for s in students_data]
                cursor.executemany(sql, values)
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error in bulk adding students: {e}")
            return False

    # Course related methods
    def get_course(self, course_code: str) -> Optional[Dict]:
        """Get course information by code"""
        try:
            with self.connection.cursor() as cursor:
                sql = "SELECT * FROM courses WHERE course_code = %s"
                cursor.execute(sql, (course_code,))
                return cursor.fetchone()
        except Exception as e:
            print(f"Error getting course: {e}")
            return None

    def add_course(self, course_data: Dict) -> bool:
        """Add a new course"""
        try:
            with self.connection.cursor() as cursor:
                columns = ', '.join(course_data.keys())
                placeholders = ', '.join(['%s'] * len(course_data))
                sql = f"INSERT INTO courses ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, tuple(course_data.values()))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error adding course: {e}")
            return False

    # Application related methods
    def submit_application(self, student_id: str, app_type: str, process_note: str = None, file: str = None) -> bool:
        """Submit a new application"""
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT INTO applications (student_id, type, process_note, file, status)
                VALUES (%s, %s, %s, %s, 'Pending')
                """
                cursor.execute(sql, (student_id, app_type, process_note, file))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error submitting application: {e}")
            return False

    def get_student_applications(self, student_id: str) -> List[Dict]:
        """Get all applications for a student"""
        try:
            with self.connection.cursor() as cursor:
                sql = "SELECT * FROM applications WHERE student_id = %s ORDER BY created_at DESC"
                cursor.execute(sql, (student_id,))
                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting applications: {e}")
            return []

    # Transaction related methods
    def add_transaction(self, transaction_data: Dict) -> bool:
        """Add a new transaction"""
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT INTO transactions 
                (student_id, receipt_no, receipt_date, fee_type, amount, input_by, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    transaction_data['student_id'],
                    transaction_data['receipt_no'],
                    transaction_data['receipt_date'],
                    transaction_data['fee_type'],
                    transaction_data['amount'],
                    transaction_data['input_by'],
                    transaction_data['description']
                ))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error adding transaction: {e}")
            return False

    def get_student_transactions(self, student_id: str) -> List[Dict]:
        """Get all transactions for a student"""
        try:
            with self.connection.cursor() as cursor:
                sql = "SELECT * FROM transactions WHERE student_id = %s ORDER BY receipt_date DESC"
                cursor.execute(sql, (student_id,))
                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return []

    # Utility methods
    def execute_query(self, sql: str, params: tuple = None) -> Optional[List[Dict]]:
        """Execute a custom SQL query"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                if sql.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                self.connection.commit()
                return None
        except Exception as e:
            print(f"Error executing query: {e}")
            return None

    def get_table_columns(self, table_name: str) -> List[Dict]:
        """Get column information for a table"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SHOW COLUMNS FROM {table_name}")
                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting table columns: {e}")
            return [] 