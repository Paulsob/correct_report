import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blocks import config

import json
from datetime import date
import calendar

ANCHOR_DATE = 1
YEAR = int(config.TARGET_YEAR)
MONTH = int(config.TARGET_MONTH)
DAYS_IN_MONTH = calendar.monthrange(YEAR, MONTH)[1]
CUSTOM_HOLIDAYS = []


def load_matrix_data(schedule_type):
    """Загружает нужную матрицу и длину её цикла из общего файла."""
    with open(config.MATRICES_FILE, "r", encoding="utf-8") as f:
        all_matrices = json.load(f)

    if schedule_type not in all_matrices:
        raise ValueError(f"Ошибка: График '{schedule_type}' не найден в {config.MATRICES_FILE}!")

    matrix_data = all_matrices[schedule_type]
    active_matrix = {int(k): v for k, v in matrix_data["matrix"].items()}
    cycle_length = matrix_data["cycle_length"]

    return active_matrix, cycle_length


def get_required_role(cycle_day, target_slot, active_matrix):
    """Спрашиваем матрицу: какая роль закрывает этот слот в этот день цикла?"""
    day_index = cycle_day - 1
    for role, days_list in active_matrix.items():
        if days_list[day_index] == target_slot:
            return role
    return None


def build_drivers_lookup(drivers_data, schedule_type):
    """Создаем словарь ТОЛЬКО для водителей нужного графика."""
    lookup = {}
    for driver in drivers_data.get("drivers", []):
        if driver.get("schedule_type") != schedule_type:
            continue

        b_id = driver.get("block_id")
        m_role = driver.get("matrix_role")

        if b_id not in lookup:
            lookup[b_id] = {}

        driver["schedule_dict"] = driver.get("days", {})
        lookup[b_id][m_role] = driver
    return lookup


def get_day_type(day):
    """Определяет, рабочий это день или выходной."""
    if day in CUSTOM_HOLIDAYS or date(YEAR, MONTH, day).weekday() >= 5:
        return "выходной"
    return "рабочий"


def generate_schedule():
    print(f"\nСтарт моделирования для графика: [{config.TARGET_SCHEDULE}]")

    active_matrix, cycle_length = load_matrix_data(config.TARGET_SCHEDULE)

    print("Загрузка данных расписания и водителей...")
    with open(config.SCHEDULE_PREPARED, "r", encoding="utf-8") as f:
        trams_data = json.load(f)
    with open(config.DRIVERS_PREPARED, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    drivers_lookup = build_drivers_lookup(drivers_data, config.TARGET_SCHEDULE)

    # --- Логирование ---
    total_drivers = sum(len(roles) for roles in drivers_lookup.values())
    if total_drivers == 0:
        print("ВНИМАНИЕ: Для этого графика не найдено ни одного водителя в файле drivers_prepared.json!")

    monthly_result = []

    print("Генерация расписания по дням...")
    for current_day in range(1, DAYS_IN_MONTH + 1):
        cycle_day = ((current_day - ANCHOR_DATE) % cycle_length) + 1
        current_day_type = get_day_type(current_day)
        daily_assignments = []
        daily_unassigned = []

        for route in trams_data:
            if route.get("день") and route.get("день") != current_day_type:
                continue

            route_num = route.get("маршрут")

            for tram in route.get("трамваи", []):
                block_id = tram.get("block_ids", {}).get(config.TARGET_SCHEDULE)
                if not block_id:
                    continue

                tram_num = tram.get("номер")

                shifts = []
                if tram.get("смена_1"): shifts.append(("Утро", tram["смена_1"]))
                if tram.get("смена_2"): shifts.append(("Вечер", tram["смена_2"]))

                for shift_name, shift_data in shifts:
                    target_slot = shift_data.get("matrix_slots", {}).get(config.TARGET_SCHEDULE)
                    if not target_slot:
                        continue

                    required_role = get_required_role(cycle_day, target_slot, active_matrix)
                    if not required_role:
                        continue

                    driver = drivers_lookup.get(block_id, {}).get(required_role)

                    if not driver:
                        daily_unassigned.append({
                            "маршрут": route_num,
                            "трамвай": tram_num,
                            "смена": shift_name,
                            "причина": f"В блоке {block_id} нет водителя с ролью {required_role}"
                        })
                        continue

                    expected_status = "1" if target_slot % 2 != 0 else "2"
                    actual_status = driver["schedule_dict"].get(str(current_day), "Нет данных")

                    if actual_status == expected_status:
                        daily_assignments.append({
                            "маршрут": route_num,
                            "трамвай": tram_num,
                            "смена": shift_name,
                            "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                            "таб_номер_водителя": driver.get("tab_number"),
                            "роль_по_матрице": required_role
                        })
                    else:
                        daily_unassigned.append({
                            "маршрут": route_num,
                            "трамвай": tram_num,
                            "смена": shift_name,
                            "нужна_роль": required_role,
                            "таб_номер_водителя": driver.get("tab_number"),
                            "причина": f"Ожидался статус '{expected_status}', а в графике '{actual_status}'"
                        })

        monthly_result.append({
            "дата": f"{YEAR}-{MONTH:02d}-{current_day:02d}",
            "тип_дня": current_day_type,
            "день_цикла": cycle_day,
            "успешные_назначения": daily_assignments,
            "открытые_смены_без_водителя": daily_unassigned
        })

    with open(config.FINAL_SCHEDULE, "w", encoding="utf-8") as f:
        json.dump(monthly_result, f, ensure_ascii=False, indent=2)

    print(f"\nРасписание на {DAYS_IN_MONTH} дней сгенерировано.")
    print(f"Результат сохранен в: {config.FINAL_SCHEDULE}")


if __name__ == "__main__":
    generate_schedule()
