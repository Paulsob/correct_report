import json
import os
from datetime import datetime, timedelta
from new_generate_summary_report import auto_generate_report

# Настройки
MONTHLY_NORM_HOURS = 180.0
MIN_HOURS_THRESHOLD = 0.0
REST_MIN_REDUCED = 12

MONTHS = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12
}

# Глобальные переменные для истории
history = {}
accumulated_hours = {}
last_worked_day = {}


# Загрузка данных
def load_data():
    with open("../data/10_drivers_october.json", "r", encoding="utf-8") as f:
        drivers_raw = json.load(f)

    year = drivers_raw.get("year", 2026)
    month_name = drivers_raw.get("month", "Октябрь").lower()
    month = MONTHS.get(month_name, 10)

    drivers = []
    max_days = 0
    for d in drivers_raw.get("drivers", []):
        pattern_dict = {item["day"]: item["value"] for item in d.get("days", [])}
        if pattern_dict:
            max_days = max(max_days, max(pattern_dict.keys()))

        drivers.append({
            "tab_number": d["tab_number"],
            "pattern": pattern_dict
        })

    with open("../data/schedule.json", "r", encoding="utf-8") as f:
        schedules_raw = json.load(f)

    target_schedule = schedules_raw[0]
    return drivers, target_schedule, year, month, max_days


def get_shift_datetimes(base_date, time_data):
    if not time_data:
        return None, None, 0

    h_start, m_start = map(int, time_data["отправление"].split(':'))
    h_end, m_end = map(int, time_data["прибытие"].split(':'))

    start_dt = base_date.replace(hour=h_start, minute=m_start, second=0)
    end_dt = base_date.replace(hour=h_end, minute=m_end, second=0)

    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    duration = (end_dt - start_dt).total_seconds() / 3600.0
    return start_dt, end_dt, duration


# ЖЕСТКАЯ ПРОВЕРКА ОТДЫХА (ОТДЫХ = 2 * РАБОТА)
def validate_rest(prev_end_dt, current_start_dt, prev_duration):
    gap = (current_start_dt - prev_end_dt).total_seconds() / 3600.0
    if gap < 0: return False

    required_rest = prev_duration * 2.0
    return gap >= required_rest


def check_rest_rules(driver, start_dt):
    d_id = str(driver["tab_number"])
    last = history.get(d_id)
    if not last: return True

    return validate_rest(last["end_dt"], start_dt, last["duration"])


def select_best_driver():
    """
    Функция подбора лучшего водителя на конкретную смену.
    На первую смену первого дня назначаются первые водители, имеющие в первом дне "1".
    На вторую смену первого дня назначаются первые водители, имеющие в первом дне "2".
    Далее необходим алгоритм, который находит водителя, у которого уже набрались необходимые часы отдыха
    Если такого водителя нет - то берем одного нового водителя.
    Тогда этот водитель считается активным, нужно использовать его по максимуму
    Цель:
        минимизация штата
        минимизация простоев водителей
        максимизация числа рабочих часов водителей
    """


if __name__ == "__main__":

    print()
# if __name__ == "__main__":
#     if not os.path.exists("4x2_10_drivers_october.json") or not os.path.exists("schedule.json"):
#         print("ОШИБКА: Рядом со скриптом должны лежать файлы 4x2_10_drivers_october.json и schedule.json")
#     else:
#
#         auto_generate_report(final_schedule, drivers_list, output_excel="Расписание_Октябрь_Оптимизировано.xlsx")