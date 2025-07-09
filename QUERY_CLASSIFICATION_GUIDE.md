# Hướng dẫn phân loại câu hỏi cho hệ thống RAG FAP

## Tổng quan

Document này phân loại các loại câu hỏi mà hệ thống RAG FAP có thể xử lý theo 3 mức độ:
- **🟢 TỐT**: Câu hỏi có thể trả lời chính xác và đầy đủ
- **🟡 MƠ HỒ**: Câu hỏi có thể trả lời một phần hoặc cần làm rõ
- **🔴 SAI**: Câu hỏi không thể trả lời hoặc trả lời sai

## 🟢 CÂU HỎI CÓ THỂ TRẢ LỜI TỐT

### 1. Thông tin sinh viên
```
- "Thông tin cá nhân của tôi"
- "Hồ sơ sinh viên"
- "Thông tin liên hệ"
- "Mã sinh viên của tôi"
- "Ngày sinh, địa chỉ"
```

### 2. Điểm danh (Attendance)
```
- "Điểm danh môn CSI105"
- "Lịch học tuần sau"
- "Điểm danh tháng này"
- "Buổi học ngày mai"
- "Phòng học môn AIL303m"
- "Giảng viên môn PFP191"
- "Trạng thái điểm danh"
- "Lịch học kì này"
```

### 3. Chi tiết điểm (Grade Details)
```
- "Điểm lab 1 môn CPV301"
- "Điểm progress test 2"
- "Điểm assignment môn DBI202"
- "Điểm final exam"
- "Trọng số các mục đánh giá"
- "Điểm từng phần môn học"
```

### 4. Tổng kết môn học (Course Summaries)
```
- "Điểm trung bình môn CSI105"
- "Trạng thái môn AIL303m"
- "Tổng kết môn PFP191"
- "Điểm cuối kỳ môn DBI202"
- "Kết quả học tập"
```

### 5. Time Range Queries
```
- "Điểm danh tuần sau"
- "Lịch học tháng này"
- "Điểm danh kì sau"
- "Lịch học tuần trước"
- "Điểm danh ngày mai"
- "Lịch học hôm nay"
```

### 6. Kết hợp nhiều điều kiện
```
- "Điểm danh môn CSI105 tuần sau"
- "Điểm lab môn AIL303m kì này"
- "Lịch học môn PFP191 tháng này"
- "Điểm trung bình môn CPV301"
```

## 🟡 CÂU HỎI CÓ THỂ TRẢ LỜI MỘT PHẦN

### 1. Câu hỏi quá rộng
```
- "Tất cả điểm của tôi" → Cần chỉ định môn học cụ thể
- "Lịch học" → Cần chỉ định thời gian
- "Điểm danh" → Cần chỉ định môn học hoặc thời gian
```

### 2. Câu hỏi không có context thời gian
```
- "Điểm môn CSI105" → Có thể trả về tất cả kỳ học
- "Lịch học môn AIL303m" → Cần chỉ định kỳ học
- "Điểm danh PFP191" → Có thể trả về tất cả buổi học
```

### 3. Câu hỏi về môn học không có trong dữ liệu
```
- "Điểm môn XYZ123" → Môn học không tồn tại
- "Lịch học môn ABC456" → Môn học không có trong hệ thống
```

### 4. Câu hỏi về thời gian quá xa
```
- "Điểm danh năm 2020" → Dữ liệu có thể không có
- "Lịch học học kỳ Spring2020" → Dữ liệu cũ
```

### 5. Câu hỏi cần suy luận
```
- "Tôi có bị thiếu buổi học nào không?" → Cần phân tích trạng thái
- "Môn nào tôi học tốt nhất?" → Cần so sánh điểm trung bình
- "Tôi có đủ điều kiện tốt nghiệp không?" → Cần kiểm tra nhiều điều kiện
```

## 🔴 CÂU HỎI KHÔNG THỂ TRẢ LỜI

### 1. Câu hỏi ngoài phạm vi dữ liệu
```
- "Học phí bao nhiêu?"
- "Lịch thi cuối kỳ"
- "Thông tin về giảng viên"
- "Lịch nghỉ lễ"
- "Thông tin về thư viện"
- "Quy định về việc thi lại"
```

### 2. Câu hỏi về tương lai
```
- "Lịch học tuần tới" → Chưa có dữ liệu
- "Điểm môn học kỳ sau" → Chưa thi
- "Lịch thi cuối kỳ" → Chưa được lên lịch
```

### 3. Câu hỏi về sinh viên khác
```
- "Điểm của bạn A"
- "Lịch học của bạn B"
- "Thông tin sinh viên khác"
```

### 4. Câu hỏi về hành động/thay đổi
```
- "Đăng ký môn học"
- "Thay đổi lịch học"
- "Nộp đơn xin nghỉ học"
- "Đăng ký thi lại"
```

### 5. Câu hỏi về hệ thống
```
- "Cách sử dụng FAP"
- "Quên mật khẩu"
- "Lỗi đăng nhập"
- "Cách tải báo cáo"
```

## 📊 PHÂN LOẠI THEO LOẠI DỮ LIỆU

### Thông tin sinh viên (Student Profile)
| Loại câu hỏi | Mức độ | Ví dụ |
|-------------|--------|-------|
| Thông tin cá nhân cơ bản | 🟢 TỐT | "Tên, ngày sinh, địa chỉ" |
| Thông tin học tập | 🟢 TỐT | "Mã SV, chuyên ngành, lớp" |
| Thông tin tài chính | 🟡 MƠ HỒ | "Số dư tài khoản" |
| Thông tin phụ huynh | 🟢 TỐT | "Thông tin liên hệ phụ huynh" |

### Điểm danh (Attendance)
| Loại câu hỏi | Mức độ | Ví dụ |
|-------------|--------|-------|
| Lịch học theo môn | 🟢 TỐT | "Lịch học môn CSI105" |
| Lịch học theo thời gian | 🟢 TỐT | "Lịch học tuần sau" |
| Trạng thái điểm danh | 🟢 TỐT | "Tôi có đi học đủ không?" |
| Thông tin phòng học | 🟢 TỐT | "Phòng học môn AIL303m" |
| Thông tin giảng viên | 🟢 TỐT | "Giảng viên môn PFP191" |

### Chi tiết điểm (Grade Details)
| Loại câu hỏi | Mức độ | Ví dụ |
|-------------|--------|-------|
| Điểm từng phần | 🟢 TỐT | "Điểm lab 1 môn CPV301" |
| Trọng số đánh giá | 🟢 TỐT | "Trọng số final exam" |
| Điểm theo loại | 🟢 TỐT | "Điểm assignment" |
| So sánh điểm | 🟡 MƠ HỒ | "Môn nào điểm cao nhất?" |

### Tổng kết môn học (Course Summaries)
| Loại câu hỏi | Mức độ | Ví dụ |
|-------------|--------|-------|
| Điểm trung bình | 🟢 TỐT | "Điểm TB môn CSI105" |
| Trạng thái môn học | 🟢 TỐT | "Tôi có pass môn AIL303m không?" |
| Tổng kết học kỳ | 🟢 TỐT | "Kết quả học kỳ Fall2024" |

## 🎯 HƯỚNG DẪN SỬ DỤNG

### 1. Câu hỏi tốt nhất
- Chỉ định rõ môn học (mã môn)
- Chỉ định thời gian cụ thể
- Sử dụng từ khóa chuẩn

### 2. Tránh câu hỏi mơ hồ
- Không chỉ định môn học
- Không chỉ định thời gian
- Sử dụng từ ngữ không rõ ràng

### 3. Ví dụ câu hỏi tối ưu
```
✅ "Điểm danh môn CSI105 tuần sau"
✅ "Điểm lab 1 môn AIL303m"
✅ "Lịch học môn PFP191 tháng này"
✅ "Điểm trung bình môn CPV301"

❌ "Điểm của tôi"
❌ "Lịch học"
❌ "Tôi học gì?"
```

## 🔧 CẢI THIỆN HỆ THỐNG

### 1. Cho câu hỏi mơ hồ
- Gợi ý làm rõ câu hỏi
- Đưa ra các lựa chọn
- Hỏi lại thông tin cần thiết

### 2. Cho câu hỏi sai
- Giải thích phạm vi dữ liệu
- Hướng dẫn sử dụng đúng
- Đề xuất câu hỏi thay thế

### 3. Cải thiện accuracy
- Thêm validation cho input
- Cải thiện intent detection
- Mở rộng từ điển synonyms 