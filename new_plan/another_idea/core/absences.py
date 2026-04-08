import json
import random
import os
import sys
import calendar

# Добавляем корневую папку в пути для импорта config.py
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from another_idea import config

ABSENCE_TYPES = {
    "1": {"code": "sick_leave", "name": "Больничный"},
    "2": {"code": "vacation", "name": "Отпуск"},
    "3": {"code": "other", "name": "Прочие причины"}
}


def parse_input_amount(input_str, all_drivers):
    input_str = input_str.strip().lower()

    # Конкретные табельные номера
    if input_str.startswith("id:"):
        try:
            # Отрезаем 'id:', убираем пробелы и сплитим
            ids_str = input_str.replace("id:", "")
            ids = [int(x.strip()) for x in ids_str.split(",") if x.strip()]
            return [d for d in all_drivers if d['tab_number'] in ids]
        except ValueError:
            print("Ошибка парсинга табельных номеров.")
            return []

    total = len(all_drivers)
    # Проценты
    if "%" in input_str:
        percent = float(input_str.replace("%", "").strip())
        count = round(total * percent / 100)
    # Доли (например, 0.25)
    elif "." in input_str:
        count = round(total * float(input_str))
    # Штуки
    else:
        try:
            count = int(input_str)
        except ValueError:
            print("Неверный формат ввода количества.")
            return []

    count = min(count, total)
    return random.sample(all_drivers, count)


def load_existing_absences(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []


def main():
    # Используем данные из config.py
    year = config.TARGET_YEAR
    month = config.TARGET_MONTH
    target_schedules = config.TARGET_SCHEDULE_TYPES

    # Определяем количество дней в выбранном месяце
    _, days_in_month = calendar.monthrange(year, month)

    try:
        with open(config.INPUT_TABEL_FILE, 'r', encoding='utf-8') as f:
            tabel_data = json.load(f)
    except FileNotFoundError:
        print(f"Файл не найден: {config.INPUT_TABEL_FILE}")
        return

    all_drivers = tabel_data.get('drivers', [])
    target_drivers = [d for d in all_drivers if d.get('schedule_type') in target_schedules]

    if not target_drivers:
        print(f"Не найдено водителей для графиков: {', '.join(target_schedules)}")
        return

    print(f"Период моделирования: {month:02d}.{year} (дней в месяце: {days_in_month})")
    print(f"Текущие графики: {', '.join(target_schedules)} (доступно {len(target_drivers)} водителей)")

    # === БЛОК ОЧИСТКИ СУЩЕСТВУЮЩИХ ОТСУТСТВИЙ ===
    existing_absences = load_existing_absences(config.OUTPUT_ABSENCES_FILE)
    if existing_absences:
        print(f"\nВ базе absences.json сейчас {len(existing_absences)} записей.")
        clear_choice = input("Хотите полностью очистить этот список? (д/н): ").strip().lower()

        if clear_choice in ['д', 'y', 'да', 'yes']:
            # Перезаписываем файл пустым массивом
            with open(config.OUTPUT_ABSENCES_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print("Список отсутствующих успешно очищен!")

            # Спрашиваем, нужно ли продолжать генерацию
            continue_choice = input("\nХотите сгенерировать новые отсутствия? (д/н): ").strip().lower()
            if continue_choice not in ['д', 'y', 'да', 'yes']:
                print("Работа завершена.")
                return
        else:
            print("Существующие записи сохранены. Новые будут добавлены к ним.")
    # ============================================

    print("\nТип отсутствия:")
    for k, v in ABSENCE_TYPES.items():
        print(f"{k} - {v['name']}")
    absence_choice = input("Выберите тип (1/2/3): ").strip()
    absence_type = ABSENCE_TYPES.get(absence_choice, ABSENCE_TYPES["3"])

    print("\nКак задать количество водителей?")
    print("Примеры: 5 (штуки), 15% (проценты), 0.25 (доли), id:7,12,45 (конкретные)")
    amount_input = input("Ввод: ").strip()

    selected_drivers = parse_input_amount(amount_input, target_drivers)
    if not selected_drivers:
        print("Водители не выбраны. Операция прервана.")
        return

    print(f"Выбрано водителей: {len(selected_drivers)}")

    same_period = True
    if len(selected_drivers) > 1:
        print("\nСпособ распределения дат:")
        print("1 - Все выбранные водители отсутствуют в одни и те же даты")
        print("2 - Даты отсутствий равномерно (случайно) распределяются по месяцу")
        mode = input("Выберите (1/2): ").strip()
        same_period = (mode == "1")

    # Ввод дат и длительности
    if same_period:
        start_day = int(input("\nДень начала отсутствия (число месяца): "))
        duration = int(input("Длительность отсутствия (в днях): "))
    else:
        print("\nУкажите длительность (даты начала будут выбраны случайно).")
        duration = int(input("Длительность отсутствия (в днях): "))

    # Генерация записей
    new_absences = []
    for driver in selected_drivers:
        if same_period:
            current_start = start_day
        else:
            # Вычисляем максимальный день начала
            max_start = max(1, days_in_month - duration + 1)
            current_start = random.randint(1, max_start)

        new_absences.append({
            "tab_number": driver["tab_number"],
            "absence_type": absence_type["code"],
            "year": year,
            "month": month,
            "start_day": current_start,
            "end_day": current_start + duration - 1,
            "duration": duration
        })

    # Читаем старые записи (если мы их очистили выше, тут будет пусто), добавляем новые, сохраняем
    all_absences = load_existing_absences(config.OUTPUT_ABSENCES_FILE)
    all_absences.extend(new_absences)

    with open(config.OUTPUT_ABSENCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_absences, f, ensure_ascii=False, indent=2)

    print(f"\nГотово! Добавлено {len(new_absences)} записей.")
    print(f"Всего в файле absences.json: {len(all_absences)} записей.")


if __name__ == "__main__":
    main()