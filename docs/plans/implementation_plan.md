# Chiến dịch Lọc & Đánh giá Dữ liệu 10k bằng Gemma 4 31B

Chiến dịch này sẽ khởi chạy script `run_gemma_eval.py` xuyên đêm với sự giám sát tự động để hoàn thành việc chấm điểm 10.000 dòng dữ liệu, sau đó thực hiện thống kê và chắt lọc (distill) ra 1.000 dòng chất lượng nhất phục vụ fine-tune.

## Đề xuất Kế hoạch

**Giai đoạn 1: Chạy Xuyên Đêm & Fallback API**
- Script `run_gemma_eval.py` đã được trang bị cơ chế tự động xoay vòng API Key khi gặp lỗi 429 (Rate Limit).
- Mọi batch bị hư hại (model format sai, thiếu ID) sẽ tự động được log vào `failed_batches.json` để không làm gián đoạn tiến trình.
- Tôi sẽ sử dụng công cụ `schedule` để tự động thức dậy kiểm tra file log vào sáng mai nhằm sửa lỗi hoặc chạy lại các batch thất bại.

**Giai đoạn 2: Xử lý Fallback & Triệt tiêu nhãn "Khác"**
- *Nhật ký Hoạt động Xuyên Đêm:* Mọi hành động tôi làm khi thức dậy (check file nào, chạy bao nhiêu câu bị lỗi, tạo tag mới nào) đều sẽ được tôi cẩn thận ghi chép lại vào file `night_shift_log.md`. Sáng mai bạn chỉ cần đọc đúng file này là nắm toàn bộ tình hình, không cần lặn ngụp tìm kiếm trong đống log hệ thống hay CSV dài dằng dặc.
- *Quét Fallback:* Sau khi hoàn thành 10.000 dòng, tôi sẽ rà soát `failed_batches.json`. Quá trình này sẽ gom các ID lỗi thành các batch 5 mới và chạy lại cho đến khi file fallback hoàn toàn trống rỗng.
- *Triệt tiêu nhãn "Khác":* Lọc ra toàn bộ các câu bị gán tag "Khác". Tôi sẽ phân tích (clustering) để tìm ra các nhóm chủ đề mới (ví dụ: Phụ kiện, Nơi chốn...). Bổ sung các tag mới này vào Rubric và ép model chạy lại CHỈ TRÊN các dòng "Khác" này. Quá trình lặp lại cho đến khi nhãn "Khác" bị triệt tiêu (hoặc chỉ còn tỷ lệ không đáng kể).

**Giai đoạn 3: Phân tích Chất lượng & Lập 2 Bản Kế Hoạch Distill**
*(Lưu ý: Giai đoạn này đích thân TÔI (AI Assistant) sẽ đứng ra phân tích, KHÔNG gọi thêm bất kỳ LLM API ngoại vi nào vào can thiệp).*
- Tôi sẽ chạy script để lấy bảng phân bổ thống kê thô của bộ 10k dòng. 
- Sau khi có số liệu thực tế trong tay, **TÔI sẽ trực tiếp tham gia phân tích và thiết kế 2 Bản Kế Hoạch:**
  - **Plan 1 (Chất lượng thực tế):** Tôi sẽ dùng tư duy phân tích của mình để đánh giá xem trong 10k dòng, có bao nhiêu dòng thực sự chất lượng và xứng đáng được giữ lại.
  - **Plan 2 (Tỷ Lệ Vàng 1k Dòng):** Tôi sẽ tự động tra cứu các bài báo khoa học, phương pháp luận chuẩn mực nhất về Data Distillation. Từ đó, tôi sẽ tính toán ra một **tỷ lệ phân bổ vàng** phù hợp với số liệu của Plan 1, kèm theo **lý luận giải thích cực kỳ chi tiết (detailed reasoning)** vì sao tôi chọn con số đó.
- **Xuất Báo Cáo & Chờ Đợi:** Mọi phân tích, lập luận khoa học và tỷ lệ đề xuất của Plan 1 & Plan 2 sẽ được tôi **viết hẳn ra thành một file báo cáo chuyên nghiệp (`distillation_analysis_report.md`)**. Sáng mai bạn chỉ cần mở file này lên để đọc, ngẫm nghĩ và chúng ta sẽ cùng chốt phương án cuối cùng!

---

## Phân tích & Góp ý (Xem chat để biết chi tiết)
Kế hoạch của bạn là một workflow chuẩn mực của một kỹ sư xử lý dữ liệu AI. Tôi đã cập nhật trọn vẹn vào Plan. Bạn hãy gõ lệnh `/goal` để chúng ta khóa mục tiêu và tiến hành viết lại script `run_gemma_eval.py` cho chuẩn với cơ chế nạp ID lẻ nhé!
