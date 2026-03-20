import os
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


def generate_excel_report(assigned_shifts, all_shifts, covered_shift_ids, drivers_dict, max_days,
                          filename="Отчет_Расписание.xlsx"):
    # Создаем папку, если путь содержит директорию
    save_dir = os.path.dirname(filename)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Расписание"

    # --- СТИЛИ ---
    bold_font = Font(bold=True)
    center_aligned = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'),
                         bottom=Side(style='thin'))

    header_fill = PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid")
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")  # Успешная смена
    yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")  # Резерв
    gray_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")  # Выходной
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")  # Незакрытая смена

    # --- ЗАГОЛОВКИ ---
    headers = ["Таб. №", "Смен", "Часов"] + [str(d) for d in range(1, max_days + 1)]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = bold_font
        cell.alignment = center_aligned
        cell.fill = header_fill
        cell.border = thin_border

    # --- ЗАПОЛНЕНИЕ ВОДИТЕЛЕЙ ---
    # Сортируем водителей по количеству часов (по убыванию)
    drivers_sorted = sorted(assigned_shifts.items(), key=lambda item: sum(s.duration for s in item[1]), reverse=True)

    for d_id, shifts_list in drivers_sorted:
        if not shifts_list:
            continue  # Пропускаем водителей, которых алгоритм вообще не вызвал в этом месяце

        shifts_list.sort(key=lambda s: s.start_dt)
        total_shifts = len(shifts_list)
        total_hours = sum(s.duration for s in shifts_list)

        row_cells = [d_id, total_shifts, round(total_hours, 1)]
        ws.append(row_cells)
        current_row = ws.max_row

        for col_idx in range(1, 4):
            ws.cell(row=current_row, column=col_idx).alignment = center_aligned
            ws.cell(row=current_row, column=col_idx).border = thin_border

        shifts_by_day = {s.day: s for s in shifts_list}
        driver_pattern = drivers_dict[d_id]["pattern"]

        # Заполняем дни
        for day in range(1, max_days + 1):
            col_idx = day + 3
            cell = ws.cell(row=current_row, column=col_idx)
            cell.alignment = center_aligned
            cell.border = thin_border

            pattern_val = driver_pattern.get(day, "В")

            if day in shifts_by_day:
                # ВОДИТЕЛЬ РАБОТАЕТ (ЗЕЛЕНЫЙ)
                current_shift = shifts_by_day[day]
                idx = shifts_list.index(current_shift)
                rest_str = "---"
                if idx > 0:
                    prev_shift = shifts_list[idx - 1]
                    rest_hours = (current_shift.start_dt - prev_shift.end_dt).total_seconds() / 3600.0
                    rest_str = f"{round(rest_hours, 1)}ч"

                cell.value = f"Р ({round(current_shift.duration, 1)}ч)\n[Отд: {rest_str}]"
                cell.fill = green_fill
            else:
                if pattern_val in ["1", "2"]:
                    # ДОЛЖЕН БЫЛ РАБОТАТЬ, НО НЕ ПОЛУЧИЛ СМЕНУ (ЖЕЛТЫЙ - РЕЗЕРВ)
                    cell.value = "Резерв"
                    cell.fill = yellow_fill
                else:
                    # ЗАКОННЫЙ ВЫХОДНОЙ (СЕРЫЙ)
                    cell.value = "В (Вых)"
                    cell.fill = gray_fill
                    cell.font = Font(color="808080")

    # --- ИНФОРМАЦИЯ О НЕЗАКРЫТЫХ СМЕНАХ (ПОДВАЛ) ---
    uncovered_by_day = {day: [] for day in range(1, max_days + 1)}
    for s in all_shifts:
        if s.id not in covered_shift_ids:
            uncovered_by_day[s.day].append(f"См.{s.type_str} (Тр.{s.tram_num})")

    ws.append([])  # Пустая строка для отступа
    bottom_row_idx = ws.max_row + 1
    ws.cell(row=bottom_row_idx, column=1).value = "НЕЗАКРЫТЫЕ СМЕНЫ:"
    ws.cell(row=bottom_row_idx, column=1).font = bold_font

    for day in range(1, max_days + 1):
        cell = ws.cell(row=bottom_row_idx, column=day + 3)
        cell.alignment = center_aligned
        cell.border = thin_border
        uncovered = uncovered_by_day[day]

        if uncovered:
            cell.value = "\n".join(uncovered)
            cell.fill = red_fill
            cell.font = Font(color="9C0006", bold=True)
        else:
            cell.value = "ОК"
            cell.font = Font(color="006100")
            cell.fill = green_fill

    # --- ШИРИНА КОЛОНОК ---
    ws.column_dimensions['A'].width = 10
    ws.column_dimensions['B'].width = 8
    ws.column_dimensions['C'].width = 8
    for col in range(4, max_days + 4):
        ws.column_dimensions[get_column_letter(col)].width = 15

    wb.save(filename)
    print(f"Готово! Отчет сохранен: {filename}.")
