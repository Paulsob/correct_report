import os
import sys
import json
import calendar
from datetime import datetime, timedelta

# Подключение конфигурации
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import config

# Настройки отдыха
WEEKEND_REST_MIN = 42


class DriverState:
    """Класс для хранения динамического состояния водителя."""

    def __init__(self, driver_data, start_date):
        self.data = driver_data
        self.tab = driver_data["tab_number"]
        self.worked_hours_month = 0.0  # Текущая выработка
        self.next_available_time = start_date


def parse_shift_time(year, month, day, time_str, is_end_time=False, start_time_obj=None):
    hours, minutes = map(int, time_str.split(':'))
    dt = datetime(year, month, day, hours, minutes)
    if is_end_time and start_time_obj and dt < start_time_obj:
        dt += timedelta(days=1)
    return dt


def is_driver_absent(tab, day, absences_dict):
    for abs_record in absences_dict.get(tab, []):
        if abs_record["start_day"] <= day <= abs_record["end_day"]:
            return True
    return False


def main():
    year = config.TARGET_YEAR
    month = config.TARGET_MONTH
    target_schedules = config.TARGET_SCHEDULE_TYPES

    # Загрузка данных
    with open(config.INPUT_TABEL_FILE, 'r', encoding='utf-8') as f:
        all_drivers_data = json.load(f).get("drivers", [])
    with open(config.INPUT_SCHEDULE_FILE, 'r', encoding='utf-8') as f:
        schedule_data = json.load(f)
    with open(config.OUTPUT_ABSENCES_FILE, 'r', encoding='utf-8') as f:
        absences_data = json.load(f)

    # Фильтрация водителей
    drivers_data = [d for d in all_drivers_data if d.get("schedule_type") in target_schedules]

    if not drivers_data:
        print(f"Водители не найдены.")
        return

    print(f"--- Запуск балансировки резерва: {month:02d}.{year} ---")

    absences_by_tab = {}
    for a in absences_data:
        if a.get("month") == month and a.get("year") == year:
            absences_by_tab.setdefault(a["tab_number"], []).append(a)

    start_of_month = datetime(year, month, 1, 0, 0)
    drivers_state = [DriverState(d, start_of_month) for d in drivers_data]

    result_shifts = []
    result_drivers = []
    _, days_in_month = calendar.monthrange(year, month)

    for day in range(1, days_in_month + 1):
        current_date = datetime(year, month, day)
        day_type = "выходной" if current_date.weekday() >= 5 else "рабочий"

        daily_routes = [r for r in schedule_data if r.get("day_type", r.get("день")) == day_type]
        unassigned_tasks = []
        for route_info in daily_routes:
            r_num = str(route_info["маршрут"])
            for tram in route_info["трамваи"]:
                for s_key in ["смена_1", "смена_2"]:
                    s_data = tram.get(s_key)
                    if s_data:
                        st = parse_shift_time(year, month, day, s_data["отправление"])
                        en = parse_shift_time(year, month, day, s_data["прибытие"], True, st)
                        unassigned_tasks.append({
                            "route": r_num, "tram_id": tram["номер"],
                            "shift_num": s_key[-1], "start_dt": st, "end_dt": en, "assigned": False
                        })

        # 1. Собираем тех, кто должен работать сегодня по графику
        candidates_today = []
        for d_state in drivers_state:
            if is_driver_absent(d_state.tab, day, absences_by_tab):
                continue

            planned_status = d_state.data.get("days", {}).get(str(day))
            if planned_status in ["1", "2"]:
                candidates_today.append((d_state, planned_status))

        # 2. АЛГОРИТМ ПЕРЕМЕШИВАНИЯ (Балансировка)
        # Сортируем: сначала те, у кого МЕНЬШЕ выработка (worked_hours_month)
        # Это гарантирует, что "резервисты" вчерашнего дня сегодня будут первыми в очереди
        candidates_today.sort(key=lambda x: (x[0].worked_hours_month, len(x[0].data.get("allowed_routes", []))))

        daily_reserve = 0
        for d_state, shift_num in candidates_today:
            match_found = False
            for task in unassigned_tasks:
                if task["assigned"]: continue
                if task["shift_num"] != shift_num: continue
                if task["route"] not in d_state.data.get("allowed_routes", []): continue
                if d_state.next_available_time > task["start_dt"]: continue

                # Назначение успешно
                task["assigned"] = True
                match_found = True

                # Расчет отдыха (2 * работа)
                duration = task["end_dt"] - task["start_dt"]
                work_sec = duration.total_seconds()
                rest_sec = work_sec * 2

                # Еженедельный отдых
                nx_day = d_state.data.get("days", {}).get(str(day + 1), "В")
                if nx_day == "В" or is_driver_absent(d_state.tab, day + 1, absences_by_tab):
                    rest_sec = max(rest_sec, WEEKEND_REST_MIN * 3600)

                d_state.next_available_time = task["end_dt"] + timedelta(seconds=rest_sec)
                d_state.worked_hours_month += (work_sec / 3600)

                # Запись результата
                rec = {
                    "day": day, "month": month, "year": year,
                    "route": task["route"], "tram_id": task["tram_id"],
                    "shift_num": task["shift_num"],
                    "start_time": task["start_dt"].strftime("%Y-%m-%d %H:%M"),
                    "end_time": task["end_dt"].strftime("%Y-%m-%d %H:%M"),
                    "assigned_driver": d_state.tab
                }
                result_shifts.append(rec)

                res_driver = rec.copy()
                res_driver["schedule_type"] = d_state.data["schedule_type"]
                result_drivers.append(res_driver)
                break

            if not match_found:
                daily_reserve += 1

    # Сохранение
    os.makedirs(os.path.dirname(config.OUTPUT_SHIFTS), exist_ok=True)
    with open(config.OUTPUT_SHIFTS, "w", encoding="utf-8") as f:
        json.dump(result_shifts, f, indent=2, ensure_ascii=False)

    print(f"Моделирование завершено. Смены распределены равномерно.")


if __name__ == "__main__":
    main()