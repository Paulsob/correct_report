import sys
import os
import random
import json
from datetime import date
import calendar
import time

# Подключаем конфиг
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

ANCHOR_DATE = 1
YEAR = int(config.TARGET_YEAR)
MONTH = int(config.TARGET_MONTH)
DAYS_IN_MONTH = calendar.monthrange(YEAR, MONTH)[1]
CUSTOM_HOLIDAYS = []

PRIMARY_SCHEDULE = "4x2"
SECONDARY_SCHEDULE = "5x2h"
SIMULATE_OPTIMAL_STAFF = True


def load_reference_data():
    ref_dir = os.path.join(config.BASE_DIR, "input_data", "02_reference")

    route_models_dict = {}
    try:
        with open(os.path.join(ref_dir, "route_types.json"), "r", encoding="utf-8") as f:
            route_types_list = json.load(f)
        for item in route_types_list:
            route_num = str(item.get("маршрут"))
            models = []
            for tram_info in item.get("трамваи", []):
                models.extend(tram_info.get("модели", []))
            route_models_dict[route_num] = list(set(models))
    except FileNotFoundError:
        print("route_types.json не найден. Проверки моделей отключены.")

    permits_dict = {}
    try:
        with open(os.path.join(ref_dir, "permits_synthetic.json"), "r", encoding="utf-8") as f:
            permits_raw = json.load(f)
        if isinstance(permits_raw, list):
            for p in permits_raw:
                tab = str(p.get("tab_number"))
                if tab:
                    permits_dict[tab] = {
                        "routes": p.get("routes", []),
                        "models": p.get("models", [])
                    }
        elif isinstance(permits_raw, dict):
            permits_dict = permits_raw
    except FileNotFoundError:
        print("permits_synthetic.json не найден. Проверки допусков отключены.")

    return route_models_dict, permits_dict


def is_qualified(driver, route_num, required_models, permits_data):
    tab_num = str(driver.get('tab_number'))
    driver_permits = permits_data.get(tab_num, {})

    allowed_routes = driver_permits.get("routes", [])
    route_ok = (str(route_num) in allowed_routes) or ("ALL" in allowed_routes) or (not allowed_routes)

    allowed_driver_models = driver_permits.get("models", [])
    model_ok = True
    if required_models and allowed_driver_models and "ALL" not in allowed_driver_models:
        model_ok = any(m in allowed_driver_models for m in required_models)

    return route_ok and model_ok


def count_permits(tab_num, permits_data):
    """Возвращает общее количество допусков у водителя (маршруты + модели)"""
    p = permits_data.get(str(tab_num), {})
    return len(p.get("routes", [])) + len(p.get("models", []))


def calculate_dynamic_quotas(trams_data, buffer_weekend=2):
    weekday_shifts = 0
    weekend_shifts = 0
    for route in trams_data:
        day_type = route.get("день")
        if not day_type: continue
        route_shifts = sum(1 for t in route.get("трамваи", []) if t.get("смена_1") or t.get("смена_2"))
        if day_type == "рабочий":
            weekday_shifts += route_shifts
        elif day_type in ("выходной", "праздник"):
            weekend_shifts += route_shifts

    return {
        "limit_weekday": max(1, weekday_shifts),
        "limit_weekend": weekend_shifts + buffer_weekend,
        "weekday_shifts": weekday_shifts,
        "weekend_shifts": weekend_shifts,
        "recommended_5x2h": max(0, weekday_shifts - (weekend_shifts + buffer_weekend))
    }


def load_matrix_data(schedule_type):
    with open(config.MATRICES_FILE, "r", encoding="utf-8") as f:
        all_matrices = json.load(f)
    if schedule_type not in all_matrices:
        raise ValueError(f"Ошибка: График '{schedule_type}' не найден!")
    matrix_data = all_matrices[schedule_type]
    active_matrix = {int(k): v for k, v in matrix_data["matrix"].items()}
    return active_matrix, matrix_data["cycle_length"]


def get_required_role(cycle_day, target_slot, active_matrix):
    day_index = cycle_day - 1
    for role, days_list in active_matrix.items():
        if days_list[day_index] == target_slot:
            return role
    return None


def build_hybrid_driver_pools(drivers_data):
    pool_primary = {}
    pool_secondary = []
    for driver in drivers_data.get("drivers", []):
        sched_type = driver.get("schedule_type")
        driver["schedule_dict"] = driver.get("days", {})
        if sched_type == PRIMARY_SCHEDULE:
            b_id = driver.get("block_id")
            m_role = driver.get("matrix_role")
            if b_id not in pool_primary: pool_primary[b_id] = {}
            pool_primary[b_id][m_role] = driver
        elif sched_type == SECONDARY_SCHEDULE:
            pool_secondary.append(driver)
    return pool_primary, pool_secondary


def get_day_type(day):
    if day in CUSTOM_HOLIDAYS or date(YEAR, MONTH, day).weekday() >= 5:
        return "выходной"
    return "рабочий"


def generate_hybrid_schedule():
    start_time = time.time()
    print("=" * 60)
    mode_str = "ОПТИМИЗАЦИЯ ШТАТА ВКЛЮЧЕНА" if SIMULATE_OPTIMAL_STAFF else "ТЕКУЩИЙ ШТАТ"
    print(f" СТАРТ ГИБРИДНОГО МОДЕЛИРОВАНИЯ ({mode_str})")
    print(f" Период: {YEAR}-{MONTH:02d}")
    print("=" * 60)

    route_models_dict, permits_dict = load_reference_data()

    matrix_primary, cycle_length_primary = load_matrix_data(PRIMARY_SCHEDULE)
    with open(config.SCHEDULE_PREPARED, "r", encoding="utf-8") as f:
        trams_data = json.load(f)
    with open(config.DRIVERS_PREPARED, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    pool_primary, pool_secondary = build_hybrid_driver_pools(drivers_data)
    quotas = calculate_dynamic_quotas(trams_data, buffer_weekend=2)

    print("\nАНАЛИТИКА НАГРУЗКИ:")
    print(f" Смен в будни: {quotas['weekday_shifts']} | В выходные: {quotas['weekend_shifts']}")
    print(f" Рекомендуемый штат 5x2h: {quotas['recommended_5x2h']} чел.")
    print(f" Фактический пул 5x2h:    {len(pool_secondary)} чел.\n")

    base_weekend_blocks = set()
    for route in trams_data:
        if route.get("день") == "рабочий": continue
        for tram in route.get("трамваи", []):
            if tram.get("день") == "рабочий": continue
            b_id = tram.get("block_ids", {}).get(PRIMARY_SCHEDULE)
            if b_id: base_weekend_blocks.add(b_id)

    max_active_4x2 = quotas["limit_weekend"] * 2 if SIMULATE_OPTIMAL_STAFF else quotas["limit_weekday"] * 2
    print(f" Лимит активных водителей 4x2: {max_active_4x2}")
    print(f" Работает базовых блоков 4x2: {len(base_weekend_blocks)}\n")

    monthly_result = []
    total_assigned_primary = 0
    total_assigned_secondary = 0
    total_unassigned = 0
    unassigned_weekend = 0
    unassigned_qualification = 0

    print("Генерация расписания по дням:")
    print("-" * 60)

    for current_day in range(1, DAYS_IN_MONTH + 1):
        cycle_day_primary = ((current_day - ANCHOR_DATE) % cycle_length_primary) + 1
        current_day_type = get_day_type(current_day)
        daily_assignments = []
        daily_unassigned = []
        day_assigned_primary = 0
        day_assigned_secondary = 0
        daily_quota_4x2 = max_active_4x2

        available_secondary_today = [
            d for d in pool_secondary if d["schedule_dict"].get(str(current_day), "В") in ["1", "2"]
        ]

        available_primary_today = []
        for b_id in base_weekend_blocks:
            roles_dict = pool_primary.get(b_id, {})
            for role, driver in roles_dict.items():
                day_index = cycle_day_primary - 1
                target_slot = matrix_primary[int(role)][day_index]
                if target_slot != "В":
                    expected_status = "1" if target_slot % 2 != 0 else "2"
                    actual_status = driver["schedule_dict"].get(str(current_day), "Нет данных")
                    if actual_status == expected_status:
                        available_primary_today.append({
                            "block_id": b_id, "role": str(role), "driver": driver
                        })

        if SIMULATE_OPTIMAL_STAFF:
            random.shuffle(available_primary_today)
            available_primary_today = available_primary_today[:daily_quota_4x2]

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
                    required_role = get_required_role(cycle_day_primary, target_slot_primary,
                                                      matrix_primary) if target_slot_primary else None

                    # --- ЭТАП 1: РОДНОЙ ВОДИТЕЛЬ + ПРОВЕРКА ДОПУСКОВ ---
                    if target_slot_primary and block_id_primary and (day_assigned_primary < daily_quota_4x2):
                        candidates = [
                            x for x in available_primary_today
                            if x["block_id"] == block_id_primary and x["role"] == str(required_role)
                               and is_qualified(x["driver"], route_num, required_models, permits_dict)
                        ]
                        if candidates:
                            # Сортируем: сначала те, у кого МЕНЬШЕ допусков
                            candidates.sort(key=lambda x: count_permits(x["driver"].get("tab_number"), permits_dict))
                            pick = candidates[0]
                            available_primary_today.remove(pick)
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": PRIMARY_SCHEDULE,
                                "таб_номер_водителя": pick["driver"].get("tab_number"),
                                "роль_по_матрице": required_role,
                                "комментарий": "Идеальное совпадение (допуски ОК, приоритет по дефициту)"
                            })
                            is_assigned = True
                            day_assigned_primary += 1

                    # --- ЭТАП 1.5: КРОСС-БЛОЧНЫЙ ПЕРЕХВАТ + ДОПУСКИ ---
                    if not is_assigned and (day_assigned_primary < daily_quota_4x2):
                        candidates = [
                            x for x in available_primary_today
                            if is_qualified(x["driver"], route_num, required_models, permits_dict)
                        ]
                        if candidates:
                            candidates.sort(key=lambda x: count_permits(x["driver"].get("tab_number"), permits_dict))
                            pick = candidates[0]
                            available_primary_today.remove(pick)
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": PRIMARY_SCHEDULE,
                                "таб_номер_водителя": pick["driver"].get("tab_number"),
                                "роль_по_матрице": pick["role"],
                                "комментарий": f"Перехват (Блок {pick['block_id']}, допуски ОК, приоритет по дефициту)"
                            })
                            is_assigned = True
                            day_assigned_primary += 1

                    # --- ЭТАП 2: 5x2h (ТОЛЬКО БУДНИ) ---
                    if not is_assigned and current_day_type == "рабочий":
                        # Добавлена проверка допусков и для 5x2h для согласованности системы
                        qualified_5x2h = [d for d in available_secondary_today
                                          if is_qualified(d, route_num, required_models, permits_dict)]
                        if qualified_5x2h:
                            qualified_5x2h.sort(key=lambda d: count_permits(d.get("tab_number"), permits_dict))
                            driver_sec = qualified_5x2h[0]
                            available_secondary_today.remove(driver_sec)
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": SECONDARY_SCHEDULE,
                                "таб_номер_водителя": driver_sec.get("tab_number"),
                                "роль_по_матрице": "Без роли",
                                "комментарий": "Штатная смена 5x2h (допуски ОК)"
                            })
                            is_assigned = True
                            day_assigned_secondary += 1
                        else:
                            daily_unassigned.append({"маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                                     "причина": "Пул 5x2h пуст или нет допусков"})
                            is_assigned = True

                    # --- ЭТАП 3: НЕ ЗАКРЫТО ---
                    if not is_assigned:
                        if current_day_type == "выходной":
                            reason = f"Выходной: лимит 4x2 ({daily_quota_4x2}) исчерпан, 5x2h не работают по регламенту"
                            unassigned_weekend += 1
                        else:
                            reason = "Нет квалифицированного водителя (не хватает допусков или пул пуст)"
                            unassigned_qualification += 1

                        daily_unassigned.append(
                            {"маршрут": route_num, "трамвай": tram_num, "смена": shift_name, "причина": reason})
                        # Детальный лог для отладки
                        print(f"  НЕ НАЗНАЧЕНО: Маршрут {route_num}, Трамвай {tram_num} ({shift_name}) -> {reason}")

        total_assigned_primary += day_assigned_primary
        total_assigned_secondary += day_assigned_secondary
        total_unassigned += len(daily_unassigned)

        print(
            f"День {current_day:02d} | {current_day_type.ljust(8)} | 4x2: {day_assigned_primary:3} | 5x2h: {day_assigned_secondary:3} | Резерв: {len(available_primary_today):2} | Открыто: {len(daily_unassigned):2}")
        monthly_result.append({
            "дата": f"{YEAR}-{MONTH:02d}-{current_day:02d}", "тип_дня": current_day_type,
            "день_цикла": cycle_day_primary, "успешные_назначения": daily_assignments,
            "открытые_смены_без_водителя": daily_unassigned
        })

    print("-" * 60)
    output_dir = config.get_schedule_output_dir(PRIMARY_SCHEDULE, SECONDARY_SCHEDULE)
    os.makedirs(output_dir, exist_ok=True)
    final_output_path = os.path.join(output_dir, f"{PRIMARY_SCHEDULE}_{SECONDARY_SCHEDULE}_BLOCK_final_schedule.json")
    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(monthly_result, f, ensure_ascii=False, indent=2)

    print(f"\nФайл сохранён: {final_output_path}")
    print("=" * 60)
    print(" ИТОГИ:")
    print(f"  - Назначено 4x2:  {total_assigned_primary}")
    print(f"  - Назначено 5x2h: {total_assigned_secondary}")
    print(f"  - Не закрыто всего:     {total_unassigned}")
    print(f"    ├─ Из-за выходных (лимит 4x2): {unassigned_weekend}")
    print(f"    └─ Из-за квалификации/пула:    {unassigned_qualification}")
    if SIMULATE_OPTIMAL_STAFF:
        print(
            f"\nОПТИМИЗАЦИЯ: При штате 5x2h = {quotas['recommended_5x2h']} чел. резерв 4x2 в выходные упадёт до 0-2.")
    print("=" * 60)


if __name__ == "__main__":
    generate_hybrid_schedule()
