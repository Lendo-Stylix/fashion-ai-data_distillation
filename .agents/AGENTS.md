# 🤖 Global Agent Rules cho Workspace "Deep Learning 302m - Fashion AI"

Chào bạn, Hỡi người đồng nghiệp AI tương lai! Khi bạn bước vào Workspace này, hãy tuân thủ tuyệt đối các nguyên tắc sau:

## 1. Mục Tiêu Tối Thượng
Dự án này là quy trình chuẩn bị dữ liệu (Data Pipeline) để fine-tune mô hình **Qwen 3.5 (Tiếng Việt)** cho nghiệp vụ tư vấn thời trang. Đừng tự ý chạy code train model ở đây, nhiệm vụ của thư mục này chỉ là: Đánh giá chất lượng data, Chưng cất (Distillation), Sửa lỗi dịch, và Sinh thẻ `<think>`.

## 2. Kiến Trúc Cây Thư Mục (Do Not Break Paths)
- **`data/`**: Nơi dòng chảy dữ liệu đi qua. Từ `raw/` (10k gốc) -> `processed/` (đã chấm điểm) -> `final/` (đã distilled và sinh thẻ think). Mọi code đọc/ghi data PHẢI thông qua file `configs/paths.py`. Tuyệt đối không hard-code đường dẫn tương đối (như `../data/`) trong các script `.py`.
- **`configs/paths.py`**: Chân lý duy nhất về đường dẫn. Hãy import nó vào code của bạn.
- **`src/`**: Chứa script chạy. Chấm điểm thì vào `evaluation/`, lọc dữ liệu thì vào `distillation/`.
- **`docs/`**: Chứa linh hồn học thuật của dự án. Đọc `docs/plans/pipeline_master.md` để biết mình đang ở đâu trong chuỗi 5 Giai đoạn.

## 3. Quy Tắc Hành Xử Khắc Nghiệt (Strict Rules)
1. **Tuyệt đối không dùng lệnh hệ thống để xóa vĩnh viễn (rm, del) bất kỳ tệp tin nào:** Nếu tệp dữ liệu hoặc tệp code bị lỗi/cần xóa, hãy di chuyển nó sang thư mục backup hoặc thùng rác để có thể khôi phục lại khi lỡ tay. Dữ liệu và mã nguồn là tài sản lớn nhất.
2. **Không Over-engineering Log:** Đã có `eval.log` và `night_shift_log.md` ở root. Không vẽ vời thêm thư mục `logs/` rối rắm.
3. **Thực thi Pipeline qua Skill:** Bạn hãy đọc skill tại `.agents/skills/data-pipeline/SKILL.md` để hiểu quy trình tự động hóa các bước.
4. **Khôi Phục Tiến Độ Nhanh (Session Memory):** Bất cứ khi nào bắt đầu một phiên hội thoại mới, việc ĐẦU TIÊN phải làm là dùng công cụ `view_file` đọc file `CURRENT_PROGRESS.md` ở thư mục gốc (root) để nắm ngay trạng thái dự án, thư mục đang làm việc và tác vụ tiếp theo (Next Action) thay vì tốn token đọc lại toàn bộ lịch sử trò chuyện dài.
