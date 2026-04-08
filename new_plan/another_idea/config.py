import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TARGET_YEAR = 2026
TARGET_MONTH = 10

TARGET_SCHEDULE_TYPES = ["4x2"]

INPUT_SCHEDULE_FILE = os.path.join(BASE_DIR, "input_data", "schedule.json")
INPUT_TABEL_FILE = os.path.join(BASE_DIR, "input_data", "prepared_tabel.json")
OUTPUT_ABSENCES_FILE = os.path.join(BASE_DIR, "input_data", "absences.json")

OUTPUT_DRIVERS = os.path.join(BASE_DIR, "output_data", "output_drivers.json")
OUTPUT_SHIFTS = os.path.join(BASE_DIR, "output_data", "output_shifts.json")
