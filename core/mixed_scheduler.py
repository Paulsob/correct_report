import sys
import os
import random
import json
import calendar
import time

# Подключаем конфиг
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import (
    load_reference_data, load_absences_data, is_absent, is_qualified,
    count_permits, calculate_dynamic_quotas, load_matrix_data, get_required_role, get_day_type
)

ANCHOR_DATE = 1
YEAR = int(config.TARGET_YEAR)
MONTH = int(config.TARGET_MONTH)
DAYS_IN_MONTH = calendar.monthrange(YEAR, MONTH)[1]
CUSTOM_HOLIDAYS = []

PRIMARY_SCHEDULE = config.PRIMARY_SCHEDULE
SECONDARY_SCHEDULE = config.SECONDARY_SCHEDULE
SIMULATE_OPTIMAL_STAFF = config.SIMULATE_OPTIMAL_STAFF


def build_hybrid_driver_pools(drivers_data):
    pool_primary = {}
    pool_secondary = []

    drivers_list = drivers_data.get("drivers", []) if isinstance(drivers_data, dict) else drivers_data

    for driver in drivers_list:
        sched_type = driver.get("schedule_type")
        driver["schedule_dict"] = driver.get("days", {})

        if sched_type == PRIMARY_SCHEDULE:
            b_id = driver.get("block_id")
            m_role = driver.get("matrix_role")
            if b_id not in pool_primary: pool_primary[b_id] = {}
            pool_primary[b_id][m_role] = driver
        elif SECONDARY_SCHEDULE and sched_type == SECONDARY_SCHEDULE:
            pool_secondary.append(driver)

    return pool_primary, pool_secondary


def generate_hybrid_schedule():
    start_time = time.time()
    print("=" * 60)
    mode_str = "ОПТИМИЗАЦИЯ ШТАТА ВКЛЮЧЕНА" if SIMULATE_OPTIMAL_STAFF else "ТЕКУЩИЙ ШТАТ"
    print(f" СТАРТ ГИБРИДНОГО МОДЕЛИРОВАНИЯ ({mode_str})")
    print(f" Период: {YEAR}-{MONTH:02d}")
    print("=" * 60)

    route_models_dict, permits_dict = load_reference_data()
    absences_data = load_absences_data()

    matrix_primary, cycle_length_primary = load_matrix_data(PRIMARY_SCHEDULE)
    with open(config.SCHEDULE_PREPARED, "r", encoding="utf-8") as f:
        trams_data = json.load(f)
    with open(config.DRIVERS_PREPARED, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    pool_primary, pool_secondary = build_hybrid_driver_pools(drivers_data)
    quotas = calculate_dynamic_quotas(trams_data, buffer_weekend=2)

    print("\nАНАЛИТИКА НАГРУЗКИ И ПУЛА:")
    print(f" Смен в будни: {quotas['weekday_shifts']} | В выходные: {quotas['weekend_shifts']}")
    if absences_data:
        print(f" Загружена база отсутствий: {len(absences_data)} записей.")

    if SECONDARY_SCHEDULE:
        print(f" Рекомендуемый штат {SECONDARY_SCHEDULE}: {quotas['recommended_secondary']} чел.")
        print(f" Фактический пул {SECONDARY_SCHEDULE}:    {len(pool_secondary)} чел.\n")
    else:
        print(" Вспомогательный график отключен.\n")

    max_active_primary = quotas["limit_weekend"] * 2 if SIMULATE_OPTIMAL_STAFF else quotas["limit_weekday"] * 2
    print(f" Лимит активных водителей {PRIMARY_SCHEDULE}: {max_active_primary}\n")

    monthly_result = []
    total_assigned_primary = 0
    total_assigned_secondary = 0
    total_unassigned = 0
    unassigned_weekend = 0
    unassigned_qualification = 0
    overall_used_drivers = set()

    print("Генерация расписания по дням:")
    print("-" * 60)

    for current_day in range(1, DAYS_IN_MONTH + 1):
        cycle_day_primary = ((current_day - ANCHOR_DATE) % cycle_length_primary) + 1
        current_day_type = get_day_type(current_day, YEAR, MONTH, CUSTOM_HOLIDAYS)
        current_date_str = f"{YEAR}-{MONTH:02d}-{current_day:02d}"

        daily_assignments = []
        daily_unassigned = []
        day_assigned_primary = 0
        day_assigned_secondary = 0
        daily_quota_primary = max_active_primary

        available_secondary_today = [
            d for d in pool_secondary
            if d["schedule_dict"].get(str(current_day), "В") in ["1", "2"]
               and not is_absent(d.get("tab_number"), current_date_str, absences_data)
        ]

        available_primary_today = []
        for b_id, roles_dict in pool_primary.items():
            for role, driver in roles_dict.items():
                day_index = cycle_day_primary - 1
                target_slot = matrix_primary[int(role)][day_index]
                if target_slot != "В":
                    expected_status = "1" if target_slot % 2 != 0 else "2"
                    actual_status = driver["schedule_dict"].get(str(current_day), "Нет данных")
                    if actual_status == expected_status or actual_status in ["1", "2"]:
                        if not is_absent(driver.get("tab_number"), current_date_str, absences_data):
                            available_primary_today.append({
                                "block_id": b_id, "role": str(role), "driver": driver
                            })

        for route in trams_data:
            if route.get("день") and route.get("день") != current_day_type: continue
            route_num = route.get("маршрут")
            required_models = route_models_dict.get(str(route_num), [])

            for tram in route.get("трамваи", []):
                block_id_primary = tram.get("block_ids", {}).get(PRIMARY_SCHEDULE)
                tram_num = tram.get("номер")
                shifts = []
                if tram.get("смена_1"): shifts.append(("Утро", tram["смена_1"]))
                if tram.get("смена_2"): shifts.append(("Вечер", tram["смена_2"]))

                for shift_name, shift_data in shifts:
                    is_assigned = False
                    target_slot_primary = shift_data.get("matrix_slots", {}).get(PRIMARY_SCHEDULE)
                    required_role = get_required_role(cycle_day_primary, target_slot_primary, matrix_primary) if target_slot_primary else None

                    # ЭТАП 1: РОДНОЙ ВОДИТЕЛЬ
                    if target_slot_primary and block_id_primary and (day_assigned_primary < daily_quota_primary):
                        candidates = [
                            x for x in available_primary_today
                            if x["block_id"] == block_id_primary and x["role"] == str(required_role)
                               and is_qualified(x["driver"], route_num, required_models, permits_dict)
                        ]
                        if candidates:
                            candidates.sort(key=lambda x: count_permits(x["driver"].get("tab_number"), permits_dict))
                            pick = candidates[0]
                            available_primary_today.remove(pick)
                            overall_used_drivers.add(pick["driver"].get("tab_number"))
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": PRIMARY_SCHEDULE,
                                "таб_номер_водителя": pick["driver"].get("tab_number"),
                                "роль_по_матрице": required_role,
                                "комментарий": "Штатное совпадение"
                            })
                            is_assigned = True
                            day_assigned_primary += 1

                    # ЭТАП 1.5: РЕЗЕРВ (Та же роль)
                    if not is_assigned and (day_assigned_primary < daily_quota_primary):
                        candidates = [
                            x for x in available_primary_today
                            if str(x["role"]) == str(required_role)
                               and is_qualified(x["driver"], route_num, required_models, permits_dict)
                        ]
                        if candidates:
                            candidates.sort(key=lambda x: count_permits(x["driver"].get("tab_number"), permits_dict))
                            pick = candidates[0]
                            available_primary_today.remove(pick)
                            overall_used_drivers.add(pick["driver"].get("tab_number"))
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": PRIMARY_SCHEDULE,
                                "таб_номер_водителя": pick["driver"].get("tab_number"),
                                "роль_по_матрице": required_role,
                                "комментарий": f"Резерв (Блок {pick['block_id']})"
                            })
                            is_assigned = True
                            day_assigned_primary += 1

                    # ЭТАП 1.8: ГЛУБОКИЙ РЕЗЕРВ
                    if not is_assigned and (day_assigned_primary < daily_quota_primary):
                        candidates = [
                            x for x in available_primary_today
                            if is_qualified(x["driver"], route_num, required_models, permits_dict)
                        ]
                        if candidates:
                            candidates.sort(key=lambda x: count_permits(x["driver"].get("tab_number"), permits_dict))
                            pick = candidates[0]
                            available_primary_today.remove(pick)
                            overall_used_drivers.add(pick["driver"].get("tab_number"))
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": PRIMARY_SCHEDULE,
                                "таб_номер_водителя": pick["driver"].get("tab_number"),
                                "роль_по_матрице": pick["role"],
                                "комментарий": "Глубокий резерв"
                            })
                            is_assigned = True
                            day_assigned_primary += 1

                    # ЭТАП 2: 5x2h В БУДНИ
                    if not is_assigned and current_day_type == "рабочий":
                        qualified_5x2h = [d for d in available_secondary_today
                                          if is_qualified(d, route_num, required_models, permits_dict)]
                        if qualified_5x2h:
                            qualified_5x2h.sort(key=lambda d: count_permits(d.get("tab_number"), permits_dict))
                            driver_sec = qualified_5x2h[0]
                            available_secondary_today.remove(driver_sec)
                            overall_used_drivers.add(driver_sec.get("tab_number"))
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": SECONDARY_SCHEDULE,
                                "таб_номер_водителя": driver_sec.get("tab_number"),
                                "роль_по_матрице": "Без роли",
                                "комментарий": f"Штатная смена {SECONDARY_SCHEDULE}"
                            })
                            is_assigned = True
                            day_assigned_secondary += 1

                    if not is_assigned:
                        if current_day_type == "выходной":
                            unassigned_weekend += 1
                            reason = f"Выходной: лимит {PRIMARY_SCHEDULE} исчерпан"
                        else:
                            unassigned_qualification += 1
                            reason = "Нет свободного водителя"

                        daily_unassigned.append(
                            {"маршрут": route_num, "трамвай": tram_num, "смена": shift_name, "причина": reason})

        total_assigned_primary += day_assigned_primary
        total_assigned_secondary += day_assigned_secondary
        total_unassigned += len(daily_unassigned)

        sec_label = SECONDARY_SCHEDULE if SECONDARY_SCHEDULE else "Откл"
        print(f"День {current_day:02d} | {current_day_type.ljust(8)} | {PRIMARY_SCHEDULE}: {day_assigned_primary:3} | {sec_label}: {day_assigned_secondary:3} | Резерв: {len(available_primary_today):2} | Открыто: {len(daily_unassigned):2}")
        monthly_result.append({
            "дата": f"{current_date_str}", "тип_дня": current_day_type,
            "день_цикла": cycle_day_primary, "успешные_назначения": daily_assignments,
            "открытые_смены_без_водителя": daily_unassigned
        })

    print("-" * 60)
    output_dir = config.get_schedule_output_dir(PRIMARY_SCHEDULE, SECONDARY_SCHEDULE)
    os.makedirs(output_dir, exist_ok=True)
    file_prefix = f"{PRIMARY_SCHEDULE}_{SECONDARY_SCHEDULE}" if SECONDARY_SCHEDULE else PRIMARY_SCHEDULE
    final_output_path = os.path.join(output_dir, f"{file_prefix}_BLOCK_final_schedule.json")

    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(monthly_result, f, ensure_ascii=False, indent=2)

    print(f"\nФайл сохранён: {final_output_path}")
    print("=" * 60)
    print(" ИТОГИ:")
    print(f"  - Назначено {PRIMARY_SCHEDULE}:  {total_assigned_primary}")
    if SECONDARY_SCHEDULE:
        print(f"  - Назначено {SECONDARY_SCHEDULE}: {total_assigned_secondary}")

    print(f"  - ВСЕГО уникальных водителей: {len(overall_used_drivers)} чел.")
    print(f"  - Не закрыто всего:     {total_unassigned}")
    print(f"    ├─ Из-за выходных (лимит {PRIMARY_SCHEDULE}): {unassigned_weekend}")
    print(f"    └─ Из-за квалификации/пула:    {unassigned_qualification}")
    print("=" * 60)
    print("=" * 60)
    return len(overall_used_drivers), total_unassigned, (total_assigned_primary + total_assigned_secondary)



if __name__ == "__main__":
    generate_hybrid_schedule()