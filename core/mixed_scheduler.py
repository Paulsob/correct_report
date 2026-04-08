import sys
import os

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

# НОВЫЕ КВОТЫ
LIMIT_4X2_WEEKDAY = 144  # Пн-Пт (было 144, стало 140)
LIMIT_4X2_WEEKEND = 137  # Сб-Вс (оставили как есть)


# Для справки: теперь нужно 67 водителей 5x2h (было 63)


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
    print(f" СТАРТ УМНОГО ГИБРИДНОГО МОДЕЛИРОВАНИЯ: {PRIMARY_SCHEDULE} + {SECONDARY_SCHEDULE} ")
    print(f" НОВЫЕ квоты {PRIMARY_SCHEDULE}: Будни = {LIMIT_4X2_WEEKDAY}, Выходные = {LIMIT_4X2_WEEKEND}")
    print(f" Требуется водителей {SECONDARY_SCHEDULE}: 67 (на 4 больше)")
    print(f" Период: {YEAR}-{MONTH:02d}")
    print("=" * 60)

    matrix_primary, cycle_length_primary = load_matrix_data(PRIMARY_SCHEDULE)

    with open(config.SCHEDULE_PREPARED, "r", encoding="utf-8") as f:
        trams_data = json.load(f)
    with open(config.DRIVERS_PREPARED, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    pool_primary, pool_secondary = build_hybrid_driver_pools(drivers_data)

    # --- УМНЫЙ ФИЛЬТР БЛОКОВ ---
    base_weekend_blocks = set()
    for route in trams_data:
        if route.get("день") == "рабочий": continue
        for tram in route.get("трамваи", []):
            if tram.get("день") == "рабочий": continue
            b_id = tram.get("block_ids", {}).get(PRIMARY_SCHEDULE)
            if b_id:
                base_weekend_blocks.add(b_id)

    print(f"  -> Работает базовых блоков 4x2 на маршруте: {len(base_weekend_blocks)}")
    print(f"  -> Найдено водителей 5x2h: {len(pool_secondary)}")
    print(f"  -> Ожидаемый резерв в будние: {LIMIT_4X2_WEEKDAY - LIMIT_4X2_WEEKEND} водителей 4x2")
    print(f"  -> Ожидаемый резерв в выходные: {len(base_weekend_blocks) - LIMIT_4X2_WEEKEND} водителей 4x2\n")

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

        # Установка жесткой квоты на сегодня
        daily_quota_4x2 = LIMIT_4X2_WEEKDAY if current_day_type == "рабочий" else LIMIT_4X2_WEEKEND

        # 1. Пул свободных 5x2h на сегодня
        available_secondary_today = [
            d for d in pool_secondary if d["schedule_dict"].get(str(current_day), "В") in ["1", "2"]
        ]

        # 2. Пул 4x2 (собираем тех, кто сегодня не на выходном по матрице)
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
                            "block_id": b_id,
                            "role": str(role),
                            "driver": driver
                        })

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

                    # --- ЭТАП 1: Ищем "РОДНОГО" водителя (Строго в рамках квоты) ---
                    if target_slot_primary and block_id_primary and (day_assigned_primary < daily_quota_4x2):
                        native_idx = next((i for i, d in enumerate(available_primary_today)
                                           if d["block_id"] == block_id_primary and d["role"] == str(required_role)),
                                          None)

                        if native_idx is not None:
                            native_driver_info = available_primary_today.pop(native_idx)
                            driver_primary = native_driver_info["driver"]
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": PRIMARY_SCHEDULE,
                                "таб_номер_водителя": driver_primary.get("tab_number"),
                                "роль_по_матрице": required_role,
                                "комментарий": "Идеальное совпадение"
                            })
                            is_assigned = True
                            day_assigned_primary += 1

                    # --- ЭТАП 1.5: КРОСС-БЛОЧНЫЙ ПЕРЕХВАТ (Строго в рамках квоты) ---
                    if not is_assigned and available_primary_today and (day_assigned_primary < daily_quota_4x2):
                        p_driver = available_primary_today.pop(0)
                        driver_primary = p_driver["driver"]
                        daily_assignments.append({
                            "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                            "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                            "график_водителя": PRIMARY_SCHEDULE,
                            "таб_номер_водителя": driver_primary.get("tab_number"),
                            "роль_по_матрице": p_driver["role"],
                            "комментарий": f"Перехват (Резерв из блока {p_driver['block_id']})"
                        })
                        is_assigned = True
                        day_assigned_primary += 1

                    # --- ЭТАП 2: ОТДАЕМ ОСТАТКИ 5x2h ---
                    if not is_assigned and current_day_type == "рабочий":
                        if available_secondary_today:
                            driver_secondary = available_secondary_today.pop(0)
                            daily_assignments.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": SECONDARY_SCHEDULE,
                                "таб_номер_водителя": driver_secondary.get("tab_number"),
                                "роль_по_матрице": "Без роли",
                                "комментарий": "Штатная смена 5x2h"
                            })
                            is_assigned = True
                            day_assigned_secondary += 1
                        else:
                            daily_unassigned.append({
                                "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                                "причина": f"Пул свободных водителей {SECONDARY_SCHEDULE} пуст!"
                            })
                            is_assigned = True

                    # --- ЭТАП 3: ОШИБКА ---
                    if not is_assigned:
                        daily_unassigned.append({
                            "маршрут": route_num, "трамвай": tram_num, "смена": shift_name,
                            "причина": f"Никто не назначен (выходной день, и не хватило 4x2)"
                        })

        total_assigned_primary += day_assigned_primary
        total_assigned_secondary += day_assigned_secondary
        total_unassigned += len(daily_unassigned)

        reserve_count = len(available_primary_today)
        print(f"День {current_day:02d} | {current_day_type.ljust(8)} | "
              f"Закрыто {PRIMARY_SCHEDULE}: {day_assigned_primary:3} | "
              f"Закрыто {SECONDARY_SCHEDULE}: {day_assigned_secondary:3} | "
              f"Резерв (4x2): {reserve_count:2} | "
              f"Открытых смен: {len(daily_unassigned):2}")

        monthly_result.append({
            "дата": f"{YEAR}-{MONTH:02d}-{current_day:02d}",
            "тип_дня": current_day_type,
            "день_цикла": cycle_day_primary,
            "успешные_назначения": daily_assignments,
            "открытые_смены_без_водителя": daily_unassigned
        })

    print("-" * 60)
    blocks_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(blocks_dir, "output_data", str(YEAR), f"{MONTH:02d}")
    os.makedirs(output_dir, exist_ok=True)
    final_output_path = os.path.join(output_dir, f"{PRIMARY_SCHEDULE}_{SECONDARY_SCHEDULE}_BLOCK_final_schedule.json")

    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(monthly_result, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(" ИТОГИ МОДЕЛИРОВАНИЯ:")
    print(f"  - Графиком {PRIMARY_SCHEDULE: <5}: {total_assigned_primary}")
    print(f"  - Графиком {SECONDARY_SCHEDULE: <5}: {total_assigned_secondary}")
    print(f"Всего НЕ закрыто смен: {total_unassigned}")
    print("=" * 60)


if __name__ == "__main__":
    generate_hybrid_schedule()