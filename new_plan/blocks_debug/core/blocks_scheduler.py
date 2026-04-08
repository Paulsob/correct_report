import sys
import os
import json
import calendar
import time
from datetime import date

# ВАЖНО: импортируем config из папки blocks_debug
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blocks_debug import config

ANCHOR_DATE = 1
YEAR = int(config.TARGET_YEAR)
MONTH = int(config.TARGET_MONTH)
DAYS_IN_MONTH = calendar.monthrange(YEAR, MONTH)[1]


def load_matrix_data(schedule_type):
    """Загружает нужную матрицу и длину её цикла из общего файла."""
    with open(config.MATRICES_FILE, "r", encoding="utf-8") as f:
        all_matrices = json.load(f)

    if schedule_type not in all_matrices:
        raise ValueError(f"Ошибка: График '{schedule_type}' не найден в {config.MATRICES_FILE}!")

    matrix_data = all_matrices[schedule_type]
    active_matrix = {int(k): v for k, v in matrix_data["matrix"].items()}
    cycle_length = matrix_data["cycle_length"]

    return active_matrix, cycle_length


def get_required_role(cycle_day, target_slot, active_matrix):
    """Спрашиваем матрицу: какая роль закрывает этот слот в этот день цикла?"""
    day_index = cycle_day - 1
    for role, days_list in active_matrix.items():
        if days_list[day_index] == target_slot:
            return role
    return None


def build_drivers_lookup(drivers_data, schedule_type):
    """Создаем словарь ТОЛЬКО для водителей нужного графика."""
    lookup = {}
    for driver in drivers_data.get("drivers", []):
        if driver.get("schedule_type") != schedule_type:
            continue

        b_id = driver.get("block_id")
        m_role = driver.get("matrix_role")

        if b_id not in lookup:
            lookup[b_id] = {}

        driver["schedule_dict"] = driver.get("days", {})
        lookup[b_id][m_role] = driver
    return lookup


def get_day_type(day):
    """
    ДЕБАГ-РЕЖИМ: Все дни считаются рабочими.
    Игнорируем календарь и выходные.
    """
    return "рабочий"


def generate_schedule():
    start_time = time.time()

    print(f"\n{'=' * 60}")
    print(f"🔧 СТАРТ МОДЕЛИРОВАНИЯ РАСПИСАНИЯ (DEBUG РЕЖИМ) 🔧")
    print(f"График: [{config.TARGET_SCHEDULE}] | Период: {MONTH:02d}.{YEAR}")
    print(f"Режим: ВСЕ ДНИ РАБОЧИЕ")
    print(f"{'=' * 60}")

    print("\n[1] ИСТОЧНИКИ ДАННЫХ И ИХ ЗАГРУЗКА:")

    print(f"  -> Файл матриц: {config.MATRICES_FILE}")
    active_matrix, cycle_length = load_matrix_data(config.TARGET_SCHEDULE)
    print(f"     [OK] Длина цикла: {cycle_length} дн., Количество ролей: {len(active_matrix)}")

    print(f"  -> Файл расписания: {config.SCHEDULE_PREPARED}")
    with open(config.SCHEDULE_PREPARED, "r", encoding="utf-8") as f:
        trams_data = json.load(f)

    total_routes = len(trams_data)
    total_trams = sum(len(route.get("трамваи", [])) for route in trams_data)
    print(f"     [OK] Загружено маршрутов: {total_routes}, Всего трамваев: {total_trams}")

    print(f"  -> Файл базы водителей: {config.DRIVERS_PREPARED}")
    with open(config.DRIVERS_PREPARED, "r", encoding="utf-8") as f:
        drivers_data = json.load(f)

    print("\n[2] ФИЛЬТРАЦИЯ И ПОДГОТОВКА:")
    drivers_lookup = build_drivers_lookup(drivers_data, config.TARGET_SCHEDULE)

    total_drivers_used = sum(len(roles) for roles in drivers_lookup.values())
    total_blocks_used = len(drivers_lookup)

    print(f"  -> Для графика '{config.TARGET_SCHEDULE}' отобрано:")
    print(f"     Блоков (бригад): {total_blocks_used}")
    print(f"     Водителей: {total_drivers_used}")

    if total_drivers_used == 0:
        print("\n  [!] ВНИМАНИЕ: Не найдено водителей! Смены будут открытыми.")

    print("\n[3] ГЕНЕРАЦИЯ РАСПИСАНИЯ ПО ДНЯМ...")
    monthly_result = []

    for current_day in range(1, DAYS_IN_MONTH + 1):
        cycle_day = ((current_day - ANCHOR_DATE) % cycle_length) + 1

        # Теперь всегда возвращает "рабочий"
        current_day_type = get_day_type(current_day)

        daily_assignments = []
        daily_unassigned = []

        for route in trams_data:
            # Если в JSON указан тип дня, и он не совпадает с текущим (в дебаге всегда совпадает)
            if route.get("день") and route.get("день") != current_day_type:
                continue

            route_num = route.get("маршрут")

            for tram in route.get("трамваи", []):
                block_id = tram.get("block_ids", {}).get(config.TARGET_SCHEDULE)
                if not block_id:
                    continue

                tram_num = tram.get("номер")

                shifts = []
                if tram.get("смена_1"): shifts.append(("Утро", tram["смена_1"]))
                if tram.get("смена_2"): shifts.append(("Вечер", tram["смена_2"]))

                for shift_name, shift_data in shifts:
                    target_slot = shift_data.get("matrix_slots", {}).get(config.TARGET_SCHEDULE)
                    if not target_slot:
                        continue

                    # Какая роль нужна по матрице на сегодня?
                    required_role = get_required_role(cycle_day, target_slot, active_matrix)
                    if not required_role:
                        continue

                    # Ищем водителя в этом блоке (бригаде) с нужной ролью
                    driver = drivers_lookup.get(block_id, {}).get(required_role)

                    if not driver:
                        daily_unassigned.append({
                            "маршрут": route_num,
                            "трамвай": tram_num,
                            "смена": shift_name,
                            "нужна_роль": required_role,
                            "причина": f"В блоке {block_id} нет водителя с ролью {required_role}"
                        })
                        continue

                    # Проверка совпадения графиков (Утро = 1, Вечер = 2)
                    expected_status = "1" if target_slot % 2 != 0 else "2"
                    actual_status = driver["schedule_dict"].get(str(current_day), "Нет данных")

                    if actual_status == expected_status:
                        daily_assignments.append({
                            "маршрут": route_num,
                            "трамвай": tram_num,
                            "смена": shift_name,
                            "время": f"{shift_data.get('отправление')} - {shift_data.get('прибытие')}",
                            "таб_номер_водителя": driver.get("tab_number"),
                            "роль_по_матрице": required_role
                        })
                    else:
                        daily_unassigned.append({
                            "маршрут": route_num,
                            "трамвай": tram_num,
                            "смена": shift_name,
                            "нужна_роль": required_role,
                            "таб_номер_водителя": driver.get("tab_number"),
                            "причина": f"Ожидался статус '{expected_status}', а в графике водителя '{actual_status}'"
                        })

        monthly_result.append({
            "дата": f"{YEAR}-{MONTH:02d}-{current_day:02d}",
            "тип_дня": current_day_type,
            "день_цикла": cycle_day,
            "успешные_назначения": daily_assignments,
            "открытые_смены_без_водителя": daily_unassigned
        })

    with open(config.FINAL_SCHEDULE, "w", encoding="utf-8") as f:
        json.dump(monthly_result, f, ensure_ascii=False, indent=2)

    execution_time = time.time() - start_time

    print(f"\n[4] ЗАВЕРШЕНО!")
    print(f"  -> Расписание на {DAYS_IN_MONTH} дней сгенерировано.")
    print(f"  -> Результат сохранен в: {config.FINAL_SCHEDULE}")
    print(f"  -> Время выполнения: {execution_time:.2f} сек.\n")


if __name__ == "__main__":
    generate_schedule()