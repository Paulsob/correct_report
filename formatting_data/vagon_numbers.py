import pandas as pd
import json
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# КОНФИГУРАЦИЯ ПУТЕЙ
# ─────────────────────────────────────────────────────────────
BASE_DIR = Path(r"C:\Users\psobo\PycharmProjects\correct_report")
INPUT_FILE = BASE_DIR / "input_data" / "vagons.xlsx"
OUTPUT_DIR = BASE_DIR / "input_data" / "prepared_data"
OUTPUT_FILE = OUTPUT_DIR / "vagon_numbers.json"


def process_vagons():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"❌ Входной файл не найден: {INPUT_FILE}")

    # Читаем Excel:
    # header=1 → пропускаем первую строку (общий заголовок), берём вторую как шапку
    # usecols="A,B,C,F" → загружаем только нужные столбцы, игнорируя остальные
    df = pd.read_excel(INPUT_FILE, header=1, usecols="A,B,C,F")

    # Даём колонкам понятные имена в порядке A, B, C, F
    df.columns = ['park', 'garage', 'model', 'type']

    # Убираем строки, где отсутствуют обязательные поля (Тип, Модель, Номер)
    df = df.dropna(subset=['type', 'model', 'garage'])

    result = {}

    for _, row in df.iterrows():
        v_type = str(row['type']).strip()
        model = str(row['model']).strip()
        garage = str(row['garage']).strip()

        # Принадлежность к парку может быть пустой, обрабатываем корректно
        park_val = row['park']
        park = str(park_val).strip() if pd.notna(park_val) else ""

        # Пропускаем строки, если после очистки ключевые поля пусты
        if not (v_type and model and garage):
            continue

        # Формируем вложенную структуру: Тип -> Модель -> {}
        result.setdefault(v_type, {}).setdefault(model, {})

        # 🔍 ПРОВЕРКА НА ДУБЛИКАТЫ (по вашему требованию)
        if garage in result[v_type][model]:
            raise ValueError(
                f"⛔ КРИТИЧЕСКАЯ ОШИБКА: Дубликат гаражного номера '{garage}' "
                f"найден для типа '{v_type}' и модели '{model}'. "
                f"Номера должны быть уникальными!"
            )

        # Записываем принадлежность к парку
        result[v_type][model][garage] = park

    # Сохранение JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ Успешно обработано строк: {len(df)}")
    print(f"💾 Результат сохранён: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        process_vagons()
    except Exception as e:
        print(f"❌ Скрипт завершил работу с ошибкой: {e}")
        raise