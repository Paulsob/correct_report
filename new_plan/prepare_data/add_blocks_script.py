import json
import os

# --- НАСТРОЙКИ ПУТЕЙ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

SCHEDULE_INPUT = os.path.join(DATA_DIR, "schedule.json")
DRIVERS_INPUT = os.path.join(DATA_DIR, "4x2_10_drivers_october.json")

SCHEDULE_OUTPUT = os.path.join(DATA_DIR, "schedule_prepared.json")
DRIVERS_OUTPUT = os.path.join(DATA_DIR, "10_drivers_october_prepared.json")

# --- ЭТАЛОННЫЕ ПАТТЕРНЫ НА ПЕРВЫЕ 12 ДНЕЙ (на основе вашей матрицы) ---
# "1" - Утро, "2" - Вечер, "В" - Выходной
MATRIX_PATTERNS = {
    1: ["1", "1", "1", "1", "В", "В", "2", "2", "2", "2", "В", "В"],
    2: ["2", "2", "2", "2", "В", "В", "1", "1", "1", "1", "В", "В"],
    3: ["В", "1", "1", "1", "1", "В", "В", "2", "2", "2", "2", "В"],
    4: ["В", "2", "2", "2", "2", "В", "В", "1", "1", "1", "1", "В"],
    5: ["В", "В", "1", "1", "1", "1", "В", "В", "2", "2", "2", "2"],
    6: ["В", "В", "2", "2", "2", "2", "В", "В", "1", "1", "1", "1"],
    7: ["1", "В", "В", "2", "2", "2", "2", "В", "В", "1", "1", "1"],
    8: ["2", "В", "В", "1", "1", "1", "1", "В", "В", "2", "2", "2"],
    9: ["1", "1", "В", "В", "2", "2", "2", "2", "В", "В", "1", "1"],
    10: ["2", "2", "В", "В", "1", "1", "1", "1", "В", "В", "2", "2"],  # Ваш пример!
    11: ["1", "1", "1", "В", "В", "2", "2", "2", "2", "В", "В", "1"],
    12: ["2", "2", "2", "В", "В", "1", "1", "1", "1", "В", "В", "2"]
}


def detect_role(driver_days):
    # Берем первые 12 дней месяца
    first_12_days = driver_days[:12]
    # Создаем массив значений (например: ['2', '2', 'В', 'В', '1', ...])
    pattern = [str(day.get("value")) for day in first_12_days]

    # Ищем совпадение в наших эталонах
    for role_id, target_pattern in MATRIX_PATTERNS.items():
        if pattern == target_pattern:
            return role_id

    # Если идеального совпадения нет (например, больничный в первые дни)
    return None


def process_schedule():
    print("⏳ Обработка расписания трамваев...")
    with open(SCHEDULE_INPUT, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)

    global_block_id = 1

    for route in schedule_data:
        trams = route.get("трамваи", [])
        for i in range(0, len(trams), 4):
            tram_chunk = trams[i:i + 4]
            for index, tram in enumerate(tram_chunk):
                tram["block_id"] = global_block_id
                slot_base = index * 2
                if "смена_1" in tram:
                    tram["смена_1"]["matrix_slot"] = slot_base + 1
                if "смена_2" in tram:
                    tram["смена_2"]["matrix_slot"] = slot_base + 2
            global_block_id += 1

    with open(SCHEDULE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(schedule_data, f, ensure_ascii=False, indent=2)
    print(f"✅ Расписание готово ({global_block_id - 1} блоков).")


def process_drivers():
    print("⏳ Обработка водителей (Умное распознавание ролей)...")
    with open(DRIVERS_INPUT, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    drivers_list = drivers_data.get("drivers", [])

    # 1. Распознаем роли для всех водителей
    unrecognized_count = 0
    for driver in drivers_list:
        role = detect_role(driver.get("days", []))
        if role:
            driver["matrix_role"] = role
        else:
            driver["matrix_role"] = 99  # Ставим 99, если график нестандартный
            unrecognized_count += 1
            print(
                f"⚠️ Внимание: Водитель Таб.№{driver.get('tab_number')} имеет нестандартный график. Роль не определена.")

    # 2. Разбиваем на блоки по 12 человек и сортируем внутри
    final_drivers_list = []

    for i in range(0, len(drivers_list), 12):
        chunk = drivers_list[i:i + 12]
        block_id = (i // 12) + 1

        # Назначаем ID блока
        for d in chunk:
            d["block_id"] = block_id

        # Сортируем водителей в этом блоке по их роли (от 1 до 12)
        chunk.sort(key=lambda x: x.get("matrix_role", 99))

        final_drivers_list.extend(chunk)

    drivers_data["drivers"] = final_drivers_list

    with open(DRIVERS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(drivers_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Водители сохранены. Обработано {len(drivers_list)} чел.")
    if unrecognized_count > 0:
        print(f"❌ Не удалось определить роль у {unrecognized_count} водителей (проверьте их графики в начале месяца).")


if __name__ == "__main__":
    print("🚀 Старт подготовки данных...\n")
    if not os.path.exists(SCHEDULE_INPUT) or not os.path.exists(DRIVERS_INPUT):
        print("❌ Ошибка: Файлы данных не найдены!")
    else:
        process_schedule()
        process_drivers()
        print("\n🎉 Подготовка данных идеально завершена!")