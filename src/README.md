# Source Code (Mã nguồn)

Thư mục này chứa toàn bộ các script Python dùng để thực thi pipeline của dự án.
- **`evaluation/`**: Chứa các script dùng để chấm điểm 10,000 dòng dữ liệu bằng LLM (`run_eval.py`).
- **`distillation/`**: Chứa các script chắt lọc dữ liệu, phân tích nhóm thiểu số và quét lỗi dịch thuật (`distill_dataset.py`, `analyze_khac.py`).

**Lưu ý:** Mọi script trong này đều tự động gọi thư viện `configs.paths` để quản lý file. Không sửa đường dẫn tĩnh (hard-code) bên trong script.
