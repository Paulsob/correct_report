import pandas as pd
from pathlib import Path
from prepare_data.models import SimulationResult


def generate_excel_reports(result: SimulationResult, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"Расписание_{result.month}_{result.year}.xlsx"
    summary_data = []
    for d in result.drivers_log:
        row = {
            "Таб. №": d.tab_number,
            "Итого часов": d.total_hours_worked,
            "Итого смен": d.total_shifts_worked
        }
        for day in range(1, 32):
            row[str(day)] = d.daily_status.get(day, "")

        summary_data.append(row)

    df_summary = pd.DataFrame(summary_data)

    schedule_data = []
    audit_data = []

    for s in result.shifts_log:
        driver = s.assigned_driver_tab if s.assigned_driver_tab else "НЕ НАЗНАЧЕН"

        schedule_data.append({
            "Дата": s.date,
            "Маршрут": s.route,
            "Трамвай": s.tram_number,
            "Смена": s.shift_num,
            "Отправление": s.start_time.strftime("%H:%M"),
            "Прибытие": s.end_time.strftime("%H:%M"),
            "Длительность (ч)": round(s.duration_hours, 2),
            "Водитель (Таб. №)": driver
        })

        rest_val = round(s.rest_before_shift_hours, 1) if s.rest_before_shift_hours else "Первая смена"
        available_val = s.available_from_next.strftime("%d.%m %H:%M") if s.available_from_next else ""

        audit_data.append({
            "Дата": s.date,
            "Водитель": driver,
            "Код смены": f"М{s.route}-Т{s.tram_number}-С{s.shift_num}",
            "Начало работы": s.start_time.strftime("%d.%m %H:%M"),
            "Конец работы": s.end_time.strftime("%d.%m %H:%M"),
            "Отдых ДО смены (ч)": rest_val,
            "Снова доступен с": available_val if driver != "НЕ НАЗНАЧЕН" else ""
        })

    df_schedule = pd.DataFrame(schedule_data)
    df_audit = pd.DataFrame(audit_data)

    print(f"Формирование Excel файла: {filename.name}")

    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df_summary.to_excel(writer, sheet_name="Сводный_отчет", index=False)
        df_schedule.to_excel(writer, sheet_name="Книга_расписания", index=False)
        df_audit.to_excel(writer, sheet_name="Аудит_отдыха", index=False)

    print(f"Готово! Файл сохранен в: {filename}")