# fap_search_engine.py
import pandas as pd
import numpy as np
import uuid
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue, Range
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
def content_hash(content: str) -> str:
    import hashlib
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
from FAP.llm_helper import LLMHelper
from dotenv import load_dotenv

class FapSearchEngine:
    def __init__(self, csv_paths: dict, qdrant_url: str = None, qdrant_api_key: str = None, collection_name: str = None, enable_llm: bool = False):
        """
        Khởi tạo client, load CSV, khởi tạo embedder + config + LLM
        """
        load_dotenv()
        # Qdrant config
        self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL")
        self.qdrant_api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY")
        self.collection_name = collection_name or os.environ.get("QDRANT_COLLECTION", "Fap_data_testing")
        print(self.qdrant_url, self.qdrant_api_key, self.collection_name)
        # Khởi tạo Qdrant client
        self.client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key,
            prefer_grpc=False
        )
        # Tự động tạo collection nếu chưa có
        try:
            self.client.get_collection(self.collection_name)
            print(f"✅ Collection {self.collection_name} already exists.")
        except Exception:
            print(f"⚠️ Collection {self.collection_name} not found. Creating...")
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
            )
            print(f"✅ Created collection {self.collection_name}.")
        
        # CSV paths
        self.csv_paths = csv_paths
        
        # DataFrames storage
        self.dataframes = {}
        
        # Khởi tạo BGE-M3 embedder
        self.embedder = SentenceTransformer("BAAI/bge-m3")
        self.prefix = "Represent this sentence for searching relevant passages: "
        
        # Embedding caches cho detection
        self.subject_embeddings = {}
        self.type_embeddings = {}
        self.term_embeddings = {}
        
        # LLM Helper
        self.enable_llm = enable_llm
        self.llm_helper = LLMHelper() if enable_llm else None
        if enable_llm and self.llm_helper.is_available():
            print(f"✅ LLM enabled with {self.llm_helper.model}")
        else:
            print("⚠️ LLM disabled or not available")
        
        print(f"✅ Fap Search Engine initialized with collection: {self.collection_name}")
    
    def _normalize_date_format(self, date_str: str) -> str:
        """
        Chuyển đổi format ngày từ "Monday 09/09/2024" thành "09/09/2024"
        """
        if not date_str or date_str == "Không rõ":
            return "Không rõ"
        
        # Tìm pattern ngày tháng trong chuỗi
        import re
        date_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
        match = re.search(date_pattern, date_str)
        
        if match:
            day, month, year = match.groups()
            return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        
        return date_str
    
    def load_all_dataframes(self):
        """
        Đọc toàn bộ dữ liệu CSV vào các DataFrame:
        - student_profile
        - attendance_reports
        - grade_details
        - course_summaries
        """
        expected_keys = ['student_profile', 'attendance_reports', 'grade_details', 'course_summaries']
        
        for key in expected_keys:
            if key in self.csv_paths:
                path = self.csv_paths[key]
                if os.path.exists(path):
                    self.dataframes[key] = pd.read_csv(path)
                    print(f"✅ Loaded {key}: {len(self.dataframes[key])} rows")
                else:
                    print(f"❌ File not found: {path}")
            else:
                print(f"⚠️  Missing key in csv_paths: {key}")
        
        print(f"📊 Total DataFrames loaded: {len(self.dataframes)}")
    
    def chunk_student_profile(self, df, user_full_name=None):
        """
        Build payloads cho bảng student_profile
        → output: list[dict]
        """
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
                "ho_ten": full_name,
                "ngay_sinh": safe(row["date_of_birth"]),
                "gioi_tinh": safe(row["gender"]),
                "so_cmnd": safe(row["id_card_number"]),
                "ngay_cap_cmnd": safe(row["id_date_of_issue"]),
                "noi_cap_cmnd": safe(row["id_place_of_issue"]),
                "dia_chi": safe(row["home_address"]),
                "sdt": safe(row["phone_number"]),
                "email": safe(row["email_address"]),
                "ma_sinh_vien": safe(row["roll_number"]),
                "ma_cu": safe(row["old_roll_number"]),
                "ma_thanh_vien": safe(row["member_code"]),
                "ngay_nhap_hoc": safe(row["enrollment_date"]),
                "chuyen_nganh": safe(row["major"]),
                "lop_chinh": safe(row["main_class"]),
                "trang_thai_hoc_tap": safe(row["current_status"]),
                "sinh_vien_chinh_quy": bool(row["is_full_time_student"]),
                "sinh_vien_hoc_bong": bool(row["is_scholarship_student"]),
                "loai_dao_tao": safe(row["training_type"]),
                "hoc_ky_bat_dau": safe(row["start_term"]),
                "loai": "thông tin sinh viên",
                "noi_dung": noi_dung,
                "content_hash": content_hash(noi_dung)
            }
            payloads.append(payload)
        return payloads
    def chunk_attendance_reports(self, df, user_full_name=None):
        """
        Build payloads cho bảng attendance_reports
        """
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
                "ma_sinh_vien": safe(row["student_id"]),
                "hoc_ky": safe(row["term"]),
                "ten_mon_hoc": safe(row["course_name"]),
                "ma_mon_hoc": safe(row["course_code"]),
                "buoi_so": int(row["no"]) if pd.notnull(row["no"]) else -1,
                "ngay": self._normalize_date_format(safe(row["date"])),
                "ca_hoc": safe(row["slot"]),
                "phong": safe(row["room"]),
                "giang_vien": safe(row["lecturer"]),
                "nhom_lop": safe(row["group"]),
                "trang_thai": safe(row["status"]),
                "ghi_chu": safe(row["comment"]),
                "loai": "điểm danh",
                "noi_dung": noi_dung,
                "content_hash": content_hash(noi_dung)
            }
            payloads.append(payload)
        print(f"📝 Generated {len(payloads)} attendance report payloads")
        return payloads
    
    def chunk_grade_details(self, df, user_full_name=None):
        """
        Build payloads cho bảng grade_details
        """
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
                "ma_sinh_vien": safe(row["student_id"]),
                "hoc_ky": safe(row["term"]),
                "ten_mon_hoc": safe(row["course_name"]),
                "ma_mon_hoc": safe(row["course_code"]),
                "phan_loai": safe(row["category"]),
                "muc_danh_gia": safe(row["item"]),
                "trong_so": safe(row["weight"]),
                "gia_tri_diem": row["value"] if pd.notnull(row["value"]) else -1.0,
                "loai": "chi tiết điểm",
                "noi_dung": noi_dung,
                "content_hash": content_hash(noi_dung)
            }
            payloads.append(payload)
        
        print(f"📝 Generated {len(payloads)} grade detail payloads")
        return payloads
    
    def chunk_course_summaries(self, df, user_full_name=None):
        """
        Build payloads cho bảng course_summaries
        """
        def safe(x):
            return str(x).strip() if pd.notnull(x) else "Không rõ"
        payloads = []
        
        for _, row in df.iterrows():
            full_name = user_full_name or ""
            noi_dung = (
                f"LOẠI: tổng kết môn học\n"
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
                "diem_trung_binh": float(row["avg_score"]) if pd.notnull(row["avg_score"]) else -1.0,
                "trang_thai": safe(row["status"]),
                "tom_tat": safe(row["summary"]),
                "loai": "tổng kết môn học",
                "noi_dung": noi_dung,
                "content_hash": content_hash(noi_dung)
            }
            payloads.append(payload)
        
        print(f"📝 Generated {len(payloads)} course summary payloads")
        return payloads
    
    def generate_content_embedding(self, payloads: list[dict]):
        """
        Nhúng field 'noi_dung' của payloads bằng BGE-M3
        """
        # Lấy các nội dung cần embedding
        contents = []
        for payload in payloads:
            if "noi_dung" in payload:
                content = payload["noi_dung"]
                # Thêm prefix cho BGE-M3
                if not content.startswith(self.prefix):
                    content = self.prefix + content
                contents.append(content)
            else:
                contents.append(self.prefix + "")
        
        print(f"🔄 Embedding {len(contents)} contents with BGE-M3...")
        
        # Tạo embeddings
        embeddings = self.embedder.encode(
            contents, 
            batch_size=64, 
            normalize_embeddings=True,
            show_progress_bar=True
        )
        
        print(f"✅ Generated {len(embeddings)} embeddings, shape: {embeddings.shape}")
        return embeddings
    
    def merge_point_structs(self, payloads, embeddings):
        """
        Tạo list PointStruct từ embedding + payloads
        """
        points = []
        
        for i, (payload, embedding) in enumerate(zip(payloads, embeddings)):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist(),
                payload=payload
            )
            points.append(point)
        
        print(f"📦 Created {len(points)} PointStruct objects")
        return points
    
    def get_existing_hashes(self):
        """
        Lấy tất cả content_hash đã có trong collection Qdrant.
        """
        existing_hashes = set()
        try:
            scroll = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=None,
                limit=10000,  # Tùy chỉnh nếu dữ liệu lớn
                with_payload=["content_hash"]
            )
            for point in scroll[0]:
                h = point.payload.get("content_hash")
                if h:
                    existing_hashes.add(h)
        except Exception as e:
            print(f"❌ Error getting existing hashes: {e}")
        return existing_hashes

    def safe_upsert_to_qdrant(self, points: list, batch_size: int = 100, user_id: str = None):
        """
        Upsert theo batch an toàn với kiểm tra duplicate content_hash
        Hỗ trợ kiểm tra trùng lặp theo user nếu user_id được cung cấp
        """
        total_points = len(points)
        success_count = 0
        print(f"📤 Upserting {total_points} points in batches of {batch_size} (with duplicate check)...")
        
        # Lấy existing hashes
        if user_id:
            existing_hashes = self.get_existing_hashes_for_user(user_id)
            print(f"🔒 User-specific duplicate check for user: {user_id}")
        else:
            existing_hashes = self.get_existing_hashes()
            print("⚠️  Global duplicate check (no user_id provided)")
        
        filtered_points = []
        for point in points:
            h = point.payload.get("content_hash")
            if h not in existing_hashes:
                filtered_points.append(point)
                existing_hashes.add(h)
            # Nếu muốn update khi nội dung khác, có thể thêm logic ở đây
        
        print(f"➡️  {len(filtered_points)}/{total_points} points to upsert (unique by content_hash)")
        
        for i in range(0, len(filtered_points), batch_size):
            batch = filtered_points[i:i + batch_size]
            retry_count = 0
            max_retries = 3
            while retry_count < max_retries:
                try:
                    self.client.upsert(
                        collection_name=self.collection_name,
                        points=batch
                    )
                    success_count += len(batch)
                    print(f"✅ Batch {i//batch_size + 1}: {len(batch)} points uploaded")
                    break
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"⚠️  Retry {retry_count}/3 for batch {i//batch_size + 1}: {e}")
                        time.sleep(2 ** retry_count)
                    else:
                        print(f"❌ Failed batch {i//batch_size + 1} after {max_retries} retries: {e}")
        
        print(f"🎯 Successfully uploaded {success_count}/{total_points} points (unique)")
        return success_count
    
    def create_payload_index(self):
        """
        Tạo các index filter cho các field:
        - user_id (bảo mật)
        - loai
        - hoc_ky
        - ma_mon_hoc
        """
        index_fields = [
            ("user_id", "keyword"),  # 🔒 Bảo mật: index cho user_id
            ("loai", "keyword"),
            ("hoc_ky", "keyword"), 
            ("ma_mon_hoc", "keyword"),
            ("ngay", "keyword"),  # ⏰ Time range filtering
        ]
        
        for field_name, field_schema in index_fields:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_schema
                )
                print(f"✅ Created index for field: {field_name}")
            except Exception as e:
                print(f"⚠️  Index creation failed for {field_name}: {e}")
    
    def create_subject_embeddings(self):
        """
        Tạo embedding cho từng môn học từ course_code + course_name
        """
        if 'course_summaries' not in self.dataframes:
            print("⚠️  No course_summaries data available")
            return
        
        df = self.dataframes['course_summaries']
        subjects_texts = []
        subjects_code = []

        
        for _, row in df.iterrows():
            course_code = row.get('course_code', '')
            course_name = row.get('course_name', '')
            subject_text = f"{course_code} - {course_name}".strip()
            if subject_text and subject_text not in subjects_texts:
                subjects_texts.append(subject_text)
            if course_code and course_code not in subjects_code:
                subjects_code.append(course_code)
        
        if subjects_texts:
            # Tạo embedding cho các môn học
            embeddings = self.generate_content_embedding(subjects_texts)
            
            for subject_code, embedding in zip(subjects_code, embeddings):
                self.subject_embeddings[subject_code] = embedding
            
            print(f"📚 Created embeddings for {len(subjects_code)} subjects")
    
    def create_type_embeddings(self):
        """
        Tạo embedding cho từng loại dữ liệu: điểm danh, chi tiết điểm,...
        """
        type_descriptions = {
            "tổng kết môn học": "Tóm tắt và đánh giá tổng quan về một môn học, bao gồm điểm trung bình, trạng thái và điểm số tổng quan các loại điểm như lab, assignment, Participation, final exam.",
            "chi tiết điểm": "Thông tin chi tiết về điểm số của sinh viên trong các mục đánh giá khác nhau, bao gồm phân loại, trọng số và giá trị điểm chi tiết, ví dụ lab 1, lab 2, lab 3, progress test 1, 2, 3,...",
            "điểm danh": "Thông tin về việc điểm danh, hoặc thời gian biểu, lịch học sinh viên trong các buổi học, bao gồm ngày, ca học, phòng học, giảng viên và trạng thái điểm danh.",
            "thông tin sinh viên": "Thông tin cá nhân của sinh viên, bao gồm họ tên, ngày sinh, giới tính, địa chỉ, mã sinh viên và các thông tin liên quan đến sinh viên.",
        }
        
        # Tạo embedding cho các loại dữ liệu
        type_texts = list(type_descriptions.values())
        embeddings = self.generate_content_embedding(type_texts)
        
        for data_type, embedding in zip(type_descriptions.keys(), embeddings):
            self.type_embeddings[data_type] = embedding
        
        print(f"🏷️  Created embeddings for {len(type_descriptions)} data types")
    
    def create_term_embeddings(self):
        """
        Tạo embedding cho từng học kỳ (Fall2023, Spring2024,...)
        """
        term_descriptions = {
        "Fall2023": "Học kỳ mùa thu năm 2023, diễn ra từ tháng 9 đến tháng 12.",
        "Spring2024": "Học kỳ mùa xuân năm 2024, bắt đầu từ tháng 1 đến tháng 4.",
        "Summer2024": "Học kỳ hè năm 2024, diễn ra từ tháng 5 đến tháng 8.",
        "Fall2024": "Học kỳ mùa thu năm 2024, từ tháng 9 đến tháng 12.",
        "Spring2025": "Học kỳ mùa xuân năm 2025, từ tháng 1 đến tháng 4."
        }
        type_texts = list(term_descriptions.values())
        embeddings = self.generate_content_embedding(type_texts)
        
        for data_type, embedding in zip(term_descriptions.keys(), embeddings):
            self.term_embeddings[data_type] = embedding
        
        print(f"🏷️  Created embeddings for {len(term_descriptions)} data types")
    
    def detect_subject_from_query(self, query, threshold=0.3, return_score=False):
        if not self.subject_embeddings:
            return (None, 0) if return_score else None
        query_embedding = self.generate_content_embedding([query])[0]
        best_match = None
        best_score = 0
        for subject, subject_embedding in self.subject_embeddings.items():
            similarity = cosine_similarity([query_embedding], [subject_embedding])[0][0]
            if similarity > threshold and similarity > best_score:
                best_score = similarity
                best_match = subject
        if return_score:
            return (best_match, best_score)
        return best_match
    
    def detect_type_from_query(self, query, threshold=0.3, return_score=False):
        if not self.type_embeddings:
            return (None, 0) if return_score else None
        query_embedding = self.generate_content_embedding([query])[0]
        best_match = None
        best_score = 0
        for data_type, type_embedding in self.type_embeddings.items():
            similarity = cosine_similarity([query_embedding], [type_embedding])[0][0]
            if similarity > threshold and similarity > best_score:
                best_score = similarity
                best_match = data_type
        if return_score:
            return (best_match, best_score)
        return best_match
    
    def detect_term_from_query(self, query, threshold=0.3, return_score=False):
        if not self.term_embeddings:
            return (None, 0) if return_score else None
        query_embedding = self.generate_content_embedding([query])[0]
        best_match = None
        best_score = 0
        for term, term_embedding in self.term_embeddings.items():
            similarity = cosine_similarity([query_embedding], [term_embedding])[0][0]
            if similarity > threshold and similarity > best_score:
                best_score = similarity
                best_match = term
        if return_score:
            return (best_match, best_score)
        return best_match
    
    def search_qdrant(self, query: str, user_id: str = None, limit: int = 5, threshold: float = 0.3, chat_history: list = None):
        """
        Hàm search chính, detect → filter → truy vấn Qdrant → LLM enhance
        Trả về list kết quả (rank, score, type, subject, content)
        """
        print(f"🔍 Searching for: '{query}' (User: {user_id})")
        
        # LLM Extract Intent (nếu enabled)
        llm_intent = {}
        if self.enable_llm and self.llm_helper:
            llm_intent = self.llm_helper.extract_query_intent(query, chat_history=chat_history)
            print(f"🤖 LLM Intent: {llm_intent}")
        
        # Detect các thông tin từ query (backup khi LLM fail)
        detected_subject, subject_score = self.detect_subject_from_query(query, threshold, return_score=True)
        detected_type, type_score = self.detect_type_from_query(query, threshold, return_score=True)
        
        # Ưu tiên LLM intent nếu có (sử dụng tên trường mới)
        if llm_intent.get('ma_mon_hoc'):
            detected_subject = llm_intent['ma_mon_hoc']
        if llm_intent.get('loai'):
            detected_type = llm_intent['loai']
        
        # Time range filtering từ LLM intent
        time_range_filter = None
        if llm_intent.get('time_range'):
            time_range = llm_intent['time_range']
            if isinstance(time_range, dict) and 'start_date' in time_range and 'end_date' in time_range:
                start_date = time_range['start_date']
                end_date = time_range['end_date']
                if isinstance(start_date, str):
                    start_date = datetime.strptime(start_date, "%d/%m/%Y")
                if isinstance(end_date, str):
                    end_date = datetime.strptime(end_date, "%d/%m/%Y")
                time_range_filter = {
                    "start_date": start_date.strftime("%d/%m/%Y"),
                    "end_date": end_date.strftime("%d/%m/%Y")
                }
                print(f"⏰ Time range filter: {time_range_filter['start_date']} - {time_range_filter['end_date']}")
        
        print(f"[Detect] Subject: {detected_subject} (score={subject_score:.3f}) | Type: {detected_type} (score={type_score:.3f})")
        
        # Xác thực metadata (chỉ khi LLM helper available)
        if self.llm_helper and detected_subject and hasattr(self.llm_helper, 'SUBJECTS') and detected_subject not in self.llm_helper.SUBJECTS:
            print(f"Mã môn học '{detected_subject}' không hợp lệ. Vui lòng kiểm tra lại truy vấn.")
            return []
        if self.llm_helper and detected_type and hasattr(self.llm_helper, 'TYPES') and detected_type not in self.llm_helper.TYPES:
            print(f"Loại dữ liệu '{detected_type}' không hợp lệ. Vui lòng kiểm tra lại truy vấn.")
            return []
        
        # Tạo embedding cho query
        query_embedding = self.embedder.encode([self.prefix + query], normalize_embeddings=True)[0]
        
        # Xây dựng filters
        must = []
        should = []
        
        if detected_type:
            must.append(FieldCondition(key="loai", match=MatchValue(value=detected_type)))
        
        if detected_subject:
            should.append(FieldCondition(key="ma_mon_hoc", match=MatchValue(value=detected_subject)))
        
        # Thêm time range filter nếu có
        if time_range_filter:
            # Qdrant can filter string dates with gte/lte if they're in sortable format
            # Our dates are in DD/MM/YYYY format which is sortable as strings
            must.append(FieldCondition(
                key="ngay",
                range=Range(
                    gte=time_range_filter["start_date"],
                    lte=time_range_filter["end_date"]
                )
            ))
            print(f"⏰ Time range filter applied in Qdrant: {time_range_filter['start_date']} - {time_range_filter['end_date']}")
        
        # Tạo Qdrant filter
        qdrant_filter = Filter(must=must, should=should) if must or should else None
        
        # Search trong Qdrant
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding.tolist(),
                query_filter=qdrant_filter,
                limit=limit * 2,  # Lấy nhiều hơn để LLM re-rank
                score_threshold=0
            )
            
            print(f"📊 Found {len(results)} results for user {user_id}")
            
            # Format kết quả
            formatted_results = []
            for i, hit in enumerate(results, 1):
                result = {
                    "rank": i,
                    "score": hit.score,
                    "loai": hit.payload.get("loai", "N/A"),
                    "ma_mon_hoc": hit.payload.get("ma_mon_hoc", "N/A"),
                    "ten_mon_hoc": hit.payload.get("ten_mon_hoc", "N/A"),
                    "content": hit.payload.get("noi_dung", "")[:300] + ("..." if len(hit.payload.get("noi_dung", "")) > 300 else "")
                }
                formatted_results.append(result)
            
            # LLM Re-rank (nếu enabled)
            if self.enable_llm and self.llm_helper and formatted_results:
                original_results = formatted_results.copy()
                formatted_results = self.llm_helper.re_rank_results(query, formatted_results, limit)
                # Cập nhật lại rank sau khi re-rank
                for i, result in enumerate(formatted_results):
                    result['rank'] = i + 1
            
            # In kết quả
            for i, result in enumerate(formatted_results[:limit], 1):
                print(f"  {i}. Score: {result['score']:.3f} | Loai: {result['loai']} | Mon hoc: {result['ma_mon_hoc']} - {result['ten_mon_hoc']}")
                print(f"     Content: {result['content']}")
            
            return formatted_results[:limit]
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []

    def run_full_embedding_pipeline_from_db(self, user_id, df_profile, df_attendance, df_grades, df_courses):
        """
        Pipeline: chunk -> check hash -> embedding -> upsert Qdrant -> tạo index detection
        Chỉ embedding các payload mới (hash chưa có)
        """
        # Lấy tên user
        user_full_name = None
        if not df_profile.empty:
            user_full_name = str(df_profile.iloc[0].get('full_name', ''))
        all_payloads = []
        if not df_profile.empty:
            profile_payloads = self.chunk_student_profile(df_profile, user_full_name)
            all_payloads.extend(profile_payloads)
            print(f"📋 Student profile: {len(profile_payloads)} payloads")
        else:
            print("⚠️  No student profile data")
            
        if not df_attendance.empty:
            attendance_payloads = self.chunk_attendance_reports(df_attendance, user_full_name)
            all_payloads.extend(attendance_payloads)
            print(f"📋 Attendance: {len(attendance_payloads)} payloads")
        else:
            print("⚠️  No attendance data")
            
        if not df_grades.empty:
            grades_payloads = self.chunk_grade_details(df_grades, user_full_name)
            all_payloads.extend(grades_payloads)
            print(f"📋 Grades: {len(grades_payloads)} payloads")
        else:
            print("⚠️  No grades data")
            
        if not df_courses.empty:
            courses_payloads = self.chunk_course_summaries(df_courses, user_full_name)
            all_payloads.extend(courses_payloads)
            print(f"📋 Course summaries: {len(courses_payloads)} payloads")
        else:
            print("⚠️  No course summaries data")
            
        print(f"📊 Total payloads: {len(all_payloads)}")
        # Check hash
        existing_hashes = self.get_existing_hashes()
        new_payloads = [p for p in all_payloads if p['content_hash'] not in existing_hashes]
        print(f"New payloads to embed: {len(new_payloads)}")
        if not new_payloads:
            print("No new data to embed.")
            return 0
        # Embedding
        embeddings = self.generate_content_embedding(new_payloads)
        points = self.merge_point_structs(new_payloads, embeddings)
        self.safe_upsert_to_qdrant(points)
        self.create_payload_index()
        self.create_subject_embeddings()
        self.create_type_embeddings()
        self.create_term_embeddings()
        return len(new_payloads)

    def search_with_metadata(self, query: str, limit: int = 5):
        """
        Hàm search đơn giản sử dụng metadata từ LLM
        """
        print(f"🔍 Searching with metadata: '{query}'")
        
        # LLM Extract Intent
        llm_intent = {}
        if self.enable_llm and self.llm_helper:
            llm_intent = self.llm_helper.extract_query_intent(query)
            print(f"🤖 LLM Metadata: {llm_intent}")
        
        # Tạo embedding cho query
        query_embedding = self.embedder.encode([self.prefix + query], normalize_embeddings=True)[0]
        
        # Xây dựng filters từ metadata
        must = []
        should = []
        
        if llm_intent.get('loai'):
            must.append(FieldCondition(key="loai", match=MatchValue(value=llm_intent['loai'])))
            print(f"🔍 Filter by loai: {llm_intent['loai']}")
        
        if llm_intent.get('ma_mon_hoc'):
            should.append(FieldCondition(key="ma_mon_hoc", match=MatchValue(value=llm_intent['ma_mon_hoc'])))
            print(f"🔍 Filter by ma_mon_hoc: {llm_intent['ma_mon_hoc']}")
        
        # Tạo Qdrant filter
        qdrant_filter = Filter(must=must, should=should) if must or should else None
        
        # Search trong Qdrant
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding.tolist(),
                query_filter=qdrant_filter,
                limit=limit,
                score_threshold=0
            )
            
            print(f"📊 Found {len(results)} results")
            
            # Format kết quả
            formatted_results = []
            for i, hit in enumerate(results, 1):
                result = {
                    "rank": i,
                    "score": hit.score,
                    "loai": hit.payload.get("loai", "N/A"),
                    "ma_mon_hoc": hit.payload.get("ma_mon_hoc", "N/A"),
                    "ten_mon_hoc": hit.payload.get("ten_mon_hoc", "N/A"),
                    "content": hit.payload.get("noi_dung", "")[:200] + ("..." if len(hit.payload.get("noi_dung", "")) > 200 else "")
                }
                formatted_results.append(result)
            
            # In kết quả
            for i, result in enumerate(formatted_results, 1):
                print(f"  {i}. Score: {result['score']:.3f}")
                print(f"     Loai: {result['loai']}")
                print(f"     Mon hoc: {result['ma_mon_hoc']} - {result['ten_mon_hoc']}")
                print(f"     Content: {result['content']}")
                print()
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []

    def get_existing_hashes_for_user(self, user_id: str):
        """
        Lấy tất cả content_hash đã có trong collection Qdrant cho một user cụ thể.
        """
        existing_hashes = set()
        try:
            scroll = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                ),
                limit=10000,
                with_payload=["content_hash"]
            )
            for point in scroll[0]:
                h = point.payload.get("content_hash")
                if h:
                    existing_hashes.add(h)
            print(f"📊 Found {len(existing_hashes)} existing hashes for user {user_id}")
        except Exception as e:
            print(f"❌ Error getting existing hashes for user {user_id}: {e}")
        return existing_hashes

    def check_duplicates_for_user(self, user_id: str):
        """
        Kiểm tra trùng lặp dữ liệu cho một user cụ thể.
        """
        try:
            # Lấy tất cả records của user
            scroll = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                ),
                limit=10000,
                with_payload=True
            )
            
            # Phân tích trùng lặp
            content_hashes = {}
            duplicates = []
            
            for point in scroll[0]:
                content_hash = point.payload.get("content_hash")
                if content_hash:
                    if content_hash in content_hashes:
                        duplicates.append({
                            "hash": content_hash,
                            "existing_id": content_hashes[content_hash],
                            "duplicate_id": point.id,
                            "content": point.payload.get("noi_dung", "")[:100]
                        })
                    else:
                        content_hashes[content_hash] = point.id
            
            print(f"🔍 Duplicate check for user {user_id}:")
            print(f"   Total records: {len(scroll[0])}")
            print(f"   Unique content hashes: {len(content_hashes)}")
            print(f"   Duplicates found: {len(duplicates)}")
            
            if duplicates:
                print("   Duplicate details:")
                for dup in duplicates[:5]:  # Chỉ hiển thị 5 duplicate đầu tiên
                    print(f"     - Hash: {dup['hash'][:20]}...")
                    print(f"       Content: {dup['content']}")
            
            return {
                "total_records": len(scroll[0]),
                "unique_hashes": len(content_hashes),
                "duplicates": duplicates
            }
            
        except Exception as e:
            print(f"❌ Error checking duplicates for user {user_id}: {e}")
            return None

# ===== USAGE EXAMPLE =====
def main():
    """Example usage"""
    # Cấu hình paths
    # Use relative paths instead of hardcoded paths
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'FAP')
    csv_paths = {
        'student_profile': os.path.join(data_dir, 'student_profile.csv'),
        'attendance_reports': os.path.join(data_dir, 'attendance_reports.csv'), 
        'grade_details': os.path.join(data_dir, 'grade_details.csv'),
        'course_summaries': os.path.join(data_dir, 'course_summaries.csv')
    }
    # Qdrant config sẽ lấy từ .env nếu không truyền vào
    engine = FapSearchEngine(csv_paths=csv_paths)
    
    # Kết nối thử Qdrant
    # Load data và tạo embeddings
    engine.load_all_dataframes()
    
    # Tạo các payload
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
    
    # Tạo embeddings và upload
    embeddings = engine.generate_content_embedding(all_payloads)
    points = engine.merge_point_structs(all_payloads, embeddings)
    engine.safe_upsert_to_qdrant(points)
    engine.create_payload_index()
    
    # # Tạo detection embeddings
    engine.create_subject_embeddings()
    engine.create_type_embeddings()
    engine.create_term_embeddings()
    
    # Test search
    results = engine.search_qdrant("điểm trung bình cpv", limit=5)
    print(results)
    print("\n🔑 Lưu ý: Đặt file .env với các biến QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION nếu muốn cấu hình riêng!")
    return engine

if __name__ == "__main__":
    main()