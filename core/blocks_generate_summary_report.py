import os
import json
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Alignment


def generate_report():
    # Пути
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    input_path = os.path.join(project_root, 'output_data', 'output_shifts.json')
    output_path = os.path.join(project_root, 'output_data', 'summary_report_month.xlsx')

    if not os.path.exists(input_path):
        print(f"Файл не найден: {input_path}")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    df = pd.DataFrame(data)

    # 1. Собираем дату из колонок day, month, year
    # Создаем временную колонку 'date' для сводной таблицы
    df['date'] = pd.to_datetime(df[['year', 'month', 'day']])

    # 2. Определяем статус
    # В твоем примере нет явного поля "status", но есть "assigned_driver".
    # Предположим, если в исходных данных запись помечена как резервная,
    # там будет соответствующий текст. Если нет — выводим номер смены/маршрут.
    if 'status' not in df.columns:
        # Если статуса нет, будем отображать номер смены (shift_num)
        df['display_status'] = df['shift_num'].astype(str)
    else:
        df['display_status'] = df['status']

    # 3. Создаем сводную таблицу
    # Строки: ID водителя, Столбцы: Дата, Значения: Статус/Номер смены
    report = df.pivot_table(
        index='assigned_driver',
        columns='date',
        values='display_status',
        aggfunc='first'  # Берем первую найденную смену, если их несколько
    )

    # Сортируем и форматируем даты (ДД.ММ)
    report = report.sort_index(axis=1)
    report.columns = [d.strftime('%d.%m') for d in report.columns]

    # Сохраняем
    report.to_excel(output_path, engine='openpyxl')

    # 4. Оформление через openpyxl
    wb = load_workbook(output_path)
    ws = wb.active
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")

    for row in ws.iter_rows(min_row=2, min_col=2):
        for cell in row:
            val = str(cell.value).upper() if cell.value else ""
            # Логика выделения резерва
            if val in ['РЕЗЕРВ', 'RESERVE', 'NAN', 'NONE']:
                # Если ячейка пустая (NaN) или содержит текст резерва
                if val in ['РЕЗЕРВ', 'RESERVE']:
                    cell.value = "РЕЗЕРВ"
                    cell.fill = yellow_fill

            cell.alignment = Alignment(horizontal='center')

    # Настройка колонок
    ws.column_dimensions['A'].width = 15  # Для ID водителя
    for col in range(2, ws.max_column + 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = 8

    wb.save(output_path)
    print(f"Отчет сформирован: {output_path}")


if __name__ == "__main__":
    generate_report()