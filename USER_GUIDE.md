# Hướng dẫn sử dụng hệ thống RAG FAP

## 🎯 Tổng quan

Hệ thống RAG FAP giúp sinh viên tra cứu thông tin học tập một cách nhanh chóng và chính xác thông qua các câu hỏi tự nhiên.

## 📚 Các loại thông tin có thể tra cứu

### 1. Thông tin sinh viên
- Thông tin cá nhân
- Hồ sơ sinh viên
- Thông tin liên hệ
- Mã sinh viên

### 2. Điểm danh và lịch học
- Lịch học theo môn
- Lịch học theo thời gian
- Trạng thái điểm danh
- Thông tin phòng học
- Thông tin giảng viên

### 3. Chi tiết điểm
- Điểm từng phần (lab, assignment, progress test, final exam)
- Trọng số đánh giá
- Điểm theo loại

### 4. Tổng kết môn học
- Điểm trung bình
- Trạng thái môn học
- Kết quả học tập

## 🎯 Cách đặt câu hỏi hiệu quả

### ✅ Câu hỏi tốt (có thể trả lời chính xác)

#### Thông tin sinh viên:
```
- "Thông tin cá nhân của tôi"
- "Hồ sơ sinh viên"
- "Thông tin liên hệ"
- "Mã sinh viên của tôi"
```

#### Điểm danh và lịch học:
```
- "Điểm danh môn CSI105"
- "Lịch học tuần sau"
- "Buổi học ngày mai"
- "Phòng học môn AIL303m"
- "Giảng viên môn PFP191"
- "Điểm danh môn CPV301 tuần sau"
```

#### Chi tiết điểm:
```
- "Điểm lab 1 môn CPV301"
- "Điểm progress test 2 môn AIL303m"
- "Điểm assignment môn DBI202"
- "Điểm final exam môn CSI105"
```

#### Tổng kết môn học:
```
- "Điểm trung bình môn CSI105"
- "Tổng kết môn AIL303m"
- "Kết quả môn PFP191"
- "Trạng thái môn CPV301"
```

### 🟡 Câu hỏi mơ hồ (cần làm rõ)

#### Thiếu thông tin cụ thể:
```
❌ "Điểm của tôi" → ✅ "Điểm môn CSI105"
❌ "Lịch học" → ✅ "Lịch học tuần sau"
❌ "Điểm danh" → ✅ "Điểm danh môn AIL303m"
```

#### Thiếu context thời gian:
```
❌ "Điểm môn CSI105" → ✅ "Điểm môn CSI105 học kỳ này"
❌ "Lịch học môn AIL303m" → ✅ "Lịch học môn AIL303m tuần sau"
```

### 🔴 Câu hỏi không thể trả lời

#### Ngoài phạm vi dữ liệu:
```
- "Học phí bao nhiêu?"
- "Lịch thi cuối kỳ"
- "Thông tin về giảng viên"
- "Lịch nghỉ lễ"
```

#### Về tương lai:
```
- "Lịch học tuần tới"
- "Điểm môn học kỳ sau"
- "Lịch thi cuối kỳ"
```

#### Về sinh viên khác:
```
- "Điểm của bạn A"
- "Lịch học của bạn B"
```

## ⏰ Cách sử dụng thời gian

### Tuần:
```
- "tuần sau"
- "tuần trước"
- "tuần này"
- "tuần tới"
- "tuần vừa rồi"
```

### Tháng:
```
- "tháng sau"
- "tháng trước"
- "tháng này"
- "tháng tới"
- "tháng vừa qua"
```

### Học kỳ:
```
- "học kỳ sau"
- "học kỳ trước"
- "học kỳ này"
- "kì sau"
- "kì trước"
- "kì này"
- "semester sau"
- "semester trước"
```

### Ngày:
```
- "ngày mai"
- "ngày hôm qua"
- "hôm nay"
- "hôm qua"
```

## 📋 Danh sách mã môn học

### Môn học AI/ML:
- **AIL303m**: Machine Learning
- **CPV301**: Computer Vision
- **ADY201m**: AI, DS with Python & SQL
- **DAP391m**: AI-DS Project

### Môn học cơ bản:
- **CSI105**: Introduction to Computer Science
- **PFP191**: Programming Fundamentals with Python
- **CSD203**: Data Structures and Algorithm with Python
- **DBI202**: Database Systems

### Môn học toán:
- **MAD101**: Discrete mathematics
- **MAE101**: Mathematics for Engineering
- **MAI391**: Advanced mathematics
- **MAS291**: Statistics & Probability

### Môn học khác:
- **CEA201**: Computer Organization and Architecture
- **SWE201c**: Introduction to Software Engineering
- **SSG104**: Communication and In-Group Working Skills
- **OTP101**: Orientation and General Training Program

### Môn học ngoại ngữ:
- **JPD113**: Elementary Japanese 1-A1.1
- **JPD123**: Japanese Elementary 1-A1.2

### Môn học thể thao:
- **VOV114**: Vovinam 1
- **VOV124**: Vovinam 2
- **VOV134**: Vovinam 3

### Môn học âm nhạc:
- **DSA103**: Traditional music instrument

## 💡 Mẹo sử dụng hiệu quả

### 1. Kết hợp nhiều điều kiện
```
✅ "Điểm danh môn CSI105 tuần sau"
✅ "Lịch học môn AIL303m tháng này"
✅ "Điểm lab 1 môn CPV301"
```

### 2. Sử dụng từ khóa chuẩn
```
✅ "điểm danh" thay vì "có đi học không"
✅ "lịch học" thay vì "khi nào học"
✅ "điểm trung bình" thay vì "điểm TB"
```

### 3. Chỉ định rõ ràng
```
✅ "Điểm lab 1 môn CPV301" thay vì "Điểm lab"
✅ "Lịch học tuần sau" thay vì "Lịch học"
✅ "Thông tin sinh viên" thay vì "Thông tin"
```

## 🚨 Lưu ý quan trọng

### 1. Phạm vi dữ liệu
- Hệ thống chỉ có dữ liệu về thông tin học tập
- Không có thông tin về học phí, lịch thi, etc.
- Không có dữ liệu về sinh viên khác

### 2. Thời gian dữ liệu
- Chỉ có dữ liệu về quá khứ và hiện tại
- Không có dữ liệu về tương lai
- Dữ liệu được cập nhật theo thời gian thực

### 3. Bảo mật
- Chỉ có thể tra cứu thông tin của chính mình
- Không thể tra cứu thông tin sinh viên khác
- Thông tin được mã hóa và bảo vệ

## 🔧 Xử lý lỗi thường gặp

### 1. Không tìm thấy môn học
```
Lỗi: "Điểm danh môn XYZ123"
Giải pháp: Kiểm tra lại mã môn học trong danh sách
```

### 2. Không có dữ liệu thời gian
```
Lỗi: "Lịch học tuần tới"
Giải pháp: Sử dụng thời gian trong quá khứ hoặc hiện tại
```

### 3. Câu hỏi quá chung chung
```
Lỗi: "Điểm của tôi"
Giải pháp: Chỉ định môn học cụ thể
```

### 4. Câu hỏi ngoài phạm vi
```
Lỗi: "Học phí bao nhiêu?"
Giải pháp: Liên hệ phòng tài chính
```

## 📞 Hỗ trợ

Nếu gặp vấn đề khi sử dụng hệ thống:
1. Kiểm tra lại cách đặt câu hỏi
2. Tham khảo danh sách mã môn học
3. Sử dụng các từ khóa chuẩn
4. Liên hệ hỗ trợ kỹ thuật nếu cần

---

**Lưu ý**: Hệ thống được thiết kế để hỗ trợ tra cứu thông tin học tập một cách nhanh chóng và chính xác. Hãy sử dụng đúng cách để có trải nghiệm tốt nhất! 