import subprocess
import time
import sys
from pathlib import Path

ROOT = Path(__file__).parent
LOG_FILE = ROOT / "pipeline_run.log"
CHECKPOINT_FILE = ROOT / "data/reasoning_generation/reasoning_generation_v3_log.json"

def get_checkpoint_time_and_size():
    if CHECKPOINT_FILE.exists():
        stat = CHECKPOINT_FILE.stat()
        return stat.st_mtime, stat.st_size
    return 0, 0

def main():
    # Open log file for appending stdout and stderr of the process
    log_f = open(LOG_FILE, "a", encoding="utf-8")
    log_f.write(f"\n--- Wrapper started run at {time.ctime()} ---\n")
    log_f.flush()

    env = dict(subprocess.os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    
    cmd = [sys.executable, "src/reasoning_generation/ver_2/run_reasoning_pipeline_openrouter.py"]
    
    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=log_f,
        env=env,
        cwd=str(ROOT),
        text=True
    )
    
    last_update_time = time.time()
    last_mtime, last_size = get_checkpoint_time_and_size()
    
    # Inactivity limit: 15 minutes (900 seconds)
    INACTIVITY_LIMIT = 900
    
    try:
        while True:
            ret = proc.poll()
            if ret is not None:
                # Process finished
                if ret == 0:
                    print(f"SUCCESS: Pipeline completed successfully with exit code 0.")
                    sys.exit(0)
                else:
                    # Non-zero exit code is a critical error!
                    print(f"CRITICAL ERROR: Pipeline exited with code {ret}.", file=sys.stderr)
                    # Dump last few lines of the log to stderr so it wakes up the agent with details
                    print("\n--- Last 20 lines of log ---", file=sys.stderr)
                    if LOG_FILE.exists():
                        try:
                            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
                            for line in lines[-20:]:
                                print(line, file=sys.stderr)
                        except Exception:
                            pass
                    sys.exit(ret)
            
            # Check if checkpoint changed
            mtime, size = get_checkpoint_time_and_size()
            if mtime != last_mtime or size != last_size:
                last_mtime = mtime
                last_size = size
                last_update_time = time.time()
            
            # Check inactivity timeout
            if time.time() - last_update_time > INACTIVITY_LIMIT:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                print(f"CRITICAL ERROR: Watchdog timeout! No progress detected in checkpoint for {INACTIVITY_LIMIT}s.", file=sys.stderr)
                sys.exit(2)
                
            time.sleep(10)
    finally:
        log_f.close()

if __name__ == "__main__":
    main()
