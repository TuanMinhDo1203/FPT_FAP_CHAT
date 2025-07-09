from database_manager import DatabaseManager
from datetime import datetime

def main():
    # Khởi tạo và kết nối database
    with DatabaseManager() as db:
        # Tạo các bảng nếu chưa tồn tại
        db.create_tables()

        # Ví dụ thêm sinh viên
        student_data = {
            'student_id': 'SE170001',
            'full_name': 'Nguyen Van A',
            'email': 'ase170001@fpt.edu.vn',
            'class': 'SE1701'
        }
        db.add_student(**student_data)

        # Ví dụ thêm nhiều sinh viên cùng lúc
        students_list = [
            {
                'student_id': 'SE170002',
                'full_name': 'Tran Thi B',
                'email': 'bse170002@fpt.edu.vn',
                'class': 'SE1701'
            },
            {
                'student_id': 'SE170003',
                'full_name': 'Le Van C',
                'email': 'cse170003@fpt.edu.vn',
                'class': 'SE1701'
            }
        ]
        db.bulk_add_students(students_list)

        # Ví dụ thêm khóa học
        course_data = {
            'course_code': 'SEG301',
            'course_name': 'Software Engineering',
            'credits': 3,
            'department': 'Software Engineering',
            'description': 'Learn about software development process'
        }
        db.add_course(course_data)

        # Ví dụ tạo đơn xin phép
        db.submit_application(
            student_id='SE170001',
            app_type='Leave Request',
            process_note='Sick leave for 2 days',
            file='medical_certificate.pdf'
        )

        # Ví dụ thêm giao dịch học phí
        transaction_data = {
            'student_id': 'SE170001',
            'receipt_no': 'R001',
            'receipt_date': datetime.now().date(),
            'fee_type': 'Tuition Fee',
            'amount': 1500.00,
            'input_by': 'admin',
            'description': 'Fall 2023 Semester Fee'
        }
        db.add_transaction(transaction_data)

        # Ví dụ lấy thông tin sinh viên
        student = db.get_student('SE170001')
        if student:
            print("Student info:", student)

        # Ví dụ lấy danh sách đơn từ của sinh viên
        applications = db.get_student_applications('SE170001')
        print("Student applications:", applications)

        # Ví dụ lấy lịch sử giao dịch của sinh viên
        transactions = db.get_student_transactions('SE170001')
        print("Student transactions:", transactions)

if __name__ == "__main__":
    main() 