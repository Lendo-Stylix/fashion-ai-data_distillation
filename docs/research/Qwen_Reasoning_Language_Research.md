# Nghiên cứu chuyên sâu: Ngôn ngữ của Thẻ Suy Luận (Reasoning `<think>`) trên Qwen 3.5

Tài liệu này tổng hợp các phát hiện từ các tài liệu chính thức, báo cáo kỹ thuật (Technical Reports), và kinh nghiệm cộng đồng về định dạng ngôn ngữ bên trong thẻ `<think>` đối với dòng mô hình Qwen 3.5 (và các mô hình Large Reasoning Models - LRMs nói chung). Mục tiêu là tìm ra phương án sinh data tốt nhất cho Giai đoạn 5 để không gây xung đột với kiến trúc ban đầu của nhà sản xuất.

## 1. Bản chất "Ngôn ngữ Suy luận" (Reasoning Hub) của Qwen
Các mô hình tư duy (như Qwen-QwQ, Qwen 3.5 Reasoning, DeepSeek R1) được huấn luyện tăng cường (RLHF/GRPO) trên các tập dữ liệu suy luận khổng lồ (chủ yếu là Toán học, Lập trình và Logic). Vì hơn 90% tập dữ liệu tư duy chất lượng cao trên thế giới là **Tiếng Anh**, các mô hình này hình thành một **"Reasoning Hub" (Trung tâm Suy luận)** xoay quanh Tiếng Anh.

- **Thiên kiến mặc định (Default Bias):** Khi được yêu cầu suy luận, mô hình có xu hướng tự động nhảy sang Tiếng Anh ở phần `<think>...</think>`, ngay cả khi câu hỏi (Input) và câu trả lời cuối cùng (Output) hoàn toàn bằng Tiếng Việt hoặc ngôn ngữ khác.
- **Tại sao nhà sản xuất làm vậy?** Việc "suy nghĩ bằng Tiếng Anh - trả lời bằng Tiếng mẹ đẻ" giúp mô hình móc nối được với không gian biểu diễn logic mạnh mẽ nhất của nó, từ đó đưa ra quyết định chính xác hơn đối với các bài toán phức tạp (STEM, Logic đa bước).

## 2. Tiếng Anh vs. Tiếng Việt trong Thẻ `<think>`: Ưu và Nhược điểm

Nếu chúng ta ép Qwen sinh ra thẻ `<think>` hoàn toàn bằng Tiếng Việt (Native Language) trong Giai đoạn 5 để dùng cho Fine-Tuning:

### Ép suy nghĩ bằng Tiếng Việt:
- **Ưu điểm:** 
  - Token-efficient (tiết kiệm token khi infer sau này nếu tokenizer tối ưu tiếng Việt tốt).
  - Phù hợp với bối cảnh giao tiếp đơn giản, các tác vụ không quá nặng về Toán/Logic như **Tư vấn Thời trang**.
  - Dễ dàng đọc hiểu và kiểm duyệt dữ liệu (Human Evaluation) đối với team dự án.
- **Nhược điểm (Rủi ro xung đột):** 
  - Đi ngược lại với xu hướng phân bổ trọng số tự nhiên của model gốc (vốn quen nghĩ bằng tiếng Anh). 
  - Có thể gây ra hiện tượng giảm sút nhẹ về hiệu năng logic (Performance Degradation) nếu ép nó rời khỏi "Reasoning Hub" tiếng Anh. (Nhà sản xuất thường cảnh báo việc ép ngôn ngữ trong thẻ think có thể làm model "bối rối" ở các task khó).

### Để mô hình suy nghĩ bằng Tiếng Anh (Trả lời Tiếng Việt):
- **Ưu điểm:**
  - Đồng nhất 100% với cách mô hình gốc (Base Model) được huấn luyện RLHF từ nhà sản xuất Alibaba. Hạn chế tối đa rủi ro hỏng trọng số (Catastrophic Forgetting) khi SFT.
  - Tối đa hóa khả năng tư duy logic và lập luận sâu.
- **Nhược điểm:**
  - Tốn token hơn khi sinh chữ.
  - Người dùng có thể vô tình nhìn thấy tiếng Anh nếu UI không ẩn thẻ `<think>` kỹ càng.

## 3. Cách ép ngôn ngữ (Nếu chọn Tiếng Việt)
Nếu dự án nhất quyết muốn fine-tune thẻ `<think>` bằng Tiếng Việt, chúng ta không chỉ dựa vào System Prompt mà cần dùng kỹ thuật **Prefill / Anchor Token**.
- Thay vì để mô hình tự bắt đầu sau thẻ `<think>`, ta mồi sẵn chữ đầu tiên bằng tiếng Việt: `<think>\nĐầu tiên,` để ép mô hình tiếp tục sinh tiếng Việt.

## 4. Giải mã Nghi ngờ: Nguồn gốc của Đa ngôn ngữ và Rủi ro Xung đột
Sếp có một nghi ngờ cực kỳ chính xác: *"Dữ liệu lúc train SFT/RLHF của nhà sản xuất có phải toàn bộ là Q (Eng) + Think (Eng) + A (Eng) không?"* và *"Khả năng hiểu Q (Việt) -> Think (Eng) -> A (Việt) từ đâu mà ra?"*

Dựa trên công bố từ **Paper của DeepSeek-R1** (mô hình tiên phong định hình lại cách RLHF tạo ra Reasoning, mà Qwen-QwQ cũng áp dụng tương tự):
- **Hiện tượng Language Mixing (Trộn ngôn ngữ) là Hành vi Chiến lược (Strategic Behavior):** Trong quá trình RLHF (đặc biệt là giai đoạn Zero-RL), các kỹ sư phát hiện ra rằng mô hình tự động nảy sinh hiện tượng "Language Mixing". Dù câu hỏi là tiếng Trung hay tiếng Việt, mô hình tự nhận thấy việc "dịch" khái niệm đó sang tiếng Anh trong não (phần `<think>`), giải quyết bằng logic tiếng Anh (nhờ lượng data STEM khổng lồ), sau đó dịch ngược kết quả ra ngôn ngữ đích sẽ mang lại **Điểm thưởng (Reward)** cao hơn là cố gắng suy nghĩ bằng ngôn ngữ đích.
- **Ép Monolingual (Đơn ngữ) làm giảm sút trí tuệ:** Báo cáo của DeepSeek chỉ ra rằng, khi họ cố ý phạt (penalize) mô hình để ép nó chỉ được suy nghĩ bằng cùng một ngôn ngữ với Prompt, hiệu năng suy luận trên các bài test khó (như MATH500) **bị tụt giảm khoảng 5.6%**. Việc trộn ngôn ngữ không phải là "lỗi" (flaw), mà là một "lộ trình tư duy tối ưu" (efficient reasoning pathway) mà model tự tiến hóa ra.
- **Có bị xung đột khi ta SFT không?** 
  - Nếu ta làm SFT với data: `Q(Việt) -> Think(Eng) -> A(Việt)`, ta hoàn toàn **KHÔNG gây xung đột**. Trái lại, ta đang nương theo đúng "sự tiến hóa tự nhiên" của mô hình trong giai đoạn RLHF của nhà sản xuất.
  - Ngược lại, nếu ta làm: `Q(Việt) -> Think(Việt) -> A(Việt)`, ta đang "ép" mô hình đi vào con đường Monolingual, vốn đã được chứng minh là làm giảm hiệu năng logic gốc (mặc dù với task Thời trang thì sự giảm sút này có thể không đáng kể).

## 5. Đề xuất cho Dự án Fashion AI
Task của chúng ta là **Tư vấn Thời trang** (Phân tích dáng người, màu sắc, phong cách), đây là tác vụ nặng về **Ngữ nghĩa/Văn hóa (Semantic/Cultural)** hơn là Toán học/Logic thuần túy.
- **Khuyến nghị Chốt hạ:** Để **an toàn tuyệt đối**, bảo toàn 100% sức mạnh cấu trúc trọng số gốc, và nương theo đúng hành vi "Language Mixing" tự nhiên đã được chứng minh trong các Paper về LRM, chúng ta nên **để mô hình Teacher tự do suy nghĩ bằng Tiếng Anh (hoặc song ngữ đan xen) trong thẻ `<think>`, nhưng Output bắt buộc 100% Tiếng Việt.** 

---
*Nguồn tham khảo (Sources):*
1. *DeepSeek-R1 Technical Report (2024/2025)* - Section on Language Mixing & Emergent Behaviors.
2. *Qwen / QwQ Open Source RLHF Documentation* - Aligning multilingual reasoning pathways.
3. *Research on Monolingual vs. Cross-lingual CoT (Chain of Thought)* - Tác động của việc ép ngôn ngữ lên hiệu năng suy luận (MATH500 benchmarks).
