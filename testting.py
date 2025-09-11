import os
os.environ["HF_HOME"] = r"D:/huggingface_cache"
import json
import time
import pandas as pd
import numpy as np
import uuid
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue, Range
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import logging
import re
import hashlib
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import google.generativeai as genai
from deep_translator import GoogleTranslator
from collections import defaultdict
from numpy import dot
from numpy.linalg import norm
import heapq
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification
import torch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
qdrant_url = r"https://0f47d391-b7c1-45d9-a956-5f7228cd80f3.europe-west3-0.gcp.cloud.qdrant.io:6333"
qdrant_api_key = os.getenv("qdrant_api_key")
gemini_api_key = os.getenv("gemini_api_key")
collection_name_student = "Fap_data_testing"
collection_name_general = "FINAL"
# gemini_api_key = 'ben'
# CSV paths
csv_paths = {
    'student_profile': os.path.join(BASE_DIR, 'data', 'FAP', 'student_profile.csv'),
    'attendance_reports': os.path.join(BASE_DIR, 'data', 'FAP', 'attendance_reports.csv'),
    'grade_details': os.path.join(BASE_DIR, 'data', 'FAP', 'grade_details.csv'),
    'course_summaries': os.path.join(BASE_DIR, 'data', 'FAP', 'course_summaries.csv'),
    'flm_data': os.path.join(BASE_DIR, 'data', 'DATA cố định', 'FLM', 'FINAL', 'FINAL_DF_FLM.csv')
}

# --- BGEEmbedder Class ---
class BGEEmbedder:
    def __init__(self, model_name=r"D:\huggingface_cache\hub\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181"):
        self.model = SentenceTransformer(model_name)
        self.prefix = "Represent this sentence for searching relevant passages: "
    
    def embed(self, texts, batch_size=16):
        texts_with_prefix = [
            text if text.startswith(self.prefix) else self.prefix + text
            for text in texts
        ]
        embeddings = self.model.encode(
            texts_with_prefix,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings

# --- LLMHelper Class ---
class LLMHelper:
    def __init__(self, api_key: str = None, model: str = "gemini-2.0-flash"):
        self.api_key = api_key or gemini_api_key
        self.model = model
        self.enabled = bool(self.api_key)
        if self.enabled:
            try:
                genai.configure(api_key=self.api_key)
                self.model_instance = genai.GenerativeModel(self.model)
                logger.info(f"✅ LLM Helper initialized with {self.model}")
            except Exception as e:
                logger.error(f"⚠️ LLM initialization failed: {e}")
                self.enabled = False
        else:
            logger.warning("⚠️ No Gemini API key found, LLM features disabled")

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
        "tổng kết môn học": "Course summaries",
        "overview": "Queries about which subjects match certain characteristics (e.g., taught in a specific semester, related to a topic, or having certain prerequisites), or general overviews of subject goals, credits, syllabus, or curriculum structure.",
        "construtive_question": "Thought-provoking questions",
        "assessment": "Evaluations, types of tests, exams, FE, PE, TE and grading weights",
        "session": "Lecture sessions, lessons, topics covered in each week or session",
        "material": "Recommended textbooks, reference materials, slides, or other learning resources",
        "learning outcome": "Learning outcome, expected knowledge, skills, or competencies students should achieve after completing the course",
        "student_list": "List of students enrolled in the course, including name, student ID, and email",
        "guide": "Instructions or guidance for students on how to complete tasks, assignments, projects, or use certain tools/platforms."
    }

    TYPE_KEYWORDS = {
        "overview": ["overview", "objective", "goal", "credits", "semester", "prerequisite", "syllabus", "subject", "subjects", 'general'],
        "construtive_question": ["why", "what if", "critical", "discussion", "reflect", "ethical", "opinion", "thinking"],
        "assessment": ["exam", "test", "quiz", "grading", "project", "evaluation", "score", "mark", "weight", "assessment"],
        "session": ["week", "lesson", "lecture", "topic", "schedule", "session", "class", "timetable"],
        "material": ["textbook", "slide", "document", "reading", "reference", "material", "resource", "book", "pdf", "file"],
        "learning outcome": ["learn", "outcome", "skill", "competency", "ability", "achieve", "knowledge", "CLO", "LO", "learning outcome"],
        "student_list": ["student", "id", "mssv", "email", "class list", "enrolled", "danh sách sinh viên", "học sinh", "danh sách"],
        "guide": ["how to", "instruction", "guide", "tutorial", "step", "steps", "do", "complete", "submit", "platform", "tool", "usage", "help", "assist", "support", "direction"],
        "attendance": ["attendance", "present", "absent", "record", "check-in", "participation", "presence", "ca học", "phòng", "giảng viên"],
        "grade detail": ["score", "mark", "value", "grade", "item", "category", "evaluation", "component", "trọng số", "điểm"],
        "course summary": ["summarize","summary", "average", "final", "result", "status", "performance", "overall", "total", "điểm trung bình", "kết quả"],
        "student profile": ["student", "profile", "id", "name", "email", "program", "major", "class", "course", "personal"]
    }

    TERMS = {
        "Fall2023": "Fall 2023",
        "Spring2024": "Spring 2024",
        "Summer2024": "Summer 2024",
        "Fall2024": "Fall 2024",
        "Spring2025": "Spring 2025"
    }

    def safe_json_parse(self, llm_output: str):
        try:
            cleaned = re.sub(r"^```(?:json)?|```$", "", llm_output.strip(), flags=re.MULTILINE).strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"❌ LLM extract failed: {e}")
            return {}

    def parse_time_range(self, query: str) -> Dict[str, datetime]:
        today = datetime.now()
        query_lower = query.lower()
        time_patterns = {
            r"tuần sau": lambda: (today + timedelta(days=7), today + timedelta(days=13)),
            r"tuần trước": lambda: (today - timedelta(days=7), today - timedelta(days=1)),
            r"tuần này": lambda: (today - timedelta(days=today.weekday()), today + timedelta(days=6-today.weekday())),
            r"tháng sau": lambda: (today + relativedelta(months=1, day=1), today + relativedelta(months=1, day=31)),
            r"tháng trước": lambda: (today - relativedelta(months=1, day=1), today - relativedelta(months=1, day=31)),
            r"tháng này": lambda: (today.replace(day=1), (today + relativedelta(months=1, day=1)) - timedelta(days=1)),
            r"ngày mai": lambda: (today + timedelta(days=1), today + timedelta(days=1)),
            r"ngày hôm qua": lambda: (today - timedelta(days=1), today - timedelta(days=1)),
            r"hôm nay": lambda: (today, today),
            r"học kỳ này|kì này|semester này": lambda: self._get_current_term_range(today),
            r"học kỳ sau|kì sau|semester sau": lambda: self._get_next_term_range(today),
            r"học kỳ trước|kì trước|semester trước": lambda: self._get_previous_term_range(today),
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
                    logger.error(f"❌ Error parsing time range for pattern '{pattern}': {e}")
                    continue
        return {}

    def _get_current_term_range(self, today: datetime) -> Tuple[datetime, datetime]:
        month = today.month
        year = today.year
        if month in [1, 2, 3]:
            return (datetime(year, 1, 1), datetime(year, 4, 30))
        elif month in [4, 5, 6]:
            return (datetime(year, 5, 1), datetime(year, 8, 31))
        elif month in [7, 8, 9]:
            return (datetime(year, 9, 1), datetime(year, 12, 31))
        else:
            return (datetime(year, 10, 1), datetime(year, 12, 31))

    def _get_next_term_range(self, today: datetime) -> Tuple[datetime, datetime]:
        month = today.month
        year = today.year
        if month in [1, 2, 3]:
            return (datetime(year, 5, 1), datetime(year, 8, 31))
        elif month in [4, 5, 6]:
            return (datetime(year, 9, 1), datetime(year, 12, 31))
        elif month in [7, 8, 9]:
            return (datetime(year, 10, 1), datetime(year, 12, 31))
        else:
            return (datetime(year + 1, 1, 1), datetime(year + 1, 4, 30))

    def _get_previous_term_range(self, today: datetime) -> Tuple[datetime, datetime]:
        month = today.month
        year = today.year
        if month in [1, 2, 3]:
            return (datetime(year - 1, 10, 1), datetime(year - 1, 12, 31))
        elif month in [4, 5, 6]:
            return (datetime(year, 1, 1), datetime(year, 4, 30))
        elif month in [7, 8, 9]:
            return (datetime(year, 5, 1), datetime(year, 8, 31))
        else:
            return (datetime(year, 9, 1), datetime(year, 12, 31))

    def extract_query_intent(self, query: str, chat_history: list = None) -> dict:
        if not self.enabled:
            return {}
        today = datetime.now()
        today_str = today.strftime("%d/%m/%Y %H:%M")
        history_text = ""
        if chat_history:
            for turn in chat_history:
                history_text += f"{turn['role'].capitalize()}: {turn['content']}\n"
            history_text += f"User (truy vấn cuối): {query}\n"
        subjects_text = "\n".join([f"- {code} - {name}" for code, name in self.SUBJECTS.items()])
        types_text = "\n".join([f"- {type_val}" for type_val in self.TYPES.keys()])
        prompt = f"""
Bạn là trợ lý AI cho hệ thống quản lý sinh viên FPT University. Phân tích truy vấn sau và trả về JSON với các trường: ma_mon_hoc, ten_mon_hoc, loai, time_range, semester.
Truy vấn: "{query}"
{history_text}
THÔNG TIN THỜI GIAN:
- Ngày hôm nay: {today_str}
QUY TẮC PHÂN TÍCH:
1. MA_MON_HOC: Phải là một trong các mã môn học sau:
{subjects_text}
2. LOAI: Phải là một trong các loại sau:
{types_text}
3. TIME_RANGE: Nếu có thời gian tương đối, tính toán khoảng thời gian cụ thể.
4. SEMESTER: Nếu có học kỳ được đề cập rõ ràng, trả về số học kỳ (0-9). Nếu không chắc chắn, để null.
CÁC TỪ KHÓA THỜI GIAN:
- Tuần: "tuần sau", "tuần trước", "tuần này"
- Tháng: "tháng sau", "tháng trước", "tháng này"
- Ngày: "ngày mai", "ngày hôm qua", "hôm nay"
- Học kỳ: "học kỳ sau", "học kỳ trước", "học kỳ này", "kì sau", "kì trước", "kì này"
Lưu ý:
- Nếu không tìm thấy thông tin, trả về null
- ma_mon_hoc và ten_mon_hoc phải match chính xác
- loai phải là một trong các loại chuẩn
- time_range phải có start_date và end_date (dd/mm/yyyy)
Trả về JSON:
{{
  "ma_mon_hoc": "mã hoặc null",
  "ten_mon_hoc": "tên hoặc null",
  "loai": "loại hoặc null",
  "time_range": {{"start_date": "dd/mm/yyyy", "end_date": "dd/mm/yyyy", "time_range_type": "mô tả"}} hoặc null,
  "semester": số hoặc null
}}
"""
        try:
            response = self.model_instance.generate_content(prompt)
            result = self.safe_json_parse(response.text)
            if result.get('ma_mon_hoc') and result['ma_mon_hoc'] in self.SUBJECTS:
                result['ten_mon_hoc'] = self.SUBJECTS[result['ma_mon_hoc']]
            if result.get('time_range'):
                time_range = result['time_range']
                try:
                    start_date = datetime.strptime(time_range['start_date'], "%d/%m/%Y")
                    end_date = datetime.strptime(time_range['end_date'], "%d/%m/%Y")
                    result['time_range'] = {
                        "start_date": start_date,
                        "end_date": end_date,
                        "time_range_type": time_range.get('time_range_type', 'unknown')
                    }
                except:
                    result['time_range'] = None
            return result
        except Exception as e:
            logger.error(f"❌ LLM extract intent failed: {e}")
            return {}

    def re_rank_results(self, query: str, results: List[Dict], top_k: int = 5) -> List[Dict]:
        if not self.enabled or not results:
            return results
        results_text = "\n".join([f"{i}. Score: {r['score']:.3f} | Loai/Type: {r.get('loai', r.get('type', 'N/A'))} | Mon hoc: {r.get('ma_mon_hoc', r.get('subject_code', 'N/A'))} - {r.get('ten_mon_hoc', r.get('subject_name', 'N/A'))}\n   Content: {r['content'][:200]}..." for i, r in enumerate(results, 1)])
        prompt = f"""
Dựa trên truy vấn: "{query}"
Kết quả hiện tại:
{results_text}
Sắp xếp lại top {top_k} kết quả phù hợp nhất, trả về danh sách số thứ tự (e.g., [3, 1, 5, 2, 4]):
"""
        try:
            response = self.model_instance.generate_content(prompt)
            numbers = re.findall(r'\d+', response.text)
            indices = [int(n) - 1 for n in numbers[:top_k] if 0 <= int(n) - 1 < len(results)]
            re_ranked = [results[i] for i in indices if i < len(results)]
            for i, result in enumerate(re_ranked):
                result['rank'] = i + 1
            return re_ranked
        except:
            return results

    def synthesize_answer(self, query: str, results: List[Dict], retrieved_chunks: str = '') -> str:
        if not self.enabled or not results:
            prompt = f"""
Bạn là chatbot hỗ trợ sinh viên FPT University. Trả lời câu hỏi "{query}" một cách tự nhiên và hữu ích dựa trên tri thức chung. Nếu không có dữ liệu cụ thể, hãy cung cấp thông tin tổng quát hoặc đề xuất cách tìm hiểu thêm. Thời gian hiện tại: {datetime.now().strftime('%H:%M %p +07, %d/%m/%Y')}.
Trả lời:
"""
            try:
                response = self.model_instance.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                logger.error(f"❌ LLM synthesis failed: {e}")
                return "Không thể tổng hợp kết quả."
        results_text = "\n".join([f"{i}. {r['content']}" for i, r in enumerate(results, 1)])
        prompt = f"""
Bạn là chatbot hỗ trợ sinh viên FPT University.
Tổng hợp thông tin từ kết quả sau để trả lời truy vấn "{query}" một cách ngắn gọn, tự nhiên, dễ hiểu.
KHÔNG bịa thêm thông tin. Nếu không đủ dữ liệu, trả lời lịch sự.
Kết quả:
{retrieved_chunks}
Trả lời:
"""
        try:
            response = self.model_instance.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"❌ LLM synthesis failed: {e}")
            return "Không thể tổng hợp kết quả."

    def is_available(self) -> bool:
        return self.enabled



# --- FapSearchEngine Class ---
class FapSearchEngine:
    def __init__(self, csv_paths: dict, qdrant_url: str = qdrant_url, qdrant_api_key: str = qdrant_api_key, collection_name_student: str = collection_name_student, collection_name_general: str = collection_name_general, enable_llm: bool = True):
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.collection_name_student = collection_name_student
        self.collection_name_general = collection_name_general
        self.client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key, prefer_grpc=False)
        
        # Initialize student collection
        try:
            self.client.get_collection(self.collection_name_student)
            logger.info(f"✅ Collection {self.collection_name_student} exists.")
        except:
            logger.info(f"⚠️ Creating collection {self.collection_name_student}...")
            self.client.recreate_collection(collection_name=self.collection_name_student, vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
        
        # Initialize general collection
        try:
            self.client.get_collection(self.collection_name_general)
            logger.info(f"✅ Collection {self.collection_name_general} exists.")
        except:
            logger.info(f"⚠️ Creating collection {self.collection_name_general}...")
            self.client.recreate_collection(collection_name=self.collection_name_general, vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
        
        self.csv_paths = csv_paths
        self.dataframes = {}
        self.embedder = BGEEmbedder()
        self.subject_embeddings = {}
        self.type_embeddings = {}
        self.term_embeddings = {}
        self.static_subjects = LLMHelper.SUBJECTS
        self.enable_llm = enable_llm
        self.llm_helper = LLMHelper() if enable_llm else None
        
        # Load subject map
        df_flm = pd.read_csv(csv_paths['flm_data'])
        self.subject_map = {
            row["SubjectCode"]: f"{row['SubjectCode']} - {row['Subject Name']}"
            for _, row in df_flm[["SubjectCode", "Subject Name"]].dropna().drop_duplicates().iterrows()
        }
        self.subject_map = self.filter_subjects(self.subject_map)
        
        # Load data and initialize embeddings
        self.load_all_dataframes()
        self.ingest_flm_data()
        self.create_subject_embeddings()
        self.create_type_embeddings()
        self.create_term_embeddings()

    def filter_subjects(self, subject_map):
        for prefix in ["PHE_COM", "AI17_COM", "AI17_GRA_ELE"]:
            subject_map = {k: v for k, v in subject_map.items() if not k.startswith(prefix)}
        return subject_map

    def _normalize_date_format(self, date_str: str) -> str:
        if not date_str or date_str == "Không rõ":
            return "Không rõ"
        date_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
        match = re.search(date_pattern, date_str)
        if match:
            day, month, year = match.groups()
            return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        return date_str

    def load_all_dataframes(self):
        for key, path in self.csv_paths.items():
            logger.info(f"Checking {key}: {os.path.exists(path)} - {path}")
            if os.path.exists(path):
                self.dataframes[key] = pd.read_csv(path)
                logger.info(f"✅ Loaded {key}: {len(self.dataframes[key])} rows")
            else:
                logger.error(f"❌ File not found: {path}")

    def chunk_student_profile(self, df, user_full_name=None):
        def safe(x):
            return str(x).strip() if pd.notnull(x) else "Không rõ"
        payloads = []
        for _, row in df.iterrows():
            full_name = user_full_name or safe(row.get('full_name', ''))
            roll_number = safe(row.get('roll_number', ''))
            noi_dung = (
                f"Thông tin sinh viên: {full_name} | Mã SV: {roll_number}\n"
                f"Ngày sinh: {safe(row['date_of_birth'])} | Giới tính: {safe(row['gender'])}\n"
                f"Chuyên ngành: {safe(row['major'])} | Lớp: {safe(row['main_class'])} | Trạng thái: {safe(row['current_status'])}\n"
                f"Đào tạo: {'Chính quy' if bool(row['is_full_time_student']) else 'Không chính quy'} | Học bổng: {'Có' if bool(row['is_scholarship_student']) else 'Không'}\n"
                f"Địa chỉ: {safe(row['home_address'])} | Email: {safe(row['email_address'])} | SĐT: {safe(row['phone_number'])}"
            )
            payload = {
                "user_full_name": full_name,
                "user_id": roll_number,
                "loai": "thông tin sinh viên",
                "noi_dung": noi_dung,
                "content_hash": hashlib.sha256(noi_dung.encode('utf-8')).hexdigest()
            }
            payloads.append(payload)
        return payloads

    def chunk_attendance_reports(self, df, user_full_name=None):
        def safe(x):
            return str(x).strip() if pd.notnull(x) else "Không rõ"
        payloads = []
        for _, row in df.iterrows():
            full_name = user_full_name or safe(row.get('full_name', ''))
            student_id = safe(row.get('student_id', ''))
            noi_dung = (
                f"LOẠI: Điểm danh\n"
                f"Sinh viên: {full_name} ({student_id})\n"
                f"Môn học: {safe(row['course_code'])} - {safe(row['course_name'])}\n"
                f"Học kỳ: {safe(row['term'])} | Buổi số: {safe(row['no'])} - Ngày: {safe(row['date'])} - Ca: {safe(row['slot'])} - Phòng: {safe(row['room'])}\n"
                f"Giảng viên: {safe(row['lecturer'])} | Nhóm: {safe(row['group'])}\n"
                f"Trạng thái: {safe(row['status'])} | Ghi chú: {safe(row['comment'])}"
            )
            payload = {
                "user_full_name": full_name,
                "user_id": student_id,
                "ma_sinh_vien": student_id,
                "hoc_ky": safe(row["term"]),
                "ten_mon_hoc": safe(row["course_name"]),
                "ma_mon_hoc": safe(row["course_code"]),
                "ngay": self._normalize_date_format(safe(row["date"])),
                "loai": "điểm danh",
                "noi_dung": noi_dung,
                "content_hash": hashlib.sha256(noi_dung.encode('utf-8')).hexdigest()
            }
            payloads.append(payload)
        return payloads

    def chunk_grade_details(self, df, user_full_name=None):
        def safe(x):
            return str(x).strip() if pd.notnull(x) else "Không rõ"
        payloads = []
        for _, row in df.iterrows():
            full_name = user_full_name or safe(row.get('full_name', ''))
            student_id = safe(row.get('student_id', ''))
            noi_dung = (
                f"LOẠI: Chi tiết điểm\n"
                f"Sinh viên: {full_name} ({student_id})\n"
                f"Môn học: {safe(row['course_code'])} - {safe(row['course_name'])}\n"
                f"Học kỳ: {safe(row['term'])}\n"
                f"Mục: {safe(row['item'])} | Loại: {safe(row['category'])}\n"
                f"Trọng số: {safe(row['weight'])} | Điểm đạt: {safe(row['value'])}"
            )
            payload = {
                "user_full_name": full_name,
                "user_id": student_id,
                "ma_sinh_vien": student_id,
                "hoc_ky": safe(row["term"]),
                "ten_mon_hoc": safe(row["course_name"]),
                "ma_mon_hoc": safe(row["course_code"]),
                "loai": "chi tiết điểm",
                "noi_dung": noi_dung,
                "content_hash": hashlib.sha256(noi_dung.encode('utf-8')).hexdigest()
            }
            payloads.append(payload)
        return payloads

    def chunk_course_summaries(self, df, user_full_name=None):
        def safe(x):
            return str(x).strip() if pd.notnull(x) else "Không rõ"
        payloads = []
        for _, row in df.iterrows():
            full_name = user_full_name or ""
            noi_dung = (
                f"LOẠI: Tổng kết môn học\n"
                f"Sinh viên: {full_name}\n"
                f"Môn học: {safe(row['course_code'])} - {safe(row['course_name'])}\n"
                f"Học kỳ: {safe(row['term'])}\n"
                f"Điểm trung bình: {safe(row['avg_score'])}\n"
                f"Trạng thái: {safe(row['status'])}\n"
                f"Tóm tắt: {safe(row['summary'])}"
            )
            payload = {
                "user_full_name": full_name,
                "user_id": None,
                "hoc_ky": safe(row["term"]),
                "ten_mon_hoc": safe(row["course_name"]),
                "ma_mon_hoc": safe(row["course_code"]),
                "loai": "tổng kết môn học",
                "noi_dung": noi_dung,
                "content_hash": hashlib.sha256(noi_dung.encode('utf-8')).hexdigest()
            }
            payloads.append(payload)
        return payloads

    def chunk_flm_data(self, df):
        payloads = []
        for _, row in df.iterrows():
            content = (
                f"Môn học: {row['SubjectCode']} - {row['Subject Name']}\n"
                f"Cấp độ: {row.get('Degree Level', 'N/A')}\n"
                f"Tín chỉ: {row.get('Credits', 'N/A')}\n"
                f"Học kỳ: {row.get('Semester', 'N/A')}\n"
                f"Môn tiên quyết: {row.get('Pre-requisites', 'N/A')}\n"
                f"Mô tả: {row.get('Description', 'N/A')}\n"
                f"Nhiệm vụ sinh viên: {row.get('Student Tasks', 'N/A')}\n"
                f"Công cụ: {row.get('Tools', 'N/A')}\n"
                f"Ghi chú: {row.get('Note', 'N/A')}"
            )
            detected_type = self.detect_type_by_embedding(content) or "overview"
            payload = {
                "type": detected_type,
                "subject_code": row.get('SubjectCode', 'N/A'),
                "subject_name": row.get('Subject Name', 'N/A'),
                "degree_level": row.get('Degree Level', 'N/A'),
                "credits": row.get('Credits', 'N/A'),
                "semester": row.get('Semester', 'N/A'),
                "belong_to_combo": row.get('Belong to Combo', 'N/A'),
                "pre_requisites": row.get('Pre-requisites', 'N/A'),
                "scoring_scale": row.get('Scoring Scale', 'N/A'),
                "approved": row.get('Approved', 'N/A'),
                "subject_link": row.get('Subject Link', 'N/A'),
                "time_allocation": row.get('Time Allocation', 'N/A'),
                "description": row.get('Description', 'N/A'),
                "student_tasks": row.get('Student Tasks', 'N/A'),
                "tools": row.get('Tools', 'N/A'),
                "note": row.get('Note', 'N/A'),
                "content": content,
                "content_hash": hashlib.sha256(content.encode('utf-8')).hexdigest()
            }
            payloads.append(payload)
        return payloads

    def generate_content_embedding(self, payloads: list[dict]):
        contents = [p["noi_dung"] if p.get("noi_dung", "").startswith(self.embedder.prefix) else self.embedder.prefix + p.get("noi_dung", p.get("content", "")) for p in payloads]
        embeddings = self.embedder.embed(contents, batch_size=64)
        return embeddings

    def merge_point_structs(self, payloads, embeddings):
        points = []
        for i, (payload, embedding) in enumerate(zip(payloads, embeddings)):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist(),
                payload=payload
            )
            points.append(point)
        return points

    def get_existing_hashes(self, user_id: str = None, collection_name: str = None):
        existing_hashes = set()
        try:
            scroll_filter = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]) if user_id else None
            scroll = self.client.scroll(
                collection_name=collection_name or self.collection_name_student,
                scroll_filter=scroll_filter,
                limit=10000,
                with_payload=["content_hash"]
            )
            for point in scroll[0]:
                h = point.payload.get("content_hash")
                if h:
                    existing_hashes.add(h)
        except Exception as e:
            logger.error(f"❌ Error getting existing hashes: {e}")
        return existing_hashes

    def safe_upsert_to_qdrant(self, points: list, batch_size: int = 100, user_id: str = None, collection_name: str = None):
        existing_hashes = self.get_existing_hashes(user_id, collection_name)
        filtered_points = [p for p in points if p.payload['content_hash'] not in existing_hashes]
        success_count = 0
        failed_batches = 0
        for i in range(0, len(filtered_points), batch_size):
            batch = filtered_points[i:i + batch_size]
            retry = 0
            while retry < 3:
                try:
                    self.client.upsert(collection_name=collection_name or self.collection_name_student, points=batch)
                    success_count += len(batch)
                    logger.info(f"✅ Batch {i//batch_size + 1}: {len(batch)} points uploaded (retry {retry})")
                    break
                except Exception as e:
                    retry += 1
                    logger.error(f"❌ Failed batch {i//batch_size + 1} (retry {retry}): {e}")
                    time.sleep(2 * retry)  # exponential backoff
            else:
                logger.error(f"❌ Batch {i//batch_size + 1} failed after 3 retries, skipped!")
                failed_batches += 1
        logger.info(f"🎯 Uploaded {success_count}/{len(points)} points. Failed batches: {failed_batches}")
        return success_count

    def ingest_flm_data(self):
        df_flm = pd.read_csv(self.csv_paths['flm_data'])
        payloads = self.chunk_flm_data(df_flm)
        # embeddings = self.generate_content_embedding(payloads)
        # points = self.merge_point_structs(payloads, embeddings)
        # self.safe_upsert_to_qdrant(points, collection_name=self.collection_name_general)
        self.create_payload_index(self.collection_name_general)
        # logger.info(f"✅ Ingested {len(points)} points into {self.collection_name_general}")

    def create_payload_index(self, collection_name: str):
        index_fields = [
            ("user_id", "keyword"),
            ("loai", "keyword"),
            ("type", "keyword"),
            ("hoc_ky", "keyword"),
            ("ma_mon_hoc", "keyword"),
            ("subject_code", "keyword"),
            ("ngay", "keyword"),
            ("semester", "keyword")
        ]
        for field_name, field_schema in index_fields:
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_schema
                )
                logger.info(f"✅ Created index for {field_name} in {collection_name}")
            except:
                logger.warning(f"⚠️ Index creation failed for {field_name} in {collection_name}")

    def create_subject_embeddings(self):
        subjects_texts = []
        subjects_code = []
        # From course summaries
        if 'course_summaries' in self.dataframes:
            df = self.dataframes['course_summaries']
            for _, row in df.iterrows():
                course_code = row.get('course_code', '')
                course_name = row.get('course_name', '')
                subject_text = f"{course_code} - {course_name}".strip()
                if subject_text and subject_text not in subjects_texts:
                    subjects_texts.append(subject_text)
                if course_code and course_code not in subjects_code:
                    subjects_code.append(course_code)
        # From FLM data
        general_subjects = [self.subject_map[code] for code in self.subject_map]
        subjects_texts.extend(general_subjects)
        subjects_code.extend(self.subject_map.keys())
        
        if subjects_texts:
            embeddings = self.embedder.embed(subjects_texts)
            for code, embedding in zip(subjects_code, embeddings):
                self.subject_embeddings[code] = embedding
            logger.info(f"📚 Created embeddings for {len(subjects_code)} subjects")

    def create_type_embeddings(self):
        type_descriptions = LLMHelper.TYPES
        embeddings = self.embedder.embed([desc for desc in type_descriptions.values()])
        for data_type, embedding in zip(type_descriptions.keys(), embeddings):
            self.type_embeddings[data_type] = embedding
        logger.info(f"🏷️ Created embeddings for {len(type_descriptions)} data types")

    def create_term_embeddings(self):
        term_descriptions = {
            "Fall2023": "Học kỳ mùa thu năm 2023, diễn ra từ tháng 9 đến tháng 12.",
            "Spring2024": "Học kỳ mùa xuân năm 2024, bắt đầu từ tháng 1 đến tháng 4.",
            "Summer2024": "Học kỳ hè năm 2024, diễn ra từ tháng 5 đến tháng 8.",
            "Fall2024": "Học kỳ mùa thu năm 2024, từ tháng 9 đến tháng 12.",
            "Spring2025": "Học kỳ mùa xuân năm 2025, từ tháng 1 đến tháng 4."
        }
        embeddings = self.embedder.embed([desc for desc in term_descriptions.values()])
        for term, embedding in zip(term_descriptions.keys(), embeddings):
            self.term_embeddings[term] = embedding
        logger.info(f"🏷️ Created embeddings for {len(term_descriptions)} terms")

    def detect_subject_from_query(self, query, threshold=0.3):
        if not self.subject_embeddings:
            return None
        query_embedding = self.embedder.embed([query])[0]
        best_match, best_score = None, 0
        for subject, embedding in self.subject_embeddings.items():
            similarity = cosine_similarity([query_embedding], [embedding])[0][0]
            if similarity > threshold and similarity > best_score:
                best_score = similarity
                best_match = subject
        return best_match

    def detect_type_by_embedding(self, query, alpha=0.8, beta=0.2):
        if not self.type_embeddings:
            return None
        query_embedding = self.embedder.embed([query])[0]
        sims = {
            t: dot(query_embedding, vec) / (norm(query_embedding) * norm(vec))
            for t, vec in self.type_embeddings.items()
        }
        keyword_scores = defaultdict(int)
        query_lower = query.lower()
        for t, keywords in LLMHelper.TYPE_KEYWORDS.items():
            for kw in keywords:
                if re.search(rf"\\b{re.escape(kw)}\\b", query_lower):
                    keyword_scores[t] += 1
        max_kw = max(keyword_scores.values(), default=1)
        keyword_scores_norm = {
            t: keyword_scores[t] / max_kw if max_kw > 0 else 0
            for t in self.type_embeddings
        }
        final_scores = {
            t: alpha * sims.get(t, 0) + beta * keyword_scores_norm.get(t, 0)
            for t in self.type_embeddings
        }
        best_type = max(final_scores, key=final_scores.get)
        return best_type

    def detect_subject(self, query, top_k=2, threshold=0.75):
        query_vec = self.embedder.embed([query])[0]
        sims = {
            code: dot(query_vec, emb) / (norm(query_vec) * norm(emb))
            for code, emb in self.subject_embeddings.items()
        }
        top_subjects = heapq.nlargest(top_k, sims.items(), key=lambda x: x[1])
        top_subjects = [(code, score) for code, score in top_subjects if score >= threshold]
        return top_subjects

    def extract_semester(self, query: str):
        import re
        patterns = [
            r"k[ỳì]\s*(\d+)",      # kỳ 5
            r"semester\s*(\d+)",   # semester 3
            r"term\s*(\d+)",       # term 2
            r"k[ỳì]\s*cuối",       # kỳ cuối → có thể gán là 9
            r"k[ỳì]\s*đ[âầu]",     # kỳ đầu → 0
        ]
        for p in patterns:
            match = re.search(p, query.lower())
            if match:
                try:
                    return int(match.group(1))
                except:
                    if "cuối" in p: return 9
                    if "đầu" in p: return 0
        return None
    
    def predict_type(self, query_en: str) -> str:
        intent_model.eval()
        inputs = intent_tokenizer(query_en, return_tensors="pt", truncation=True, padding=True)
        with torch.no_grad():
            outputs = intent_model(**inputs)
            logits = outputs.logits
            pred = torch.argmax(logits, dim=1).item()
        return intent_model.config.id2label[pred]

    def analyze_intent(self, query_vi: str) -> dict:
        # Dịch
        try:
            query_en = translate_vi_to_en_local(query_vi)
        except Exception:
            query_en = query_vi
        # Predict type bằng model local
        intent = self.predict_type(query_en)
        # Detect subject
        subjects = self.detect_subject(query_en)
        # Detect semester
        semester = self.extract_semester(query_vi)
        result = {
            "type": intent,
            "subjects": subjects,
            "query_en": query_en
        }
        if semester is not None:
            result["semester"] = semester
        return result

    def search_qdrant(self, query: str, user_id: str = None, limit: int = 5, threshold: float = 0.3, chat_history: list = None):
        # Fallback variables
        detected_type = None
        detected_subject = None
        detected_semester = None
        time_range = None
        query_en = None
        llm_intent = {}
        # 1. Thử dùng LLM intent
        try:
            llm_intent = self.llm_helper.extract_query_intent(query, chat_history) if self.enable_llm and self.llm_helper else {}
        except Exception as e:
            logger.error(f"❌ LLM intent extract failed: {e}")
            llm_intent = {}
        # 2. Nếu LLM intent lỗi hoặc rỗng, fallback sang analyze_intent logic
        if not llm_intent or llm_intent == {}:
            logger.warning("⚠️ LLM intent lỗi hoặc rỗng, fallback sang analyze_intent notebook logic")
            analyze = self.analyze_intent(query_vi=query)
            detected_type = analyze.get("type")
            detected_subject = [s[0] for s in analyze.get("subjects", [])]
            detected_semester = analyze.get("semester")
            query_en = analyze.get("query_en", query)
            # Không có time_range khi fallback
        else:
            detected_type = llm_intent.get('loai')
            detected_subject = llm_intent.get('ma_mon_hoc', self.detect_subject_from_query(query, threshold))
            detected_semester = llm_intent.get('semester')
            time_range = llm_intent.get('time_range')
        
        query_embedding = self.embedder.embed([query])[0]
        # Decide which collection to query
        student_types = ["thông tin sinh viên", "điểm danh", "chi tiết điểm", "tổng kết môn học"]
        is_student_query = (
            (detected_type in student_types and user_id) or
            any(keyword in query.lower() for keyword in ["điểm của tôi", "điểm danh của tôi", "thông tin của tôi", "profile", "cá nhân"])
        )
        collection_name = self.collection_name_student if is_student_query else self.collection_name_general
        field_key = "loai" if is_student_query else "type"
        logger.info(f"🔍 Search decision: is_student_query={is_student_query}, collection={collection_name}, user_id={user_id}")
        # Build query filter
        must = []
        should = []
        # Add type filter if detected_type is valid
        if detected_type and detected_type in self.llm_helper.TYPES:
            must.append(FieldCondition(key=field_key, match=MatchValue(value=detected_type)))
        # Add subject filter
        if detected_subject:
            subject_field = "ma_mon_hoc" if is_student_query else "subject_code"
            should.append(FieldCondition(key=subject_field, match=MatchValue(value=detected_subject)))
        # Add time range filter for student collection
        if time_range and is_student_query:
            try:
                must.append(FieldCondition(
                    key="ngay",
                    range=Range(
                        gte=time_range["start_date"].strftime("%d/%m/%Y"),
                        lte=time_range["end_date"].strftime("%d/%m/%Y")
                    )
                ))
            except Exception as e:
                logger.warning(f"⚠️ Failed to apply time range filter: {e}")
        # Add semester filter for general collection
        if detected_semester and not is_student_query:
            should.append(FieldCondition(key="semester", match=MatchValue(value=detected_semester)))
        # Add user_id filter for student collection
        if user_id and is_student_query:
            must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        qdrant_filter = Filter(must=must, should=should) if must or should else None
        print('='*50)
        logger.info(f"Querying collection: {collection_name}, Filter: {qdrant_filter}, Detected Type: {detected_type}, Subject: {detected_subject}, Semester: {detected_semester}, Time Range: {time_range}")
        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding.tolist(),
                query_filter=qdrant_filter,
                limit=limit * 2,
                # score_threshold=0
            )
            print(results)
            formatted_results = []
            retrieved_chunks = ''
            for i, hit in enumerate(results):
                payload = hit.payload
                if is_student_query:
                    result = {
                        "rank": i + 1,
                        "score": hit.score,
                        "loai": payload.get("loai", "N/A"),
                        "ma_mon_hoc": payload.get("ma_mon_hoc", "N/A"),
                        "ten_mon_hoc": payload.get("ten_mon_hoc", "N/A"),
                        "content": payload.get("noi_dung", "")[:300] + ("..." if len(payload.get("noi_dung", "")) > 300 else "")
                    }
                else:
                    result = {
                        "rank": i + 1,
                        "score": hit.score,
                        "type": payload.get("type", "N/A"),
                        "subject_code": payload.get("subject_code", "N/A"),
                        "subject_name": payload.get("subject_name", "N/A"),
                        "degree_level": payload.get("degree_level"),
                        "credits": payload.get("credits"),
                        "semester": payload.get("semester"),
                        "belong_to_combo": payload.get("belong_to_combo"),
                        "pre_requisites": payload.get("pre_requisites"),
                        "scoring_scale": payload.get("scoring_scale"),
                        "approved": payload.get("approved"),
                        "subject_link": payload.get("subject_link"),
                        "time_allocation": payload.get("time_allocation"),
                        "description": payload.get("description"),
                        "student_tasks": payload.get("student_tasks"),
                        "tools": payload.get("tools"),
                        "note": payload.get("note"),
                        "content": payload.get("content", "")[:] + ("..." if len(payload.get("content", "")) > 300 else "")
                    }
                formatted_results.append(result)
                retrieved_chunks += payload.get("noi_dung", payload.get("content", "")) + '\n'
            if self.enable_llm and self.llm_helper and formatted_results:
                formatted_results = self.llm_helper.re_rank_results(query, formatted_results, limit)
            elif self.enable_llm and self.llm_helper and not formatted_results:
                detected_subject = self.detect_subject_from_query(query, threshold)
                if detected_subject and detected_subject in self.static_subjects:
                    return [{"content": f"Thông tin về môn {detected_subject} - {self.static_subjects[detected_subject]}. Hiện chưa có dữ liệu điểm cụ thể."}], "No specific data found.", retrieved_chunks
                return [], self.llm_helper.synthesize_answer(query, [], retrieved_chunks), retrieved_chunks
            summary = self.llm_helper.synthesize_answer(query, formatted_results, retrieved_chunks) if self.llm_helper else "No summary available."
            return formatted_results[:limit], summary, retrieved_chunks
        except Exception as e:
            logger.error(f"❌ Search error in collection {collection_name}: {e}")
            if self.enable_llm and self.llm_helper:
                return [], self.llm_helper.synthesize_answer(query, [], ""), ""
            return [], "Search failed due to an internal error.", ""

    def run_full_embedding_pipeline_from_db(self, user_id, df_profile, df_attendance, df_grades, df_courses):
        user_full_name = str(df_profile.iloc[0].get('full_name', '')) if not df_profile.empty else ""
        all_payloads = []
        if not df_profile.empty:
            all_payloads.extend(self.chunk_student_profile(df_profile, user_full_name))
        if not df_attendance.empty:
            all_payloads.extend(self.chunk_attendance_reports(df_attendance, user_full_name))
        if not df_grades.empty:
            all_payloads.extend(self.chunk_grade_details(df_grades, user_full_name))
        if not df_courses.empty:
            all_payloads.extend(self.chunk_course_summaries(df_courses, user_full_name))
        existing_hashes = self.get_existing_hashes(user_id, self.collection_name_student)
        new_payloads = [p for p in all_payloads if p['content_hash'] not in existing_hashes]
        if not new_payloads:
            logger.info("No new data to embed.")
            return 0
        embeddings = self.generate_content_embedding(new_payloads)
        points = self.merge_point_structs(new_payloads, embeddings)
        self.safe_upsert_to_qdrant(points, user_id=user_id, collection_name=self.collection_name_student)
        self.create_payload_index(self.collection_name_student)
        return len(new_payloads)

# --- FapScraper Class ---
class FapScraper:
    BASE_URL = "https://fap.fpt.edu.vn"
    PROFILE_URL = f"{BASE_URL}/User/Profile.aspx"
    ATTENDANCE_URL = f"{BASE_URL}/Report/ViewAttendstudent.aspx"
    GRADE_URL = f"{BASE_URL}/Grade/StudentGrade.aspx"

    def __init__(self, gmail=None, password=None, timeout=200):
        self.gmail = gmail
        self.password = password
        self.timeout = timeout
        self.driver = None
        self.wait = None
        self.student_data = {}

    def get_term_from_date(self, dt):
        year = dt.year
        month = dt.month
        if month in [1, 2, 3]:
            return f"Spring{year}"
        elif month in [4, 5, 6]:
            return f"Summer{year}"
        elif month in [7, 8, 9]:
            return f"Fall{year}"
        elif month in [10, 11, 12]:
            return f"Winter{year}"

    def setup_driver(self):
        options = Options()
        service = Service(ChromeDriverManager().install())
        self.driver = uc.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, self.timeout)
        return self.driver

    def interact_safely(self, by, value, action='click', text=None, clear=True, press_enter=False, timeout=None, description=''):
        try:
            wait_time = timeout if timeout else self.timeout
            wait = WebDriverWait(self.driver, wait_time)
            if action == 'click':
                element = wait.until(EC.element_to_be_clickable((by, value)))
            elif action == 'input':
                element = wait.until(EC.visibility_of_element_located((by, value)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            if action == 'click':
                element.click()
            elif action == 'input':
                element.click()
                if clear:
                    element.clear()
                element.send_keys(text)
                if press_enter:
                    element.send_keys(Keys.RETURN)
            return True
        except Exception as e:
            logger.error(f"❌ Error during {action} {description or value}: {e}")
            return False

    def bypass_cloudflare_check(self, timeout=60):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if "Just a moment..." not in self.driver.page_source:
                logger.info("✅ Bypassed Cloudflare")
                return True
            time.sleep(1)
        logger.error("❌ Failed to bypass Cloudflare")
        return False

    def login(self):
        self.driver.get(self.BASE_URL)
        time.sleep(13)
        if not self.bypass_cloudflare_check():
            return False
        if not self.interact_safely(By.ID, "ctl00_mainContent_btnloginFeId", description="Login button"):
            return False
        if not self.interact_safely(By.XPATH, "//a[contains(@class, 'btn-outline-primary') and contains(., 'Email fpt.edu.vn')]", description="Gmail button"):
            return False
        if not self.interact_safely(By.ID, "identifierId", action='input', text=self.gmail, press_enter=True, description="Enter Gmail"):
            return False
        if not self.interact_safely(By.NAME, "Passwd", action='input', text=self.password, press_enter=True, description="Enter password"):
            return False
        logger.info("✅ Logged in successfully")
        return True

    def scrape_profile(self):
        try:
            self.interact_safely(By.XPATH, '//a[@href="User/Profile.aspx"]', description="Profile button")
            self.student_data = {
                "full_name": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblFullname"]').text,
                "date_of_birth": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblDateOfBirth"]').text,
                "gender": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblGender"]').text,
                "id_card_number": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblIDCard"]').text,
                "home_address": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblAddress"]').text,
                "phone_number": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblPhoneNumber"]').text,
                "email_address": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblEmail"]').text,
                "roll_number": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblRollNumber"]').text,
                "old_roll_number": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblOldRoll"]').text,
                "member_code": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblMemberCode"]').text,
                "enrollment_date": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblEnrolDate"]').text,
                "study_mode": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblMode"]').text,
                "current_status": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblStatus"]').text,
                "current_term_number": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblTermNo"]').text,
                "major": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblMajor"]').text,
                "curriculum": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblSpecialIn"]').text,
                "capstone_project": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblCapstoneProject"]').text,
                "main_class": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblMainClass"]').text,
                "specialization": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblChuyennganh"]').text,
                "account_balance": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblAccBlance"]').text,
                "previous_major": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblOldMajor"]').text,
                "decision_graduate_check": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblQDCN"]').text,
                "is_full_time_student": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblSVCQ"]').text,
                "full_time_confirmed_date": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblDateSVCQ"]').text,
                "is_scholarship_student": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblSVDB"]').text,
                "valid_study_period": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblHan7nam"]').text,
                "training_type": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblLoaiTC"]').text,
                "decision_dropout": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblQDTH"]').text,
                "decision_transfer_campus": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblQDTranfer"]').text,
                "decision_academic_leave": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblBaoluu"]').text,
                "decision_graduation": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblQDTN"]').text,
                "decision_rejoin": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblRejoin"]').text,
                "destination_after_study": self.driver.find_element(By.XPATH, '//*[@id="ctl00_mainContent_lblTTDen"]').text
            }
            dt_svcq = datetime.strptime(self.student_data["full_time_confirmed_date"], "%m/%d/%Y %I:%M:%S %p") - relativedelta(months=4)
            self.student_data["start_term"] = self.get_term_from_date(dt_svcq)
            logger.info(f"✅ Scraped profile for {self.student_data['roll_number']}")
            return True
        except Exception as e:
            logger.error(f"❌ Error scraping profile: {e}")
            return False

    def parse_attendance_info_from_html_table(self, html_table, term_name, course_name, course_code):
        attendance_records = []
        soup = BeautifulSoup(html_table, 'html.parser')
        tbody = soup.find_all('tbody')[1]
        rows = tbody.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            attendance_records.append({
                'student_id': self.student_data['roll_number'],
                'term': term_name,
                'course_name': course_name,
                'course_code': course_code,
                'no': cols[0].text.strip(),
                'date': cols[1].text.strip(),
                'slot': cols[2].text.strip(),
                'room': cols[3].text.strip(),
                'lecturer': cols[4].text.strip(),
                'group': cols[5].text.strip(),
                'status': cols[6].text.strip(),
                'comment': cols[7].text.strip()
            })
        return attendance_records

    def parse_grade_info_from_html_table(self, html_table, term_name, course_name, course_code):
        mark_details = []
        course_summaries = []
        try:
            soup = BeautifulSoup(html_table.get_attribute('outerHTML'), 'html.parser')
            tbody = soup.find('tbody')
            if not tbody:
                logger.error(f"❌ No tbody found for course {course_code}")
                return [], []
            rows = tbody.find_all('tr')
            if not rows:
                logger.error(f"❌ No rows in tbody for course {course_code}")
                return [], []
            tfoot = soup.find('tfoot')
            if not tfoot:
                logger.error(f"❌ No tfoot found for course {course_code}")
                return [], []
            trs_tfoot = tfoot.find_all('tr')
            if not trs_tfoot:
                logger.error(f"❌ No rows in tfoot for course {course_code}")
                return [], []
            tds = trs_tfoot[0].find_all('td')
            if len(tds) < 3:
                logger.error(f"❌ Not enough columns in tfoot for course {course_code}")
                return [], []
            avg_score = tds[2].text.strip()
            status = tfoot.find('font').text.strip() if tfoot.find('font') else "Unknown"
            current_category = None
            summary_weights = {}
            for row in rows:
                cols = row.find_all('td')
                if not cols:
                    continue
                if cols[0].has_attr('rowspan'):
                    current_category = cols[0].text.strip()
                    grade_item = cols[1].text.strip()
                    weight = cols[2].text.strip()
                    value = cols[3].text.strip()
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
                    total_weight = cols[1].text.strip()
                    total_value = cols[2].text.strip()
                    summary_weights[current_category] = {
                        "weight": total_weight if total_weight else None,
                        "value": total_value if total_value else None
                    }
                else:
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
            course_summaries.append({
                "term": term_name,
                "course_name": course_name,
                "course_code": course_code,
                "avg_score": avg_score,
                "status": status,
                "summary": json.dumps(summary_weights)
            })
            logger.info(f"✅ Parsed {len(mark_details)} details and 1 summary for course {course_code}")
            return course_summaries, mark_details
        except Exception as e:
            logger.error(f"❌ Error parsing grade info for course {course_code}: {e}")
            return [], []

    def scrape_attendance(self):
        attendance_data = []
        try:
            self.interact_safely(By.XPATH, '//a[@href="Report/ViewAttendstudent.aspx"]', description="Attendance button")
            terms_div = self.driver.find_element(By.ID, "ctl00_mainContent_divTerm")
            term_tags = terms_div.find_elements(By.CSS_SELECTOR, "tbody tr td a")
            term_list = [term.text.strip() for term in term_tags]
            start_term_index = term_list.index(self.student_data['start_term'])
            
            for i in range(start_term_index, len(term_tags)):
                try:
                    # Refresh terms_div và term_links để tránh stale element
                    terms_div = self.driver.find_element(By.ID, "ctl00_mainContent_divTerm")
                    term_links = terms_div.find_elements(By.CSS_SELECTOR, "a")
                    
                    # Kiểm tra index hợp lệ
                    if i >= len(term_links):
                        logger.warning(f"⚠️ Index {i} vượt quá số lượng term links ({len(term_links)})")
                        continue
                    
                    term = self.wait.until(EC.element_to_be_clickable(term_links[i]))
                    term_name = term.text.strip()
                    term.click()
                    
                    # Đợi course_div load
                    time.sleep(2)
                    course_div = self.driver.find_element(By.ID, "ctl00_mainContent_divCourse")
                    course_tags = course_div.find_elements(By.CSS_SELECTOR, "a")
                    available_course = course_div.find_elements(By.CSS_SELECTOR, "b")
                    
                    # Lưu danh sách course trước khi lặp
                    course_list = []
                    
                    # Xử lý available course (nếu có)
                    if available_course:
                        try:
                            course_name_and_code = available_course[0].text.strip()
                            if course_name_and_code:
                                course_name = course_name_and_code.split('(')[0].strip()
                                course_code_match = re.search(r"\((.*?)\)", course_name_and_code)
                                if course_code_match:
                                    course_code = course_code_match.group(1)
                                    course_list.append({
                                        'name': course_name,
                                        'code': course_code,
                                        'is_available': True
                                    })
                        except Exception as e:
                            logger.warning(f"⚠️ Error parsing available course: {e}")
                    
                    # Xử lý các course khác
                    for course_tag in course_tags:
                        try:
                            course_name_and_code = course_tag.text.strip()
                            if course_name_and_code:
                                course_name = course_name_and_code.split('(')[0].strip()
                                course_code_match = re.search(r"\((.*?)\)", course_name_and_code)
                                if course_code_match:
                                    course_code = course_code_match.group(1)
                                    # Kiểm tra xem course đã có trong list chưa
                                    if not any(c['code'] == course_code for c in course_list):
                                        course_list.append({
                                            'name': course_name,
                                            'code': course_code,
                                            'is_available': False
                                        })
                        except Exception as e:
                            logger.warning(f"⚠️ Error parsing course tag: {e}")
                            continue
                    
                    logger.info(f"📚 Tìm thấy {len(course_list)} môn học trong kỳ {term_name}")
                    
                    # Lặp qua danh sách course đã lưu
                    for j, course_info in enumerate(course_list):
                        try:
                            course_name = course_info['name']
                            course_code = course_info['code']
                            is_available = course_info['is_available']
                            
                            logger.info(f"🔍 Đang xử lý môn {j+1}/{len(course_list)}: {course_code} - {course_name}")
                            
                            # Nếu là available course, không cần click
                            if not is_available:
                                # Refresh course_div và tìm course element mới
                                course_div = self.driver.find_element(By.ID, "ctl00_mainContent_divCourse")
                                course_tags = course_div.find_elements(By.CSS_SELECTOR, "a")
                                
                                # Tìm course element tương ứng
                                course_element = None
                                for course_tag in course_tags:
                                    if course_code in course_tag.text:
                                        course_element = course_tag
                                        break
                                
                                if not course_element:
                                    logger.warning(f"⚠️ Không tìm thấy course element cho {course_code}")
                                    continue
                                
                                # Click vào course
                                course_element.click()
                                time.sleep(2)
                            
                            # Lấy table attendance
                            table = self.driver.find_element(By.XPATH, f"//table[contains(@class, 'table table-bordered table1')]")
                            attendance_records = self.parse_attendance_info_from_html_table(table.get_attribute('outerHTML'), term_name, course_name, course_code)
                            attendance_data.extend(attendance_records)
                            logger.info(f"✅ Đã xử lý {len(attendance_records)} attendance records cho môn {course_code}")
                            
                        except Exception as e:
                            logger.error(f"❌ Lỗi xử lý course {course_code}: {e}")
                            continue
                except Exception as e:
                    logger.error(f"❌ Lỗi xử lý term {i}: {e}")
                    continue
                    
            logger.info(f"✅ Scraped {len(attendance_data)} attendance records")
            return attendance_data
        except Exception as e:
            logger.error(f"❌ Error scraping attendance: {e}")
            return None

    def scrape_grades(self):
        course_summaries = []
        mark_details = []
        try:
            self.interact_safely(By.XPATH, '//a[@href="Grade/StudentGrade.aspx"]', description="Grades button")
            terms_div = self.driver.find_element(By.ID, "ctl00_mainContent_divTerm")
            term_tags = terms_div.find_elements(By.CSS_SELECTOR, "tbody tr td a, tbody tr td b")
            
            for i in range(len(term_tags)):
                try:
                    # Refresh terms_div và term_links để tránh stale element
                    terms_div = self.driver.find_element(By.ID, "ctl00_mainContent_divTerm")
                    term_links = terms_div.find_elements(By.CSS_SELECTOR, "a, b")
                    
                    # Kiểm tra index hợp lệ
                    if i >= len(term_links):
                        logger.warning(f"⚠️ Index {i} vượt quá số lượng term links ({len(term_links)})")
                        continue
                    
                    term = self.wait.until(EC.element_to_be_clickable(term_links[i]))
                    term_name = term.text.strip()
                    term.click()
                    
                    # Đợi course_div load
                    time.sleep(2)
                    course_div = self.driver.find_element(By.ID, "ctl00_mainContent_divCourse")
                    course_tags = course_div.find_elements(By.CSS_SELECTOR, "a")
                    
                    # Lưu danh sách course trước khi lặp để tránh stale element
                    course_list = []
                    for course_tag in course_tags:
                        try:
                            course_name_and_code = course_tag.text.strip()
                            if course_name_and_code:
                                course_name = course_name_and_code.split('(')[0].strip()
                                course_code_match = re.search(r"\((.*?)\)", course_name_and_code)
                                if course_code_match:
                                    course_code = course_code_match.group(1)
                                    course_list.append({
                                        'name': course_name,
                                        'code': course_code
                                    })
                        except Exception as e:
                            logger.warning(f"⚠️ Error parsing course tag: {e}")
                            continue
                    
                    logger.info(f"📚 Tìm thấy {len(course_list)} môn học trong kỳ {term_name}")
                    
                    # Lặp qua danh sách course đã lưu
                    for j, course_info in enumerate(course_list):
                        try:
                            course_name = course_info['name']
                            course_code = course_info['code']
                            
                            logger.info(f"🔍 Đang xử lý môn {j+1}/{len(course_list)}: {course_code} - {course_name}")
                            
                            # Refresh course_div và tìm course element mới
                            course_div = self.driver.find_element(By.ID, "ctl00_mainContent_divCourse")
                            course_tags = course_div.find_elements(By.CSS_SELECTOR, "a")
                            
                            # Tìm course element tương ứng
                            course_element = None
                            for course_tag in course_tags:
                                if course_code in course_tag.text:
                                    course_element = course_tag
                                    break
                            
                            if not course_element:
                                logger.warning(f"⚠️ Không tìm thấy course element cho {course_code}")
                                continue
                            
                            # Click vào course
                            course_element.click()
                            time.sleep(2)  # Tăng thời gian chờ
                            
                            grade_div = self.driver.find_element(By.ID, "ctl00_mainContent_divGrade")
                            
                            # Debug: Kiểm tra số lượng bảng trong grade_div
                            tables = grade_div.find_elements(By.TAG_NAME, "table")
                            logger.info(f"🔍 Có {len(tables)} bảng table trong grade_div cho môn {course_code}")
                            
                            if grade_div.find_elements(By.CSS_SELECTOR, "table.table.table-bordered"):
                                logger.info(f"📊 Xử lý môn Coursera: {course_code}")
                                try:
                                    coursera_table = grade_div.find_element(By.CSS_SELECTOR, "table.table.table-bordered")
                                    sum_table = grade_div.find_element(By.XPATH, ".//table[@summary='Report']")
                                    sum_table_soup = BeautifulSoup(sum_table.get_attribute('outerHTML'), 'html.parser')
                                    coursera_table_soup = BeautifulSoup(coursera_table.get_attribute('outerHTML'), 'html.parser')
                                    
                                    tfoot = sum_table_soup.find('tfoot')
                                    if not tfoot:
                                        logger.error(f"❌ No tfoot found in sum_table for course {course_code}")
                                        continue
                                    
                                    trs_tfoot = tfoot.find_all('tr')
                                    if not trs_tfoot:
                                        logger.error(f"❌ No rows in tfoot for course {course_code}")
                                        continue
                                    
                                    tds = trs_tfoot[0].find_all('td')
                                    if len(tds) < 3:
                                        logger.error(f"❌ Not enough columns in tfoot for course {course_code}")
                                        continue
                                    
                                    avg_score = tds[2].text.strip()
                                    font_tag = tfoot.find('font')
                                    status = font_tag.text.strip() if font_tag else "Unknown"
                                    
                                    tbody = coursera_table_soup.find('tbody')
                                    if not tbody:
                                        logger.error(f"❌ No tbody in coursera table for course {course_code}")
                                        continue
                                    
                                    rows = tbody.find_all('tr')
                                    if len(rows) < 2:
                                        logger.error(f"❌ Not enough rows in coursera table for course {course_code}")
                                        continue
                                    
                                    cols = rows[1].find_all('td')
                                    theory_exam_val = cols[0].text.strip() if cols[0].text.strip() else None
                                    practise_exam_val = cols[1].text.strip() if len(cols) > 1 and cols[1].text.strip() else None
                                    bonus = cols[2].text.strip() if len(cols) > 2 and cols[2].text.strip() else None
                                    
                                    summary_value = {
                                        "theory_exam": theory_exam_val,
                                        "practise_exam": practise_exam_val,
                                        "bonus": bonus
                                    }
                                    
                                    course_summaries.append({
                                        "term": term_name,
                                        "course_name": course_name,
                                        "course_code": course_code,
                                        "avg_score": avg_score,
                                        "status": status,
                                        "summary": json.dumps(summary_value)
                                    })
                                    logger.info(f"✅ Đã xử lý môn Coursera {course_code}: {avg_score}")
                                except Exception as e:
                                    logger.error(f"❌ Lỗi xử lý môn Coursera {course_code}: {e}")
                                    continue
                            else:
                                logger.info(f"📊 Xử lý môn thường: {course_code}")
                                try:
                                    table = self.driver.find_element(By.XPATH, "//table[@summary='Report']")
                                    summaries, details = self.parse_grade_info_from_html_table(table, term_name, course_name, course_code)
                                    if summaries:
                                        course_summaries.extend(summaries)
                                        logger.info(f"✅ Đã xử lý {len(summaries)} summary cho môn {course_code}")
                                    if details:
                                        mark_details.extend(details)
                                        logger.info(f"✅ Đã xử lý {len(details)} detail cho môn {course_code}")
                                except Exception as e:
                                    logger.error(f"❌ Lỗi xử lý môn thường {course_code}: {e}")
                                    continue
                        except Exception as e:
                            logger.error(f"❌ Lỗi xử lý course {course_code}: {e}")
                            continue
                except Exception as e:
                    logger.error(f"❌ Lỗi xử lý term {i}: {e}")
                    continue
                    
            logger.info(f"✅ Scraped grades: {len(course_summaries)} summaries, {len(mark_details)} details")
            return course_summaries, mark_details
        except Exception as e:
            logger.error(f"❌ Error scraping grades: {e}")
            return None, None

    def save_to_csv(self, data, filename):
        try:
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"✅ Saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving CSV: {e}")
            return False

    def full_scraping_process(self):
        try:
            self.setup_driver()
            if not self.login():
                return None
            self.interact_safely(By.XPATH, "//a[contains(@href,'Student.aspx')]", description="Home button")
            if not self.scrape_profile():
                return None
            self.interact_safely(By.XPATH, "//a[contains(@href,'Student.aspx')]", description="Home button")
            attendance_data = self.scrape_attendance()
            self.interact_safely(By.XPATH, "//a[contains(@href,'Student.aspx')]", description="Home button")
            course_summaries, grade_details = self.scrape_grades()
            self.driver.quit()
            return {
                'profile': self.student_data,
                'attendance': attendance_data,
                'course_summaries': course_summaries,
                'grade_details': grade_details
            }
        except Exception as e:
            logger.error(f"❌ Error in scraping process: {e}")
            if self.driver:
                self.driver.quit()
            return None

# --- Flask API ---
app = Flask(__name__)
CORS(app)
engine = FapSearchEngine(csv_paths)

# Translation setup
try:
    model_id = "facebook/nllb-200-distilled-600M"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model_trans = AutoModelForSeq2SeqLM.from_pretrained(model_id)
    translator = pipeline(
        "translation",
        model=model_trans,
        tokenizer=tokenizer,
        src_lang="vie",
        tgt_lang="eng_Latn",
        max_length=512
    )
    def translate_vi_to_en_local(text):
        result = translator(text)
        return result[0]['translation_text']
    USE_LOCAL_TRANSLATE = True
except Exception:
    def translate_vi_to_en_local(text):
        return GoogleTranslator(source='auto', target='en').translate(text)
    USE_LOCAL_TRANSLATE = False

# Load model và tokenizer intent classification (chỉnh lại path nếu cần)
intent_model = DistilBertForSequenceClassification.from_pretrained(r"D:\Learn\Semester_5\SEG301\FPT_FAP_CHAT\intent_model2")
intent_tokenizer = DistilBertTokenizerFast.from_pretrained(r"D:\Learn\Semester_5\SEG301\FPT_FAP_CHAT\intent_model2")
intent_model.eval()

@app.route('/')
def index():
    return 'FAP Chat API Server is running.'


@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    data = request.get_json()
    gmail = data.get('gmail')
    password = data.get('password')
    if not gmail or not password:
        return jsonify({'error': 'Missing gmail or password'}), 400
    
    logger.info(f"🔄 Bắt đầu scrape cho user: {gmail}")
    scraper = FapScraper(gmail, password)
    results = scraper.full_scraping_process()
    
    if results:
        user_id = results['profile']['roll_number']
        
        # Log thông tin chi tiết về dữ liệu đã scrape
        logger.info(f"📊 Kết quả scrape cho {user_id}:")
        logger.info(f"  - Profile: {len([results['profile']]) if results['profile'] else 0} records")
        logger.info(f"  - Attendance: {len(results['attendance']) if results['attendance'] else 0} records")
        logger.info(f"  - Grade details: {len(results['grade_details']) if results['grade_details'] else 0} records")
        logger.info(f"  - Course summaries: {len(results['course_summaries']) if results['course_summaries'] else 0} records")
        
        # Save to CSV với error handling
        try:
            scraper.save_to_csv([results['profile']], csv_paths['student_profile'])
            logger.info("✅ Saved student profile")
        except Exception as e:
            logger.error(f"❌ Error saving profile: {e}")
        
        try:
            if results['attendance']:
                scraper.save_to_csv(results['attendance'], csv_paths['attendance_reports'])
                logger.info("✅ Saved attendance reports")
            else:
                logger.warning("⚠️ No attendance data to save")
        except Exception as e:
            logger.error(f"❌ Error saving attendance: {e}")
        
        try:
            if results['grade_details']:
                scraper.save_to_csv(results['grade_details'], csv_paths['grade_details'])
                logger.info("✅ Saved grade details")
            else:
                logger.warning("⚠️ No grade details to save")
        except Exception as e:
            logger.error(f"❌ Error saving grade details: {e}")
        
        try:
            if results['course_summaries']:
                scraper.save_to_csv(results['course_summaries'], csv_paths['course_summaries'])
                logger.info("✅ Saved course summaries")
            else:
                logger.warning("⚠️ No course summaries to save")
        except Exception as e:
            logger.error(f"❌ Error saving course summaries: {e}")
        
        # Reload dataframes và upload to Qdrant
        try:
            engine.load_all_dataframes()
            df_profile = pd.DataFrame([results['profile']]) if results['profile'] else pd.DataFrame()
            df_attendance = pd.DataFrame(results['attendance']) if results['attendance'] else pd.DataFrame()
            df_grades = pd.DataFrame(results['grade_details']) if results['grade_details'] else pd.DataFrame()
            df_courses = pd.DataFrame(results['course_summaries']) if results['course_summaries'] else pd.DataFrame()
            
            uploaded_count = engine.run_full_embedding_pipeline_from_db(user_id, df_profile, df_attendance, df_grades, df_courses)
            logger.info(f"✅ Uploaded {uploaded_count} records to Qdrant")
            
        except Exception as e:
            logger.error(f"❌ Error uploading to Qdrant: {e}")
        
        return jsonify({
            'status': 'success', 
            'message': 'Data scraped and uploaded to Qdrant', 
            'time': datetime.now().strftime('%H:%M %p +07, %d/%m/%Y'),
            'stats': {
                'profile': len([results['profile']]) if results['profile'] else 0,
                'attendance': len(results['attendance']) if results['attendance'] else 0,
                'grade_details': len(results['grade_details']) if results['grade_details'] else 0,
                'course_summaries': len(results['course_summaries']) if results['course_summaries'] else 0
            }
        })
    
    logger.error("❌ Scraping failed")
    return jsonify({'status': 'error', 'message': 'Failed to scrape data'}), 500

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.get_json()
    query = data.get('query')
    user_id = data.get('user_id')
    chat_history = data.get('chat_history', [])
    if not query:
        return jsonify({'error': 'Missing query'}), 400

    # Translate query
    query_en = translate_vi_to_en_local(query)

    # Search Qdrant (Gemini intent + fallback local intent)
    try:
        try:
            # Thử search với Gemini intent
            results, summary, retrieved_chunks = engine.search_qdrant(query, user_id=user_id, limit=5, chat_history=chat_history)
        except Exception as e:
            logger.error(f"❌ Gemini intent search error: {e}")
            # Nếu lỗi (timeout, quota, ...), fallback sang local intent
            logger.warning("⚠️ Fallback sang local intent (DistilBERT)")
            print(f"Query: {query}")
            analyze = engine.analyze_intent(query_vi=query)
            detected_type = analyze.get("type")

            detected_subject = [s[0] for s in analyze.get("subjects", [])]
            detected_semester = analyze.get("semester")
            # Build filter cho FLM (FINAL)
            must = []
            should = []
            if detected_type:
                must.append(FieldCondition(key="type", match=MatchValue(value=detected_type)))
            if detected_subject:
                for subj in detected_subject:
                    should.append(FieldCondition(key="subject_code", match=MatchValue(value=subj)))
            if detected_semester:
                should.append(FieldCondition(key="semester", match=MatchValue(value=detected_semester)))
            qdrant_filter = Filter(must=must, should=should) if must or should else None
            query_embedding = engine.embedder.embed([query])[0]
            results = engine.client.search(
                collection_name=engine.collection_name_general,
                query_vector=query_embedding.tolist(),
                query_filter=qdrant_filter,
                limit=10,
                score_threshold=0
            )
            formatted_results = []
            for i, hit in enumerate(results):
                payload = hit.payload
                formatted_results.append({
                    "rank": i + 1,
                    "type": payload.get("type", "N/A"),
                    "subject_code": payload.get("subject_code", "N/A"),
                    "subject_name": payload.get("subject_name", "N/A"),
                    "content": payload.get("content", "")[:300] + ("..." if len(payload.get("content", "")) > 300 else "")
                })
            summary = f"Không thể tổng hợp kết quả tự động. Vui lòng xem chi tiết bên dưới hoặc thử lại truy vấn khác." if not formatted_results else ""
            results = formatted_results
            retrieved_chunks = "\n".join([r["content"] for r in formatted_results])


        # Nếu summary là lỗi hoặc rỗng, luôn trả về raw_results
        response = {
            'query_translated': query_en,
            'results': results,
            'summary': summary,
            'time': datetime.now().strftime('%H:%M %p +07, %d/%m/%Y')
        }
        if not summary or 'LLM' in summary or 'Không thể tổng hợp' in summary or 'quota' in summary.lower():
            response['raw_results'] = results
        return jsonify(response)
    except Exception as e:
        logger.error(f"❌ /api/search error: {e}")
        return jsonify({
            'query_translated': query_en,
            'results': [],
            'summary': 'Đã xảy ra lỗi hệ thống.',
            'raw_results': [],
            'time': datetime.now().strftime('%H:%M %p +07, %d/%m/%Y')
        }), 500

@app.route('/api/general', methods=['POST'])
def api_general():
    data = request.get_json()
    query = data.get('query')
    if not query:
        return jsonify({'error': 'Missing query'}), 400
    summary = engine.llm_helper.synthesize_answer(query, []) if engine.llm_helper else "Không có thông tin cụ thể."
    return jsonify({
        'summary': summary,
        'time': datetime.now().strftime('%H:%M %p +07, %d/%m/%Y')
    })

if __name__ == '__main__':
    logger.info(f"Current working directory: {os.getcwd()}")
    for key, path in csv_paths.items():
        logger.info(f"Checking {key}: {os.path.exists(path)} - {path}")
    app.run(host="0.0.0.0", port=5000, debug=True)
