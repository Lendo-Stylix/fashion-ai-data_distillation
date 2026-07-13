import subprocess
import sys
import os
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
train_v1_path = os.path.join(script_dir, "train_v1.py")
train_v2_path = os.path.join(script_dir, "train_v2.py")

print("=== STARTING PARALLEL FINE-TUNING PROCESS ===")
print("Version 1 (r=8, alpha=16) -> Dedicated GPU 0")
print("Version 2 (r=16, alpha=32) -> Dedicated GPU 1")
print("--------------------------------------------")

# Khởi chạy 2 tiến trình song song
proc_v1 = subprocess.Popen([sys.executable, train_v1_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
proc_v2 = subprocess.Popen([sys.executable, train_v2_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def read_process_output(proc, tag, file_handle):
    line = proc.stdout.readline()
    if line:
        clean_line = line.strip()
        print(f"[{tag}] {clean_line}", flush=True)
        file_handle.write(f"[{tag}] {clean_line}\n")
        return True
    return False

# Mở file ghi log chung
log_file_path = "parallel_training.log"
with open(log_file_path, "w", encoding="utf-8") as f:
    while proc_v1.poll() is None or proc_v2.poll() is None:
        # Đọc v1
        read_process_output(proc_v1, "GPU_0_V1", f)
        # Đọc v2
        read_process_output(proc_v2, "GPU_1_V2", f)
        time.sleep(0.01)

    # Đọc hết phần còn lại nếu còn
    while read_process_output(proc_v1, "GPU_0_V1", f):
        pass
    while read_process_output(proc_v2, "GPU_1_V2", f):
        pass

print("\n=== PARALLEL FINE-TUNING COMPLETED ===")
print(f"Detailed logs saved to {log_file_path}")
