import sys
import os

# Подключаем конфиг (предполагается, что скрипт лежит на том же уровне абстракции)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blocks_debug import config

import json
from datetime import date
import calendar
import time

ANCHOR_DATE = 1
YEAR = int(config.TARGET_YEAR)
MONTH = int(config.TARGET_MONTH)
DAYS_IN_MONTH = calendar.monthrange(YEAR, MONTH)[1]
CUSTOM_HOLIDAYS = []

# Константы для гибридного режима
PRIMARY_SCHEDULE = "4x2"
SECONDARY_SCHEDULE = "5x2h"


def load_matrix_data(schedule_type):
    """Загружает нужную матрицу и длину её цикла."""
    with open(config.MATRICES_FILE, "r", encoding="utf-8") as f:
        all_matrices = json.load(f)

    if schedule_type not in all_matrices:
        raise ValueError(f"Ошибка: График '{schedule_type}' не найден в {config.MATRICES_FILE}!")

    matrix_data = all_matrices[schedule_type]
    active_matrix = {int(k): v for k, v in matrix_data["matrix"].items()}
    return active_matrix, matrix_data["cycle_length"]


def get_required_role(cycle_day, target_slot, active_matrix):
    """Какая роль закрывает этот слот в этот день цикла?"""
    day_index = cycle_day - 1
    for role, days_list in active_matrix.items():
        if days_list[day_index] == target_slot:
            return role
    return None


def build_hybrid_driver_pools(drivers_data):
    """
    Создает два пула:
    1. pool_primary - сложный словарь {block_id: {role: driver}}
    2. pool_secondary - простой список водителей [driver1, driver2, ...]
    """
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
    """Определяет, рабочий это день или выходной."""
    if day in CUSTOM_HOLIDAYS or date(YEAR, MONTH, day).weekday() >= 5:
        return "выходной"
    return "рабочий"


def generate_hybrid_schedule():
    start_time = time.time()
    print("=" * 60)
    print(f" СТАРТ ГИБРИДНОГО МОДЕЛИРОВАНИЯ: {PRIMARY_SCHEDULE} + {SECONDARY_SCHEDULE} ")
    print(f" Период: {YEAR}-{MONTH:02d}")
    print("=" * 60)

    # 1. Загружаем матрицу только для 4x2
    matrix_primary, cycle_length_primary = load_matrix_data(PRIMARY_SCHEDULE)

    print("Загрузка данных расписания и водителей...")
    with open(config.SCHEDULE_PREPARED, "r", encoding="utf-8") as f:
        trams_data = json.load(f)
    with open(config.DRIVERS_PREPARED, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    # 2. Формируем два независимых пула водителей
    pool_primary, pool_secondary = build_hybrid_driver_pools(drivers_data)

    print(f"  -> Найдено блоков {PRIMARY_SCHEDULE}: {len(pool_primary)}")
    print(f"  -> Найдено водителей {SECONDARY_SCHEDULE}: {len(pool_secondary)}")

    # --- РАСЧЕТ КВОТЫ ДЛЯ 4x2 ---
    # Считаем, сколько смен 4x2 доступно в обычный выходной день
    base_weekend_shifts = 0
    for route in trams_data:
        # Игнорируем маршруты, которые выходят только в будни
        if route.get("день") == "рабочий":
            continue

        for tram in route.get("трамваи", []):
            # Игнорируем трамваи, которые выходят только в будни
            if tram.get("день") == "рабочий":
                continue

            # Считаем слоты 4x2
            if tram.get("смена_1") and tram.get("смена_1", {}).get("matrix_slots", {}).get(PRIMARY_SCHEDULE):
                base_weekend_shifts += 1
            if tram.get("смена_2") and tram.get("смена_2", {}).get("matrix_slots", {}).get(PRIMARY_SCHEDULE):
                base_weekend_shifts += 1

    print(f"  -> Жесткий лимит смен {PRIMARY_SCHEDULE} на будний день: {base_weekend_shifts}\n")

    monthly_result = []

    # Глобальные счетчики для итоговой статистики
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

        # Дневные счетчики
        day_assigned_primary = 0
        day_assigned_secondary = 0

        # Устанавливаем квоту на сегодня
        if current_day_type == "рабочий":
            daily_quota_4x2 = base_weekend_shifts
        else:
            daily_quota_4x2 = float('inf')  # В выходные лимита нет (берут все доступные смены)

        # Пул свободных водителей SECONDARY НА СЕГОДНЯ
        available_secondary_today = [
            d for d in pool_secondary
            if d["schedule_dict"].get(str(current_day), "В") in ["1", "2"]
        ]

        for route in trams_data:
            if route.get("день") and route.get("день") != current_day_type:
                continue

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

                    # --- ЭТАП 1: Назначаем PRIMARY (4x2) по матрице С УЧЕТОМ КВОТЫ ---
                    if target_slot_primary and block_id_primary and (day_assigned_primary < daily_quota_4x2):
                        required_role = get_required_role(cycle_day_primary, target_slot_primary, matrix_primary)
                        driver_primary = pool_primary.get(block_id_primary, {}).get(required_role)

                        if driver_primary:
                            expected_status = "1" if target_slot_primary % 2 != 0 else "2"
                            actual_status = driver_primary["schedule_dict"].get(str(current_day), "Нет данных")

                            if actual_status == expected_status:
                                daily_assignments.append({
                                    "маршрут": route_num,
                                    "трамвай": tram_num,
                                    "смена": shift_name,
                                    "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                    "график_водителя": PRIMARY_SCHEDULE,
                                    "таб_номер_водителя": driver_primary.get("tab_number"),
                                    "роль_по_матрице": required_role
                                })
                                is_assigned = True
                                day_assigned_primary += 1

                    # --- ЭТАП 2: Добиваем остаток графиком SECONDARY (5x2h) ---
                    # Если смена не была назначена 4х2 (например, превышен лимит или это добавочная смена)
                    if not is_assigned and current_day_type == "рабочий":
                        if available_secondary_today:
                            driver_secondary = available_secondary_today.pop(0)

                            daily_assignments.append({
                                "маршрут": route_num,
                                "трамвай": tram_num,
                                "смена": shift_name,
                                "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                                "график_водителя": SECONDARY_SCHEDULE,
                                "таб_номер_водителя": driver_secondary.get("tab_number"),
                                "роль_по_матрице": "Без роли"
                            })
                            is_assigned = True
                            day_assigned_secondary += 1
                        else:
                            daily_unassigned.append({
                                "маршрут": route_num,
                                "трамвай": tram_num,
                                "смена": shift_name,
                                "причина": f"Пул свободных водителей {SECONDARY_SCHEDULE} пуст!"
                            })
                            is_assigned = True  # Чтобы не сработал ЭТАП 3 и не дублировал ошибку

                    # --- ЭТАП 3: Логирование ошибки (никто не назначен) ---
                    if not is_assigned:
                        if current_day_type == "выходной":
                            reason = f"Выходной: В блоке {block_id_primary} нет водителя на роль {required_role}"
                        else:
                            reason = f"Неизвестная ошибка: не найден ни {PRIMARY_SCHEDULE}, ни {SECONDARY_SCHEDULE}"

                        daily_unassigned.append({
                            "маршрут": route_num,
                            "трамвай": tram_num,
                            "смена": shift_name,
                            "причина": reason
                        })

        # Суммируем в глобальные счетчики
        total_assigned_primary += day_assigned_primary
        total_assigned_secondary += day_assigned_secondary
        total_unassigned += len(daily_unassigned)

        # Вывод лога за день
        print(f"День {current_day:02d} | {current_day_type.ljust(8)} | "
              f"Закрыто {PRIMARY_SCHEDULE}: {day_assigned_primary:3} | "
              f"Закрыто {SECONDARY_SCHEDULE}: {day_assigned_secondary:3} | "
              f"Открытых смен: {len(daily_unassigned):2}")

        monthly_result.append({
            "дата": f"{YEAR}-{MONTH:02d}-{current_day:02d}",
            "тип_дня": current_day_type,
            "день_цикла": cycle_day_primary,
            "успешные_назначения": daily_assignments,
            "открытые_смены_без_водителя": daily_unassigned
        })

    print("-" * 60)

    # --- 3. Динамическое формирование пути и сохранение ---
    # Получаем абсолютный путь к папке 'blocks'
    # (__file__ = .../blocks/core/mixed_scheduler.py -> dirname -> core -> dirname -> blocks)
    blocks_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Формируем жесткий абсолютный путь к output_data
    output_dir = os.path.join(blocks_dir, "output_data", str(YEAR), f"{MONTH:02d}")

    # Создаем директории, если их не существует
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{PRIMARY_SCHEDULE}_{SECONDARY_SCHEDULE}_final_schedule.json"
    final_output_path = os.path.join(output_dir, filename)

    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(monthly_result, f, ensure_ascii=False, indent=2)

    execution_time = time.time() - start_time

    # --- 4. Итоговая статистика ---
    print("\n" + "=" * 60)
    print(" ИТОГИ МОДЕЛИРОВАНИЯ:")
    print("=" * 60)
    print(f"Всего назначено смен:")
    print(f"  - Графиком {PRIMARY_SCHEDULE: <5}: {total_assigned_primary}")
    print(f"  - Графиком {SECONDARY_SCHEDULE: <5}: {total_assigned_secondary}")
    print(f"Всего НЕ закрыто смен: {total_unassigned}")
    print("-" * 60)
    print(f"Результат сохранен в: {final_output_path}")
    print(f"Время выполнения: {execution_time:.2f} сек.")
    print("=" * 60)


if __name__ == "__main__":
    generate_hybrid_schedule()