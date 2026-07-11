# Rubric Đánh Giá Dữ Liệu Thời Trang (LLM Evaluator: Gemma)

Dưới đây là bộ tiêu chí (Rubric) sẽ được sử dụng trực tiếp làm Prompt cho LLM để chấm điểm từng dòng dữ liệu trong tập 10k Q&A.

## 1. Tiêu chí 1: Độ chi tiết của câu trả lời (Thang 1-3)
*(Tiêu chí quyết định xem data có đủ độ sâu để làm bước đệm cho thẻ `<think>` hay không)*
*   **1 điểm:** Trả lời ngắn gọn, chung chung, đi thẳng vào vấn đề mà không giải thích nhiều.
*   **2 điểm:** Trả lời có cấu trúc tốt, có giải thích cơ bản và phân tách các ý.
*   **3 điểm:** Câu trả lời cực kỳ chi tiết, phân tích đa chiều, đưa ra lời khuyên cụ thể và mở rộng thêm kiến thức.

## 2. Tiêu chí 2: Độ khó của ngữ cảnh (Thang 1-3)
*(Tiêu chí đo lường vấn đề của người dùng có đòi hỏi sự phân tích logic nhiều bước hay không)*
*   **1 điểm:** Hỏi kiến thức chung (Vd: Quần ống loe là gì?).
*   **2 điểm:** Nhờ tư vấn theo sở thích (Vd: Tôi thích màu đỏ, nên phối quần màu gì?).
*   **3 điểm:** Nêu ra khuyết điểm cơ thể hoặc hoàn cảnh khó khăn cần giải quyết (Vd: Tôi đùi to nhưng phải mặc váy đi sự kiện, làm sao che khuyết điểm?).

## 3. Tiêu chí 3: Độ đa dạng từ vựng chuyên ngành (Thang 1-3)
*(Tiêu chí giúp loại bỏ những câu có văn phong nhạt nhẽo, ưu tiên văn phong của stylist)*
*   **1 điểm:** Dùng từ vựng giao tiếp bình thường (quần, áo, giày, màu sắc).
*   **2 điểm:** Có sử dụng một vài từ ngữ chuyên môn (tôn dáng, phối màu tương phản, form dáng cơ bản).
*   **3 điểm:** Sử dụng nhiều từ vựng chuyên sâu (silhouette, mid-rise, selvedge denim, color-blocking, dress-code...).

## 4. Tiêu chí 4: Chủ đề (Category Tags)
*(Ép buộc model phân loại dữ liệu để phục vụ việc lấy mẫu Stratified Sampling sau này. Model được thoải mái chọn không giới hạn số lượng tag phù hợp từ danh sách dưới đây, phân cách bằng dấu phẩy. Đối với những câu bị gán nhãn "Khác", ta sẽ có bước phân tích thứ hai sau khi chạy xong để khám phá thêm các cụm chủ đề mới)*
1. `Dáng người` (Khắc phục khuyết điểm, định hình vóc dáng)
2. `Hoàn cảnh` (Công sở, tiệc tùng, dạo phố, thể thao...)
3. `Kiến thức cơ bản` (Chất liệu, màu sắc, định nghĩa thời trang...)
4. `Phong cách` (Timeless, Classic, Minimalism, Vintage...)
5. `Phong thái & Tâm lý` (Tự tin, ngôn ngữ cơ thể, tư thế, thần thái...)
6. `Làm đẹp & Chăm sóc cá nhân` (Tóc, nước hoa, trang điểm, skincare...)
7. `Mua sắm & Quản lý tủ đồ` (Ngân sách, sắp xếp, dọn dẹp, chọn size...)
8. `Bảo quản & Thời trang bền vững` (Giặt giũ, sửa chữa, tái chế, eco-friendly...)
9. `Phong cách sống` (Trang trí nhà cửa, quà tặng, nghệ thuật sống...)
10. `Khác` (Không thuộc 9 nhóm trên)

---

## 5. Hướng dẫn định dạng đầu ra (Output Format)
Model BẮT BUỘC trả về kết quả định dạng Plain Text (Tuyệt đối không dùng JSON).
Mỗi đánh giá nằm trên một dòng riêng biệt, phân cách bằng ký tự `|`.
**Cú pháp:** `ID | Chi tiết | Độ khó | Từ vựng | Chủ đề`
**Ví dụ đầu ra chuẩn:** `105 | 3 | 3 | 2 | Hoàn cảnh, Dáng người`
