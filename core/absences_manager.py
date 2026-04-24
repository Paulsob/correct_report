import sys
import os
import json
import random
import calendar
from datetime import datetime, timedelta

# Подключаем конфиг
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import config

ABSENCES_FILE = getattr(config, "ABSENCES_FILE", os.path.join(config.BASE_DIR, "absences.json"))


# ==========================================
# БАЗОВЫЕ ФУНКЦИИ И ПРОВЕРКИ
# ==========================================

def load_absences():
    if not os.path.exists(ABSENCES_FILE):
        return []
    try:
        with open(ABSENCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_absences(data):
    os.makedirs(os.path.dirname(ABSENCES_FILE), exist_ok=True)
    with open(ABSENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_all_driver_tabs():
    """Загружает список всех доступных табельных номеров из текущего пула."""
    try:
        with open(config.DRIVERS_PREPARED, "r", encoding="utf-8") as f:
            data = json.load(f)
            drivers_list = data.get("drivers", []) if isinstance(data, dict) else data
            return [str(d["tab_number"]) for d in drivers_list if "tab_number" in d]
    except FileNotFoundError:
        print(f"Файл водителей не найден: {config.DRIVERS_PREPARED}")
        return []


def validate_date(date_text):
    try:
        return datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return None


def check_overlap(start_dt, end_dt, driver_tab, existing_absences):
    """Проверяет, нет ли уже отсутствия у водителя в эти даты."""
    for record in existing_absences:
        if str(record["tab_number"]) == str(driver_tab):
            rec_start = validate_date(record["start_date"])
            rec_end = validate_date(record["end_date"])
            if rec_start and rec_end:
                if max(start_dt, rec_start) <= min(end_dt, rec_end):
                    return record
    return None


def get_available_drivers(start_dt, end_dt, all_tabs, existing_absences, needed_count):
    """Возвращает список случайных табельных номеров, которые свободны в указанный период."""
    available = []
    for tab in all_tabs:
        if not check_overlap(start_dt, end_dt, tab, existing_absences):
            available.append(tab)

    if len(available) < needed_count:
        return None

    return random.sample(available, needed_count)


# ==========================================
# ЛОГИКА ДОБАВЛЕНИЯ (БИЗНЕС-ТРЕБОВАНИЯ)
# ==========================================

def add_single_absence(abs_type, prompt_title, fixed_days=None):
    """1.1, 2.1, 3.1: Отсутствие для одного человека."""
    print(f"\n--- {prompt_title} (1 человек) ---")
    tab_num = input("Введите табельный номер: ").strip()

    start_str = input("Дата начала (ГГГГ-ММ-ДД): ").strip()
    start_dt = validate_date(start_str)
    if not start_dt:
        print("Ошибка формата даты.")
        return

    if fixed_days:
        end_dt = start_dt + timedelta(days=fixed_days - 1)
        print(f"Дата окончания рассчитана автоматически: {end_dt.strftime('%Y-%m-%d')}")
    else:
        end_str = input("Дата окончания (ГГГГ-ММ-ДД): ").strip()
        end_dt = validate_date(end_str)
        if not end_dt or end_dt < start_dt:
            print("Ошибка даты окончания.")
            return

    comment = input("Комментарий (необязательно): ").strip()

    absences = load_absences()
    overlap = check_overlap(start_dt, end_dt, tab_num, absences)

    if overlap:
        print(
            f"ОШИБКА: У водителя {tab_num} уже есть {overlap['type']} в этот период ({overlap['start_date']} - {overlap['end_date']}).")
        return

    absences.append({
        "tab_number": tab_num,
        "type": abs_type,
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "end_date": end_dt.strftime("%Y-%m-%d"),
        "comment": comment
    })
    save_absences(absences)
    print(f"Успешно: Водитель {tab_num} отправлен в {abs_type}.")


def add_group_absence_fixed(abs_type, prompt_title, fixed_days=None):
    """1.2, 2.2: Отсутствие для группы людей на заданный срок."""
    print(f"\n--- {prompt_title} (Группа на точные даты) ---")
    try:
        count = int(input("Количество человек: "))
    except ValueError:
        print("Введите число.")
        return

    start_str = input("Дата начала (ГГГГ-ММ-ДД): ").strip()
    start_dt = validate_date(start_str)
    if not start_dt: return

    if fixed_days:
        end_dt = start_dt + timedelta(days=fixed_days - 1)
        print(f"Дата окончания рассчитана автоматически: {end_dt.strftime('%Y-%m-%d')}")
    else:
        end_str = input("Дата окончания (ГГГГ-ММ-ДД): ").strip()
        end_dt = validate_date(end_str)
        if not end_dt or end_dt < start_dt: return

    all_tabs = load_all_driver_tabs()
    absences = load_absences()

    selected_tabs = get_available_drivers(start_dt, end_dt, all_tabs, absences, count)

    if not selected_tabs:
        print("ОШИБКА: Не хватает водителей, у которых нет пересечений по датам.")
        return

    for tab in selected_tabs:
        absences.append({
            "tab_number": tab,
            "type": abs_type,
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "comment": f"[Групповое назначение] {abs_type}"
        })

    save_absences(absences)
    print(
        f"Успешно: {count} чел. отправлены в {abs_type} с {start_dt.strftime('%Y-%m-%d')} по {end_dt.strftime('%Y-%m-%d')}.")


def add_group_sick_random():
    """1.3: Больничный для группы на незаданный срок (размазать по месяцу)."""
    print("\n--- Больничный (Группа, разброс по текущему месяцу) ---")
    try:
        count = int(input("Количество человек: "))
    except ValueError:
        print("Введите число.")
        return

    _distribute_sick_leaves(count, "[Генерация] Случайный больничный")


# ==========================================
# ЛОГИКА СЦЕНАРНОГО МОДЕЛИРОВАНИЯ (% ОТ ПУЛА)
# ==========================================

def _distribute_sick_leaves(count, comment_prefix):
    """Вспомогательная функция для размазывания больничных по месяцу"""
    year = config.TARGET_YEAR
    month = config.TARGET_MONTH
    _, days_in_month = calendar.monthrange(year, month)

    all_tabs = load_all_driver_tabs()
    if not all_tabs: return

    absences = load_absences()
    success_count = 0
    random.shuffle(all_tabs)

    for tab in all_tabs:
        if success_count >= count: break

        duration = random.randint(5, 14)
        max_start = max(1, days_in_month - duration + 1)
        start_day = random.randint(1, max_start)

        start_dt = datetime(year, month, start_day)
        end_dt = start_dt + timedelta(days=duration - 1)

        if not check_overlap(start_dt, end_dt, tab, absences):
            absences.append({
                "tab_number": tab,
                "type": "sick",
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": end_dt.strftime("%Y-%m-%d"),
                "comment": f"{comment_prefix} на {duration} дн."
            })
            success_count += 1

    if success_count > 0:
        save_absences(absences)
        print(f"Успешно: {success_count} чел. получили больничные (цель была {count}).")
    else:
        print("Не удалось назначить больничные (все водители заняты).")


def generate_sick_percentage(mode):
    """Генерация больничных по процентам от расчетного числа водителей"""
    all_tabs = load_all_driver_tabs()
    total_drivers = len(all_tabs)
    if total_drivers == 0: return

    pct = 0.0
    if mode == "8%":
        pct = 0.08
        comment = "[Сценарий] Больничный 8%"
    elif mode == "normal":
        # Гауссово распределение: среднее 5.5%, откл 1.5% -> дает колокол от 1% до 10%
        pct_val = random.gauss(5.5, 1.5)
        pct_val = max(1.0, min(10.0, pct_val))  # Ограничиваем жестко от 1 до 10
        pct = pct_val / 100.0
        comment = f"[Сценарий] Больничный Нормальное распр. ({pct_val:.1f}%)"
    elif mode == "random_15":
        pct_val = random.uniform(0.0, 15.0)
        pct = pct_val / 100.0
        comment = f"[Сценарий] Больничный Случайный ({pct_val:.1f}%)"

    target_count = int(total_drivers * pct)
    print(f"\n--- СЦЕНАРИЙ: Больничный ({mode}) ---")
    print(f"Всего водителей: {total_drivers}. Расчетная цель: {pct * 100:.1f}% -> {target_count} чел.")

    if target_count == 0:
        print("Количество человек для генерации равно нулю.")
        return

    _distribute_sick_leaves(target_count, comment)


def generate_vacation_percentage(mode):
    """Генерация отпусков по процентам от расчетного числа водителей"""
    year = config.TARGET_YEAR
    month = config.TARGET_MONTH
    _, days_in_month = calendar.monthrange(year, month)

    all_tabs = load_all_driver_tabs()
    total_drivers = len(all_tabs)
    if total_drivers == 0: return

    if mode == "1/12":
        target_count = int(total_drivers / 12)
        comment = "[Сценарий] Отпуск Равномерно (1/12 парка)"
    elif mode == "15%":
        target_count = int(total_drivers * 0.15)
        comment = "[Сценарий] Отпуск (15% парка)"

    print(f"\n--- СЦЕНАРИЙ: Отпуск ({mode}) ---")
    print(f"Всего водителей: {total_drivers}. Расчетная цель: {target_count} чел.")

    if target_count == 0:
        print("Количество человек для генерации равно нулю.")
        return

    absences = load_absences()
    success_count = 0
    random.shuffle(all_tabs)

    for i, tab in enumerate(all_tabs):
        if success_count >= target_count: break

        # Равномерное распределение по дням месяца, если режим 1/12
        if mode == "1/12":
            step = max(1, days_in_month / target_count)
            start_day = int((success_count * step) % days_in_month) + 1
        else:
            # Случайное распределение старта в рамках месяца
            start_day = random.randint(1, days_in_month)

        start_dt = datetime(year, month, start_day)
        end_dt = start_dt + timedelta(days=27)  # 28 дней отпуска

        if not check_overlap(start_dt, end_dt, tab, absences):
            absences.append({
                "tab_number": tab,
                "type": "vacation",
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": end_dt.strftime("%Y-%m-%d"),
                "comment": comment
            })
            success_count += 1

    if success_count > 0:
        save_absences(absences)
        print(f"Успешно: {success_count} чел. отправлены в отпуск (цель была {target_count}).")
    else:
        print("Не удалось назначить отпуска.")


# ==========================================
# ИНТЕРФЕЙС УПРАВЛЕНИЯ
# ==========================================

def show_absences():
    data = load_absences()
    print("\n=== ТЕКУЩИЕ ОТСУТСТВИЯ ===")
    if not data:
        print("Список пуст.")
        return

    print(f"{'Таб.№':<7} | {'Тип':<10} | {'Период':<23} | {'Комментарий'}")
    print("-" * 70)
    for item in sorted(data, key=lambda x: x['start_date']):
        t = item["type"]
        period = f"{item['start_date']} - {item['end_date']}"
        print(f"{item['tab_number']:<7} | {t:<10} | {period:<23} | {item.get('comment', '')}")


def clear_absences():
    if input("Удалить ВСЕ записи? (да/нет): ").strip().lower() == 'да':
        save_absences([])
        print("База очищена.")


def main():
    while True:
        print("\n=== МЕНЮ УПРАВЛЕНИЯ ОТСУТСТВИЯМИ ===")
        print("РУЧНОЙ ВВОД:")
        print("  1. Больничный (1 человек, точные даты)")
        print("  2. Больничный (Группа, точные даты)")
        print("  3. Больничный (Группа, случайно размазать по месяцу)")
        print("  4. Отпуск (1 человек, авто +28 дней)")
        print("  5. Отпуск (Группа, авто +28 дней)")
        print("  6. Прочее (1 человек, точные даты)")
        print("СЦЕНАРНОЕ МОДЕЛИРОВАНИЕ:")
        print("  7. Больничный: 8% от парка")
        print("  8. Больничный: 1-10% (Нормальное распределение)")
        print("  9. Больничный: Случайно до 15%")
        print(" 10. Отпуск: 1/12 парка (Равномерно)")
        print(" 11. Отпуск: 15% парка")
        print("-" * 35)
        print(" 12. Показать все отсутствия")
        print(" 13. Очистить базу")
        print("  0. Выход")

        choice = input("Выбор: ").strip()

        if choice == "1":
            add_single_absence("sick", "Больничный")
        elif choice == "2":
            add_group_absence_fixed("sick", "Больничный")
        elif choice == "3":
            add_group_sick_random()
        elif choice == "4":
            add_single_absence("vacation", "Отпуск", fixed_days=28)
        elif choice == "5":
            add_group_absence_fixed("vacation", "Отпуск", fixed_days=28)
        elif choice == "6":
            add_single_absence("other", "Прочее")
        elif choice == "7":
            generate_sick_percentage("8%")
        elif choice == "8":
            generate_sick_percentage("normal")
        elif choice == "9":
            generate_sick_percentage("random_15")
        elif choice == "10":
            generate_vacation_percentage("1/12")
        elif choice == "11":
            generate_vacation_percentage("15%")
        elif choice == "12":
            show_absences()
        elif choice == "13":
            clear_absences()
        elif choice == "0":
            break
        else:
            print("Неверный выбор.")


if __name__ == "__main__":
    main()