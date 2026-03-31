import time
from pathlib import Path

from prepare_data.data_loader import load_schedule_data, load_transport_schedule
from kernel.new_scheduler import run_simulation
from kernel.new_generate_summary_report import generate_excel_reports

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
RAW_RESULTS_DIR = REPORTS_DIR / "raw_results"


def save_raw_json(result_obj, filename: str):
    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    filepath = RAW_RESULTS_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result_obj.model_dump_json(indent=4))
    print(f"Сырой лог сохранен в: {filepath}")


def main():
    print("Запуск системы планирования")
    start_time = time.time()

    print("\n[1/3] Загрузка данных")
    try:
        drivers_data = load_schedule_data("4x2_10_drivers_october.json")
        transport_data = load_transport_schedule("schedule.json")
    except Exception as e:
        print(f"Ошибка при загрузке данных. Программа остановлена.")
        return

    print("\n[2/3] Распределение смен")
    result = run_simulation(drivers_data, transport_data)

    print("\n[3/3] Сохранение результатов")
    save_raw_json(result, f"simulation_result_{result.month.lower()}.json")

    # Заглушка для будущего генератора Excel
    generate_excel_reports(result, REPORTS_DIR / "excel_reports")

    execution_time = round(time.time() - start_time, 2)
    print("ИТОГИ РАСПРЕДЕЛЕНИЯ:")
    print(f"Период:             {result.month} {result.year}")
    print(f"Всего смен:         {len(result.shifts_log)}")
    print(f"Закрыто водителями: {len(result.shifts_log) - result.uncovered_shifts_count}")

    if result.uncovered_shifts_count > 0:
        print(f"НЕ ЗАКРЫТО: {result.uncovered_shifts_count} смен!")
    else:
        print(f"ВСЕ СМЕНЫ ЗАКРЫТЫ ИДЕАЛЬНО!")

    print(f"Время расчета:    {execution_time} сек.")


if __name__ == "__main__":
    main()