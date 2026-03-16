import json
import os
from datetime import datetime, timedelta
from new_generate_summary_report import auto_generate_report


MONTHLY_NORM_HOURS = 180.0
MIN_HOURS_THRESHOLD = 110.0
REST_MIN_REDUCED = 10

MONTHS = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12
}


history = {}
accumulated_hours = {}
last_worked_day = {}


def load_data():
    with open("10_drivers_october.json", "r", encoding="utf-8") as f:
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

    with open("schedule.json", "r", encoding="utf-8") as f:
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


def find_candidate(pool, day, target_shift, start_dt, duration):
    def sort_key(driver):
        d_id = str(driver["tab_number"])
        hours = accumulated_hours.get(d_id, 0.0)

        if hours == 0:
            return 100000.0

        if hours >= MONTHLY_NORM_HOURS:
            return 200000.0 + hours

        weight = hours

        last_work = last_worked_day.get(d_id, 0)
        reserve_days_count = 0
        if last_work > 0:
            for check_day in range(last_work + 1, day):
                if driver["pattern"].get(check_day, "В") != "В":
                    reserve_days_count += 1

        if reserve_days_count > 0:
            weight -= (reserve_days_count * 50000.0)

        return weight

    valid_pool = []
    for driver in pool:
        d_id = str(driver["tab_number"])

        if d_id in history and history[d_id]["end_dt"].date() == start_dt.date():
            continue

        status = driver["pattern"].get(day, "В")

        if status == "В":
            continue

        if str(status) != str(target_shift):
            continue

        if check_rest_rules(driver, start_dt):
            valid_pool.append(driver)

    if not valid_pool:
        return None, 0, []

    sorted_pool = sorted(valid_pool, key=sort_key)
    return sorted_pool[0], 0, []


def optimize_schedule(roster_result, schedule_data, drivers_list, year, month, rest_min=REST_MIN_REDUCED):
    print("\n[ОПТИМИЗАЦИЯ] Запуск умного диспетчера (Версия 3.1 - Без работы в выходные)...")

    driver_patterns = {str(d["tab_number"]): d.get("pattern", {}) for d in drivers_list}

    driver_shifts = {}
    driver_hours = {}

    for day_num, trams in roster_result.items():
        base_date = datetime(year, month, int(day_num))

        for tram_num, shifts in trams.items():
            tram_source = next(
                (t for t in schedule_data.get("трамваи", []) if str(t["номер"]) == str(tram_num)),
                None
            )
            if not tram_source:
                continue

            for shift_key in ["1", "2"]:
                shift_entry = shifts.get(shift_key)

                if not shift_entry:
                    continue

                d_id = None
                if isinstance(shift_entry, dict):
                    d_id = str(shift_entry.get("driver"))
                elif isinstance(shift_entry, str):
                    if "НЕТ ВОДИТЕЛЯ" in shift_entry or "NO_DRIVER" in shift_entry:
                        continue
                    parts = shift_entry.split()
                    if len(parts) >= 2:
                        d_id = parts[1]
                    else:
                        continue
                else:
                    continue

                if not d_id:
                    continue

                shift_source_key = "смена_1" if shift_key == "1" else "смена_2"
                time_data = tram_source.get(shift_source_key)
                if not time_data:
                    continue

                start_dt, end_dt, duration = get_shift_datetimes(base_date, time_data)

                driver_shifts.setdefault(d_id, []).append(
                    (start_dt, end_dt, duration, day_num, tram_num, shift_key)
                )
                driver_hours[d_id] = driver_hours.get(d_id, 0.0) + duration

    swaps_made = 0
    optimization_running = True
    loop_count = 0
    MAX_LOOPS = 15

    while optimization_running and loop_count < MAX_LOOPS:
        optimization_running = False
        loop_count += 1

        donors = sorted([d for d in driver_hours if 0 < driver_hours[d] < 80],
                        key=lambda x: driver_hours[x])

        for donor_id in donors:
            shifts_to_reassign = list(driver_shifts.get(donor_id, []))

            for shift_info in shifts_to_reassign:
                start_dt, end_dt, duration, day_num, tram_num, shift_key = shift_info

                best_receiver = None
                best_score = -10**9

                for rec_id in driver_hours.keys():
                    if rec_id == donor_id:
                        continue
                    if driver_hours[rec_id] == 0:
                        continue

                    pattern_status = str(driver_patterns.get(rec_id, {}).get(int(day_num), "В"))
                    if pattern_status not in ["1", "2"]:
                        continue

                    new_hours = driver_hours[rec_id] + duration
                    if new_hours > 250:
                        continue

                    rec_shifts = driver_shifts.get(rec_id, [])

                    if any(s[3] == day_num for s in rec_shifts):
                        continue

                    temp_shifts = [(s[0], s[1]) for s in rec_shifts] + [(start_dt, end_dt)]
                    temp_shifts.sort(key=lambda x: x[0])

                    rest_violation = False
                    for i in range(len(temp_shifts) - 1):
                        gap = (temp_shifts[i + 1][0] - temp_shifts[i][1]).total_seconds() / 3600.0
                        if gap < rest_min:
                            rest_violation = True
                            break
                    if rest_violation:
                        continue

                    score = 0
                    is_active_driver = driver_hours[rec_id] >= 80
                    is_bigger_stub = driver_hours[rec_id] > driver_hours[donor_id]

                    if is_active_driver:
                        score += 1000000
                    elif is_bigger_stub:
                        score += 100000
                    else:
                        continue

                    score -= new_hours * 10

                    if score > best_score:
                        best_score = score
                        best_receiver = rec_id

                if best_receiver:
                    driver_shifts[donor_id].remove(shift_info)
                    driver_hours[donor_id] -= duration

                    driver_shifts.setdefault(best_receiver, []).append(shift_info)
                    driver_hours[best_receiver] = driver_hours.get(best_receiver, 0.0) + duration

                    roster_result[day_num][tram_num][shift_key] = {
                        "driver": str(best_receiver),
                        "duration": round(duration, 1),
                        "start_dt": start_dt.isoformat(),
                        "end_dt": end_dt.isoformat()
                    }

                    swaps_made += 1
                    optimization_running = True
                    print(f"  [+] Смена {day_num} числа передана: {donor_id} -> {best_receiver} (очки: {best_score})")
                    break

    culled_shifts = 0
    for d_id, hours in list(driver_hours.items()):
        if 0 < hours < MIN_HOURS_THRESHOLD:
            for s in list(driver_shifts.get(d_id, [])):
                day_num, tram_num, shift_key = s[3], s[4], s[5]
                roster_result[day_num][tram_num][shift_key] = "НЕТ ВОДИТЕЛЯ"
                culled_shifts += 1

            driver_shifts[d_id] = []
            driver_hours[d_id] = 0.0
            print(f"  [!] Водитель {d_id} аннулирован ({hours:.1f} ч.). Его рейсы сняты.")

    print(f"[ОПТИМИЗАЦИЯ] Завершена! Перестановок: {swaps_made}. Аннулировано смен: {culled_shifts}\n")
    return roster_result


def build_schedule(drivers, schedule_data, year, month, days_in_month):
    roster_result = {}

    for day in range(1, days_in_month + 1):
        try:
            base_date = datetime(year, month, day)
        except ValueError:
            break

        roster_result[day] = {}
        trams = schedule_data.get("трамваи", [])

        for tram in trams:
            tram_num = tram["номер"]
            roster_result[day][tram_num] = {"1": None, "2": None}

            for shift_key, shift_name in [("1", "смена_1"), ("2", "смена_2")]:
                shift_data = tram.get(shift_name)
                if shift_data:
                    start_dt, end_dt, duration = get_shift_datetimes(base_date, shift_data)
                    driver, rest_hours, warnings = find_candidate(drivers, day, int(shift_key), start_dt, duration)

                    if driver:
                        d_id = str(driver["tab_number"])
                        history[d_id] = {"end_dt": end_dt, "duration": duration, "rest_hours": rest_hours}
                        accumulated_hours[d_id] = accumulated_hours.get(d_id, 0) + duration

                        last_worked_day[d_id] = day

                        roster_result[day][tram_num][shift_key] = {
                            "driver": d_id,
                            "duration": round(duration, 1),
                            "start_dt": start_dt.isoformat(),
                            "end_dt": end_dt.isoformat()
                        }
                    else:
                        roster_result[day][tram_num][shift_key] = "НЕТ ВОДИТЕЛЯ"
    return roster_result


if __name__ == "__main__":
    if not os.path.exists("10_drivers_october.json") or not os.path.exists("schedule.json"):
        print("ОШИБКА: Рядом со скриптом должны лежать файлы 10_drivers_october.json и schedule.json")
    else:
        drivers_list, target_schedule, y, m, total_days = load_data()

        final_schedule = build_schedule(drivers_list, target_schedule, y, m, total_days)
        final_schedule = optimize_schedule(final_schedule, target_schedule, drivers_list, y, m)

        with open("schedule_output.json", "w", encoding="utf-8") as f:
            json.dump(final_schedule, f, ensure_ascii=False, indent=2)

        auto_generate_report(final_schedule, drivers_list, output_excel="Расписание_Октябрь_Оптимизировано.xlsx")