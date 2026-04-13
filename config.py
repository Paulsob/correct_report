import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TARGET_YEAR = 2026
TARGET_MONTH = 10

TARGET_SCHEDULE_TYPES = ["4x2", "5x2h"]

INPUT_SCHEDULE_FILE = os.path.join(BASE_DIR, "input_data", "prepared_data", "schedule_prepared.json")
INPUT_TABEL_FILE = os.path.join(BASE_DIR, "input_data", "prepared_data", "2026", "10", "drivers_prepared.json")
# OUTPUT_ABSENCES_FILE = os.path.join(BASE_DIR, "input_data", "absences.json")

OUTPUT_DRIVERS = os.path.join(BASE_DIR, "output_data", "output_drivers.json")
OUTPUT_SHIFTS = os.path.join(BASE_DIR, "output_data", "output_shifts.json")

MATRICES_FILE = os.path.join(BASE_DIR, "input_data", "matrices.json")
SCHEDULE_PREPARED = os.path.join(BASE_DIR, "input_data", "prepared_data", "new_schedule_prepared.json")
DRIVERS_PREPARED = os.path.join(BASE_DIR, "input_data", "prepared_data", "2026", "10", "drivers_prepared.json")

OUTPUT_SCHEDULES_ROOT = os.path.join(BASE_DIR, "output_data")

SCHEDULE_OUTPUT_FOLDERS = {
    "3x2x3x1": os.path.join(OUTPUT_SCHEDULES_ROOT, str(TARGET_YEAR), f"{TARGET_MONTH:02d}", "3x2x3x1"),
    "4x2":     os.path.join(OUTPUT_SCHEDULES_ROOT, str(TARGET_YEAR), f"{TARGET_MONTH:02d}", "4x2"),
    "4x2_5x2h":os.path.join(OUTPUT_SCHEDULES_ROOT, str(TARGET_YEAR), f"{TARGET_MONTH:02d}", "4x2_5x2h"),
    "5x2":     os.path.join(OUTPUT_SCHEDULES_ROOT, str(TARGET_YEAR), f"{TARGET_MONTH:02d}", "5x2"),
    "5x2_5x2h":os.path.join(OUTPUT_SCHEDULES_ROOT, str(TARGET_YEAR), f"{TARGET_MONTH:02d}", "5x2_5x2h")
}


def get_schedule_output_dir(primary: str, secondary: str = None, year: int = TARGET_YEAR, month: int = TARGET_MONTH):
    key = f"{primary}_{secondary}" if secondary else primary
    return SCHEDULE_OUTPUT_FOLDERS.get(key, OUTPUT_SCHEDULES_ROOT)
