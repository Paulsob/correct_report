import json
import os


def main():
    # Определяем пути (скрипт лежит в formatting_data, поднимаемся на уровень выше в blocks)
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

    # Проверяем, существует ли файл
    if not os.path.exists(input_file_path):
        print(f"Ошибка: Файл не найден по пути {input_file_path}")
        return

    # Читаем JSON файл
    with open(input_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Пробегаемся по всем водителям
    for driver in data.get('drivers', []):
        schedule_type = driver.get('schedule_type', '')

        # Нормализуем строку: переводим в нижний регистр и заменяем кириллическую 'х' на латинскую 'x'
        sched_norm = schedule_type.lower().replace('х', 'x')

        current_tab = driver.get('tab_number')
        if current_tab is None:
            continue

        # Получаем базовый номер (от 1 до 999), чтобы скрипт можно было запускать сколько угодно раз
        base_tab = current_tab % 1000

        # В случае, если номер кратен 1000 (например 1000 станет 0), возвращаем тысячу обратно (хотя у вас нумерация с 1)
        if base_tab == 0:
            base_tab = 1000

        # Применяем логику сдвига табельных номеров
        if sched_norm == '4x2':
            driver['tab_number'] = base_tab
        elif sched_norm == '5x2':
            driver['tab_number'] = base_tab + 1000
        elif sched_norm == '3x2x3x1':
            driver['tab_number'] = base_tab + 2000
        else:
            print(f"Внимание: Неизвестный тип графика '{schedule_type}' у таб. номера {current_tab}")

    # Перезаписываем тот же файл обновленными данными
    with open(input_file_path, 'w', encoding='utf-8') as f:
        # ensure_ascii=False сохраняет русский язык, indent=2 делает JSON красивым (с отступами)
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Табельные номера успешно обновлены!")


if __name__ == "__main__":
    main()