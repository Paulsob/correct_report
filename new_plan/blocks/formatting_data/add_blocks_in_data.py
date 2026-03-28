import json
import os

# --- НАСТРОЙКИ ПУТЕЙ ---
# Текущая папка: new_plan/blocks/formatting_data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Поднимаемся на уровень выше: new_plan/blocks
PROJECT_DIR = os.path.dirname(BASE_DIR)
# Папка с данными: new_plan/blocks/input_data
INPUT_DIR = os.path.join(PROJECT_DIR, "input_data")

# Файлы расписания
SCHEDULE_INPUT = os.path.join(INPUT_DIR, "raw_schedule.json")
SCHEDULE_OUTPUT = os.path.join(INPUT_DIR, "schedule_prepared.json")

# Файлы водителей (предполагаем, что они тоже лежат в input_data)
DRIVERS_INPUT = os.path.join(INPUT_DIR, "10_drivers_october.json")
DRIVERS_OUTPUT = os.path.join(INPUT_DIR, "10_drivers_october_prepared.json")

# --- ЭТАЛОННЫЕ ПАТТЕРНЫ НА ПЕРВЫЕ 12 ДНЕЙ ---
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
    10: ["2", "2", "В", "В", "1", "1", "1", "1", "В", "В", "2", "2"],
    11: ["1", "1", "1", "В", "В", "2", "2", "2", "2", "В", "В", "1"],
    12: ["2", "2", "2", "В", "В", "1", "1", "1", "1", "В", "В", "2"]
}


def detect_role(driver_days):
    """Определяет роль водителя по первым 12 дням его графика."""
    first_12_days = driver_days[:12]
    pattern = [str(day.get("value")) for day in first_12_days]

    for role_id, target_pattern in MATRIX_PATTERNS.items():
        if pattern == target_pattern:
            return role_id
    return None


def process_schedule():
    print("⏳ Обработка расписания трамваев (Создание СКВОЗНЫХ блоков)...")
    with open(SCHEDULE_INPUT, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)

    # Создаем пулы трамваев по типам дней
    # В Python объекты передаются по ссылке. Изменяя словарь tram здесь,
    # мы изменим его и в исходном schedule_data
    trams_pool = {
        "рабочий": [],
        "выходной": []
    }

    # 1. Собираем все трамваи со всех маршрутов в общие пулы
    for route in schedule_data:
        day_type = route.get("день", "рабочий")
        # Добавляем все трамваи этого маршрута в соответствующий пул
        trams_pool[day_type].extend(route.get("трамваи", []))

    # 2. Назначаем сквозные блоки
    for day_type, trams in trams_pool.items():
        global_block_id = 1

        # Берем по 4 трамвая из общего котла
        for i in range(0, len(trams), 4):
            tram_chunk = trams[i:i + 4]

            for index, tram in enumerate(tram_chunk):
                tram["block_id"] = global_block_id
                slot_base = index * 2

                if tram.get("смена_1"):
                    tram["смена_1"]["matrix_slot"] = slot_base + 1
                if tram.get("смена_2"):
                    tram["смена_2"]["matrix_slot"] = slot_base + 2

            # Переходим к следующему блоку
            global_block_id += 1

    # 3. Сохраняем результат
    with open(SCHEDULE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(schedule_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Расписание готово! Сформировано сквозных блоков: {global_block_id - 1}.")


def process_drivers():
    print("⏳ Обработка водителей (Умное распознавание ролей)...")
    with open(DRIVERS_INPUT, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    drivers_list = drivers_data.get("drivers", [])
    unrecognized_count = 0

    # 1. Распознаем роли
    for driver in drivers_list:
        role = detect_role(driver.get("days", []))
        if role:
            driver["matrix_role"] = role
        else:
            driver["matrix_role"] = 99
            unrecognized_count += 1
            print(f"⚠️ Внимание: Водитель Таб.№{driver.get('tab_number')} имеет нестандартный график.")

    # 2. Разбиваем на блоки по 12 человек
    final_drivers_list = []
    for i in range(0, len(drivers_list), 12):
        chunk = drivers_list[i:i + 12]
        block_id = (i // 12) + 1

        for d in chunk:
            d["block_id"] = block_id

        # Сортируем внутри блока по ролям (от 1 до 12)
        chunk.sort(key=lambda x: x.get("matrix_role", 99))
        final_drivers_list.extend(chunk)

    drivers_data["drivers"] = final_drivers_list

    with open(DRIVERS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(drivers_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Водители сохранены. Обработано {len(drivers_list)} чел.")
    if unrecognized_count > 0:
        print(f"❌ Не удалось определить роль у {unrecognized_count} водителей.")


if __name__ == "__main__":
    print("🚀 Старт подготовки данных...\n")
    if not os.path.exists(SCHEDULE_INPUT):
        print(f"❌ Ошибка: Файл расписания не найден по пути: {SCHEDULE_INPUT}")
    elif not os.path.exists(DRIVERS_INPUT):
        print(f"❌ Ошибка: Файл водителей не найден по пути: {DRIVERS_INPUT}")
    else:
        process_schedule()
        process_drivers()
        print("\n🎉 Подготовка данных идеально завершена!")