import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import pickle
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re
from . import embedder
from qdrant_client.models import VectorParams, Distance

"""
Cấu hình logging
"""
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FapScraper:
    """
    Class để cào dữ liệu từ FAP (FPT Academic Portal)
    """
    
    # Các URL cố định
    BASE_URL = "https://fap.fpt.edu.vn"
    PROFILE_URL = f"{BASE_URL}/User/Profile.aspx"
    ATTENDANCE_URL = f"{BASE_URL}/Report/ViewAttendstudent.aspx"
    GRADE_URL = f"{BASE_URL}/Grade/StudentGrade.aspx"
    
    def __init__(self, gmail=None, password=None, timeout=200):
        """
        Khởi tạo FapScraper với thông tin đăng nhập và thời gian chờ
        
        Args:
            gmail: Email FPT để đăng nhập
            password: Mật khẩu
            timeout: Thời gian chờ tối đa cho mỗi thao tác (giây)
        """
        self.gmail = gmail
        self.password = password
        self.timeout = timeout
        self.driver = None
        self.wait = None
        self.student_data = {}  # Lưu trữ thông tin profile sinh viên
    
    def get_term_from_date(self, dt):
        """
        Xác định học kỳ từ ngày tháng
        
        Args:
            dt: Đối tượng datetime
            
        Returns:
            str: Tên học kỳ (VD: Spring2023)
        """
        year = dt.year
        month = dt.month

        if month in [1, 2, 3]:  # Tháng 1-3
            return f"Spring{year}"
        elif month in [4, 5, 6]:  # Tháng 4-6
            return f"Summer{year}"
        elif month in [7, 8, 9]:  # Tháng 7-9
            return f"Fall{year}"
        elif month in [10, 11, 12]:  # Tháng 10-12
            return f"Winter{year}"
        
    def setup_driver(self):
        """
        Khởi tạo trình duyệt Chrome với undetected-chromedriver
        """
        options = Options()
        service = Service(ChromeDriverManager().install())
        self.driver = uc.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, self.timeout)
        return self.driver

    def interact_safely(self, by, value, action='click', text=None, clear=True, press_enter=False, timeout=None, description=''):
        """
        Tương tác an toàn với các phần tử web (click hoặc nhập text)
        
        Args:
            by: Phương thức tìm kiếm (By.ID, By.XPATH,...)
            value: Giá trị để tìm phần tử
            action: Hành động ('click' hoặc 'input')
            text: Text cần nhập (chỉ dùng cho action='input')
            clear: Xóa text cũ trước khi nhập (mặc định: True)
            press_enter: Nhấn Enter sau khi nhập (mặc định: False)
            timeout: Thời gian chờ tùy chỉnh
            description: Mô tả hành động để log
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            wait_time = timeout if timeout else self.timeout
            wait = WebDriverWait(self.driver, wait_time)

            # Chọn điều kiện chờ tùy theo hành động
            if action == 'click':
                element = wait.until(EC.element_to_be_clickable((by, value)))
            elif action == 'input':
                element = wait.until(EC.visibility_of_element_located((by, value)))
            else:
                logger.error(f"❌ Hành động không được hỗ trợ: {action}")
                return False

            # Scroll vào vùng nhìn thấy
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

            if action == 'click':
                element.click()
            elif action == 'input':
                element.click()  # focus vào input
                if clear:
                    element.clear()
                element.send_keys(text)
                if press_enter:
                    element.send_keys(Keys.RETURN)

            return True

        except Exception as e:
            logger.error(f"❌ Lỗi khi {action} {description or value}: {str(e)}")
            return False

    def bypass_cloudflare_check(self, timeout=60):
        """
        Chờ cho Cloudflare check hoàn tất
        
        Args:
            timeout: Thời gian chờ tối đa (giây)
            
        Returns:
            bool: True nếu bypass thành công, False nếu thất bại
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            page_source = self.driver.page_source
            if "Just a moment..." not in page_source and "Checking your browser" not in page_source:
                logger.info("✅ Đã bypass Cloudflare thành công")
                return True
            time.sleep(1)
        logger.error("❌ Không thể bypass Cloudflare")
        return False

    def login(self):
        """
        Xử lý toàn bộ quá trình đăng nhập
        
        Returns:
            bool: True nếu đăng nhập thành công, False nếu thất bại
        """
        # Click nút đăng nhập FeID
        if not self.interact_safely(By.ID, "ctl00_mainContent_btnloginFeId", description="Nút đăng nhập FeID"):
            return False

        # Click nút đăng nhập Gmail
        if not self.interact_safely(
            By.XPATH, 
            "//a[contains(@class, 'btn-outline-primary') and contains(., 'Email fpt.edu.vn')]",
            description="Nút Gmail"
        ):
            return False

        # Nhập Gmail
        if not self.interact_safely(
            By.ID, "identifierId", 
            action='input', 
            text=self.gmail,
            press_enter=True,
            description="Nhập Gmail"
        ):
            return False

        # Nhập mật khẩu
        if not self.interact_safely(
            By.NAME, "Passwd",
            action='input',
            text=self.password,
            press_enter=True,
            description="Nhập mật khẩu"
        ):
            return False

        logger.info("✅ Đăng nhập thành công")
        return True

    def scrape_profile(self):
        """
        Cào thông tin profile sinh viên
        
        Returns:
            bool: True nếu cào thành công, False nếu thất bại
        """
        try:
            # Click vào nút Profile
            self.interact_safely(By.XPATH, '//a[@href="User/Profile.aspx"]', description="Nút Profile")
            
            # === THÔNG TIN CÁ NHÂN ===
            full_name = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblFullname"]').text
            dob = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblDateOfBirth"]').text
            gender = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblGender"]').text
            id_card = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblIDCard"]').text
            address = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblAddress"]').text
            phone = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblPhoneNumber"]').text
            email = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblEmail"]').text
            doi = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblDateOfIssue"]').text
            poi = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblPaleOfIssue"]').text

            # === PARENT ===
            parent_name = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblParentName"]').text
            parent_phone = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblParentPhone"]').text
            parent_address = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblParentAddress"]').text
            parent_email = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblParentEmail"]').text
            parent_job = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblParentJob"]').text
            parent_work = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblPlaceOfWork"]').text

            # === ACADEMIC ===
            roll_number = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblRollNumber"]').text
            old_roll = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblOldRoll"]').text
            member_code = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblMemberCode"]').text
            enrol_date = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblEnrolDate"]').text
            mode = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblMode"]').text
            status = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblStatus"]').text
            term = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblTermNo"]').text
            major = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblMajor"]').text
            curriculum = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblSpecialIn"]').text
            capstone = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblCapstoneProject"]').text

            # === FINANCE ===
            account_balance = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblAccBlance"]').text

            # === OTHER ===
            old_major = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblOldMajor"]').text
            qdcng = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblQDCN"]').text
            svcq = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblSVCQ"]').text
            svcq_date = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblDateSVCQ"]').text
            svdb = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblSVDB"]').text
            hanhoc = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblHan7nam"]').text
            main_class = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblMainClass"]').text
            loai_tc = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblLoaiTC"]').text
            qd_thoihoc = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblQDTH"]').text
            qd_chuyencoso = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblQDTranfer"]').text
            qd_bl = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblBaoluu"]').text
            qd_tn = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblQDTN"]').text
            qd_rejoin = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblRejoin"]').text
            tt_den = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblTTDen"]').text
            specialization = self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblChuyennganh"]').text

            # Tính học kỳ bắt đầu (lùi 4 tháng từ ngày xác nhận SVCQ do thời gian quân sự)
            dt_svcq = datetime.strptime(svcq_date, "%m/%d/%Y %I:%M:%S %p") - relativedelta(months=4)
            start_term = self.get_term_from_date(dt_svcq)

            # Lưu thông tin profile vào student_data
            self.student_data = {
                # === THÔNG TIN CÁ NHÂN ===
                "full_name": full_name,
                "date_of_birth": dob,
                "gender": gender,
                "id_card_number": id_card,
                "home_address": address,
                "phone_number": phone,
                "email_address": email,
                "id_date_of_issue": doi,
                "id_place_of_issue": poi,

                # === PARENT INFO ===
                "parent_full_name": parent_name,
                "parent_phone_number": parent_phone,
                "parent_address": parent_address,
                "parent_email": parent_email,
                "parent_job": parent_job,
                "parent_workplace": parent_work,

                # === ACADEMIC INFO ===
                "roll_number": roll_number,
                "old_roll_number": old_roll,
                "member_code": member_code,
                "enrollment_date": enrol_date,
                "study_mode": mode,
                "current_status": status,
                "current_term_number": term,
                "major": major,
                "curriculum": curriculum,
                "capstone_project": capstone,
                "main_class": main_class,
                "specialization": specialization,

                # === FINANCIAL INFO ===
                "account_balance": account_balance,

                # === OTHER INFO ===
                "previous_major": old_major,
                "decision_graduate_check": qdcng,
                "is_full_time_student": svcq,
                "full_time_confirmed_date": svcq_date,
                "is_scholarship_student": svdb,
                "valid_study_period": hanhoc,
                "training_type": loai_tc,
                "decision_dropout": qd_thoihoc,
                "decision_transfer_campus": qd_chuyencoso,
                "decision_academic_leave": qd_bl,
                "decision_graduation": qd_tn,
                "decision_rejoin": qd_rejoin,
                "destination_after_study": tt_den,

                # === SYSTEM DERIVED ===
                "start_term": start_term
            }
            
            logger.info(f"✅ Đã cào profile thành công cho sinh viên {roll_number}")
            return True
        except Exception as e:
            logger.error(f"❌ Lỗi khi cào profile: {str(e)}")
            return False

    def parse_attendance_info_from_html_table(self, html_table, term_name, available_course_name, available_course_code):
        attendance_records = []  # Lưu trữ tất cả bản ghi điểm danh
        soup = BeautifulSoup(html_table, 'html.parser')
        tbody = soup.find_all('tbody')[1]
        rows = tbody.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            attendance_record = {
                'student_id': self.student_data['roll_number'],
                'term': term_name,
                'course_name': available_course_name,
                'course_code': available_course_code,
                'no': cols[0].text.strip(),
                'date': cols[1].text.strip(),
                'slot': cols[2].text.strip(),
                'room': cols[3].text.strip(),
                'lecturer': cols[4].text.strip(),
                'group': cols[5].text.strip(),
                'status': cols[6].text.strip(),
                'comment': cols[7].text.strip()
            }
            attendance_records.append(attendance_record)
        return attendance_records
    
    def parse_grade_info_from_html_table(self, html_table, term_name, course_name, course_code):
        mark_details = []  # Initialize mark_details as an empty list
        course_summaries = []  # Initialize course_summaries as an empty list
        
        soup = BeautifulSoup(html_table.get_attribute('outerHTML'), 'html.parser')

        tbody = soup.find('tbody')
        rows = tbody.find_all('tr')

        tfoot = soup.find('tfoot')
        trs_tfoot = tfoot.find_all('tr')
        avg_score = trs_tfoot[0].find_all('td')[2].text.strip()
        status = tfoot.find('font').text.strip()

        current_category = None
        summary_weights = {}

        for row in rows:
            cols = row.find_all('td')

            # Dòng có rowspan là bắt đầu 1 category mới
            if cols[0].has_attr('rowspan'):
                current_category = cols[0].text.strip()
                grade_item = cols[1].text.strip()
                weight = cols[2].text.strip()
                value = cols[3].text.strip()

                # Lưu chi tiết điểm
                mark_details.append({
                    "student_id": self.student_data['roll_number'],
                    "term": term_name,
                    "course_name": course_name,
                    "course_code": course_code,
                    "category": current_category,
                    "item": grade_item,
                    "weight": weight,
                    "value": value
                })

            elif "total" in cols[0].text.lower():
                # Tổng điểm của category (lưu vào summary)
                total_weight = cols[1].text.strip()
                total_value = cols[2].text.strip()
                summary_weights[current_category] = {
                    "weight": total_weight if total_weight else None,
                    "value": total_value if total_value else None
                }
            else:
                # Dòng con
                grade_item = cols[0].text.strip()
                weight = cols[1].text.strip()
                value = cols[2].text.strip()

                mark_details.append({
                    "student_id": self.student_data['roll_number'],
                    "term": term_name,
                    "course_name": course_name,
                    "course_code": course_code,
                    "category": current_category,
                    "item": grade_item,
                    "weight": weight,
                    "value": value
                })

        # Lưu tổng kết course này
        course_summaries.append({
            "term": term_name,
            "course_name": course_name,
            "course_code": course_code,
            "avg_score": avg_score,
            "status": status,
            "summary": summary_weights
        })

# In ra course_summaries và mark_details
# print(course_summaries)
# print(mark_details)
        logger.info("✅ Đã cào xong điểm tổng kết và chi tiết")
        return course_summaries, mark_details
    
    def scrape_attendance(self):
        """
        Cào dữ liệu điểm danh của tất cả các kỳ
        
        Returns:
            list: Danh sách các bản ghi điểm danh, None nếu có lỗi
        """
        attendance_data = []
        try:
            # Click vào nút Điểm danh
            self.interact_safely(By.XPATH, '//a[@href="Report/ViewAttendstudent.aspx"]', description="Nút điểm danh")

            self.interact_safely(By.XPATH, "//a[normalize-space(text())='Fall2014']", description="Fall2014 button")
        

            # Get all terms
            terms_div = self.driver.find_element(By.ID, "ctl00_mainContent_divTerm")
            term_tags = terms_div.find_elements(By.CSS_SELECTOR, "tbody tr td a")
            term_list = [term.text.strip() for term in term_tags]
            start_term_index = term_list.index(self.student_data['start_term'])
            
            for i in range(start_term_index, len(term_tags)):
                terms_div = self.driver.find_element(By.ID, "ctl00_mainContent_divTerm")
                term_links = terms_div.find_elements(By.CSS_SELECTOR, "a")
                term = self.wait.until(EC.element_to_be_clickable(term_links[i]))
                term_name = term.text.strip()
                term.click()
                # time.sleep(1)
                
                # Get courses in current term
                courses = self.driver.find_elements(By.CSS_SELECTOR, "#ctl00_mainContent_divCourse a")
                available_course = self.driver.find_elements(By.CSS_SELECTOR, "#ctl00_mainContent_divCourse b")
                if available_course: 
                    print(available_course)
                    available_course_name_and_code = available_course[0].text.strip()
                    available_course_name = available_course_name_and_code.split('(')[0]
                    available_course_code = re.search(r"\((.*?)\)", available_course_name_and_code).group(1)
                    available_course_table = self.driver.find_element(By.XPATH, f"//table[contains(@class, 'table table-bordered table1')]")
                    html_table = available_course_table.get_attribute('outerHTML')
                    attendance_records = self.parse_attendance_info_from_html_table(html_table, term_name, available_course_name, available_course_code)
                    
                    attendance_data.extend(attendance_records)
                if courses:
                    # print(len(courses))
                    for j in range(len(courses)):
                        course_div = self.driver.find_element(By.ID, "ctl00_mainContent_divCourse")
                        courses = course_div.find_elements(By.CSS_SELECTOR, "a")

                        course = courses[j]
                        course_name_and_code = course.text.strip()
                        course_name = course_name_and_code.split('(')[0]
                        course_code = re.search(r"\((.*?)\)", course_name_and_code).group(1)
                        course.click()
                        
                        # Get attendance table
                        table = self.driver.find_element(By.XPATH, f"//table[contains(@class, 'table table-bordered table1')]")
                        attendance_html = table.get_attribute('outerHTML')
                        
                        attendance_records = self.parse_attendance_info_from_html_table(attendance_html, term_name, course_name, course_code)
                        # print(attendance_record)
                        attendance_data.extend(attendance_records)
            
            logger.info(f"✅ Đã cào {len(attendance_data)} bản ghi điểm danh")
            return attendance_data
        except Exception as e:
            logger.error(f"❌ Lỗi khi cào điểm danh: {str(e)}")
            return None

    def scrape_grades(self):
        """
        Cào dữ liệu điểm của tất cả các kỳ
        Tách riêng thành bảng tổng kết môn và bảng chi tiết điểm
        
        Returns:
            tuple: (course_summaries, mark_details) hoặc None nếu có lỗi
        """
        course_summaries = []  # Lưu tổng kết từng môn
        mark_details = []      # Lưu chi tiết điểm thành phần
        try:
            # Click vào nút Xem điểm
            self.interact_safely(By.XPATH, '//a[@href="Grade/StudentGrade.aspx"]', description="Nút xem điểm")

            terms_div = self.driver.find_element(By.ID, "ctl00_mainContent_divTerm")
            term_tags = terms_div.find_elements(By.CSS_SELECTOR, "tbody tr td a, tbody tr td b")

            for i in range(len(term_tags)):
                # Xác định lại div chứa các học kỳ để tránh stale element
                terms_div = self.driver.find_element(By.ID, "ctl00_mainContent_divTerm")
                term_links = terms_div.find_elements(By.CSS_SELECTOR, "a, b")
                term = self.wait.until(EC.element_to_be_clickable(term_links[i]))
                term_name = term.text.strip()
                term.click()

                course_div = self.driver.find_element(By.ID, "ctl00_mainContent_divCourse")
                course_tags = course_div.find_elements(By.CSS_SELECTOR, "a")
                
                if course_tags:
                    for j in range(len(course_tags)):
                        course_div = self.driver.find_element(By.ID, "ctl00_mainContent_divCourse")
                        course_tags = course_div.find_elements(By.CSS_SELECTOR, "a, b")
                        course = course_tags[j]
                        course_name_and_code = course.text.strip()
                        course_name = course_name_and_code.split('(')[0]
                        course_code = re.search(r"\((.*?)\)", course_name_and_code).group(1)
                        course.click()
                        # Tìm kiếm bảng điểm
                        grade_div = self.driver.find_element(By.ID, "ctl00_mainContent_divGrade")
                        tables = grade_div.find_elements(By.TAG_NAME, "table")
                        print(f"🔍 Có {len(tables)} bảng table trong grade_div")
                        for table in tables:
                            print(table.get_attribute('outerHTML'))
                            print("--------------------------------")
                        # Nếu grave_div có bảng class="table table-bordered"
                        if grade_div.find_elements(By.CSS_SELECTOR, "table.table.table-bordered"):
                            print("đang xử lí môn coursera")
                            coursera_course_summarie = []
                            summary_weights = {}
                            coursera_table = grade_div.find_element(By.CSS_SELECTOR, "table.table.table-bordered")
                            sum_table = grade_div.find_element(By.XPATH, ".//table[@summary='Report']")
                            sum_table_soup = BeautifulSoup(sum_table.get_attribute('outerHTML'), 'html.parser')
                            coursera_table_soup = BeautifulSoup(coursera_table.get_attribute('outerHTML'), 'html.parser')


                            tfoot = sum_table_soup.find('tfoot')
                            if not tfoot:
                                logger.error("❌ Không tìm thấy <tfoot> trong bảng sum_table")
                                print(sum_table_soup.prettify())  # In toàn bộ HTML để kiểm tra
                                return None, None

                            trs_tfoot = tfoot.find_all('tr')
                            if not trs_tfoot:
                                logger.error("❌ <tfoot> không có dòng <tr> nào")
                                print(tfoot.prettify())
                                return None, None

                            tds = trs_tfoot[0].find_all('td')
                            print(f"Số lượng cột td trong hàng đầu tiên của tfoot: {len(tds)}")
                            for i, td in enumerate(tds):
                                print(f"TD[{i}]: {td.text.strip()}")

                            if len(tds) < 3:
                                logger.error("❌ Số lượng <td> trong hàng đầu tiên của <tfoot> < 3")
                                return None, None

                            avg_score = tds[2].text.strip()

                            # Lấy trạng thái pass/fail
                            font_tag = tfoot.find('font')
                            if font_tag:
                                status = font_tag.text.strip()
                            else:
                                logger.error("❌ Không tìm thấy <font> chứa status trong <tfoot>")
                                status = "Unknown"

                            # Lấy trọng số và điểm trung bình từ bảng coursera_table
                            tbody = coursera_table_soup.find('tbody')
                            rows = tbody.find_all('tr')
                            cols = rows[1].find_all('td')
                            if len(cols) == 2:
                                theory_exam_val = cols[0].text.strip() if cols[0].text.strip() else None
                                practise_exam_val = None
                                bonus = cols[1].text.strip() if cols[1].text.strip() else None
                            else:
                                theory_exam_val = cols[0].text.strip() if cols[0].text.strip() else None
                                practise_exam_val = cols[1].text.strip() if cols[1].text.strip() else None
                                bonus = cols[2].text.strip() if cols[2].text.strip() else None
                            summary_value = {
                                "theory_exam": theory_exam_val,
                                "practise_exam": practise_exam_val,
                                "bonus": bonus
                            }

                            coursera_course_summarie.append({
                            "term": term_name,
                            "course_name": course_name,
                            "course_code": course_code,
                            "avg_score": avg_score,
                            "status": status,
                            "summary": summary_value
                            })
                            course_summaries.extend(coursera_course_summarie)
                        else:

                            # Lấy bảng điểm

                            table = self.driver.find_element(By.XPATH, "//table[@summary='Report']")
                            
                            
                            summaries, details = self.parse_grade_info_from_html_table(
                                table, term_name, course_name, course_code
                            )
                            course_summaries.extend(summaries)
                            mark_details.extend(details)

            logger.info("✅ Đã cào xong điểm tổng kết và chi tiết")
            return course_summaries, mark_details
        except Exception as e:
            logger.error(f"❌ Lỗi khi cào điểm: {str(e)}")
            return None, None

    def save_to_csv(self, data, filename):
        """
        Lưu dữ liệu vào file CSV
        
        Args:
            data: Dữ liệu cần lưu (list of dict)
            filename: Đường dẫn file CSV
            
        Returns:
            bool: True nếu lưu thành công, False nếu thất bại
        """
        try:
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"✅ Đã lưu dữ liệu vào {filename}")
            return True
        except Exception as e:
            logger.error(f"❌ Lỗi khi lưu file CSV: {str(e)}")
            return False

    def full_scraping_process(self):
        """
        Thực hiện toàn bộ quy trình cào dữ liệu
        
        Returns:
            dict: Dữ liệu đã cào (profile, điểm danh, điểm) hoặc None nếu có lỗi
        """
        try:
            # Khởi tạo trình duyệt
            self.setup_driver()
            
            # Mở FAP
            self.driver.get(self.BASE_URL)
            time.sleep(13)  # Chờ load trang
            
            # Bypass Cloudflare
            if not self.bypass_cloudflare_check():
                return None
            
            # Đăng nhập
            if not self.login():
                return None
            
            # Về trang chủ
            self.interact_safely(By.XPATH, "//a[contains(@href,'Student.aspx')]", description="Nút Home")
            
            # Cào profile trước
            if not self.scrape_profile():
                return None
            
            # Về trang chủ
            self.interact_safely(By.XPATH, "//a[contains(@href,'Student.aspx')]", description="Nút Home")

            # Cào điểm danh
            attendance_data = self.scrape_attendance()

            # Về trang chủ
            self.interact_safely(By.XPATH, "//a[contains(@href,'Student.aspx')]", description="Nút Home")

            # Cào điểm
            course_summaries, grade_details = self.scrape_grades()
            
            # Đóng trình duyệt
            self.driver.quit()
            
            # Trả về kết quả
            return {
                'profile': self.student_data,
                'attendance': attendance_data,
                'course_summaries': course_summaries,
                'grade_details': grade_details
            }
            
        except Exception as e:
            logger.error(f"❌ Lỗi trong quá trình cào dữ liệu: {str(e)}")
            if self.driver:
                self.driver.quit()
            return None

def main():
    # Use relative paths instead of hardcoded paths
    import os
    from pathlib import Path

    data_dir = Path(__file__).resolve().parents[2] / "data" / "FAP"
    csv_paths = {
        'student_profile': str(data_dir / 'student_profile.csv'),
        'attendance_reports': str(data_dir / 'attendance_reports.csv'),
        'grade_details': str(data_dir / 'grade_details.csv'),
        'course_summaries': str(data_dir / 'course_summaries.csv')
    }
    # Use environment variables for Qdrant config
    engine=embedder.FapSearchEngine(csv_paths=csv_paths)
    # Use environment variable for collection name
    collection_name = os.environ.get("QDRANT_COLLECTION", "Fap_data_testing")
    engine.client.delete_collection(collection_name)
    engine.client.recreate_collection(
    collection_name=collection_name,
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
    )

    engine.load_all_dataframes()
    all_payloads = []
    for df_name, df in engine.dataframes.items():
        if df_name == 'student_profile':
            all_payloads.extend(engine.chunk_student_profile(df))
        elif df_name == 'attendance_reports':
            all_payloads.extend(engine.chunk_attendance_reports(df))
        elif df_name == 'grade_details':
            all_payloads.extend(engine.chunk_grade_details(df))
        elif df_name == 'course_summaries':
            all_payloads.extend(engine.chunk_course_summaries(df))
    
    # # Tạo embeddings và upload
    embeddings = engine.generate_content_embedding(all_payloads)
    points = engine.merge_point_structs(all_payloads, embeddings)
    engine.safe_upsert_to_qdrant(points)
    engine.create_payload_index()
    
    # # Tạo detection embeddings
    engine.create_subject_embeddings()
    engine.create_type_embeddings()
    engine.create_term_embeddings()
    
    # Test search
    while True:
        query=input('Bạn muốn tìm thông tin gì?')
        if query=='bye':
            break
        results = engine.search_qdrant(query, limit=20)
        print(results)


if __name__ == "__main__":
    main()
