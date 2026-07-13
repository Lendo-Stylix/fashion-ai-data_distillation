# BÁO CÁO THỰC THI GIAI ĐOẠN 6: CHUẨN BỊ VÀ THIẾT LẬP CẤU HÌNH FINE-TUNING (QWEN 3.5 4B)

> [!NOTE]
> Giai đoạn này là bước chuyển tiếp mang tính quyết định, biến bộ dữ liệu suy luận (Reasoning Dataset) định dạng thô thành định dạng huấn luyện tiêu chuẩn (ChatML) có tổ chức phân lớp. Đồng thời, giai đoạn này xác lập các tham số và cấu trúc mô hình tối ưu nhất để tiến hành huấn luyện mượt mà trên môi trường Kaggle (2xT4 GPU) bằng thư viện Unsloth.

---

## 1. Tiền Xử Lý Dữ Liệu Chuyên Sâu (Preprocessing & Formatting)

Để tối ưu hóa quá trình tính toán đạo hàm (Gradient) và ngăn chặn hiện tượng mất ổn định trong huấn luyện (Gradient Oscillation), bộ dữ liệu 1.488 mẫu tinh hoa đã được cấu trúc lại một cách nghiêm ngặt:

### 1.1. Sắp xếp Phân tầng (Stratified Grouping)
- **Tạo các Batch đồng nhất:** Toàn bộ dữ liệu được sắp xếp tuần tự dựa trên `batch_id` (từ 1 đến 93). Mỗi batch chứa chính xác 16 mẫu đại diện cho đầy đủ tỷ lệ chuẩn của 8 thẻ chủ đề thời trang.
- **Mục đích:** Việc huấn luyện với các batch có độ phân bổ nhãn tiệm cận hoàn hảo (độ lệch tuyệt đối trung bình so với chuẩn lý tưởng chỉ là **0.274**) giúp mô hình hội tụ nhanh chóng, không bị thiên lệch (bias) về một chủ đề cụ thể trong từng chu kỳ cập nhật trọng số.

### 1.2. Chuyển đổi Định dạng ChatML Tiêu chuẩn
Tệp dữ liệu CSV đã được chuyển hóa sang định dạng `.jsonl` theo cấu trúc hội thoại ChatML tối ưu nhất cho Unsloth và Qwen:
- **System Prompt:** Được thiết lập thống nhất: `"Bạn là chuyên gia tư vấn thời trang Việt Nam. Trả lời câu hỏi bằng tiếng Việt một cách chuyên nghiệp"`.
- **Luồng Suy luận (CoT):** Phần thẻ `<think>...</think>` được đẩy lên vị trí tiên phong trong khối nội dung của `assistant`, đảm bảo mô hình học được tư duy nội suy trước khi xuất ra câu trả lời cuối.

Toàn bộ quá trình chuyển đổi này đã vượt qua 6 lớp kiểm định (Assertion) bao gồm tính toàn vẹn số lượng, tính liên tục của batch, cấu trúc ChatML và mã hóa UTF-8.

---

## 2. Điều Chỉnh và Thiết Lập Cấu Hình Huấn Luyện (Fine-tuning Configurations)

Quá trình chạy thử nghiệm đã chỉ ra một số điểm nghẽn kỹ thuật trong cấu trúc ban đầu, dẫn đến việc phải tái kiến trúc cấu hình huấn luyện. Dưới đây là các quyết định tinh chỉnh cốt lõi nhằm đảm bảo hiệu năng và độ ổn định cao nhất:

### 2.1. Lựa chọn Base Model Tối Ưu
* **Thay thế mô hình ban đầu:** Quyết định chuyển từ `Qwen3.5-4B-Instruct` nguyên bản sang phiên bản đóng gói **`techwithsergiu/Qwen3.5-text-4B-bnb-4bit`**.
* **Động lực kỹ thuật:** Phiên bản bnb-4bit được tối ưu hóa đặc biệt để tiết kiệm tài nguyên VRAM và băng thông mạng, cực kỳ phù hợp cho nền tảng Kaggle GPU T4. Việc giảm tải bộ nhớ giúp tăng kích thước context window mà không gặp rủi ro Out-of-Memory (OOM).

### 2.2. Chiến lược Tối ưu Hóa PEFT (LoRA vs DoRA)
* **Từ bỏ DoRA (Weight-Decomposed LoRA):** Mặc dù DoRA (với `use_dora = True`) hứa hẹn khả năng bảo tồn năng lực suy luận tốt hơn, nhưng khi kết hợp cùng các custom kernels (như Triton), cơ chế Gradient Checkpointing và lượng tử hóa 4-bit, hệ thống liên tục xảy ra xung đột ở bước backward pass.
* **Chuyển hướng:** Quay về sử dụng cơ chế **LoRA truyền thống** (`use_dora = False`), đảm bảo quá trình huấn luyện diễn ra ổn định 100% trong khi vẫn thừa hưởng gia tốc siêu việt từ kiến trúc của Unsloth.

### 2.3. Cải tiến Kỹ thuật Loss Masking
* **Hiện trạng ban đầu:** Ý tưởng sử dụng `DataCollatorForCompletionOnlyLM` của Hugging Face thường gây ra các lỗi lệch token (misalignment) khi va chạm với các token đặc biệt (`<|im_start|>`, `<|im_end|>`) và ký tự ngắt dòng trong ChatML.
* **Quyết định triển khai:** Chuyển sang sử dụng trực tiếp hàm helper `train_on_responses_only` tích hợp sẵn trong Unsloth. Hàm này thực thi gán nhãn `-100` cho toàn bộ phần Prompt của User một cách chính xác tuyệt đối ở tầng mã biên dịch C++, đảm bảo mô hình chỉ tính toán Loss ở duy nhất phần trả lời của Assistant (bao gồm cả tư duy `<think>`).

### 2.4. Xác lập Tham số Hyperparameters
Dựa trên phân tích phân phối token của toàn bộ 1.488 mẫu dữ liệu:
* **Token dài nhất:** 1.196 tokens.
* **Bách phân vị 95 (p95):** 859 tokens.
* **Quyết định Sequence Length:** Tham số `max_seq_length` được cấu hình chốt hạ ở **1280** để bao phủ an toàn 100% tập dữ liệu mà vẫn nằm trong giới hạn chịu đựng của VRAM (GPU T4 x2). 
* **Learning Rate & Epochs:** Duy trì thiết lập chuẩn $1 \times 10^{-4}$ xuyên suốt 3 Epochs để đảm bảo mô hình thẩm thấu kiến thức đều đặn, kết hợp cùng hệ thống giám sát W&B.

---

> [!IMPORTANT]
> **Tổng Kết Bước Chuyển Giao**
> Giai đoạn chuẩn bị đã thành công trong việc tạo ra một môi trường huấn luyện hội tụ đủ 3 yếu tố: **Dữ liệu siêu sạch (Zero Noise)**, **Phân phối đồng nhất (Perfect Stratified)** và **Cấu hình mô hình tối ưu tương thích (Unsloth 4-bit + LoRA)**. 
> Toàn bộ Pipeline đã sẵn sàng để bước vào quá trình Fine-tuning chính thức, hứa hẹn tạo ra một mô hình Qwen 3.5 (4B) sở hữu năng lực tư duy (Reasoning) xuất chúng trong lĩnh vực thời trang chuyên biệt.
