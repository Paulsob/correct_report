import sys
import os
import json
import calendar
import time

# Подключаем конфиг
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import (
    load_reference_data, load_absences_data, is_absent, is_qualified,
    count_permits, load_matrix_data, get_required_role, get_day_type
)

ANCHOR_DATE = 1
YEAR = int(config.TARGET_YEAR)
MONTH = int(config.TARGET_MONTH)
DAYS_IN_MONTH = calendar.monthrange(YEAR, MONTH)[1]
CUSTOM_HOLIDAYS = []

PRIMARY_SCHEDULE = config.PRIMARY_SCHEDULE


def generate_single_schedule():
    start_time = time.time()
    print("=" * 60)
    print(f" СТАРТ МАТРИЧНОГО МОДЕЛИРОВАНИЯ (С УЧЕТОМ ОТСУТСТВИЙ)")
    print(f" График: {PRIMARY_SCHEDULE}")
    print(f" Период: {YEAR}-{MONTH:02d}")
    print("=" * 60)

    route_models_dict, permits_dict = load_reference_data()
    matrix_primary, cycle_length_primary = load_matrix_data(PRIMARY_SCHEDULE)
    absences_data = load_absences_data()

    with open(config.SCHEDULE_PREPARED, "r", encoding="utf-8") as f:
        trams_data = json.load(f)
    with open(config.DRIVERS_PREPARED, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    drivers_list = drivers_data.get("drivers", []) if isinstance(drivers_data, dict) else drivers_data

    all_drivers = []
    for driver in drivers_list:
        if driver.get("schedule_type") == PRIMARY_SCHEDULE:
            driver["schedule_dict"] = driver.get("days", {})
            all_drivers.append(driver)

    print(f"\nАнализ пула: найдено {len(all_drivers)} водителей графика {PRIMARY_SCHEDULE}.")
    if absences_data:
        print(f"Загружена база отсутствий: {len(absences_data)} записей.")
    else:
        print("База отсутствий пуста или не найдена.")

    print("-" * 60)

    monthly_result = []
    total_assigned = 0
    total_unassigned = 0
    used_drivers = set()

    count_stage_1 = 0
    count_stage_2 = 0
    count_stage_3 = 0

    for current_day in range(1, DAYS_IN_MONTH + 1):
        cycle_day_primary = ((current_day - ANCHOR_DATE) % cycle_length_primary) + 1
        current_day_type = get_day_type(current_day, YEAR, MONTH, CUSTOM_HOLIDAYS)
        current_date_str = f"{YEAR}-{MONTH:02d}-{current_day:02d}"

        daily_assignments = []
        daily_unassigned = []

        available_today = []
        for d in all_drivers:
            if str(d.get("schedule_dict", {}).get(str(current_day), "В")) == "В":
                continue
            if is_absent(d.get("tab_number"), current_date_str, absences_data):
                continue
            available_today.append(d)

        day_assigned = 0

        for route in trams_data:
            if route.get("день") and route.get("день") != current_day_type:
                continue

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
                    req_role = get_required_role(cycle_day_primary, target_slot_primary, matrix_primary) if target_slot_primary else None

                    if not req_role or not block_id_primary:
                        daily_unassigned.append({
                            "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                            "причина": "Ошибка данных расписания"
                        })
                        continue

                    # ЭТАП 1: Идеальное совпадение
                    candidates_native = [
                        d for d in available_today
                        if d.get("block_id") == block_id_primary
                           and str(d.get("matrix_role")) == str(req_role)
                           and is_qualified(d, route_num, required_models, permits_dict)
                    ]

                    if candidates_native:
                        pick = candidates_native[0]
                        available_today.remove(pick)
                        used_drivers.add(pick.get("tab_number"))
                        daily_assignments.append({
                            "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                            "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                            "график_водителя": PRIMARY_SCHEDULE,
                            "таб_номер_водителя": pick.get("tab_number"),
                            "роль_по_матрице": req_role,
                            "комментарий": "Штатное совпадение"
                        })
                        is_assigned = True
                        day_assigned += 1
                        count_stage_1 += 1

                    # ЭТАП 2: Перехват (Та же Роль)
                    if not is_assigned:
                        candidates_backup = [
                            d for d in available_today
                            if str(d.get("matrix_role")) == str(req_role)
                               and is_qualified(d, route_num, required_models, permits_dict)
                        ]
                        if candidates_backup:
                            candidates_backup.sort(key=lambda x: count_permits(x.get("tab_number"), permits_dict))
                            pick = candidates_backup[0]
                            available_today.remove(pick)
                            used_drivers.add(pick.get("tab_number"))
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": PRIMARY_SCHEDULE,
                                "таб_номер_водителя": pick.get("tab_number"),
                                "роль_по_матрице": req_role,
                                "комментарий": f"Резерв (Блок {pick.get('block_id')})"
                            })
                            is_assigned = True
                            day_assigned += 1
                        count_stage_2 += 1

                    # ЭТАП 3: Глубокий резерв
                    if not is_assigned:
                        candidates_any = [
                            d for d in available_today
                            if is_qualified(d, route_num, required_models, permits_dict)
                        ]
                        if candidates_any:
                            candidates_any.sort(key=lambda x: count_permits(x.get("tab_number"), permits_dict))
                            pick = candidates_any[0]
                            available_today.remove(pick)
                            used_drivers.add(pick.get("tab_number"))
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": PRIMARY_SCHEDULE,
                                "таб_номер_водителя": pick.get("tab_number"),
                                "роль_по_матрице": pick.get("matrix_role"),
                                "комментарий": f"Глубокий резерв (Блок {pick.get('block_id')}, Роль {pick.get('matrix_role')} вместо {req_role})"
                            })
                            is_assigned = True
                            day_assigned += 1

                    if not is_assigned:
                        daily_unassigned.append({
                            "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                            "причина": f"Нет водителей с допусками (требуется роль {req_role})"
                        })

                        count_stage_3 += 1

        total_assigned += day_assigned
        total_unassigned += len(daily_unassigned)

        print(f"День {current_day:02d} | {current_day_type.ljust(8)} | Назначено: {day_assigned:3} | Резерв на базе: {len(available_today):2} | Открыто: {len(daily_unassigned):2}")

        monthly_result.append({
            "дата": f"{current_date_str}", "тип_дня": current_day_type,
            "день_цикла": cycle_day_primary, "успешные_назначения": daily_assignments,
            "открытые_смены_без_водителя": daily_unassigned
        })

    print("-" * 60)
    output_dir = config.get_schedule_output_dir(PRIMARY_SCHEDULE)
    os.makedirs(output_dir, exist_ok=True)
    final_output_path = os.path.join(output_dir, f"{PRIMARY_SCHEDULE}_BLOCK_final_schedule.json")

    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(monthly_result, f, ensure_ascii=False, indent=2)

    print(f"\nФайл сохранён: {final_output_path}")
    print("=" * 60)
    print(" ИТОГИ:")
    print(f"  - Успешно назначено: {total_assigned} смен")
    print(f"    ├─ ЭТАП 1 (Родные):      {count_stage_1}")
    print(f"    ├─ ЭТАП 2 (Дублеры):     {count_stage_2}")
    print(f"    └─ ЭТАП 3 (Любые):       {count_stage_3}")
    print(f"  - Не закрыто:        {total_unassigned} смен")
    if config.SIMULATE_OPTIMAL_STAFF:
        print(f"  - ОПТИМИЗАЦИЯ: Фактически задействовано уникальных водителей: {len(used_drivers)} чел.")
    print("=" * 60)
    return len(used_drivers), total_unassigned, total_assigned


if __name__ == "__main__":
    generate_single_schedule()