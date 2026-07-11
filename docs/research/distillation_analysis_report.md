# Báo Cáo Chuyên Sâu: Lý thuyết Chưng Cất Dữ Liệu (Data Distillation)
*(Dành cho việc tuyển chọn dataset Fine-tune Qwen 3.5)*

Trong giới nghiên cứu LLM hiện nay, quan điểm "càng nhiều dữ liệu càng tốt" (Quantity-driven) đã lỗi thời. Các phòng nghiên cứu hàng đầu đều chuyển sang trường phái "ít nhưng chất" (Quality-driven). Dưới đây là phân tích chi tiết về 2 bài báo "chuẩn vàng" tạo nên nền tảng cho chiến lược chưng cất của chúng ta.

---

## 1. LIMA (Less Is More for Alignment)
LIMA là một báo cáo nổi tiếng từ Meta AI và Carnegie Mellon University. LIMA đánh sập lầm tưởng rằng "muốn dạy model giao tiếp tốt thì phải cần hàng trăm nghìn mẫu hội thoại".

### Giả thuyết cốt lõi (Superficial Alignment Hypothesis)
LIMA cho rằng:
> *Toàn bộ kiến thức lõi và khả năng suy luận của mô hình đã được học hết ở giai đoạn Pre-training (huấn luyện trước trên hàng nghìn tỷ token).* 
> *Giai đoạn Fine-tuning (Alignment) chỉ đóng vai trò dạy model "cách định dạng" (format) và "phong cách" (style) để moi cái kiến thức lõi đó ra mà thôi.*

### Minh chứng
- Họ chỉ dùng đúng **1,000 mẫu dữ liệu** được tuyển chọn cực kỳ kỹ lưỡng bằng tay (câu hỏi đa dạng, câu trả lời sâu sắc, đúng định dạng).
- Fine-tune LLaMA-65B trên 1,000 mẫu này.
- Kết quả: Model này vượt trội hơn cả các model được train trên 50,000 mẫu, và cạnh tranh ngang ngửa với GPT-4 trong nhiều tình huống, **thậm chí không cần dùng thuật toán RLHF**.

### 💡 Áp dụng vào Project của chúng ta:
Chúng ta đang có 10,000 mẫu. Theo triết lý LIMA, thay vì ném cả 10k mẫu vào (kèm theo rác và tạp âm), ta chỉ nên chưng cất ra **khoảng 1,000 - 1,500 mẫu hoàn hảo nhất**. Việc dùng số lượng nhỏ nhưng chất lượng cao sẽ giúp Qwen 3.5 bắt chước được "phong cách stylist chuyên nghiệp" mà không bị pha loãng bởi các câu trả lời hời hợt.

---

## 2. DEITA (Data-Efficient Instruction Tuning for Alignment)
Nếu LIMA nói rằng "chỉ cần 1,000 mẫu", thì câu hỏi đặt ra là: *"Làm sao dùng máy tính để tự động tìm ra 1,000 mẫu đó từ một đống 10,000 mẫu?"* 
Đó là lúc DEITA ra đời. DEITA cung cấp một công thức toán học để chấm điểm và lọc dữ liệu tự động.

### 3 Chiều Đánh Giá (3 Dimensions)
DEITA yêu cầu mỗi mẫu dữ liệu phải được chấm điểm theo 3 trục:

1. **Complexity (Độ phức tạp của câu hỏi):**
   - Câu hỏi cơ bản: *"Phối màu gì với màu đen?"* (Thấp)
   - Câu hỏi phức tạp: *"Tôi cao 1m50, vai rộng, da ngăm, muốn phối đồ đi tiệc cưới vào mùa đông. Nên mặc gì?"* (Cao)
   - DEITA ưu tiên giữ lại các câu hỏi khó để ép model phải reasoning.

2. **Quality (Chất lượng của câu trả lời):**
   - Trả lời phải đúng, cấu trúc rõ ràng, sử dụng từ ngữ chuyên ngành (đây chính là tiêu chí **Độ chi tiết** và **Từ vựng** mà ta vừa dùng Gemma để chấm).

3. **Diversity (Sự đa dạng):**
   - Không được phép lấy 1,000 mẫu toàn về "cách mặc áo thun". Phải rải đều qua các chủ đề: Đồ công sở, dạ hội, phối màu, làm đẹp, giặt giũ...
   - Nếu bị thiếu (ví dụ: nhóm Làm Đẹp quá ít), phải **oversample** (lấy hết mọi mẫu có thể) để bù vào.

---

## 3. Tại sao hai phương pháp này cần thiết?

Việc kết hợp DEITA (dùng làm thuật toán bộ lọc) và LIMA (dùng làm mốc giới hạn số lượng) mang lại 3 lợi ích khổng lồ:
1. **Tiết kiệm chi phí Compute:** Train 1,500 dòng tốn chưa tới 1/5 thời gian so với train 10,000 dòng.
2. **Khắc phục catastrophic forgetting:** Train quá nhiều data rác (hoặc data thuần Q&A không suy luận) sẽ làm Qwen 3.5 quên mất sự thông minh gốc của nó.
3. **Mở đường cho `<think>` tag:** Sau khi lọc ra 1,500 dòng tinh hoa, ta mới đủ ngân sách để gọi API xịn (như GPT-4o hoặc Claude 3.5) để sinh ra bước suy luận `<think>...</think>` cho từng dòng, hoàn thiện file train cuối cùng.
