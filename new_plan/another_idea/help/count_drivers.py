import os
import sys
import json

# Добавляем корневую директорию проекта в sys.path для импорта конфига
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from another_idea import config


def main():
    file_path = config.OUTPUT_SHIFTS

    if not os.path.exists(file_path):
        print(f"Файл не найден: {file_path}")
        print("Сначала запустите планировщик (scheduler.py) для генерации данных.")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            shifts_data = json.load(f)
    except json.JSONDecodeError:
        print(f"Ошибка чтения JSON в файле: {file_path}")
        return

    # Используем множество (set), так как оно автоматически хранит только уникальные значения
    unique_drivers = set()

    for shift in shifts_data:
        driver_id = shift.get("assigned_driver")
        if driver_id is not None:
            unique_drivers.add(driver_id)

    print(f"Анализ файла: {os.path.basename(file_path)}")
    print(f"Всего назначенных смен: {len(shifts_data)}")
    print(f"Количество уникальных водителей (табельных номеров): {len(unique_drivers)}")

    # Раскомментируй строку ниже, если хочешь увидеть сам список этих номеров:
    # print(f"Список задействованных табельных номеров: {sorted(list(unique_drivers))}")


if __name__ == "__main__":
    main()