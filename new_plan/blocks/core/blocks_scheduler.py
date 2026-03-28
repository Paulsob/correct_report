import json
import os
from datetime import date
import calendar

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

INPUT_DIR = os.path.join(PROJECT_DIR, "input_data")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output_data")

# input_data
SCHEDULE_INPUT = os.path.join(INPUT_DIR, "schedule_prepared.json")
DRIVERS_INPUT = os.path.join(INPUT_DIR, "10_drivers_october_prepared.json")
MATRIX_INPUT = os.path.join(INPUT_DIR, "matrix.json")

# output_data
RESULT_OUTPUT = os.path.join(OUTPUT_DIR, "final_schedule_october.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

ANCHOR_DATE = 1
YEAR = 2026
MONTH = 10
DAYS_IN_MONTH = calendar.monthrange(YEAR, MONTH)[1]
CUSTOM_HOLIDAYS = []


def load_matrix():
    """Загружает матрицу из JSON и преобразует ключи 'role_1' в число 1 для совместимости с логикой."""
    with open(MATRIX_INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    matrix = {}
    for role_key, days_list in data.get("matrix", {}).items():
        # Извлекаем число из строки "role_1" -> 1
        role_num = int(role_key.replace("role_", ""))
        matrix[role_num] = days_list
    return matrix


MATRIX = load_matrix()


def get_required_role(cycle_day, target_slot):
    """Спрашиваем матрицу: какая роль закрывает этот слот в этот день цикла?"""
    day_index = cycle_day - 1
    for role, days_list in MATRIX.items():
        if days_list[day_index] == target_slot:
            return role
    return None


def build_drivers_lookup(drivers_data):
    """Создаем удобный словарь: lookup[блок][роль] = водитель"""
    lookup = {}
    for driver in drivers_data.get("drivers", []):
        b_id = driver.get("block_id")
        m_role = driver.get("matrix_role")

        if b_id not in lookup:
            lookup[b_id] = {}

        driver_schedule = {d["day"]: str(d["value"]) for d in driver.get("days", [])}
        driver["schedule_dict"] = driver_schedule

        lookup[b_id][m_role] = driver
    return lookup


def get_day_type(day):
    """Определяет, рабочий это день или выходной."""
    # weekday() возвращает: 0-понедельник, 1-вторник ... 5-суббота, 6-воскресенье
    if day in CUSTOM_HOLIDAYS or date(YEAR, MONTH, day).weekday() >= 5:
        return "выходной"
    return "рабочий"


def generate_schedule():
    print("Загрузка данных")
    with open(SCHEDULE_INPUT, "r", encoding="utf-8") as f:
        trams_data = json.load(f)
    with open(DRIVERS_INPUT, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    drivers_lookup = build_drivers_lookup(drivers_data)

    monthly_result = []

    print("Генерация расписания")
    for current_day in range(1, DAYS_IN_MONTH + 1):

        cycle_day = ((current_day - ANCHOR_DATE) % 12) + 1

        # 1. Определяем тип текущего дня
        current_day_type = get_day_type(current_day)

        daily_assignments = []
        daily_unassigned = []

        # 2. Бежим по всем маршрутам
        for route in trams_data:
            route_day_type = route.get("день")

            # НОВАЯ ЛОГИКА: Если в JSON указан тип дня, и он не совпадает с текущим, пропускаем
            if route_day_type and route_day_type != current_day_type:
                continue

            route_num = route.get("маршрут")

            for tram in route.get("трамваи", []):
                tram_num = tram.get("номер")
                block_id = tram.get("block_id")

                shifts = []
                if tram.get("смена_1"):
                    shifts.append(("Утро", tram["смена_1"]))
                if tram.get("смена_2"):
                    shifts.append(("Вечер", tram["смена_2"]))

                for shift_name, shift_data in shifts:
                    target_slot = shift_data.get("matrix_slot")
                    required_role = get_required_role(cycle_day, target_slot)

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
                    actual_status = driver["schedule_dict"].get(current_day, "Нет данных")

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
            "тип_дня": current_day_type,  # Добавили вывод типа дня в результат
            "день_цикла": cycle_day,
            "успешные_назначения": daily_assignments,
            "открытые_смены_без_водителя": daily_unassigned
        })

    with open(RESULT_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(monthly_result, f, ensure_ascii=False, indent=2)

    print(f"Расписание на {DAYS_IN_MONTH} день (дней) сгенерировано.")
    print(f"Результат сохранен в {RESULT_OUTPUT}")


if __name__ == "__main__":
    generate_schedule()