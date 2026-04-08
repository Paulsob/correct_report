import json
import os


def generate_october_2026_schedule():
    """
    Генерирует график 5х2 на октябрь 2026 года.
    1 октября - Четверг.
    Смены чередуются каждую неделю после выходных.
    """
    days = {}
    current_shift = "1"

    for day in range(1, 32):
        # Вычисляем день недели.
        # Пусть 0 - Понедельник, 6 - Воскресенье.
        # 1 октября 2026 года — это четверг (индекс 3).
        weekday = (day + 2) % 7

        if weekday in [5, 6]:  # Суббота (5) и Воскресенье (6)
            days[str(day)] = "В"
            # В конце воскресенья меняем тип смены на следующую неделю
            if weekday == 6:
                current_shift = "2" if current_shift == "1" else "1"
        else:
            days[str(day)] = current_shift

    return days


def main():
    # Определяем пути
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file_path = os.path.join(
        script_dir,
        "..",
        "input_data",
        "prepared_data",
        "2026",
        "10",
        "drivers_prepared.json"
    )

    if not os.path.exists(input_file_path):
        print(f"Ошибка: Файл не найден по пути {input_file_path}")
        return

    # Читаем данные
    with open(input_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ЗАЩИТА: Очищаем список от уже существующих водителей 5x2h (если скрипт запускают не первый раз)
    data['drivers'] = [d for d in data.get('drivers', []) if d.get('schedule_type') != '5x2h']

    # Получаем сгенерированный график на месяц
    schedule_days = generate_october_2026_schedule()

    # Добавляем 700 водителей (таб. номера с 3000 до 3699)
    start_tab_number = 3000
    for i in range(700):
        new_driver = {
            "tab_number": start_tab_number + i,
            "mode": "1х2",
            "days": schedule_days.copy(),
            "allowed_routes": ["ALL"],
            "allowed_trams": ["ALL"],
            "schedule_type": "5x2h"
            # block_id и matrix_role намеренно не добавляем
        }
        data['drivers'].append(new_driver)

    # Перезаписываем файл
    with open(input_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(
        f"Успешно! Добавлено 700 водителей с графиком 5x2h. Табельные номера от {start_tab_number} до {start_tab_number + 699}.")


if __name__ == "__main__":
    main()