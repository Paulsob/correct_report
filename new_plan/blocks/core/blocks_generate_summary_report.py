import json
import os
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)  # Поднимаемся в корень проекта

OUTPUT_DIR = os.path.join(PROJECT_DIR, "output_data")

INPUT_JSON = os.path.join(OUTPUT_DIR, "final_schedule_october.json")

OUTPUT_EXCEL = os.path.join(OUTPUT_DIR, "drivers_report_october.xlsx")


def calculate_hours(time_range_str):
    """
    Вычисляет продолжительность смены в часах по строке вида '04:39 - 12:32'
    """
    try:
        start_str, end_str = time_range_str.split(" - ")
        time_format = "%H:%M"

        start_time = datetime.strptime(start_str, time_format)
        end_time = datetime.strptime(end_str, time_format)

        # Считаем разницу в часах
        delta_hours = (end_time - start_time).total_seconds() / 3600.0

        # Если смена переходит через полночь (например 16:40 - 01:25)
        if delta_hours < 0:
            delta_hours += 24.0

        return round(delta_hours, 2)
    except Exception as e:
        print(f"Ошибка парсинга времени '{time_range_str}': {e}")
        return 0.0


def generate_excel():
    print(f"Загрузка данных из {INPUT_JSON}...")

    if not os.path.exists(INPUT_JSON):
        print(f"Файл {INPUT_JSON} не найден!")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)

    # Словарь для хранения статистики по водителям
    # Формат: { tab_number: { "Таб. номер": tab_number, "Всего смен": 0, "Всего часов": 0.0, 1: "Утро (8.5ч)", ...} }
    drivers_stats = {}
    max_day_in_month = 0

    print("Обработка данных...")
    for day_info in schedule_data:
        # Извлекаем день из даты (например "2026-10-01" -> 1)
        date_str = day_info.get("дата", "")
        if not date_str:
            continue

        day_number = int(date_str.split("-")[2])
        if day_number > max_day_in_month:
            max_day_in_month = day_number

        # Перебираем все успешные назначения
        for assignment in day_info.get("успешные_назначения", []):
            tab_number = assignment.get("таб_номер_водителя")
            shift_type = assignment.get("смена")
            time_str = assignment.get("время")

            # Считаем часы
            hours = calculate_hours(time_str)

            # Если водитель встречается впервые, создаем для него профиль
            if tab_number not in drivers_stats:
                drivers_stats[tab_number] = {
                    "Табельный номер": tab_number,
                    "Смен в месяц": 0,
                    "Часов в месяц": 0.0
                }
                # Инициализируем дни как пустые строки
                for d in range(1, 32):
                    drivers_stats[tab_number][f"{d}"] = ""

            # Обновляем статистику
            drivers_stats[tab_number]["Смен в месяц"] += 1
            drivers_stats[tab_number]["Часов в месяц"] += hours

            # Записываем информацию о смене в конкретный день
            # Формат ячейки: "Утро (7.88ч)"
            cell_text = f"{shift_type} ({hours}ч)"

            # Если в этот день уже есть смена (защита от дублей/накладок), дописываем через запятую
            if drivers_stats[tab_number][f"{day_number}"] != "":
                drivers_stats[tab_number][f"{day_number}"] += f", {cell_text}"
            else:
                drivers_stats[tab_number][f"{day_number}"] = cell_text

    # Формируем итоговый список для pandas
    data_for_df = list(drivers_stats.values())

    if not data_for_df:
        print("Нет данных для формирования отчета.")
        return

    # Создаем DataFrame
    df = pd.DataFrame(data_for_df)

    # Сортируем водителей по табельному номеру
    df = df.sort_values(by="Табельный номер")

    # Округляем итоговые часы до 2 знаков
    df["Часов в месяц"] = df["Часов в месяц"].round(2)

    # Определяем нужные колонки: база + только те дни, которые реально были в месяце (до max_day_in_month)
    columns_to_keep = ["Табельный номер", "Смен в месяц", "Часов в месяц"] + [f"{d}" for d in
                                                                              range(1, max_day_in_month + 1)]
    df = df[columns_to_keep]

    # Сохраняем в Excel
    print("Сохранение в Excel...")

    # Используем ExcelWriter для небольшой настройки ширины колонок
    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="График водителей")

        # Автоподбор ширины (опционально, делает красивее)
        worksheet = writer.sheets["График водителей"]
        for idx, col in enumerate(df.columns):
            worksheet.column_dimensions[chr(65 + idx) if idx < 26 else f"A{chr(65 + idx - 26)}"].width = 14

    print(f"Отчет успешно сохранен в: {OUTPUT_EXCEL}")


if __name__ == "__main__":
    generate_excel()