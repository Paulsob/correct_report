import os
import sys
import json
import calendar
from datetime import datetime, timedelta, date

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from another_idea import config

BASE_REST_HOURS = 12
WEEKEND_REST_BONUS = 42


class DriverState:
    def init(self, driver_data, start_date):
        self.data = driver_data
        self.tab = driver_data["tab_number"]
        self.worked_hours_month = 0.0
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


def get_day_type(day, month, year):
    current_date = date(year, month, day)
    if current_date.weekday() >= 5:
        return "выходной"
    else:
        return "рабочий"


def get_days_in_month(month, year):
    year = config.TARGET_YEAR
    month = config.TARGET_MONTH
    _, days_in_month = calendar.monthrange(year, month)

    return days_in_month


def get_ready_drivers_live(day, all_drivers):
    absences_file = config.OUTPUT_ABSENCES_FILE

    current_absences = []
    if os.path.exists(absences_file):
        try:
            with open(absences_file, 'r', encoding='utf-8') as f:
                current_absences = json.load(f)
        except json.JSONDecodeError:
            pass

    target_month = config.TARGET_MONTH
    target_year = config.TARGET_YEAR

    active_absences = [
        a for a in current_absences
        if a.get("month") == target_month and a.get("year") == target_year
    ]

    ready_drivers = []

    for driver in all_drivers:
        tab = driver.tab if hasattr(driver, 'tab') else driver.get("tab_number")
        is_absent = False

        for absence in active_absences:
            if absence.get("tab_number") == tab:
                if absence["start_day"] <= day <= absence["end_day"]:
                    is_absent = True
                    break

        if not is_absent:
            ready_drivers.append(driver)

    return ready_drivers


def get_shift_datetime(day, month, year, time_str, start_dt=None):
    h, m = map(int, time_str.split(':'))
    dt = datetime(year, month, day, h, m)
    # Если время прибытия меньше отправления - значит это следующий день (ночь)
    if start_dt and dt < start_dt:
        dt += timedelta(days=1)
    return dt


def main():
    year = config.TARGET_YEAR
    month = config.TARGET_MONTH
    target_schedules = config.TARGET_SCHEDULE_TYPES

    with open(config.INPUT_TABEL_FILE, 'r', encoding='utf-8') as f:
        all_drivers_data = json.load(f).get("drivers", [])
    with open(config.INPUT_SCHEDULE_FILE, 'r', encoding='utf-8') as f:
        schedule_data = json.load(f)

    drivers_data = [d for d in all_drivers_data if d.get("schedule_type") in target_schedules]

    if not drivers_data:
        print(f"Ошибка: Не найдено ни одного водителя с графиком {target_schedules}")
        return

    start_of_month = datetime(year, month, 1, 0, 0)
    for d in drivers_data:
        d["next_available_time"] = start_of_month
        d["worked_hours"] = 0.0
        d["is_active"] = False
        d["missed_days"] = 0

    output_shifts = []
    output_drivers = []

    unassigned_shifts_count = 0

    days_in_month = get_days_in_month(month, year)
    for day in range(1, days_in_month + 1):
        str_day = str(day)
        next_day_str = str(day + 1)
        current_day_type = get_day_type(day, month, year)
        present_drivers_data = get_ready_drivers_live(day, drivers_data)
        drivers_shift_1 = [
            d for d in present_drivers_data
            if d.get("days", {}).get(str_day) == "1"
        ]
        drivers_shift_2 = [
            d for d in present_drivers_data
            if d.get("days", {}).get(str_day) == "2"
        ]

        sort_key = lambda d: (
            not d["is_active"],
            -d["missed_days"] if d["is_active"] else d["missed_days"],
            len(d.get("allowed_routes", [])),
            d["worked_hours"]
        )

        drivers_shift_1.sort(key=sort_key)
        drivers_shift_2.sort(key=sort_key)

        total_shifts_1_today = 0
        total_shifts_2_today = 0

        for tram in schedule_data:
            if tram.get("день") != current_day_type:
                continue
            route_number = str(tram.get('маршрут'))

            for task in tram.get('трамваи', []):
                if task.get('смена_1'): total_shifts_1_today += 1
                if task.get('смена_2'): total_shifts_2_today += 1

                tram_number = task.get('номер')
                shift_1 = task.get('смена_1')
                if shift_1:
                    start_time = get_shift_datetime(day, month, year, shift_1["отправление"])
                    end_time = get_shift_datetime(day, month, year, shift_1["прибытие"], start_dt=start_time)
                    for driver in drivers_shift_1:
                        if route_number not in driver.get("allowed_routes", []):
                            continue
                        if driver["next_available_time"] > start_time:
                            continue

                        driver["is_active"] = True
                        shift_duration = (end_time - start_time).total_seconds() / 3600
                        driver["worked_hours"] += shift_duration

                        rest_hours = 12
                        if driver.get("days", {}).get(next_day_str) == "В":
                            rest_hours += 42
                        driver["next_available_time"] = end_time + timedelta(hours=rest_hours)
                        record_base = {
                            "day": day, "month": month, "year": year,
                            "route": route_number, "tram_number": tram_number,
                            "shift_num": "1",
                            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
                            "end_time": end_time.strftime("%Y-%m-%d %H:%M")
                        }

                        shift_rec = record_base.copy()
                        shift_rec["assigned_driver"] = driver.get('tab_number')
                        output_shifts.append(shift_rec)

                        driver_rec = record_base.copy()
                        driver_rec["tab_number"] = driver.get('tab_number')
                        driver_rec["schedule_type"] = driver.get('schedule_type')
                        driver_rec["mode"] = driver.get('mode')
                        driver_rec["next_available_time"] = driver["next_available_time"].strftime("%Y-%m-%d %H:%M")
                        output_drivers.append(driver_rec)

                        drivers_shift_1.remove(driver)
                        break
                    else:
                        print(
                            f"День {day}. Нет водителя на СМЕНУ 1! Маршрут {route_number}, Трамвай {tram_number} ({start_time.strftime('%H:%M')})")
                        unassigned_shifts_count += 1
                shift_2 = task.get('смена_2')
                if shift_2:
                    start_time = get_shift_datetime(day, month, year, shift_2["отправление"])
                    end_time = get_shift_datetime(day, month, year, shift_2["прибытие"], start_dt=start_time)
                    for driver in drivers_shift_2:
                        if route_number not in driver.get("allowed_routes", []):
                            continue
                        if driver["next_available_time"] > start_time:
                            continue
                            driver["is_active"] = True
                            shift_duration = (end_time - start_time).total_seconds() / 3600
                            driver["worked_hours"] += shift_duration
                            rest_hours = 12
                            if driver.get("days", {}).get(next_day_str) == "В":
                                rest_hours += 42
                            driver["next_available_time"] = end_time + timedelta(hours=rest_hours)

                            record_base = {
                                "day": day, "month": month, "year": year,
                                "route": route_number, "tram_number": tram_number,
                                "shift_num": "2",
                                "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
                                "end_time": end_time.strftime("%Y-%m-%d %H:%M")
                            }

                            shift_rec = record_base.copy()
                            shift_rec["assigned_driver"] = driver.get('tab_number')
                            output_shifts.append(shift_rec)

                            driver_rec = record_base.copy()
                            driver_rec["tab_number"] = driver.get('tab_number')
                            driver_rec["schedule_type"] = driver.get('schedule_type')
                            driver_rec["mode"] = driver.get('mode')
                            driver_rec["next_available_time"] = driver["next_available_time"].strftime("%Y-%m-%d %H:%M")
                            output_drivers.append(driver_rec)

                            drivers_shift_2.remove(driver)
                            break
                        else:
                            print(
                                f"День {day}. Нет водителя на СМЕНУ 2! Маршрут {route_number}, Трамвай {tram_number} ({start_time.strftime('%H:%M')})")
                            unassigned_shifts_count += 1

                        assigned_tabs_today = set(s["assigned_driver"] for s in output_shifts if s["day"] == day)

                        for driver in present_drivers_data:
                            planned_shift = driver.get("days", {}).get(str_day)
                            if planned_shift in ["1", "2"]:
                                if driver.get("tab_number") not in assigned_tabs_today:
                                    driver["missed_days"] += 1

                    os.makedirs(os.path.dirname(config.OUTPUT_SHIFTS), exist_ok=True)

                    with open(config.OUTPUT_SHIFTS, 'w', encoding='utf-8') as f:
                        json.dump(output_shifts, f, ensure_ascii=False, indent=2)

                    with open(config.OUTPUT_DRIVERS, 'w', encoding='utf-8') as f:
                        json.dump(output_drivers, f, ensure_ascii=False, indent=2)

                    active_count = sum(1 for d in drivers_data if d["is_active"])
                    print(f"Задействовано водителей: {active_count} из {len(drivers_data)}")

                if name == "main":
                    main()