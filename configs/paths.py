from pathlib import Path

ROOT = Path(__file__).parent.parent

# Data Directories
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_FINAL = ROOT / "data" / "final"
DATA_REASONING = ROOT / "data" / "reasoning_generation"

# File Paths
STRATIFIED_CSV = DATA_REASONING / "stratified_1488.csv"
CLEANED_10K_CSV = DATA_RAW / "cleaned_balanced_10k_dataset.csv"
EVALUATED_CSV = DATA_PROCESSED / "evaluated_dataset.csv"
FAILED_BATCHES_JSON = DATA_PROCESSED / "failed_batches.json"

# Configs
RUBRIC_FILE = ROOT / "configs" / "gemma_eval_rubric.md"

# Logs
EVAL_LOG_FILE = ROOT / "eval.log"
