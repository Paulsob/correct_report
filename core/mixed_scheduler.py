import sys
import os
import random

# Подключаем конфиг
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

import json
from datetime import date
import calendar
import time

ANCHOR_DATE = 1
YEAR = int(config.TARGET_YEAR)
MONTH = int(config.TARGET_MONTH)
DAYS_IN_MONTH = calendar.monthrange(YEAR, MONTH)[1]
CUSTOM_HOLIDAYS = []

PRIMARY_SCHEDULE = "4x2"
SECONDARY_SCHEDULE = "5x2h"

# 🔧 ВКЛЮЧИТЕ True, чтобы увидеть результат оптимизации штата
SIMULATE_OPTIMAL_STAFF = True


def calculate_dynamic_quotas(trams_data, buffer_weekend=2):
    weekday_shifts = 0
    weekend_shifts = 0

    for route in trams_data:
        day_type = route.get("день")
        if not day_type: continue

        route_shifts = 0
        for tram in route.get("трамваи", []):
            if tram.get("смена_1"): route_shifts += 1
            if tram.get("смена_2"): route_shifts += 1

        if day_type == "рабочий":
            weekday_shifts += route_shifts
        elif day_type in ("выходной", "праздник"):
            weekend_shifts += route_shifts

    dynamic_limit_weekday = max(1, weekday_shifts)
    dynamic_limit_weekend = weekend_shifts + buffer_weekend
    recommended_5x2h = max(0, dynamic_limit_weekday - dynamic_limit_weekend)

    return {
        "limit_weekday": dynamic_limit_weekday,
        "limit_weekend": dynamic_limit_weekend,
        "weekday_shifts": weekday_shifts,
        "weekend_shifts": weekend_shifts,
        "recommended_5x2h": recommended_5x2h
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
            if b_id not in pool_primary:
                pool_primary[b_id] = {}
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

    matrix_primary, cycle_length_primary = load_matrix_data(PRIMARY_SCHEDULE)

    with open(config.SCHEDULE_PREPARED, "r", encoding="utf-8") as f:
        trams_data = json.load(f)
    with open(config.DRIVERS_PREPARED, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    pool_primary, pool_secondary = build_hybrid_driver_pools(drivers_data)
    quotas = calculate_dynamic_quotas(trams_data, buffer_weekend=2)

    print("\n📊 АНАЛИТИКА НАГРУЗКИ:")
    print(f"  -> Смен в будни: {quotas['weekday_shifts']} | В выходные: {quotas['weekend_shifts']}")
    print(f"  -> Рекомендуемый штат 5x2h: {quotas['recommended_5x2h']} чел.")
    print(f"  -> Фактический пул 5x2h:    {len(pool_secondary)} чел.\n")

    base_weekend_blocks = set()
    for route in trams_data:
        if route.get("день") == "рабочий": continue
        for tram in route.get("трамваи", []):
            if tram.get("день") == "рабочий": continue
            b_id = tram.get("block_ids", {}).get(PRIMARY_SCHEDULE)
            if b_id: base_weekend_blocks.add(b_id)

    # Определяем лимит доступных 4x2 на день
    max_active_4x2 = quotas["limit_weekend"] if SIMULATE_OPTIMAL_STAFF else quotas["limit_weekday"]
    print(f"  -> Лимит активных водителей 4x2: {max_active_4x2} (оптимизация до уровня выходных)")
    print(f"  -> Работает базовых блоков 4x2: {len(base_weekend_blocks)}\n")

    monthly_result = []
    total_assigned_primary = 0
    total_assigned_secondary = 0
    total_unassigned = 0

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

        # 🔥 КЛЮЧЕВОЙ ШАГ ОПТИМИЗАЦИИ: обрезаем пул до оптимального размера
        if SIMULATE_OPTIMAL_STAFF:
            # Перемешиваем для честного распределения, если водителей больше лимита
            random.shuffle(available_primary_today)
            available_primary_today = available_primary_today[:daily_quota_4x2]

        for route in trams_data:
            if route.get("день") and route.get("день") != current_day_type: continue
            route_num = route.get("маршрут")

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

                    if target_slot_primary and block_id_primary and (day_assigned_primary < daily_quota_4x2):
                        native_idx = next((i for i, d in enumerate(available_primary_today)
                                           if d["block_id"] == block_id_primary and d["role"] == str(required_role)),
                                          None)
                        if native_idx is not None:
                            native_driver_info = available_primary_today.pop(native_idx)
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": PRIMARY_SCHEDULE,
                                "таб_номер_водителя": native_driver_info["driver"].get("tab_number"),
                                "роль_по_матрице": required_role, "комментарий": "Идеальное совпадение"
                            })
                            is_assigned = True
                            day_assigned_primary += 1

                    if not is_assigned and available_primary_today and (day_assigned_primary < daily_quota_4x2):
                        p_driver = available_primary_today.pop(0)
                        daily_assignments.append({
                            "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                            "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                            "график_водителя": PRIMARY_SCHEDULE,
                            "таб_номер_водителя": p_driver["driver"].get("tab_number"),
                            "роль_по_матрице": p_driver["role"],
                            "комментарий": f"Перехват (Блок {p_driver['block_id']})"
                        })
                        is_assigned = True
                        day_assigned_primary += 1

                    if not is_assigned and current_day_type == "рабочий":
                        if available_secondary_today:
                            driver_secondary = available_secondary_today.pop(0)
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": SECONDARY_SCHEDULE,
                                "таб_номер_водителя": driver_secondary.get("tab_number"),
                                "роль_по_матрице": "Без роли", "комментарий": "Штатная смена 5x2h"
                            })
                            is_assigned = True
                            day_assigned_secondary += 1
                        else:
                            daily_unassigned.append({"маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                                     "причина": f"Пул {SECONDARY_SCHEDULE} пуст!"})
                            is_assigned = True

                    if not is_assigned:
                        daily_unassigned.append({"маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                                 "причина": "Не хватило 4x2 (выходной)"})

        total_assigned_primary += day_assigned_primary
        total_assigned_secondary += day_assigned_secondary
        total_unassigned += len(daily_unassigned)

        reserve_count = len(available_primary_today)
        print(f"День {current_day:02d} | {current_day_type.ljust(8)} | "
              f"4x2: {day_assigned_primary:3} | 5x2h: {day_assigned_secondary:3} | "
              f"Резерв: {reserve_count:2} | Открыто: {len(daily_unassigned):2}")

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

    print(f"Файл сохранён: {final_output_path}")

    print("\n" + "=" * 60)
    print(" ИТОГИ МОДЕЛИРОВАНИЯ:")
    print(f"  - Назначено 4x2:  {total_assigned_primary}")
    print(f"  - Назначено 5x2h: {total_assigned_secondary}")
    print(f"  - Не закрыто смен: {total_unassigned}")
    if SIMULATE_OPTIMAL_STAFF:
        print(f"\n💡 ВЫВОД ОПТИМИЗАЦИИ:")
        print(f"   • При сокращении штата 4x2 на ~{quotas['weekday_shifts'] - quotas['limit_weekend']} чел.")
        print(f"   • И найме {quotas['recommended_5x2h']} водителей 5x2h")
        print(f"   • Резерв в выходные упадёт до 0-2, переработки исчезнут.")
    print("=" * 60)
    print(f"⏱ Время: {time.time() - start_time:.2f} сек.")


if __name__ == "__main__":
    generate_hybrid_schedule()