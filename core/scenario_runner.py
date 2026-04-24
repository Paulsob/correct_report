import os
import sys
import csv
import time

# Подключаем конфигурацию и модули
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import config
import absences_manager
import single_scheduler
import mixed_scheduler

# ==========================================
# НАСТРОЙКИ СИМУЛЯЦИИ
# ==========================================

# 1. Список графиков для тестирования: (Основной, Вспомогательный)
SCHEDULES_TO_TEST = [
    ("4x2", None),
    ("5x2", None),
    ("3x2x3x1", None),
    ("4x2", "5x2h"),
    ("5x2", "5x2h")
]

# 2. Матрица сценариев отсутствий (из таблицы)
SCENARIOS = [
    {"name": "1. Базовый (Идеал: 0% Бол, 0% Отп)", "sick": None, "vac": None},
    {"name": "2. Стандарт (8% Бол, 1/12 Отп)", "sick": "8%", "vac": "1/12"},
    {"name": "3. Гаусс (1-10% Бол, 1/12 Отп)", "sick": "normal", "vac": "1/12"},
    {"name": "4. Случайный всплеск (до 15% Бол, 1/12 Отп)", "sick": "random_15", "vac": "1/12"},
    {"name": "5. Только отпуска (0% Бол, 1/12 Отп)", "sick": None, "vac": "1/12"},
    {"name": "6. Пиковая нагрузка (8% Бол, 15% Отп)", "sick": "8%", "vac": "15%"},
]


def run_simulations():
    print("=" * 70)
    print(" ЗАПУСК СЦЕНАРНОГО СТРЕСС-ТЕСТИРОВАНИЯ")
    print("=" * 70)

    results = []

    for primary, secondary in SCHEDULES_TO_TEST:
        # Динамически подменяем конфиги во всех модулях
        config.PRIMARY_SCHEDULE = primary
        config.SECONDARY_SCHEDULE = secondary
        single_scheduler.PRIMARY_SCHEDULE = primary
        mixed_scheduler.PRIMARY_SCHEDULE = primary
        mixed_scheduler.SECONDARY_SCHEDULE = secondary

        sched_name = f"{primary} + {secondary}" if secondary else primary
        print(f"\n\n>>> ТЕСТИРОВАНИЕ ГРАФИКА: [ {sched_name} ] <<<")

        for scenario in SCENARIOS:
            print(f"\n--- Сценарий: {scenario['name']} ---")

            # 1. Очищаем базу отсутствий
            absences_manager.save_absences([])

            # 2. Генерируем новые отсутствия по условиям сценария
            if scenario['sick']:
                absences_manager.generate_sick_percentage(scenario['sick'])
            if scenario['vac']:
                absences_manager.generate_vacation_percentage(scenario['vac'])

            # Глушим вывод планировщиков в консоль, чтобы не засорять терминал (перенаправляем в devnull)
            old_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w', encoding='utf-8')

            # 3. Запускаем распределение и ловим метрики
            try:
                if secondary:
                    unique_drivers, unassigned, assigned = mixed_scheduler.generate_hybrid_schedule()
                else:
                    unique_drivers, unassigned, assigned = single_scheduler.generate_single_schedule()
            finally:
                # Возвращаем нормальный вывод в консоль
                sys.stdout.close()
                sys.stdout = old_stdout

            # 4. Сохраняем результат
            print(f"Результат: {unique_drivers} водителей | {unassigned} смен не закрыто.")

            results.append({
                "График": sched_name,
                "Сценарий": scenario['name'],
                "Уникальных водителей": unique_drivers,
                "Не закрыто смен": unassigned,
                "Успешных смен": assigned
            })

            time.sleep(0.5)  # Небольшая пауза для стабильности

    # ==========================================
    # ЭКСПОРТ И ВЫВОД РЕЗУЛЬТАТОВ
    # ==========================================
    print("\n\n" + "=" * 80)
    print(" ИТОГОВАЯ АНАЛИТИКА (Уникальные водители / Незакрытые смены)")
    print("=" * 80)

    # Форматированный вывод в консоль
    print(f"{'График':<15} | {'Сценарий':<45} | {'Водители':<10} | {'Дыры (смен)':<10}")
    print("-" * 85)
    for r in results:
        print(f"{r['График']:<15} | {r['Сценарий']:<45} | {r['Уникальных водителей']:<10} | {r['Не закрыто смен']:<10}")

    # Сохранение в CSV (для Excel)
    output_dir = os.path.join(config.BASE_DIR, "output_data")
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "simulation_results.csv")

    with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["График", "Сценарий", "Уникальных водителей", "Не закрыто смен",
                                               "Успешных смен"])
        writer.writeheader()
        writer.writerows(results)

    print("=" * 80)
    print(f"Отчет сохранен: {csv_path}")


if __name__ == "__main__":
    run_simulations()