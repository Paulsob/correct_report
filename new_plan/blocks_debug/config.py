import os

TARGET_YEAR = "2026"
TARGET_MONTH = "10"
# TARGET_SCHEDULE = "3x2x3x1"
TARGET_SCHEDULE = "4x2"
# TARGET_SCHEDULE = "5x2"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_DIR = os.path.join(BASE_DIR, "input_data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output_data")

RAW_DIR = os.path.join(INPUT_DIR, "raw_data", TARGET_YEAR, TARGET_MONTH)
RAW_DIR_SCHEDULE = os.path.join(INPUT_DIR, "raw_data")
PREP_DIR = os.path.join(INPUT_DIR, "prepared_data", TARGET_YEAR, TARGET_MONTH)
PREP_DIR_SCHEDULE = os.path.join(INPUT_DIR, "prepared_data")
MONTH_OUT_DIR = os.path.join(OUTPUT_DIR, TARGET_YEAR, TARGET_MONTH)

os.makedirs(PREP_DIR, exist_ok=True)
os.makedirs(MONTH_OUT_DIR, exist_ok=True)


MATRICES_FILE = os.path.join(INPUT_DIR, "matrices.json")
SCHEDULE_RAW = os.path.join(RAW_DIR_SCHEDULE, "raw_schedule.json")


SCHEDULE_PREPARED = os.path.join(PREP_DIR_SCHEDULE, "schedule_prepared.json")
DRIVERS_PREPARED = os.path.join(PREP_DIR, "drivers_prepared.json")


FINAL_SCHEDULE = os.path.join(MONTH_OUT_DIR, f"{TARGET_SCHEDULE}_final_schedule.json")
REPORT_EXCEL = os.path.join(MONTH_OUT_DIR, f"{TARGET_SCHEDULE}_drivers_report.xlsx")