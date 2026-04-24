import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TARGET_YEAR = 2026
TARGET_MONTH = 10

PRIMARY_SCHEDULE = "3x2x3x1"
SECONDARY_SCHEDULE = None  # None, если нет второго графика
SIMULATE_OPTIMAL_STAFF = True

INPUT_DIR = os.path.join(BASE_DIR, "input_data")
REF_DIR = os.path.join(INPUT_DIR, "02_reference")
OPERATIONAL_DIR = os.path.join(INPUT_DIR, "03_operational")
OUTPUT_DIR = os.path.join(BASE_DIR, "output_data")

ABSENCES_FILE = os.path.join(OPERATIONAL_DIR, "absences.json")

MATRICES_FILE = os.path.join(REF_DIR, "matrices.json")
ROUTE_TYPES = os.path.join(REF_DIR, "route_types.json")

SCHEDULE_PREPARED = os.path.join(OPERATIONAL_DIR, "schedule", "prepared", "new_schedule_prepared.json")
DRIVERS_PREPARED = os.path.join(
    OPERATIONAL_DIR, "drivers", "prepared",
    str(TARGET_YEAR), f"{TARGET_MONTH:02d}", "new_drivers_prepared.json"
)


def get_schedule_output_dir(primary: str, secondary: str = None):
    subfolder = f"{primary}_{secondary}" if secondary else primary
    path = os.path.join(OUTPUT_DIR, str(TARGET_YEAR), f"{TARGET_MONTH:02d}", subfolder)

    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path
