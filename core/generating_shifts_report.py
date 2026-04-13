import os
import sys
import json
import openpyxl
from datetime import datetime

# -----------------------------------------------------------------------
# 1. НАСТРОЙКА ПУТЕЙ (АБСОЛЮТНАЯ НАВИГАЦИЯ)
# -----------------------------------------------------------------------

# Находим путь к текущему файлу скрипта
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Поднимаемся на 1 уровень вверх (из core в корень проекта)
PROJECT_ROOT = os.path.dirname(CURRENT_SCRIPT_DIR)

# Формируем пути относительно корня
TEMPLATE_EXCEL = os.path.join(PROJECT_ROOT, "input_data", "030426.xlsx")
JSON_DATA = os.path.join(PROJECT_ROOT, "output_data", "2026", "10", "4x2_5x2h", "4x2_5x2h_BLOCK_final_schedule.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output_data", "2026", "10", "4x2_5x2h")

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Naryad_October_2026.xlsx")


# -----------------------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# -----------------------------------------------------------------------

def get_day_of_week(day, month, year):
    """Возвращает название дня недели на русском"""
    date_obj = datetime(year, month, day)
    days_map = {
        0: 'понедельник', 1: 'вторник', 2: 'среда',
        3: 'четверг', 4: 'пятница', 5: 'суббота', 6: 'воскресенье'
    }
    return days_map[date_obj.weekday()]


def load_json_data(filepath):
    """Загружает и структурирует данные из JSON"""
    print(f"📄 Загрузка данных из: {filepath}")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл JSON не найден: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    # Преобразуем в удобный словарь: {"день": {"(маршрут, трамвай)": {"утро": id, "вечер": id}}}
    structured_data = {}

    for day_record in raw_data:
        date_str = day_record.get('дата', '2026-10-01')
        day_num = int(date_str.split('-')[2])  # Получаем число дня из "2026-10-05"

        daily_shifts = {}
        for assignment in day_record.get('успешные_назначения', []):
            route = str(assignment['маршрут'])
            tram = str(assignment['трамвай'])
            driver_id = str(assignment['таб_номер_водителя'])
            shift_name = assignment['смена']  # "Утро" или "Вечер"

            key = (route, tram)
            if key not in daily_shifts:
                daily_shifts[key] = {}

            # Сохраняем водителя в нужную смену
            if "Утро" in shift_name or "утро" in shift_name.lower():
                daily_shifts[key]['утро'] = driver_id
            elif "Вечер" in shift_name or "вечер" in shift_name.lower():
                daily_shifts[key]['вечер'] = driver_id

        structured_data[day_num] = daily_shifts

    return structured_data


def create_route_tram_map(ws):
    """
    Сканирует лист Excel и создает карту:
    { ('9', '1'): 10, ('9', '2'): 11, ... } -> возвращает номер строки
    """
    print("🗺️  Сканирование структуры Excel...")
    coord_map = {}
    current_route = None

    # Проходим по строкам
    for row in ws.iter_rows(min_row=1, max_row=1000):  # Ограничим поиск 1000 строками
        cell_a = row[0]  # Колонка A
        cell_b = row[1]  # Колонка B

        # 1. Поиск заголовка маршрута (обычно содержит слово "Маршрут" и "Трамваи")
        if cell_a.value and isinstance(cell_a.value, str) and "Маршрут" in str(cell_a.value) and "Трамваи" in str(
                cell_a.value):
            # Извлекаем номер маршрута (например, "Маршрут 9 Трамваи" -> "9")
            parts = str(cell_a.value).split()
            if len(parts) > 1:
                current_route = parts[1]
            continue

        # 2. Поиск строки трамвая (В колонке A число, в колонке B тоже есть данные)
        # Мы проверяем, что в колонке A стоит число (номер наряда/трамвая)
        if current_route and cell_a.value and isinstance(cell_a.value, (int, float)):
            tram_num = str(int(cell_a.value))
            # Записываем в карту: (Маршрут, Трамвай) -> Номер строки
            # row[0].row возвращает индекс строки (1, 2, 3...)
            coord_map[(current_route, tram_num)] = cell_a.row

    print(f"✅ Найдено {len(coord_map)} строк трамваев.")
    return coord_map


def fill_naryad_report(json_data, coord_map, template_path, output_path):
    print(f"🚀 Генерация отчета...")

    # Загружаем книгу один раз
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Шаблон Excel не найден: {template_path}")

    wb = openpyxl.load_workbook(template_path)
    ws = wb.active

    # Создаем папку вывода если нет
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Генерируем 31 лист (или перезаписываем существующие, если их мало)
    for day in range(1, 32):
        date_str = f"{day:02d}.10.2026"
        day_name = get_day_of_week(day, 10, 2026)

        # 1. Создаем или выбираем лист для дня
        if day == 1:
            # Используем первый лист для 1-го числа
            ws_target = wb.active
            ws_target.title = date_str
        else:
            # Копируем шаблон (берем его из первого листа, который мы уже модифицировали,
            # но чтобы не накапливать изменения, лучше бы копировать чистый,
            # однако openpyxl не дает хранить "чистый" шаблон в памяти легко.
            # Поэтому мы будем модифицировать один и тот же лист последовательно,
            # сохранять в новый файл НЕЛЬЗЯ, так как это будет 31 файл.
            # НО! Задача скорее всего подразумевает ОДИН файл с 31 листом.
            # Тогда нам нужно каждый раз брать чистую копию.
            pass

            # ПЕРЕСМОТР СТРАТЕГИИ:
    # Openpyxl не умеет "откатывать" изменения на листе.
    # Если нам нужно 31 лист в ОДНОМ файле, нам нужно 31 раз загрузить шаблон?
    # Это медленно.
    # БЫСТРЕЕ: Создать новый файл, и 31 раз добавить туда лист, скопировав данные из активного листа wb.

    # Правильный алгоритм для 31 листа в одном файле:
    final_wb = openpyxl.Workbook()
    # Удалим дефолтный лист
    final_wb.remove(final_wb.active)

    # Источник данных (шаблон)
    source_wb = openpyxl.load_workbook(template_path)
    source_ws = source_wb.active

    for day in range(1, 32):
        date_str = f"{day:02d}.10.2026"
        day_name = get_day_of_week(day, 10, 2026)

        print(f"📅 Обработка дня: {date_str} ({day_name})")

        # 1. Копируем структуру шаблона в новый лист
        # Openpyxl copy_worksheet работает только внутри одной книги.
        # Придется копировать вручную значения и стили, или использовать хак с copy.
        # Самый надежный способ для сохранения стилей:
        target_ws = final_wb.create_sheet(title=date_str)

        # Копируем данные из источника (медленно, но надежно для структуры)
        for r_idx, row in enumerate(source_ws.iter_rows(), 1):
            for c_idx, cell in enumerate(row, 1):
                target_ws.cell(row=r_idx, column=c_idx, value=cell.value)
                # Копирование стилей (опционально, если нужно сохранить цвета)
                # if cell.has_style: ... (обычно value достаточно для наряда)

        # 2. Обновляем заголовок даты в новом листе
        # Ищем ячейку с текстом "НАРЯД"
        found_header = False
        for row in target_ws.iter_rows(min_row=1, max_row=10, min_col=1, max_col=15):
            for cell in row:
                if cell.value and "НАРЯД на" in str(cell.value):
                    cell.value = f"НАРЯД на {date_str} ({day_name})"
                    found_header = True
                    break
            if found_header: break

        # 3. Заполняем табельные номера
        if day in json_data:
            daily_schedule = json_data[day]

            # Итерация по расписанию этого дня
            for (route, tram), shifts in daily_schedule.items():
                # Ищем строку в нашей карте (она построена по шаблону, индексы совпадают)
                # ВНИМАНИЕ: карта coord_map построена по source_ws, индексы строк совпадут с target_ws
                row_idx = coord_map.get((route, tram))

                if row_idx:
                    # Колонка C (индекс 3) - Утро
                    if 'утро' in shifts:
                        target_ws.cell(row=row_idx, column=3, value=shifts['утро'])

                    # Колонка H (индекс 8) - Вечер
                    # В исходном файле: 1 смена (С), 2 смена (H) - судя по структуре "Наряд"
                    # Проверим по вашему тексту:
                    # | 1 | 5085 | 5 | ... | 6 | ...
                    # 5 стоит в 3-й колонке, 6 стоит в 8-й колонке (если считать пустые)
                    # В предоставленном CSV-подобном тексте это колонки C и H
                    if 'вечер' in shifts:
                        target_ws.cell(row=row_idx, column=8, value=shifts['вечер'])
                else:
                    # Если в шаблоне нет такого трамвая/маршрута
                    pass

    print(f"💾 Сохранение файла: {output_path}")
    final_wb.save(output_path)
    print("✅ Готово!")


# -----------------------------------------------------------------------
# ГЛАВНЫЙ ЗАПУСК
# -----------------------------------------------------------------------

if __name__ == "__main__":
    try:
        # 1. Загружаем данные
        schedule_data = load_json_data(JSON_DATA)

        # 2. Строим карту координат по шаблону
        temp_wb = openpyxl.load_workbook(TEMPLATE_EXCEL)
        coord_map = create_route_tram_map(temp_wb.active)
        temp_wb.close()

        # 3. Генерируем отчет
        fill_naryad_report(schedule_data, coord_map, TEMPLATE_EXCEL, OUTPUT_FILE)

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()