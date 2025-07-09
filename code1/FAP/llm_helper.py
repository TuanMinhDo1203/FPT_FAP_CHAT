import os
import json
import time
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


# Load env
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
load_dotenv(dotenv_path=os.path.join(ROOT_DIR, '.env'))

class LLMHelper:
    def __init__(self, api_key: str = None, model: str = "gemini-1.5-flash"):
        """
        Khởi tạo LLM helper với Gemini API
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model_instance = genai.GenerativeModel(self.model)
                print(f"✅ LLM Helper initialized with {self.model}")
            except Exception as e:
                print(f"⚠️ LLM initialization failed: {e}")
                self.enabled = False
        else:
            print("⚠️ No Gemini API key found, LLM features disabled")
    
    # Các dict được định nghĩa sẵn cho dễ sử dụng
    SUBJECTS = {
        "ADY201m": "AI, DS with Python & SQL",
        "AIL303m": "Machine Learning",
        "CEA201": "Computer Organization and Architecture",
        "CPV301": "Computer Vision",
        "CSD203": "Data Structures and Algorithm with Python",
        "CSI105": "Introduction to Computer Science",
        "DAP391m": "AI-DS Project",
        "DBI202": "Database Systems",
        "DSA103": "Traditional music instrument",
        "JPD113": "Elementary Japanese 1-A1.1",
        "JPD123": "Japanese Elementary 1-A1.2",
        "MAD101": "Discrete mathematics",
        "MAE101": "Mathematics for Engineering",
        "MAI391": "Advanced mathematics",
        "MAS291": "Statistics & Probability",
        "OTP101": "Orientation and General Training Program",
        "PFP191": "Programming Fundamentals with Python",
        "SSG104": "Communication and In-Group Working Skills",
        "SWE201c": "Introduction to Software Engineering",
        "VOV114": "Vovinam 1",
        "VOV124": "Vovinam 2",
        "VOV134": "Vovinam 3"
    }
    
    TYPES = {
        "thông tin sinh viên": "Student profile information",
        "điểm danh": "Attendance records", 
        "chi tiết điểm": "Grade details",
        "tổng kết môn học": "Course summaries"
    }
    
    TERMS = {
        "Fall2023": "Fall 2023",
        "Spring2024": "Spring 2024",
        "Summer2024": "Summer 2024", 
        "Fall2024": "Fall 2024",
        "Spring2025": "Spring 2025"
    }
    
    def safe_json_parse(self,llm_output: str):
        try:
            # Clean Markdown-like output
            cleaned = re.sub(r"^```(?:json)?|```$", "", llm_output.strip(), flags=re.MULTILINE).strip()
            return str(cleaned)
        except Exception as e:
            print(f"❌ LLM extract vif lis do j do failed: {e}")
            return {}
    
    def parse_time_range(self, query: str) -> Dict[str, datetime]:
        """
        Parse time range từ query để tạo filter cho RAG (fallback method)
        Hỗ trợ các format: "tuần sau", "tháng này", "kì sau", "semester trước", etc.
        
        Returns:
            Dict với keys: start_date, end_date, hoặc empty dict nếu không tìm thấy
        """
        today = datetime.now()
        query_lower = query.lower()
        
        # Mapping các từ khóa thời gian
        time_patterns = {
            # Tuần
            r"tuần sau": lambda: (today + timedelta(days=7), today + timedelta(days=13)),
            r"tuần trước": lambda: (today - timedelta(days=7), today - timedelta(days=1)),
            r"tuần này": lambda: (today - timedelta(days=today.weekday()), today + timedelta(days=6-today.weekday())),
            r"tuần tới": lambda: (today + timedelta(days=7), today + timedelta(days=13)),
            r"tuần vừa rồi": lambda: (today - timedelta(days=7), today - timedelta(days=1)),
            
            # Tháng
            r"tháng sau": lambda: (today + relativedelta(months=1, day=1), today + relativedelta(months=1, day=31)),
            r"tháng trước": lambda: (today - relativedelta(months=1, day=1), today - relativedelta(months=1, day=31)),
            r"tháng này": lambda: (today.replace(day=1), (today + relativedelta(months=1, day=1)) - timedelta(days=1)),
            r"tháng tới": lambda: (today + relativedelta(months=1, day=1), today + relativedelta(months=1, day=31)),
            r"tháng vừa qua": lambda: (today - relativedelta(months=1, day=1), today - relativedelta(months=1, day=31)),
            
            # Ngày
            r"ngày mai": lambda: (today + timedelta(days=1), today + timedelta(days=1)),
            r"ngày hôm qua": lambda: (today - timedelta(days=1), today - timedelta(days=1)),
            r"hôm nay": lambda: (today, today),
            r"hôm qua": lambda: (today - timedelta(days=1), today - timedelta(days=1)),
            
            # Học kỳ (với các biến thể)
            r"học kỳ này": lambda: self._get_current_term_range(today),
            r"học kỳ sau": lambda: self._get_next_term_range(today),
            r"học kỳ trước": lambda: self._get_previous_term_range(today),
            r"kì này": lambda: self._get_current_term_range(today),
            r"kì sau": lambda: self._get_next_term_range(today),
            r"kì trước": lambda: self._get_previous_term_range(today),
            r"semester này": lambda: self._get_current_term_range(today),
            r"semester sau": lambda: self._get_next_term_range(today),
            r"semester trước": lambda: self._get_previous_term_range(today),
        }
        
        for pattern, date_func in time_patterns.items():
            if re.search(pattern, query_lower):
                try:
                    start_date, end_date = date_func()
                    return {
                        "start_date": start_date,
                        "end_date": end_date,
                        "time_range_type": pattern
                    }
                except Exception as e:
                    print(f"❌ Error parsing time range for pattern '{pattern}': {e}")
                    continue
        
        return {}
    
    def _get_current_term_range(self, today: datetime) -> Tuple[datetime, datetime]:
        """Lấy khoảng thời gian của học kỳ hiện tại"""
        month = today.month
        year = today.year
        
        if month in [1, 2, 3]:  # Spring
            return (datetime(year, 1, 1), datetime(year, 4, 30))
        elif month in [4, 5, 6]:  # Summer
            return (datetime(year, 5, 1), datetime(year, 8, 31))
        elif month in [7, 8, 9]:  # Fall
            return (datetime(year, 9, 1), datetime(year, 12, 31))
        else:  # Winter
            return (datetime(year, 10, 1), datetime(year, 12, 31))
    
    def _get_next_term_range(self, today: datetime) -> Tuple[datetime, datetime]:
        """Lấy khoảng thời gian của học kỳ tiếp theo"""
        month = today.month
        year = today.year
        
        if month in [1, 2, 3]:  # Spring -> Summer
            return (datetime(year, 5, 1), datetime(year, 8, 31))
        elif month in [4, 5, 6]:  # Summer -> Fall
            return (datetime(year, 9, 1), datetime(year, 12, 31))
        elif month in [7, 8, 9]:  # Fall -> Winter
            return (datetime(year, 10, 1), datetime(year, 12, 31))
        else:  # Winter -> Spring next year
            return (datetime(year + 1, 1, 1), datetime(year + 1, 4, 30))
    
    def _get_previous_term_range(self, today: datetime) -> Tuple[datetime, datetime]:
        """Lấy khoảng thời gian của học kỳ trước"""
        month = today.month
        year = today.year
        
        if month in [1, 2, 3]:  # Spring -> Winter previous year
            return (datetime(year - 1, 10, 1), datetime(year - 1, 12, 31))
        elif month in [4, 5, 6]:  # Summer -> Spring
            return (datetime(year, 1, 1), datetime(year, 4, 30))
        elif month in [7, 8, 9]:  # Fall -> Summer
            return (datetime(year, 5, 1), datetime(year, 8, 31))
        else:  # Winter -> Fall
            return (datetime(year, 9, 1), datetime(year, 12, 31))
    
    def extract_query_intent(self, query: str, chat_history: list = None) -> dict:
        """
        Extract metadata từ truy vấn (và lịch sử hội thoại nếu có) sử dụng LLM.
        Args:
            query: Truy vấn cuối cùng của user
            chat_history: List các lượt chat, mỗi lượt là dict {"role": "user"|"assistant", "content": ...} (có thể None)
        Returns:
            dict: Metadata được extract với format:
                {"ma_mon_hoc": ..., "ten_mon_hoc": ..., "loai": ..., "time_range": ...}
        """
        if not self.enabled:
            return {}
        
        # Lấy ngày hôm nay
        today = datetime.now()
        today_str = today.strftime("%d/%m/%Y")
        
        # Tạo prompt từ lịch sử hội thoại nếu có
        history_text = ""
        if chat_history:
            for turn in chat_history:
                if turn["role"] == "user":
                    history_text += f"User: {turn['content']}\n"
                elif turn["role"] == "assistant":
                    history_text += f"Assistant: {turn['content']}\n"
            # Nhấn mạnh truy vấn cuối cùng nếu cần
            if query:
                history_text += f"User (truy vấn cuối): {query}\n"
        subjects_text = "\n".join([f"- {code} - {name}" for code, name in self.SUBJECTS.items()])
        types_text = "\n".join([f"- {type_val}" for type_val in self.TYPES.keys()])
        
        if chat_history:
            prompt = f"""
Bạn là trợ lý AI cho hệ thống quản lý sinh viên. Dưới đây là lịch sử hội thoại giữa user và assistant:
{history_text}

Truy vấn hiện tại: "{query}"

THÔNG TIN THỜI GIAN:
- Ngày hôm nay: {today_str}

QUY TẮC PHÂN TÍCH (khớp với trường trong vector database):
1. MA_MON_HOC: Phải là một trong các mã môn học sau:
{subjects_text}
2. LOAI: Phải là một trong các loại sau (theo trường 'loai' trong database):
{types_text}
3. TIME_RANGE: Nếu truy vấn có đề cập đến thời gian tương đối, hãy tính toán khoảng thời gian cụ thể dựa trên ngày hôm nay.

CÁC TỪ KHÓA THỜI GIAN ĐƯỢC HỖ TRỢ:
- Tuần: "tuần sau", "tuần trước", "tuần này", "tuần tới", "tuần vừa rồi"
- Tháng: "tháng sau", "tháng trước", "tháng này", "tháng tới", "tháng vừa qua"
- Ngày: "ngày mai", "ngày hôm qua", "hôm nay", "hôm qua"
- Học kỳ: "học kỳ sau", "học kỳ trước", "học kỳ này", "kì sau", "kì trước", "kì này", "semester sau", "semester trước"

Lưu ý:
- Nếu không tìm thấy thông tin tương ứng, trả về null
- ma_mon_hoc và ten_mon_hoc phải match chính xác với danh sách trên
- loai phải là một trong 4 loại chuẩn (theo trường 'loai')
- time_range phải là khoảng thời gian cụ thể (start_date và end_date) dựa trên ngày hôm nay
- "kì" = "học kỳ", "semester" = "học kỳ"

Hãy phân tích truy vấn cuối cùng của user và trả về JSON với các trường: ma_mon_hoc, ten_mon_hoc, loai, time_range.

Trả về JSON format:
{{
  "ma_mon_hoc": "mã môn học hoặc null",
  "ten_mon_hoc": "tên môn học hoặc null", 
  "loai": "loại dữ liệu hoặc null",
  "time_range": {{
    "start_date": "dd/mm/yyyy",
    "end_date": "dd/mm/yyyy",
    "time_range_type": "mô tả khoảng thời gian"
  }} hoặc null
}}
"""
        else:
            prompt = f"""
Bạn là trợ lý AI cho hệ thống quản lý sinh viên. Hãy phân tích truy vấn sau và trả về JSON với các trường: ma_mon_hoc, ten_mon_hoc, loai, time_range.

Truy vấn: "{query}"

THÔNG TIN THỜI GIAN:
- Ngày hôm nay: {today_str}

QUY TẮC PHÂN TÍCH (khớp với trường trong vector database):
1. MA_MON_HOC: Phải là một trong các mã môn học sau:
{subjects_text}
2. LOAI: Phải là một trong các loại sau (theo trường "loai" trong database):
{types_text}
3. TIME_RANGE: Nếu truy vấn có đề cập đến thời gian tương đối, hãy tính toán khoảng thời gian cụ thể dựa trên ngày hôm nay.

CÁC TỪ KHÓA THỜI GIAN ĐƯỢC HỖ TRỢ:
- Tuần: "tuần sau", "tuần trước", "tuần này", "tuần tới", "tuần vừa rồi"
- Tháng: "tháng sau", "tháng trước", "tháng này", "tháng tới", "tháng vừa qua"
- Ngày: "ngày mai", "ngày hôm qua", "hôm nay", "hôm qua"
- Học kỳ: "học kỳ sau", "học kỳ trước", "học kỳ này", "kì sau", "kì trước", "kì này", "semester sau", "semester trước"

Lưu ý:
- Nếu không tìm thấy thông tin tương ứng, trả về null
- ma_mon_hoc và ten_mon_hoc phải match chính xác với danh sách trên
- loai phải là một trong 4 loại chuẩn (theo trường "loai")
- time_range phải là khoảng thời gian cụ thể (start_date và end_date) dựa trên ngày hôm nay
- "kì" = "học kỳ", "semester" = "học kỳ"

Trả về JSON format:
{{
    "ma_mon_hoc": "mã môn học hoặc null",
    "ten_mon_hoc": "tên môn học hoặc null",
    "loai": "loại dữ liệu hoặc null",
    "time_range": {{
        "start_date": "dd/mm/yyyy",
        "end_date": "dd/mm/yyyy", 
        "time_range_type": "mô tả khoảng thời gian"
    }} hoặc null
}}

Ví dụ:
- "Điểm môn AIL303m" → {{"ma_mon_hoc": "AIL303m", "ten_mon_hoc": "Machine Learning", "loai": "chi tiết điểm", "time_range": null}}
- "Điểm danh môn CSI105" → {{"ma_mon_hoc": "CSI105", "ten_mon_hoc": "Introduction to Computer Science", "loai": "điểm danh", "time_range": null}}
- "Thông tin sinh viên" → {{"ma_mon_hoc": null, "ten_mon_hoc": null, "loai": "thông tin sinh viên", "time_range": null}}
- "Tổng kết môn PFP191" → {{"ma_mon_hoc": "PFP191", "ten_mon_hoc": "Programming Fundamentals with Python", "loai": "tổng kết môn học", "time_range": null}}
- "Điểm danh tuần sau" → {{"ma_mon_hoc": null, "ten_mon_hoc": null, "loai": "điểm danh", "time_range": {{"start_date": "15/01/2025", "end_date": "21/01/2025", "time_range_type": "tuần sau"}}}}
- "Lịch học tháng này" → {{"ma_mon_hoc": null, "ten_mon_hoc": null, "loai": "điểm danh", "time_range": {{"start_date": "01/01/2025", "end_date": "31/01/2025", "time_range_type": "tháng này"}}}}
- "Điểm danh kì sau" → {{"ma_mon_hoc": null, "ten_mon_hoc": null, "loai": "điểm danh", "time_range": {{"start_date": "01/05/2025", "end_date": "31/08/2025", "time_range_type": "học kỳ sau"}}}}
- "Lịch học kì trước" → {{"ma_mon_hoc": null, "ten_mon_hoc": null, "loai": "điểm danh", "time_range": {{"start_date": "01/09/2024", "end_date": "31/12/2024", "time_range_type": "học kỳ trước"}}}}
"""
        try:
            response = self.model_instance.generate_content(prompt)
            cleaned_text = self.safe_json_parse(response.text)
            result = json.loads(cleaned_text)
            
            # Validate và map ten_mon_hoc từ ma_mon_hoc
            if result and result.get('ma_mon_hoc'):
                ma_mon_hoc = result['ma_mon_hoc']
                if ma_mon_hoc in self.SUBJECTS:
                    result['ten_mon_hoc'] = self.SUBJECTS[ma_mon_hoc]
                else:
                    result['ten_mon_hoc'] = None
            
            # Convert time_range string dates to datetime objects if present
            if result and result.get('time_range'):
                time_range = result['time_range']
                try:
                    start_date = datetime.strptime(time_range['start_date'], "%d/%m/%Y")
                    end_date = datetime.strptime(time_range['end_date'], "%d/%m/%Y")
                    result['time_range'] = {
                        "start_date": start_date,
                        "end_date": end_date,
                        "time_range_type": time_range.get('time_range_type', 'unknown')
                    }
                    print(f"⏰ LLM detected time range: {time_range['start_date']} - {time_range['end_date']}")
                except Exception as e:
                    print(f"❌ Error parsing time range dates: {e}")
                    result['time_range'] = None
            
            return result
        except Exception as e:
            print(f"❌ LLM extract intent failed: {e}")
            return {}
    
    def re_rank_results(self, query: str, results: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Re-rank kết quả search bằng LLM
        Backup: trả về results gốc nếu LLM fail
        """
        if not self.enabled or not results:
            return results
        
        # Format results cho LLM
        results_text = ""
        for i, r in enumerate(results, 1):
            results_text += f"{i}. Score: {r['score']:.3f} | Loai: {r['loai']} | Mon hoc: {r['ma_mon_hoc']} - {r['ten_mon_hoc']}\n"
            results_text += f"   Content: {r['content'][:200]}...\n\n"
        
        prompt = f"""
        Dưới đây là truy vấn của người dùng và các kết quả tìm kiếm. Hãy sắp xếp lại các kết quả theo mức độ liên quan, chỉ giữ lại top {top_k} kết quả thực sự phù hợp nhất.
        
        Query: "{query}"
        
        Kết quả hiện tại:
        {results_text}
        
        Trả về danh sách số thứ tự của top {top_k} kết quả phù hợp nhất (ví dụ: [3, 1, 5, 2, 4]):
        """
        
        try:
            response = self.model_instance.generate_content(prompt)
            # Parse response để lấy danh sách index
            import re
            numbers = re.findall(r'\d+', response.text)
            if numbers:
                indices = [int(n) - 1 for n in numbers[:top_k] if 0 <= int(n) - 1 < len(results)]
                re_ranked = [results[i] for i in indices if i < len(results)]
                print(f"🔄 LLM re-ranked: {indices}")
                return re_ranked
        except Exception as e:
            print(f"❌ LLM re-rank failed: {e}")
        
        return results
    
    def synthesize_answer(self, query: str, results: List[Dict]) -> str:
        """
        Tổng hợp trả lời từ kết quả search
        Backup: trả về kết quả gốc nếu LLM fail
        """
        if not self.enabled or not results:
            return "Không tìm thấy kết quả phù hợp."
        
        # Format results cho LLM
        results_text = ""
        for i, r in enumerate(results, 1):
            results_text += f"{i}. {r['content']}\n\n"
        
        prompt = f"""
            Bạn là một chatbot hỗ trợ sinh viên trường FPT University, chuyên trả lời các câu hỏi liên quan đến điểm danh, thời khóa biểu, điểm số, v.v.

            Nhiệm vụ của bạn là:
            - Tổng hợp thông tin từ phần "Kết quả" bên dưới để trả lời truy vấn của sinh viên một cách NGẮN GỌN, TỰ NHIÊN, DỄ HIỂU.
            - KHÔNG được bịa thêm thông tin ngoài dữ liệu cho sẵn.
            - Nếu không tìm thấy thông tin phù hợp, hãy trả lời một cách lịch sự rằng chưa có đủ dữ liệu.

            ---

            Query của sinh viên:  
            "{query}"

            ---

            Kết quả đã truy xuất (có thể đến từ nhiều nguồn dữ liệu):  
            {results_text}

            ---

            Hãy trả lời:
            """
        
        try:
            response = self.model_instance.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"❌ LLM synthesis failed: {e}")
            return "Không thể tổng hợp kết quả. Vui lòng xem kết quả chi tiết bên dưới."
    
    def is_available(self) -> bool:
        """Kiểm tra LLM có sẵn sàng không"""
        return self.enabled 

