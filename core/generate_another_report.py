import json
import re
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', str(s))]


def generate_schedule_report(schedule_path: Path, assignment_path: Path, output_path: Path):
    if not schedule_path.exists() or not assignment_path.exists():
        print(f"❌ Ошибка: Файлы не найдены.")
        return

    schedule_data = json.load(open(schedule_path, 'r', encoding='utf-8'))
    assignment_data = json.load(open(assignment_path, 'r', encoding='utf-8'))

    wb = Workbook()
    wb.remove(wb.active)

    # Настройка стилей линий
    m = Side(style='medium', color='000000')  # Жирная
    t = Side(style='thin', color='000000')  # Тонкая

    # Функция для создания границы ячейки в зависимости от её колонки
    def get_border(col_idx):
        # Группы: 1-2 (A-B), 3-6 (C-F), 7-8 (G-H)
        # Примечание: в коде данные идут в колонках 1-8 (A-H)

        # Левая граница жирная, если это начало группы
        left = m if col_idx in [1, 3, 6] else t
        # Правая граница жирная, если это конец группы или край таблицы
        right = m if col_idx in [2, 5, 8] else t
        # Верх и низ всегда жирные для строк данных
        return Border(left=left, right=right, top=m, bottom=m)

    sched_map = {}
    for r_info in schedule_data:
        sched_map.setdefault(r_info['день'], {})[str(r_info['маршрут'])] = {str(t['номер']): t for t in
                                                                            r_info['трамваи']}

    for day_entry in assignment_data:
        date_str = day_entry['дата']
        ws = wb.create_sheet(title=date_str)

        # Шапка и заголовки (упростим для краткости, оставим логику границ)
        headers = ['Наряд', 'Вагон', 'Таб. Утро', 'Начало', 'Конец', 'Таб. Вечер', 'Начало', 'Конец']
        for i, h in enumerate(headers, 1):
            cell = ws.cell(row=3, column=i, value=h)
            cell.font = Font(bold=True)
            cell.border = get_border(i)
            cell.alignment = Alignment(horizontal='center')

        curr_row = 4
        routes = sorted(sched_map.get(day_entry['тип_дня'], {}).keys(), key=natural_sort_key)

        for r_num in routes:
            trams = sched_map[day_entry['тип_дня']][r_num]

            # Заголовок маршрута с жирной рамкой по краям всей таблицы
            ws.merge_cells(f'A{curr_row}:H{curr_row}')
            ws[f'A{curr_row}'] = f"Маршрут {r_num}"
            ws[f'A{curr_row}'].font = Font(bold=True)
            for col in range(1, 9):
                # Для заголовка маршрута делаем только внешние границы жирными
                l_border = m if col == 1 else None
                r_border = m if col == 8 else None
                ws.cell(row=curr_row, column=col).border = Border(left=l_border, right=r_border, top=m, bottom=m)
            curr_row += 1

            for t_num in sorted(trams.keys(), key=natural_sort_key):
                u_tab = v_tab = ""
                v_num = "Н/Д"
                for assign in day_entry['успешные_назначения']:
                    if str(assign['маршрут']) == str(r_num) and str(assign['трамвай']) == str(t_num):
                        v_num = assign.get('номер_вагона', v_num)
                        if assign['смена'] == "Утро": u_tab = assign['таб_номер_водителя']
                        if assign['смена'] == "Вечер": v_tab = assign['таб_номер_водителя']

                row_vals = [t_num, v_num, u_tab,
                            trams[t_num].get('смена_1', {}).get('отправление', '-'),
                            trams[t_num].get('смена_1', {}).get('прибытие', '-'),
                            v_tab,
                            trams[t_num].get('смена_2', {}).get('отправление', '-'),
                            trams[t_num].get('смена_2', {}).get('прибытие', '-')]

                for i, val in enumerate(row_vals, 1):
                    cell = ws.cell(row=curr_row, column=i, value=val)
                    cell.border = get_border(i)  # ПРИМЕНЯЕМ ЛОГИКУ ГРУППИРОВКИ
                    cell.alignment = Alignment(horizontal='center')
                curr_row += 1
            curr_row += 1

    wb.save(output_path)
    print(f"✅ Отчет с группировкой столбцов готов: {output_path}")


if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parent.parent
    generate_schedule_report(
        ROOT / "input_data/03_operational/schedule/prepared/new_schedule_prepared.json",
        ROOT / "output_data/2026/10/4x2_5x2h/4x2_5x2h_BLOCK_final_schedule.json",
        ROOT / "output_data/report_grouped_borders.xlsx"
    )