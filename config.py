import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Глобальные параметры периода
TARGET_YEAR = 2026
TARGET_MONTH = 10

# Основные папки данных
INPUT_DIR = os.path.join(BASE_DIR, "input_data")
REF_DIR = os.path.join(INPUT_DIR, "02_reference")
OPERATIONAL_DIR = os.path.join(INPUT_DIR, "03_operational")
OUTPUT_DIR = os.path.join(BASE_DIR, "output_data")

# 02_REFERENCE (Справочники)
MATRICES_FILE = os.path.join(REF_DIR, "matrices.json")
ROUTE_TYPES = os.path.join(REF_DIR, "route_types.json")
# Если понадобятся закрепления или вагоны:
# PERMITS_REAL = os.path.join(REF_DIR, "permits_real.json")

# 03_OPERATIONAL (Рабочие данные)
# Расписания
SCHEDULE_PREPARED = os.path.join(OPERATIONAL_DIR, "schedule", "prepared", "new_schedule_prepared.json")
# Водители (динамический путь с учетом года и месяца)
DRIVERS_PREPARED = os.path.join(
    OPERATIONAL_DIR, "drivers", "prepared",
    str(TARGET_YEAR), f"{TARGET_MONTH:02d}", "new_drivers_prepared.json"
)


def get_schedule_output_dir(primary: str, secondary: str = None):
    """
    Создает и возвращает путь к папке с результатами.
    Пример: output_data/2026/10/4x2_5x2h/
    """
    subfolder = f"{primary}_{secondary}" if secondary else primary
    path = os.path.join(OUTPUT_DIR, str(TARGET_YEAR), f"{TARGET_MONTH:02d}", subfolder)

    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path