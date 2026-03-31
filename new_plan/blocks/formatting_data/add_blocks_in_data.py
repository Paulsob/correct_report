import json
import os

# --- НАСТРОЙКИ ПУТЕЙ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
INPUT_DIR = os.path.join(PROJECT_DIR, "input_data")

TARGET_YEAR = "2026"
TARGET_MONTH = "10"

RAW_DIR = os.path.join(INPUT_DIR, "raw_data", TARGET_YEAR, TARGET_MONTH)
RAW_DIR_SCHEDULE = os.path.join(INPUT_DIR, "raw_data")
PREP_DIR = os.path.join(INPUT_DIR, "prepared_data", TARGET_YEAR, TARGET_MONTH)
PREP_DIR_SCHEDULE = os.path.join(INPUT_DIR, "prepared_data")

os.makedirs(PREP_DIR, exist_ok=True)

MATRICES_FILE = os.path.join(INPUT_DIR, "matrices.json")
SCHEDULE_INPUT = os.path.join(RAW_DIR_SCHEDULE, "raw_schedule.json")
SCHEDULE_OUTPUT = os.path.join(PREP_DIR_SCHEDULE, "schedule_prepared.json")
DRIVERS_OUTPUT = os.path.join(PREP_DIR, "drivers_prepared.json")


def load_matrices():
    with open(MATRICES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_role(days_data, matrix_data):
    cycle_len = matrix_data["cycle_length"]
    pattern = []

    if isinstance(days_data, list):
        days_dict = {str(item["day"]): str(item["value"]) for item in days_data}
    else:
        days_dict = days_data

    for day_num in range(1, cycle_len + 1):
        val = days_dict.get(str(day_num), "В")
        pattern.append(str(val).strip().upper())

    for role_id, target_pattern in matrix_data["matrix"].items():
        normalized_target = []
        for val in target_pattern:
            if str(val) in ["В", "B", "В ", " B"]:
                normalized_target.append("В")
            else:
                normalized_target.append("1" if int(val) % 2 != 0 else "2")

        if pattern == normalized_target:
            return int(role_id)
    return None


def get_trams_per_block(matrix_data):
    max_slot = 0
    for pattern in matrix_data["matrix"].values():
        for val in pattern:
            if isinstance(val, int) and val > max_slot:
                max_slot = val
    return max_slot // 2


def process_drivers(matrices):
    print("⏳ Обработка водителей...")
    all_prepared_drivers = []

    for sched_type, matrix_data in matrices.items():
        filename = None
        for f in os.listdir(RAW_DIR):
            if f.startswith(sched_type) and "drivers" in f.lower():
                filename = os.path.join(RAW_DIR, f)
                break

        if not filename:
            continue

        with open(filename, "r", encoding="utf-8") as f:
            drivers_data = json.load(f)

        drivers_list = drivers_data.get("drivers", [])
        block_size = matrix_data["block_size"]
        blocks_created = 0

        for i in range(0, len(drivers_list), block_size):
            chunk = drivers_list[i:i + block_size]
            blocks_created += 1

            for d in chunk:
                d["block_id"] = blocks_created
                d["schedule_type"] = sched_type
                d.pop("schedule", None)

                if isinstance(d.get("days"), list):
                    d["days"] = {str(item["day"]): str(item["value"]) for item in d["days"]}

                role = detect_role(d["days"], matrix_data)
                d["matrix_role"] = role if role is not None else 99

            chunk.sort(key=lambda x: x.get("matrix_role", 99))
            all_prepared_drivers.extend(chunk)

        print(f"     {sched_type}: собрано {blocks_created} блоков водителей.")

    final_json = {
        "month": TARGET_MONTH,
        "year": int(TARGET_YEAR),
        "drivers": all_prepared_drivers
    }

    with open(DRIVERS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)


def process_schedule(matrices):
    print("\nОбработка расписания (Универсальная разметка для всех графиков)...")
    with open(SCHEDULE_INPUT, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)

    trams_pool = {"рабочий": [], "выходной": []}

    for route in schedule_data:
        day_type = route.get("день", "рабочий")
        trams_pool[day_type].extend(route.get("трамваи", []))

    for day_type, trams in trams_pool.items():

        # Для КАЖДОГО типа графика параллельно размечаем всю сеть
        for sched_type, matrix_data in matrices.items():
            trams_per_block = get_trams_per_block(matrix_data)
            block_id = 1

            for i in range(0, len(trams), trams_per_block):
                chunk = trams[i:i + trams_per_block]

                for index, tram in enumerate(chunk):
                    # Создаем словари для мультиязычности графиков
                    if "block_ids" not in tram:
                        tram["block_ids"] = {}

                    tram["block_ids"][sched_type] = block_id
                    slot_base = index * 2

                    if tram.get("смена_1"):
                        if "matrix_slots" not in tram["смена_1"]:
                            tram["смена_1"]["matrix_slots"] = {}
                        tram["смена_1"]["matrix_slots"][sched_type] = slot_base + 1

                    if tram.get("смена_2"):
                        if "matrix_slots" not in tram["смена_2"]:
                            tram["смена_2"]["matrix_slots"] = {}
                        tram["смена_2"]["matrix_slots"][sched_type] = slot_base + 2

                block_id += 1

    with open(SCHEDULE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(schedule_data, f, ensure_ascii=False, indent=2)

    print("Расписание готово! Трамваи готовы к любому типу графика.")


if __name__ == "__main__":
    print("Старт подготовки данных")
    matrices = load_matrices()
    process_drivers(matrices)
    process_schedule(matrices)
    print("\nГотово")