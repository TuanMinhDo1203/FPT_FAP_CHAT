import os
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from FAP.cloud import CloudManager
from FAP.embedder import FapSearchEngine
# Thêm import cho toxic content detection (optional)
def is_toxic(query):
    try:
        from transformers import pipeline
        toxic_classifier = pipeline("text-classification", model="unitary/toxic-bert")
        result = toxic_classifier(query)
        return any(r['label'] == 'toxic' and r['score'] > 0.6 for r in result)
    except:
        # Nếu không cài đặt transformers, bỏ qua toxic detection
        return False

# Đảm bảo load đúng file .env ở gốc project
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
load_dotenv()

# Đường dẫn tuyệt đối tới thư mục data/FAP
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'FAP'))

def clean_csv_nan_to_placeholder(csv_path, placeholder="unknown"):
    df = pd.read_csv(csv_path)
    df = df.fillna(placeholder)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

if __name__ == "__main__":
    print("\n🔑 Đảm bảo đã cấu hình .env với thông tin cloud MySQL Aiven và Qdrant!")
    # 1. Sync dữ liệu lên cloud
    csv_paths = {
        "student_profile": os.path.join(DATA_DIR, "student_profile.csv"),
        "attendance_reports": os.path.join(DATA_DIR, "attendance_reports.csv"),
        "grade_details": os.path.join(DATA_DIR, "grade_details.csv"),
        "course_summaries": os.path.join(DATA_DIR, "course_summaries.csv")
    }
    for path in csv_paths.values():
        clean_csv_nan_to_placeholder(path)
    db_config = {
    "host": os.environ.get("MYSQL_HOST"),
    "port": int(os.environ.get("MYSQL_PORT", 19116)),
    "user": os.environ.get("MYSQL_USER"),
    "password": os.environ.get("MYSQL_PASSWORD"),
    "db": os.environ.get("MYSQL_DB"),
    "charset": "utf8mb4"
    }
    manager = CloudManager(csv_paths, db_config)
    # === CÀO DỮ LIỆU FAP ===
    should_scrape = input("Bạn có muốn cào lại dữ liệu từ FAP không? (y/n): ").strip().lower()
    if should_scrape == 'y':
        from FAP import fap_scraper
        gmail = input("Nhập email FPT của bạn: ")
        password = input("Nhập mật khẩu FPT: ")
        scraper = fap_scraper.FapScraper(gmail=gmail, password=password)
        results = scraper.full_scraping_process()
        if not results:
            print("❌ Lỗi khi cào dữ liệu từ FAP. Vui lòng kiểm tra lại thông tin đăng nhập hoặc thử lại sau.")
            exit(1)
        # Lưu ra CSV đúng header
        profile = results.get('profile')
        if profile:
            df_profile = pd.DataFrame([profile])
            df_profile.to_csv(csv_paths["student_profile"], index=False, encoding="utf-8-sig")
        attendance = results.get('attendance', [])
        if attendance:
            df_att = pd.DataFrame(attendance)
            df_att.to_csv(csv_paths["attendance_reports"], index=False, encoding="utf-8-sig")
        grade_details = results.get('grade_details', [])
        if grade_details:
            df_grade = pd.DataFrame(grade_details)
            df_grade.to_csv(csv_paths["grade_details"], index=False, encoding="utf-8-sig")
        course_summaries = results.get('course_summaries', [])
        if course_summaries:
            df_course = pd.DataFrame(course_summaries)
            df_course.to_csv(csv_paths["course_summaries"], index=False, encoding="utf-8-sig")
        print("✅ Đã cào và lưu dữ liệu ra 4 file CSV!")
        # Clean CSV files before cloud sync
        print("🧹 Đang làm sạch dữ liệu CSV...")
        manager.clean_all_csvs()
        manager.create_tables()
        manager.load_dataframes()
        manager.sync_all()
        print("\n🎯 Đã lưu toàn bộ dữ liệu scrape thực tế lên cloud MySQL Aiven!")

    # 2. Kéo dữ liệu từ cloud về local CSVs
    print("\n⬇️ Đang tải dữ liệu từ cloud về local CSVs...")
    manager.download_dataframes()
    # #In ra các df đã kéo về
    # print(f"File student_profile đã kéo về: {df_profile}")
    # print(f"File attendance_reports đã kéo về: {df_att}")
    # print(f"File grade_details đã kéo về: {df_grade}")
    # print(f"File course_summaries đã kéo về: {df_course}")
    
    # Clean downloaded CSV files for embedding
    print("🧹 Đang làm sạch dữ liệu CSV cho embedding...")
    manager.clean_all_csvs()

    user_id = input("Nhập mã sinh viên (user_id/roll_number) để embedding: ")
    df_profile = manager.get_student_df(user_id)
    df_attendance = manager.get_attendance_df(user_id)
    df_grades = manager.get_grades_df(user_id)
    df_courses = manager.get_all_courses_df()

    # LLM Configuration
    enable_llm = input("Bạn có muốn bật LLM để tối ưu search không? (y/n): ").strip().lower() == 'y'
    if enable_llm:
        print("🤖 LLM sẽ được sử dụng để: extract intent, re-rank results, synthesize answers")
        # print("⚠️ Đảm bảo đã cấu hình GEMINI_API_KEY trong file .env")
    else:
        print("⚠️ LLM disabled - sẽ dùng search embedding truyền thống")

    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")
    collection_name = os.environ.get("QDRANT_COLLECTION", "Fap_data_testing")
    engine = FapSearchEngine(csv_paths, qdrant_url, qdrant_api_key, collection_name, enable_llm=enable_llm)
    n_embedded = engine.run_full_embedding_pipeline_from_db(user_id, df_profile, df_attendance, df_grades, df_courses)
    print(f"\n🎯 Đã embedding và upsert {n_embedded} payloads mới cho user_id {user_id}!")

    # 3. Search terminal
    print("\n=== SEARCH MODE ===")
    if enable_llm and engine.llm_helper and engine.llm_helper.is_available():
        print("🤖 LLM Search Mode: Intent extraction + Re-ranking + Synthesis enabled")
    else:
        print("🔍 Traditional Search Mode: Embedding + Cosine similarity")
    
    # Lưu lịch sử hội thoại
    chat_history = []
    
    while True:
        query = input("\nNhập truy vấn tìm kiếm (hoặc 'bye' để thoát): ")
        if query.strip().lower() == 'bye':
            print("Tạm biệt!")
            break
        
        # Lọc truy vấn độc hại bằng mô hình AI
        if is_toxic(query):
            print("⚠️ Truy vấn của bạn có nội dung không phù hợp. Vui lòng sử dụng ngôn ngữ lịch sự.")
            continue
        
        # Thêm truy vấn vào chat_history
        chat_history.append({"role": "user", "content": query})
        try:
            results = engine.search_qdrant(query, limit=7, threshold=0.3, chat_history=chat_history)
            if not results:
                print("❌ Không tìm thấy kết quả phù hợp. Nếu bạn chắc chắn đã nhập đúng thông tin, vui lòng kiểm tra lại truy vấn hoặc liên hệ hỗ trợ.")
                chat_history.append({"role": "assistant", "content": "Không tìm thấy kết quả phù hợp."})
            else:
                print(f"\n🔎 Top {len(results)} kết quả:")
                for r in results:
                    print(f"[{r['rank']}] Score: {r['score']:.3f} | Type: {r['loai']} | Subject: {r['ma_mon_hoc']} - {r['ten_mon_hoc']}\n    {r['content']}\n---")
                # LLM Synthesis (nếu enabled)
                if enable_llm and engine.llm_helper and engine.llm_helper.is_available():
                    print("\n🤖 LLM Summary:")
                    summary = engine.llm_helper.synthesize_answer(query, results)
                    if not summary or 'không thể tổng hợp' in summary.lower() or 'không tìm thấy' in summary.lower():
                        print("Không thể tổng hợp kết quả. Vui lòng xem chi tiết các kết quả bên trên hoặc thử lại truy vấn khác.")
                        chat_history.append({"role": "assistant", "content": "Không thể tổng hợp kết quả."})
                    else:
                        print(summary)
                        chat_history.append({"role": "assistant", "content": summary})
                else:
                    # Nếu không dùng LLM synthesis, lưu lại kết quả đầu tiên
                    chat_history.append({"role": "assistant", "content": results[0]["content"] if results else ""})
        except Exception as e:
            print(f"⚠️ Đã xảy ra lỗi khi xử lý truy vấn: {e}\nVui lòng thử lại sau hoặc kiểm tra kết nối/API.")
            chat_history.append({"role": "assistant", "content": "Đã xảy ra lỗi khi xử lý truy vấn."})