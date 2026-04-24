import json
import os


# --- 1. ОБНОВЛЕНИЕ ВОДИТЕЛЕЙ ---

def update_drivers(input_file, output_file):
    print(f"Читаем файл водителей: {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    drivers = []
    if isinstance(raw_data, dict):
        if "drivers" in raw_data:
            drivers = raw_data["drivers"]
        else:
            drivers = list(raw_data.values())
    elif isinstance(raw_data, list):
        drivers = raw_data

    # Чистим старые графики 3x2x3x1
    updated_drivers = [d for d in drivers if d.get("schedule_type") != "3x2x3x1"]

    # Исходная матрица ролей (как на картинке)
    role_matrix = [
        ["2", "2", "2", "В", "В", "3", "3", "3", "В"],  # Роль 1
        ["4", "4", "В", "В", "5", "5", "5", "В", "4"],  # Роль 2
        ["6", "В", "В", "1", "1", "1", "В", "6", "6"],  # Роль 3
        ["В", "В", "3", "3", "3", "В", "2", "2", "2"],  # Роль 4
        ["В", "5", "5", "5", "В", "4", "4", "4", "В"],  # Роль 5
        ["1", "1", "1", "В", "6", "6", "6", "В", "В"],  # Роль 6
        ["3", "3", "В", "2", "2", "2", "В", "В", "3"],  # Роль 7
        ["5", "В", "4", "4", "4", "В", "В", "5", "5"],  # Роль 8
        ["В", "6", "6", "6", "В", "В", "1", "1", "1"]  # Роль 9
    ]

    TOTAL_DRIVERS = 720
    DAYS_IN_MONTH = 31
    START_TAB_NUMBER = 2000

    print(f"Генерируем {TOTAL_DRIVERS} водителей (нечетные -> 1, четные -> 2)...")
    for i in range(TOTAL_DRIVERS):
        block_id = (i // 9) + 1
        matrix_role = (i % 9) + 1

        days_schedule = {}
        for day in range(1, DAYS_IN_MONTH + 1):
            cycle_day = (day - 1) % 9
            val = role_matrix[matrix_role - 1][cycle_day]

            # Лайфхак: нечетные - 1, четные - 2, В - выходной
            if val == "В":
                shift_type = "В"
            else:
                shift_type = "1" if int(val) % 2 != 0 else "2"

            days_schedule[str(day)] = shift_type

        updated_drivers.append({
            "tab_number": START_TAB_NUMBER + i,
            "mode": "1x2",
            "days": days_schedule,
            "allowed_routes": ["47", "61", "21", "48", "20", "9"],
            "allowed_trams": ["ЛВС-86", "Богатырь", "ЛМ-99"],
            "block_id": block_id,
            "schedule_type": "3x2x3x1",
            "matrix_role": matrix_role
        })

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(updated_drivers, f, ensure_ascii=False, indent=2)
    print(f"Сохранено: {output_file}\n")


# --- 2. ОБНОВЛЕНИЕ РАСПИСАНИЯ ---

def update_schedule(input_file, output_file):
    print(f"Читаем файл расписания: {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        schedule = json.load(f)

    # Нам нужно считать трамваи (наряды) последовательно
    # Чтобы каждые 3 трамвая переключать block_id
    tram_counter = 0

    for day_data in schedule:
        if "трамваи" not in day_data: continue

        for tram in day_data["трамваи"]:
            # Проверяем, что это наш тип графика
            if "3x2x3x1" in tram.get("block_ids", {}):

                # Вычисляем номер блока: каждые 3 трамвая = новый блок
                # tram_counter // 3 даст 0,0,0, 1,1,1, 2,2,2...
                b_id = (tram_counter // 3) + 1

                # Вычисляем слоты внутри блока (1-2, 3-4, 5-6)
                # tram_counter % 3 даст 0, 1, 2
                base_slot = (tram_counter % 3) * 2

                # Присваиваем block_id
                tram["block_ids"]["3x2x3x1"] = b_id

                # Присваиваем слоты (роли) для смен
                if "смена_1" in tram:
                    tram["смена_1"]["matrix_slots"]["3x2x3x1"] = base_slot + 1
                if "смена_2" in tram:
                    tram["смена_2"]["matrix_slots"]["3x2x3x1"] = base_slot + 2

                tram_counter += 1

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)
    print(f"Сохранено: {output_file} (Обработано трамваев: {tram_counter})")


if __name__ == "__main__":
    d_in = '../input_data/03_operational/drivers/prepared/2026/10/new_drivers_prepared.json'
    s_in = '../input_data/03_operational/schedule/prepared/new_schedule_prepared.json'

    update_drivers(d_in, d_in.replace('.json', '_UPDATED.json'))
    update_schedule(s_in, s_in.replace('.json', '_UPDATED.json'))