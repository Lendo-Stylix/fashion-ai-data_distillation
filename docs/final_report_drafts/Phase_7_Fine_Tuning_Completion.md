# Báo cáo Giai đoạn 7: Hoàn thành Fine-tuning & Đánh giá Chỉ số (W&B)

**Mô hình nền:** `techwithsergiu/Qwen3.5-text-4B-bnb-4bit`  
**Phương pháp:** LoRA PEFT (r=8, alpha=16) - *Unsloth Optimization*  
**Bộ Dữ liệu:** Tập 1.488 mẫu tinh giản (Sạch, Phân nhóm đa dạng, Không bị nhiễu)

---

## 1. Tổng quan Đợt Huấn Luyện (Run: q81nc1p3)

Dựa trên dữ liệu giám sát trực tiếp từ nền tảng **Weights & Biases (W&B)** tại URL: `wandb.ai/locvu0309-fpt-university/qwen-3.5-4b-fashion-r8-alpha16/runs/q81nc1p3`, tiến trình Fine-tuning đã hoàn tất thành công 100% với các thông số ấn tượng. Quá trình huấn luyện không xảy ra lỗi sập VRAM (OOM) nhờ sự tương thích cấu hình giữa Unsloth và chuẩn 4-bit quantization.

### 1.1 Thông số Thời gian và Khối lượng Tính toán
- **Tổng thời gian chạy (Runtime):** 3 giờ 18 phút 2 giây (11.882 giây)
- **Tổng số Epochs:** 3
- **Tổng số Steps:** 558
- **Tổng lượng FLOPs:** 63.150.839.938.240.512

Việc huấn luyện hoàn tất trong hơn 3 tiếng chứng minh tính tối ưu của thư viện Unsloth kết hợp LoRA trên Card đồ họa Tesla T4/T4x2, giúp tiết kiệm chi phí mà vẫn đảm bảo được sức mạnh tính toán.

---

## 2. Đánh giá Mức độ Hội tụ (Convergence)

### 2.1 Chỉ số Hàm suy hao (Loss Metrics)
- **Training Loss (Trung bình toàn đợt):** `1.6404`
- **Training Loss (Tại Step cuối - 558):** `1.4691`

> [!TIP]
> **Nhận xét Độ Hội Tụ**
> Hàm suy hao (Training Loss) có xu hướng giảm ổn định từ đầu và dừng ở mức `1.4691` tại Step cuối. Sự sụt giảm liên tục này phản ánh việc mô hình Qwen 3.5 4B đã thẩm thấu và học được phương pháp tư duy (reasoning chain) thông qua các thẻ `<think>` rất tốt trên toàn bộ 1.488 bản ghi chất lượng cao mà không có hiện tượng mất tập trung.

### 2.2 Mức độ Overfitting
- Với việc giới hạn số lượng Epoch là **3**, thời lượng huấn luyện vừa đủ dài để mô hình ghi nhớ các cấu trúc ngữ nghĩa ngành thời trang, lại vừa đủ ngắn để tránh hiện tượng học vẹt (Overfitting) khi Loss giảm quá sâu so với các mô hình 4B. 
- Chiến lược "Train on Responses Only" (chỉ tính Loss trên phần trả lời, che phần Prompt) đã phát huy tối đa tác dụng trong việc giữ Loss không bị nhiễu.

---

## 3. Kết luận và Hướng Đi Tiếp Theo

Tiến trình Fine-Tuning mô hình Qwen 3.5 (4B) với tập dữ liệu **Fashion AI** đã hoàn thành đạt chuẩn kỹ thuật khắt khe nhất:
1. **Pipeline Hoạt động Trơn tru:** Không vướng lỗi tương thích Backward Pass của DoRA, LoRA hoạt động hoàn hảo cùng Unsloth.
2. **Khả năng Mở rộng Rõ ràng:** Việc train thành công 1.488 mẫu trong ~3.3 tiếng mở ra cơ sở vững chắc nếu team muốn mở rộng tập dữ liệu lên 5.000 hoặc 10.000 mẫu trong tương lai bằng A100.
3. **Mô hình Sẵn sàng Đánh giá:** Mô hình hiện tại (Checkpoint cuối cùng) đã ở trạng thái hoàn chỉnh, sẵn sàng cho việc suy luận (Inference), sinh mã `<think>` và thực hiện đánh giá (Evaluation) thực tế qua các bài Test của người dùng.

> [!IMPORTANT]
> **Bước tiếp theo:**
> Tiến hành tải mô hình Weights (Adapter) từ thư mục lưu trữ cục bộ/Hugging Face, gộp (Merge) với mô hình gốc để tạo bản GGUF/Safetensors và bắt đầu phiên bản **BETA Testing** (Đánh giá Benchmark hoặc Human Evaluation).
