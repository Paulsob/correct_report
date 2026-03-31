import json
import os
from datetime import datetime, timedelta
from ortools.sat.python import cp_model

# Константы для парсинга месяцев
MONTHS = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12
}


class Shift:
    def __init__(self, shift_id, day, type_str, tram_num, start_dt, end_dt):
        self.id = shift_id
        self.day = day
        self.type_str = type_str
        self.tram_num = tram_num
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.duration = (end_dt - start_dt).total_seconds() / 3600.0


def parse_time(base_date, time_str):
    h, m = map(int, time_str.split(':'))
    dt = base_date.replace(hour=h, minute=m, second=0, microsecond=0)
    return dt


def solve_schedule(rest_mode):
    """
    Основная логика решения задачи.
    :param rest_mode: 1 = Строгий, 2 = Смягченный
    :return: Кортеж данных для отчета или None при ошибке
    """
    # Пути к данным (относительно расположения скрипта)
    base_path = os.path.dirname(os.path.abspath(__file__))
    drivers_path = os.path.join(base_path, "../data/4x2_10_drivers_october.json")
    schedule_path = os.path.join(base_path, "../data/schedule.json")

    if not os.path.exists(drivers_path) or not os.path.exists(schedule_path):
        print("ОШИБКА: Файлы данных не найдены!")
        return None

    with open(drivers_path, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    with open(schedule_path, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)

    year = drivers_data.get("year", 2026)
    month_name = drivers_data.get("month", "Октябрь").lower()
    month = MONTHS.get(month_name, 10)

    schedule_by_type = {item["день"]: item["трамваи"] for item in schedule_data}

    max_days = 0
    drivers_dict = {}
    drivers = []

    for d in drivers_data["drivers"]:
        pattern = {item["day"]: item["value"] for item in d.get("days", [])}
        if pattern:
            max_days = max(max_days, max(pattern.keys()))
        driver_obj = {"tab_number": d["tab_number"], "pattern": pattern}
        drivers.append(driver_obj)
        drivers_dict[d["tab_number"]] = driver_obj

    shifts = []
    shift_id_counter = 0

    # ГЕНЕРАЦИЯ СМЕН
    for day in range(1, max_days + 1):
        current_date = datetime(year, month, day)
        day_type = "рабочий" if current_date.weekday() < 5 else "выходной"

        for tram in schedule_by_type.get(day_type, []):
            tram_num = tram["номер"]

            s1_start = parse_time(current_date, tram["смена_1"]["отправление"])
            s1_end = parse_time(current_date, tram["смена_1"]["прибытие"])
            if s1_end < s1_start: s1_end += timedelta(days=1)
            shifts.append(Shift(shift_id_counter, day, "1", tram_num, s1_start, s1_end))
            shift_id_counter += 1

            s2_start = parse_time(current_date, tram["смена_2"]["отправление"])
            s2_end = parse_time(current_date, tram["смена_2"]["прибытие"])
            if s2_end < s2_start: s2_end += timedelta(days=1)
            shifts.append(Shift(shift_id_counter, day, "2", tram_num, s2_start, s2_end))
            shift_id_counter += 1

    model = cp_model.CpModel()
    x = {}

    for shift in shifts:
        for driver in drivers:
            d_id = driver["tab_number"]
            if driver["pattern"].get(shift.day) == shift.type_str:
                x[(d_id, shift.id)] = model.NewBoolVar(f"x_{d_id}_s_{shift.id}")

    # ОГРАНИЧЕНИЕ 1: Максимум 1 водитель на смену
    is_covered = {}
    for shift in shifts:
        shift_vars = [x[(d["tab_number"], shift.id)] for d in drivers if (d["tab_number"], shift.id) in x]
        is_covered[shift.id] = model.NewBoolVar(f"covered_{shift.id}")
        model.Add(sum(shift_vars) == is_covered[shift.id])

    # ОГРАНИЧЕНИЕ 2: Отдых
    print(f"\n--- ЗАПУСК АЛГОРИТМА (МЕСЯЦ: {month_name.capitalize()} {year}) ---")
    if rest_mode == 1:
        print("Режим отдыха: СТРОГИЙ (Отдых >= 2 * Работа)")
    else:
        print("Режим отдыха: СМЯГЧЕННЫЙ (Отдых >= 2 * Работа ИЛИ минимум 12 часов)")
    print("--------------------------------------------------\n")

    for driver in drivers:
        d_id = driver["tab_number"]
        driver_shifts = [s for s in shifts if (d_id, s.id) in x]

        for i in range(len(driver_shifts)):
            for j in range(i + 1, len(driver_shifts)):
                s1 = driver_shifts[i]
                s2 = driver_shifts[j]

                first, second = (s1, s2) if s1.start_dt < s2.start_dt else (s2, s1)
                gap_hours = (second.start_dt - first.end_dt).total_seconds() / 3600.0
                required_rest = first.duration * 2.0

                if rest_mode == 1:
                    if gap_hours < required_rest:
                        model.Add(x[(d_id, first.id)] + x[(d_id, second.id)] <= 1)
                elif rest_mode == 2:
                    if gap_hours < required_rest and gap_hours < 12.0:
                        model.Add(x[(d_id, first.id)] + x[(d_id, second.id)] <= 1)

    # === АГРЕССИВНАЯ ОПТИМИЗАЦИЯ И БАЛАНСИРОВКА РЕЗЕРВОВ ===
    is_used = {}
    reserves = []
    driver_reserves = {d["tab_number"]: {} for d in drivers}

    for driver in drivers:
        d_id = driver["tab_number"]
        is_used[d_id] = model.NewBoolVar(f"used_{d_id}")
        driver_vars = [x[(d_id, s.id)] for s in shifts if (d_id, s.id) in x]

        if driver_vars:
            model.AddMaxEquality(is_used[d_id], driver_vars)
        else:
            model.Add(is_used[d_id] == 0)

        pattern = driver["pattern"]
        for day in range(1, max_days + 1):
            if pattern.get(day) in ["1", "2"]:
                worked_today = model.NewBoolVar(f"worked_{d_id}_{day}")
                shifts_today = [x[(d_id, s.id)] for s in shifts if s.day == day and (d_id, s.id) in x]
                if shifts_today:
                    model.Add(worked_today == sum(shifts_today))
                else:
                    model.Add(worked_today == 0)

                reserve_var = model.NewBoolVar(f"res_{d_id}_{day}")
                model.Add(reserve_var >= is_used[d_id] - worked_today)

                reserves.append(reserve_var)
                driver_reserves[d_id][day] = reserve_var

    # ПРАВИЛО 1: Жесткий запрет на 2 резерва подряд
    for d_id, res_dict in driver_reserves.items():
        for day in range(1, max_days):
            if day in res_dict and (day + 1) in res_dict:
                model.Add(res_dict[day] + res_dict[day + 1] <= 1)

    # ПРАВИЛО 2: Балансировка
    max_reserves_per_driver = model.NewIntVar(0, max_days, "max_res_per_driver")
    for d_id, res_dict in driver_reserves.items():
        if res_dict:
            model.Add(sum(res_dict.values()) <= max_reserves_per_driver)

    # ФОРМУЛА ЦЕЛИ
    model.Maximize(
        100000 * sum(is_covered.values())
        - 10000 * sum(is_used.values())
        - 500 * max_reserves_per_driver
        - 100 * sum(reserves)
    )

    print("Поиск оптимального расписания (OR-Tools)...")
    solver = cp_model.CpSolver()

    # --- НАСТРОЙКИ РЕШАТЕЛЯ ---
    solver.parameters.log_search_progress = True
    solver.parameters.max_time_in_seconds = 120.0
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        covered_count = sum(1 for s in shifts if solver.BooleanValue(is_covered[s.id]))
        used_count = int(sum(solver.BooleanValue(is_used[d["tab_number"]]) for d in drivers))

        print("\n=== РАСПИСАНИЕ СОСТАВЛЕНО ===")
        print(f"Закрыто смен: {covered_count} из {len(shifts)}")
        print(f"Задействовано водителей: {used_count} из {len(drivers)}")

        assigned_shifts = {d["tab_number"]: [] for d in drivers}
        covered_shift_ids = set()

        for shift in shifts:
            if solver.BooleanValue(is_covered[shift.id]):
                covered_shift_ids.add(shift.id)
            for driver in drivers:
                d_id = driver["tab_number"]
                if (d_id, shift.id) in x and solver.BooleanValue(x[(d_id, shift.id)]):
                    assigned_shifts[d_id].append(shift)

        # Возвращаем данные вместо генерации отчета
        return {
            "assigned_shifts": assigned_shifts,
            "all_shifts": shifts,
            "covered_shift_ids": covered_shift_ids,
            "drivers_dict": drivers_dict,
            "max_days": max_days,
            "month_name": month_name,
            "year": year,
            "success": True
        }

    else:
        print("\n[КРИТИЧЕСКАЯ ОШИБКА] Невозможно составить расписание даже частично.")
        return None
