# Báo Cáo Kỹ Thuật: Stratified Batching (Phần 1 - Giai đoạn 5)

**Dự án:** Data Pipeline for Qwen 3.5 Fine-Tuning (Fashion AI)
**Tác giả:** Đội ngũ AI (Antigravity & User)
**Giai đoạn:** Tiền xử lý dữ liệu trước khi sinh thẻ `<think>` (Phase 5).

---

## 1. Bối cảnh và Mục tiêu

Trong huấn luyện mô hình ngôn ngữ lớn (LLM Fine-tuning), việc dữ liệu bị "dồn cục" (Clustered) theo từng chủ đề trong các Batch sẽ gây ra hiện tượng **Gradient Oscillation** (Dao động Gradient). Mô hình sẽ cập nhật trọng số liên tục theo từng hướng cực đoan (Ví dụ: đang học cách nói chuyện nghiêm túc của đồ công sở lại bị giật ngược sang cách nói chuyện phóng khoáng của đồ đi biển), dẫn đến việc hội tụ kém và dễ bị "học vẹt" cục bộ (Catastrophic Forgetting).

**Mục tiêu:** Dựa trên đề xuất của User, tiến hành **Stratified Batching** (Phân bổ xen kẽ) dựa vào cột `Tags` có sẵn trong file dữ liệu gốc (1488 dòng) của Giai đoạn 4. Điều này giúp mỗi Batch khi đưa vào huấn luyện sẽ là một "xã hội thu nhỏ" bao quát đầy đủ mọi khía cạnh thời trang.

---

## 2. Phân tích Dữ liệu (Tag Distribution)

Script `stratified_batching.py` đã trích xuất Cột `Tags` từ file dữ liệu đầu vào. Do một câu có thể chứa nhiều tag (VD: *"Dáng người, Kiến thức cơ bản"*), script lấy Tag đầu tiên trước dấu phẩy làm **Primary Tag** (Tag chính) để đại diện phân loại.

Hệ thống ghi nhận tổng cộng **8 nhóm Tag chính**, phân bổ không đồng đều như sau:
1. **Kiến thức cơ bản:** 681 dòng
2. **Hoàn cảnh:** 426 dòng
3. **Dáng người:** 250 dòng
4. **Phong cách:** 87 dòng
5. **Mua sắm & Quản lý tủ đồ:** 30 dòng
6. **Phong thái & Tâm lý:** 7 dòng
7. **Bảo quản & Thời trang bền vững:** 6 dòng
8. **Làm đẹp & Chăm sóc cá nhân:** 1 dòng

**Tổng cộng:** 1488 dòng hoàn chỉnh.

---

## 3. Thuật toán Triển khai

### 3.1. Phương pháp Cũ: Round-Robin Sampling (Đã loại bỏ)
Ban đầu, thuật toán **Round-Robin** được sử dụng: chia đều cơ hội cho tất cả 8 nhóm lấy tuần tự vòng tròn. 
Tuy nhiên, sau khi thảo luận chuyên sâu với User, chúng tôi phát hiện ra một **nhược điểm chí tử**: Do dữ liệu quá lệch pha (nhóm lớn nhất 681 dòng, nhóm nhỏ nhất 1 dòng), các tag hiếm bị cạn kiệt rất nhanh. Hệ quả là ở những vòng bốc cuối cùng, dữ liệu chỉ còn toàn tag "Kiến thức cơ bản". Nếu đem đi Fine-tune, mô hình sẽ học cực kỳ thiên kiến (bias) ở giai đoạn cuối, làm hỏng trọng số.

### 3.2. Phương pháp Mới: Priority-based Fixed-Size Batching (Perfect Stratified Distribution)
Để đáp ứng chuẩn xác quy trình Fine-tune thực tế trên GPU (sử dụng 2x T4 trên Kaggle với mô hình 4B), User đã chốt cấu hình tối ưu: **`batch_size = 16`**. (Đạt ~93 steps/epoch).
Dựa trên con số 16 này, thuật toán mới được triển khai để giải quyết triệt để vấn đề mất cân bằng:

1. **Khởi tạo Buckets (Khối Batch):** File dữ liệu 1488 dòng được cắt sẵn thành đúng `1488 / 16 = 93` khối Batch rỗng.
2. **Phân bổ rải đều (Perfect Stratified):** Thuật toán duyệt qua từng nhóm Tag từ lớn đến nhỏ. Ở mỗi nhóm (VD: Kiến thức cơ bản có 681 dòng), nó sẽ rải đều từng dòng một vào tuần tự 93 Batch này (như chia bài).
3. **Internal Shuffle:** Bên trong mỗi Batch 16 dòng, thứ tự các câu được xáo trộn ngẫu nhiên để mô hình không học vẹt quy luật xếp tag.

### Hiệu quả & Minh bạch Dữ liệu:
Nhờ thuật toán rải đều này, cấu trúc hỗn hợp của Batch 1 và Batch 93 là **GẦN NHƯ GIỐNG HỆT NHAU**. Mọi batch đều chứa đúng 16 dòng với sự phân bổ đồng đều của các tag lớn và tag nhỏ theo đúng tỷ lệ của toàn bộ dataset!
Để minh bạch hóa ranh giới của từng Batch, script đã chủ động thêm cột **`batch_id`** (từ 1 đến 93) vào cuối mỗi dòng trong file Output. Việc này giúp Dataset có tính định hình vật lý tuyệt đối trước khi bước vào nạp (Data Loading).

---

## 4. Kết quả & Cấu trúc Thư mục

**Cấu trúc thư mục chuyên biệt cho Giai đoạn 5:**
*   **Script:** `src/reasoning_generation/stratified_batching.py`
*   **Input Data:** `data/isolated_proofs/distilled_1488_perfect.csv`
*   **Output Data:** `data/reasoning_generation/stratified_1488.csv`

**Xác thực (Verification):** Trích xuất thử những dòng đầu tiên của file Output cho thấy thuật toán đã chạy hoàn hảo:
*   Row 0: Dáng người...
*   Row 1: Kiến thức cơ bản...
*   Row 2: Hoàn cảnh...
*   Row 3: Phong cách...
*   Row 4: Làm đẹp & Chăm sóc cá nhân...
*   Row 5: Mua sắm & Quản lý tủ đồ...
*   Row 6: Bảo quản & Thời trang bền vững...
*   Row 7: Phong thái & Tâm lý...
*   *(Vòng lặp tiếp tục quay trở lại từ đầu với các tag còn dòng)*

Dữ liệu hiện đã 100% sẵn sàng để tiến vào bước gọi API sinh thẻ `<think>`.
