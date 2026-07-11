# Báo Cáo Kỹ Thuật: Xử Lý Tags "Khác" (Phase 2)

Tài liệu này lưu trữ lại quy trình thực thi Giai đoạn 2 (đã hoàn tất) nhằm mục đích phục vụ cho việc viết Báo Cáo Đồ Án (Technical Report) sau này. Không dùng để chạy code trong thực tế nữa.

## 1. Vấn Đề Gặp Phải (Problem Statement)
Sau khi chạy đánh giá 10,000 dòng dữ liệu gốc với 5 Categories cơ bản ban đầu (`Dáng người`, `Hoàn cảnh`, `Kiến thức cơ bản`, `Phong cách`, `Khác`), một lượng lớn (hàng ngàn dòng) câu hỏi bị model phân loại chung chung vào nhóm **"Khác"**.
Điều này làm mất đi tính phân tầng (Stratified) cần thiết của dataset Thời trang, khiến nhóm dữ liệu này khó có thể được lấy mẫu chuẩn xác.

## 2. Giải Pháp: Fallback & Resolution (Phase 2)
Chúng tôi đã mở rộng Rubric và thêm 5 Categories chuyên sâu hơn để "bắt" các câu hỏi đang nằm trong nhóm "Khác":
- `Làm đẹp & Chăm sóc cá nhân`
- `Phong thái & Tâm lý`
- `Mua sắm & Quản lý tủ đồ`
- `Bảo quản & Thời trang bền vững`
- `Phong cách sống`

## 3. Quy Trình Kỹ Thuật (Đã thực thi qua script `run_phase2.py` cũ)
1. **Lọc Dữ Liệu:** Script quét file `evaluated_dataset.csv`, lấy ra danh sách toàn bộ ID của các dòng chứa tag `Khác`.
2. **Chấm Điểm Lại:** Gửi các ID này qua Gemini API (Gemma 4 31B) kèm theo bộ Rubric mở rộng (gồm cả 10 categories).
3. **Ghi Đè Kết Quả (Merge):** Script `merge_and_stats.py` lấy kết quả vừa sinh ra ở Phase 2 (`evaluated_dataset_phase2_temp.csv`) để đè lên các dòng cũ bị tag `Khác` trong file CSV chính.
4. **Kết Quả:** Gần như toàn bộ các dòng "Khác" đã được tái phân loại thành công vào 5 chủ đề ngách, tăng tính đa dạng (Diversity) cho dataset.
