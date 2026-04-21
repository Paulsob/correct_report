import json
import random
from pathlib import Path

# Определение путей относительно расположения этого файла
# Path(__file__) — это путь к самому скрипту (.../formatting_data/correct_allowed_routes.py)
# .parent — это папка formatting_data/
# .parent.parent — это корень проекта
BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_PATH = BASE_DIR / 'input_data' / '03_operational' / 'drivers' / 'prepared' / '2026' / '10' / 'drivers_prepared.json'
OUTPUT_PATH = BASE_DIR / 'input_data' / '03_operational' / 'drivers' / 'prepared' / '2026' / '10' / 'new_drivers_prepared.json'

# Полный список маршрутов
ALL_ROUTES = ["9", "19", "20", "21", "47", "48", "55", "61"]


def process_drivers():
    if not INPUT_PATH.exists():
        print(f"Ошибка: Файл не найден по пути {INPUT_PATH}")
        return

    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    drivers = data.get("drivers", [])

    # 1. Удаление поля allowed_trams у всех водителей без исключения
    for driver in drivers:
        driver.pop("allowed_trams", None)

    # 2. Фильтрация целевых групп для изменения маршрутов
    target_drivers = [
        d for d in drivers
        if d.get("schedule_type") in ["4x2", "5x2h"]
    ]

    # Перемешиваем для случайного распределения долей
    random.shuffle(target_drivers)

    total = len(target_drivers)
    if total == 0:
        print("Водители с графиками 4x2 или 5x2h не найдены.")
    else:
        # Расчет границ групп по процентам
        idx_10 = int(total * 0.10)
        idx_35 = idx_10 + int(total * 0.25)
        idx_85 = idx_35 + int(total * 0.50)

        for i, driver in enumerate(target_drivers):
            if i < idx_10:
                # 10% — допуск к 1 маршруту
                driver["allowed_routes"] = random.sample(ALL_ROUTES, 1)
            elif i < idx_35:
                # 25% — допуск ко всем маршрутам
                driver["allowed_routes"] = sorted(ALL_ROUTES)
            elif i < idx_85:
                # 50% — допуск к 3 маршрутам
                driver["allowed_routes"] = sorted(random.sample(ALL_ROUTES, 3))
            else:
                # 15% — допуск ко всем, кроме одного (7 маршрутов)
                driver["allowed_routes"] = sorted(random.sample(ALL_ROUTES, 7))

    # 3. Сохранение результата
    # Создаем папку, если она вдруг отсутствует
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Готово!")
    print(f"Входной файл: {INPUT_PATH.relative_to(BASE_DIR)}")
    print(f"Выходной файл: {OUTPUT_PATH.relative_to(BASE_DIR)}")
    print(f"Обработано водителей: {total}")
    print(f"Поле 'allowed_trams' удалено из всех записей.")


if __name__ == "__main__":
    process_drivers()