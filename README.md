# FAP Chat - Student Academic Data RAG System

Hệ thống RAG (Retrieval-Augmented Generation) cho dữ liệu học tập sinh viên FPT University.
![Demo](static/demo.JPG)

## 🚀 Cài đặt

### 1. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### 2. Cấu hình Environment Variables
Tạo file `.env` trong thư mục gốc với các biến sau:

```env
# Qdrant Vector Database
QDRANT_URL=https://your-qdrant-url.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_api_key_here
QDRANT_COLLECTION=Fap_data_testing

# MySQL Database (Aiven)
MYSQL_HOST=your-mysql-host.aivencloud.com
MYSQL_PORT=19116
MYSQL_USER=your_mysql_username
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=your_database_name

# LLM (Gemini) - Optional
GEMINI_API_KEY=your_gemini_api_key_here
```

## 🎯 Sử dụng

### Chạy hệ thống chính
```bash
cd Fap_Chat/code
python main.py
```

### Các tính năng chính:

1. **Cào dữ liệu từ FAP** (tùy chọn)
   - Nhập email và mật khẩu FPT
   - Tự động cào: profile, điểm danh, điểm số, tổng kết môn học

2. **Đồng bộ với Cloud Database**
   - Upload dữ liệu lên MySQL Aiven
   - Download dữ liệu về local

3. **Vector Embedding & Search**
   - Tạo embeddings cho dữ liệu
   - Tìm kiếm semantic với BGE-M3
   - Hỗ trợ time range filtering

4. **LLM Enhancement** (tùy chọn)
   - Intent extraction
   - Re-ranking kết quả
   - Tổng hợp câu trả lời

## 🔍 Ví dụ truy vấn

### Time Range Queries:
- `"điểm danh tuần sau"`
- `"lịch học tháng này"`
- `"điểm danh kì sau"`
- `"lịch học kì trước"`

### Subject Queries:
- `"điểm môn CPV301"`
- `"điểm danh môn AIL303m"`
- `"thông tin sinh viên"`
- `"giáo trình môn Machine Learning"`
- `"outline môn Deep Learning kỳ này"`
### Combined Queries:
- `"điểm danh môn CSI105 tuần sau"`
- `"điểm môn PFP191 kì này"`
- `"giáo trình môn Trí tuệ nhân tạo kỳ FA25"`
- `"syllabus môn Data Mining học kì này"`

## 📁 Cấu trúc Project

```
FPT_FAP_CHAT/
├── app.py                          # FastAPI app, khởi tạo server và định nghĩa endpoint
│
├── code1/                          # CLI / pipeline chính
│   ├── main.py                     # entrypoint, điều khiển ingest → embed → query
│   ├── crawler.py                  # module crawl dữ liệu từ FAP
│   ├── embedder.py                 # module nhúng văn bản sang vector
│   ├── llm_helper.py               # helper gọi LLM (Gemini,... nếu có key)
│   ├── qdrant_helper.py            # helper kết nối Qdrant (vector DB)
│   ├── mysql_helper.py             # helper kết nối MySQL
│   └── utils.py                    # hàm tiện ích chung
│
├── data/                           # dữ liệu CSV (export từ FAP)
│   └── FAP/
│       ├── attendance_reports.csv  # báo cáo điểm danh
│       ├── course_summaries.csv    # thông tin môn học / syllabus ngắn
│       ├── grade_details.csv       # bảng điểm chi tiết
│       └── student_profile.csv     # thông tin hồ sơ sinh viên
│
├── templates/                      # giao diện web (FastAPI dùng Jinja2)
│   └── chatbot.html                # UI chatbot đơn giản
│
├── static/                         # file tĩnh (css/js/img nếu cần)
│   
│
├── notebook/                       # notebook thử nghiệm
│   ├── tester.ipynb                # notebook test pipeline
│   └── ...                         # (các notebook phụ khác)
│
├── requirements.txt                # danh sách thư viện Python cần cài
├── QUERY_CLASSIFICATION_GUIDE.md   # tài liệu hướng dẫn phân loại truy vấn
├── QUERY_PATTERNS_ANALYSIS.md      # phân tích pattern truy vấn thường gặp
├── USER_GUIDE.md                   # hướng dẫn sử dụng cho end-user
└── README.md                       # mô tả dự án (file bạn đang đọc)


```

## ⚠️ Lưu ý

1. **Bảo mật**: Đảm bảo file `.env` không được commit lên git
2. **Dependencies**: Cần cài đặt đầy đủ các thư viện trong requirements.txt
3. **API Keys**: Cần có Qdrant và MySQL credentials hợp lệ
4. **LLM**: Gemini API key là tùy chọn, hệ thống vẫn hoạt động không có LLM

## 🐛 Troubleshooting

### Lỗi kết nối database:
- Kiểm tra thông tin MySQL trong `.env`
- Đảm bảo database đã được tạo

### Lỗi Qdrant:
- Kiểm tra QDRANT_URL và QDRANT_API_KEY
- Đảm bảo collection có thể tạo được

### Lỗi LLM:
- Kiểm tra GEMINI_API_KEY
- Hệ thống sẽ fallback về search truyền thống nếu LLM không khả dụng
