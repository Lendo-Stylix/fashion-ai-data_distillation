# BÁO CÁO THỰC THI GIAI ĐOẠN 5: KỸ THUẬT SINH LẬP LUẬN (REASONING GENERATION) VÀ XỬ LÝ SỰ CỐ TOKEN

> [!NOTE]
> Giai đoạn 5 đánh dấu bước ngoặt quan trọng nhất của đồ án: Sinh thêm luồng suy nghĩ (reasoning, thẻ `<think>`) cho 1488 dòng dữ liệu đã được làm sạch, phục vụ trực tiếp cho mô hình Qwen 3.5. Báo cáo này ghi lại chi tiết toàn bộ quá trình thử nghiệm, đối mặt với sự cố tốn kém token trên đám mây Alibaba, cho đến khi tìm ra giải pháp "Reverse Prompting".

---

## 1. Mục Tiêu Giai Đoạn 5
Chuyển đổi tập dữ liệu QA (Question-Answer) thông thường thành định dạng suy luận (Reasoning Dataset). Mỗi câu trả lời của Trợ lý ảo Thời trang cần được bắt đầu bằng một thẻ `<think>...</think>` chứa các bước phân tích logic (hiểu nhu cầu khách hàng -> xác định vấn đề -> đề xuất giải pháp) trước khi đưa ra câu trả lời cuối cùng.

---

## 2. Iteration 1: Thử nghiệm ban đầu với Alibaba Qwen (Thất bại)

### 2.1. Phương pháp tiếp cận
Ban đầu, hệ thống được thiết kế với cơ chế "Smart Model Router" nhằm lợi dụng sức mạnh của dòng Qwen 3.7 Max và xoay tua tự động (fallback) sang một só phiên bản Qwen 3.7 khác để vượt qua giới hạn Rate Limit và Quota của Alibaba. 
* Hệ thống xử lý song song 16 luồng với cơ chế Lock Thread-Safe.
* Yêu cầu mô hình trả về luồng suy nghĩ nội bộ (internal thinking) trực tiếp.

### 2.2. Sự cố và Rủi ro (The Disaster)
Mặc dù hệ thống định tuyến (Router) hoạt động trơn tru về mặt kết nối, nhưng **kết quả dữ liệu (Dataset) lại là một thảm họa**:
1. **Bilingual Thinking (Loạn Ngôn Ngữ):** Thay vì suy nghĩ bằng tiếng Việt, các mô hình Cloud lớn liên tục "tư duy" bằng tiếng Anh hoặc trộn lẫn Anh - Việt một cách lộn xộn. (Ví dụ: ID=398 suy nghĩ 100% bằng tiếng Anh).
2. **Cạn kiệt Quota:** Việc kích hoạt chế độ "reasoning" (internal thinking) của mô hình Qwen 3.7 Max đã tiêu tốn một lượng token khổng lồ. Chỉ trong thời gian ngắn, hệ thống đã ngốn **hơn 10 triệu tokens** quota trên Alibaba nhưng kết quả không thể sử dụng.
3. **Phân mảnh dữ liệu do Fallback:** Khi Qwen 3.7 Max hết Quota, Router buộc phải đẩy các câu hỏi sang các model cùng cấp nhưng phiên bản cũ hơn. Điều này dẫn đến sự thiếu đồng nhất nghiêm trọng về chất lượng suy luận giữa các dòng dữ liệu, khiến tập data trở nên hỗn loạn.

---

## 3. Iteration 2: Tái cấu trúc hệ thống - Pipeline Ver 3 (Thành công)

Nhận thấy hướng đi dùng Qwen Smart Router không khả thi, chúng tôi đã loại bỏ hoàn toàn mã nguồn cũ và thiết kế lại **Pipeline Ver 3** với nguyên tắc cốt lõi: **Sử dụng 1 mô hình duy nhất và tách bạch quá trình suy nghĩ.**

### 3.1. Thiết kế mới: Quy trình 3 bước (Reverse Prompting)
Thay vì yêu cầu mô hình thực hiện đồng thời việc suy luận và trả lời (dẫn đến vượt quá giới hạn token và lỗi ngôn ngữ), Pipeline Ver 3 ứng dụng mô hình `tencent/hy3:free` (Hunyuan 3) qua OpenRouter theo quy trình 3 bước:
* **Bước 1 (Gen Answer):** Không kích hoạt thẻ reasoning. Chỉ yêu cầu mô hình thiết lập câu trả lời chuyên môn (A_Cloud) nhằm tối ưu hóa lượng token.
* **Bước 2 (Judge - Đánh giá 2 tiêu chí):** Sử dụng mô hình để đối chiếu câu trả lời vừa tạo (A_Cloud) với câu trả lời gốc (A_Dataset). Lựa chọn câu trả lời tối ưu nhất (A_Final).
* **Bước 3 (Reverse Prompting - Suy luận ngược):** Đây là kỹ thuật cốt lõi. Đưa Câu hỏi (Q) và Câu trả lời cuối cùng (A_Final) trở lại mô hình, yêu cầu mô hình mô phỏng các bước phân tích logic hoàn toàn bằng Tiếng Việt để tái tạo quá trình dẫn đến câu trả lời đó (150-400 từ). 

### 3.2. Xử lý rào cản Internal Thinking của HY3
Dù đã áp dụng cơ chế Reverse Prompting, mô hình Hunyuan 3 (được tinh chỉnh để suy luận sâu) vẫn duy trì cơ chế suy nghĩ ẩn nội bộ (Internal Thinking) trước khi xuất ra thẻ `<think>` hiển thị. Điều này gây ra lỗi `PARSE_ERROR` do vượt quá giới hạn `max_tokens = 1024`.
* **Giải pháp:** Dựa trên kết quả phân tích từ Pilot Run, hệ thống đã điều chỉnh tăng giới hạn token: Cấu hình `max_tokens` của Bước Judge lên 2500 và Bước Reverse lên 4000 để đáp ứng dung lượng suy luận ngầm của mô hình, đồng thời đảm bảo không gian cho kết quả JSON và thẻ suy nghĩ hiển thị.

---

## 4. Kết quả Cuối cùng
* Xử lý thành công 100% (1488/1488 dòng).
* **Chất lượng:** Toàn bộ thẻ `<think>` đều mạch lạc, có tổ chức, và **100% bằng tiếng Việt**, không còn chèn từ khóa tiếng anh hay lặp ý.
* **Tỷ lệ Verdict (Sau khi Verified/Rescue 229 lỗi PARSE_ERROR ban đầu):** 
  * Ưu tiên dùng câu gốc (DATASET_SUPERIOR): 40.3% (600 mẫu)
  * Ưu tiên dùng câu do Cloud sinh (CLOUD_SUPERIOR): 36.9% (549 mẫu)
  * Chất lượng tương đương (VERIFIED_EQUAL): 22.8% (339 mẫu)
* **Nguồn câu trả lời cuối cùng (A_Final):**
  * Sử dụng A_Cloud: 59.7% (888 mẫu)
  * Sử dụng A_Dataset: 40.3% (600 mẫu)
* **Chi phí:** Tổng token sử dụng hơn 9 triệu tokens, nhưng hoàn toàn **MIỄN PHÍ** nhờ khả năng tối ưu hóa API qua Free Tier của OpenRouter.

Giai đoạn 5 đã kết thúc trọn vẹn, xuất ra tệp `final_distilled_reasoning_1488_v3.csv` (và chuyển đổi thành định dạng ChatML `.jsonl`) sẵn sàng cho bước Fine-tune Qwen 3.5.
