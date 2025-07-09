# Phân tích Pattern Câu hỏi cho hệ thống RAG FAP

## Tổng quan

Document này phân tích chi tiết các pattern câu hỏi mà hệ thống có thể gặp phải và cách xử lý tương ứng.

## 📋 PHÂN LOẠI THEO CẤU TRÚC CÂU HỎI

### 1. Pattern: [Loại dữ liệu] + [Môn học]
```
✅ TỐT:
- "Điểm danh môn CSI105"
- "Lịch học môn AIL303m"
- "Điểm môn PFP191"
- "Tổng kết môn CPV301"

🟡 MƠ HỒ:
- "Điểm danh" (thiếu môn học)
- "Lịch học" (thiếu môn học)
- "Điểm" (quá chung chung)

🔴 SAI:
- "Điểm danh môn XYZ123" (môn không tồn tại)
```

### 2. Pattern: [Loại dữ liệu] + [Thời gian]
```
✅ TỐT:
- "Điểm danh tuần sau"
- "Lịch học tháng này"
- "Điểm danh kì sau"
- "Lịch học ngày mai"

🟡 MƠ HỒ:
- "Điểm danh" (thiếu thời gian)
- "Lịch học" (thiếu thời gian)

🔴 SAI:
- "Điểm danh năm 2020" (dữ liệu cũ)
- "Lịch học tuần tới" (chưa có dữ liệu)
```

### 3. Pattern: [Loại dữ liệu] + [Môn học] + [Thời gian]
```
✅ TỐT:
- "Điểm danh môn CSI105 tuần sau"
- "Lịch học môn AIL303m tháng này"
- "Điểm môn PFP191 kì này"
- "Tổng kết môn CPV301 học kỳ này"

🟡 MƠ HỒ:
- "Điểm danh môn CSI105" (thiếu thời gian)
- "Lịch học tháng này" (thiếu môn học)

🔴 SAI:
- "Điểm danh môn XYZ123 tuần sau" (môn không tồn tại)
```

### 4. Pattern: [Chi tiết điểm] + [Môn học]
```
✅ TỐT:
- "Điểm lab 1 môn CPV301"
- "Điểm progress test 2 môn AIL303m"
- "Điểm assignment môn DBI202"
- "Điểm final exam môn CSI105"

🟡 MƠ HỒ:
- "Điểm lab" (thiếu môn học)
- "Điểm assignment" (thiếu môn học)

🔴 SAI:
- "Điểm lab 1 môn XYZ123" (môn không tồn tại)
```

## 🎯 PHÂN TÍCH THEO LOẠI DỮ LIỆU

### 1. Thông tin sinh viên (Student Profile)

#### Pattern nhận dạng:
- Từ khóa: "thông tin", "hồ sơ", "cá nhân", "sinh viên", "profile"
- Không cần môn học hoặc thời gian

#### Ví dụ pattern:
```
✅ TỐT:
- "Thông tin cá nhân của tôi"
- "Hồ sơ sinh viên"
- "Thông tin liên hệ"
- "Mã sinh viên"

🟡 MƠ HỒ:
- "Thông tin" (quá chung chung)

🔴 SAI:
- "Thông tin sinh viên khác"
- "Thông tin giảng viên"
```

### 2. Điểm danh (Attendance)

#### Pattern nhận dạng:
- Từ khóa: "điểm danh", "lịch học", "buổi học", "phòng học", "giảng viên"
- Có thể kết hợp với môn học và/hoặc thời gian

#### Ví dụ pattern:
```
✅ TỐT:
- "Điểm danh môn CSI105"
- "Lịch học tuần sau"
- "Buổi học ngày mai"
- "Phòng học môn AIL303m"
- "Giảng viên môn PFP191"
- "Điểm danh môn CPV301 tuần sau"

🟡 MƠ HỒ:
- "Điểm danh" (thiếu context)
- "Lịch học" (thiếu context)

🔴 SAI:
- "Điểm danh môn XYZ123"
- "Lịch học tuần tới"
```

### 3. Chi tiết điểm (Grade Details)

#### Pattern nhận dạng:
- Từ khóa: "điểm", "lab", "assignment", "progress test", "final exam"
- Cần chỉ định môn học cụ thể

#### Ví dụ pattern:
```
✅ TỐT:
- "Điểm lab 1 môn CPV301"
- "Điểm progress test 2 môn AIL303m"
- "Điểm assignment môn DBI202"
- "Điểm final exam môn CSI105"
- "Trọng số lab môn PFP191"

🟡 MƠ HỒ:
- "Điểm lab" (thiếu môn học)
- "Điểm assignment" (thiếu môn học)

🔴 SAI:
- "Điểm lab 1 môn XYZ123"
- "Điểm thi cuối kỳ" (không có trong dữ liệu)
```

### 4. Tổng kết môn học (Course Summaries)

#### Pattern nhận dạng:
- Từ khóa: "điểm trung bình", "tổng kết", "kết quả", "trạng thái"
- Cần chỉ định môn học

#### Ví dụ pattern:
```
✅ TỐT:
- "Điểm trung bình môn CSI105"
- "Tổng kết môn AIL303m"
- "Kết quả môn PFP191"
- "Trạng thái môn CPV301"

🟡 MƠ HỒ:
- "Điểm trung bình" (thiếu môn học)
- "Tổng kết" (thiếu môn học)

🔴 SAI:
- "Điểm trung bình môn XYZ123"
- "Tổng kết học kỳ" (không có trong dữ liệu)
```

## ⏰ PHÂN TÍCH THEO THỜI GIAN

### 1. Time Range Patterns

#### Tuần:
```
✅ TỐT:
- "tuần sau"
- "tuần trước"
- "tuần này"
- "tuần tới"
- "tuần vừa rồi"

🟡 MƠ HỒ:
- "tuần" (không rõ tuần nào)

🔴 SAI:
- "tuần tới" (chưa có dữ liệu)
```

#### Tháng:
```
✅ TỐT:
- "tháng sau"
- "tháng trước"
- "tháng này"
- "tháng tới"
- "tháng vừa qua"

🟡 MƠ HỒ:
- "tháng" (không rõ tháng nào)

🔴 SAI:
- "tháng tới" (chưa có dữ liệu)
```

#### Học kỳ:
```
✅ TỐT:
- "học kỳ sau"
- "học kỳ trước"
- "học kỳ này"
- "kì sau"
- "kì trước"
- "kì này"
- "semester sau"
- "semester trước"

🟡 MƠ HỒ:
- "học kỳ" (không rõ kỳ nào)

🔴 SAI:
- "học kỳ tới" (chưa có dữ liệu)
```

#### Ngày:
```
✅ TỐT:
- "ngày mai"
- "ngày hôm qua"
- "hôm nay"
- "hôm qua"

🟡 MƠ HỒ:
- "ngày" (không rõ ngày nào)

🔴 SAI:
- "ngày mai" (chưa có dữ liệu)
```

## 🔍 PHÂN TÍCH THEO MỨC ĐỘ PHỨC TẠP

### 1. Câu hỏi đơn giản (1 điều kiện)
```
✅ TỐT:
- "Điểm danh môn CSI105"
- "Lịch học tuần sau"
- "Thông tin sinh viên"

🟡 MƠ HỒ:
- "Điểm danh"
- "Lịch học"
```

### 2. Câu hỏi phức tạp (2 điều kiện)
```
✅ TỐT:
- "Điểm danh môn CSI105 tuần sau"
- "Lịch học môn AIL303m tháng này"
- "Điểm lab 1 môn CPV301"

🟡 MƠ HỒ:
- "Điểm danh tuần sau" (thiếu môn học)
- "Lịch học môn AIL303m" (thiếu thời gian)
```

### 3. Câu hỏi rất phức tạp (3+ điều kiện)
```
✅ TỐT:
- "Điểm lab 1 môn CPV301 học kỳ Fall2024"
- "Lịch học môn AIL303m tuần sau ca sáng"

🟡 MƠ HỒ:
- "Điểm lab 1 môn CPV301" (thiếu học kỳ)
```

## 🚨 CÁC TRƯỜNG HỢP ĐẶC BIỆT

### 1. Câu hỏi về môn học không tồn tại
```
Input: "Điểm danh môn XYZ123"
Response: "Môn học XYZ123 không có trong hệ thống. Vui lòng kiểm tra lại mã môn học."
```

### 2. Câu hỏi về thời gian chưa có dữ liệu
```
Input: "Lịch học tuần tới"
Response: "Chưa có dữ liệu lịch học cho tuần tới. Vui lòng kiểm tra lại thời gian."
```

### 3. Câu hỏi quá chung chung
```
Input: "Điểm của tôi"
Response: "Vui lòng chỉ định môn học cụ thể. Ví dụ: 'Điểm môn CSI105'"
```

### 4. Câu hỏi ngoài phạm vi
```
Input: "Học phí bao nhiêu?"
Response: "Hệ thống chỉ hỗ trợ tra cứu thông tin học tập. Vui lòng liên hệ phòng tài chính để biết thông tin học phí."
```

## 📊 THỐNG KÊ PATTERN

### Tần suất xuất hiện các pattern:
1. **Pattern đơn giản**: 60% (chỉ 1 điều kiện)
2. **Pattern phức tạp**: 30% (2 điều kiện)
3. **Pattern rất phức tạp**: 10% (3+ điều kiện)

### Tỷ lệ thành công:
- **🟢 TỐT**: 70% (có thể trả lời chính xác)
- **🟡 MƠ HỒ**: 20% (cần làm rõ)
- **🔴 SAI**: 10% (không thể trả lời)

## 🔧 KHUYẾN NGHỊ CẢI THIỆN

### 1. Cải thiện Intent Detection
- Thêm synonyms cho các từ khóa
- Cải thiện pattern matching
- Thêm context awareness

### 2. Cải thiện Response Generation
- Tạo template responses cho từng loại câu hỏi
- Thêm gợi ý cho câu hỏi mơ hồ
- Cải thiện error messages

### 3. Cải thiện User Experience
- Thêm autocomplete cho mã môn học
- Thêm calendar picker cho thời gian
- Thêm suggestion cho câu hỏi tiếp theo 