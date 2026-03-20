import os
from kernel.new_scheduler import solve_schedule
from kernel.new_generate_summary_report import generate_excel_report

# ==========================================
# НАСТРОЙКИ РЕЖИМА МОДЕЛИРОВАНИЯ
# ==========================================
# 1 = Строгий режим (Отдых >= 2 * Работа)
# 2 = Смягченный режим (Отдых >= 2 * Работа ИЛИ минимум 12 часов)
REST_MODE = 2
# ==========================================

# Настройка путей для сохранения отчетов
REPORTS_CONFIG = {
    1: {
        "folder": "full_relax",
        "label": "Строгий"
    },
    2: {
        "folder": "12hours_relax",
        "label": "Смягченный"
    }
}

if __name__ == "__main__":
    # 1. Определяем папку для сохранения
    config = REPORTS_CONFIG.get(REST_MODE, REPORTS_CONFIG[2])
    reports_folder = config["folder"]

    # 2. Создаем полный путь: new_plan/reports/{folder}/
    base_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(base_dir, "reports", reports_folder)

    # 3. Создаем папку, если её нет
    os.makedirs(save_path, exist_ok=True)

    print(f"\n{'=' * 50}")
    print(f"РЕЖИМ: {config['label']} (REST_MODE = {REST_MODE})")
    print(f"ПУТЬ СОХРАНЕНИЯ: {save_path}")
    print(f"{'=' * 50}\n")

    # 4. Запуск логики решения
    result = solve_schedule(rest_mode=REST_MODE)

    # 5. Генерация отчета, если решение найдено
    if result and result.get("success"):
        report_name = (
            f"Расписание_{result['month_name'].capitalize()}_"
            f"{result['year']}_Режим{REST_MODE}.xlsx"
        )
        full_path = os.path.join(save_path, report_name)

        generate_excel_report(
            assigned_shifts=result["assigned_shifts"],
            all_shifts=result["all_shifts"],
            covered_shift_ids=result["covered_shift_ids"],
            drivers_dict=result["drivers_dict"],
            max_days=result["max_days"],
            filename=full_path  # Передаем полный путь
        )
    else:
        print("\nПроцесс завершен с ошибкой. Отчет не создан.")