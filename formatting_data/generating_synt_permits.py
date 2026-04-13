import os
import json

# -------------------------------
# Пути
# -------------------------------
BASE_DIR = r"C:\Users\psobo\PycharmProjects\correct_report"

INPUT_FILE = os.path.join(BASE_DIR, "input_data", "prepared_data", "permits_real.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "input_data", "prepared_data", "permits_synthetic.json")

# -------------------------------
# Загрузка исходных данных
# -------------------------------
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

# Берём ТОЛЬКО комбинации моделей (как есть)
model_combinations = [item["models"] for item in data]

if not model_combinations:
    raise ValueError("Нет данных моделей во входном файле")

# -------------------------------
# Генерация табельных номеров
# -------------------------------
tab_numbers = []

# 1–768
tab_numbers.extend(range(1, 769))

# 3000–3699
tab_numbers.extend(range(3000, 3700))

# -------------------------------
# Формирование результата
# -------------------------------
result = []

total_combinations = len(model_combinations)

for i, tab_number in enumerate(tab_numbers):
    models = model_combinations[i % total_combinations]

    result.append({
        "tab_number": str(tab_number),  # обязательно строка
        "models": models
    })

# -------------------------------
# Сортировка (ВАЖНО: как числа)
# -------------------------------
result.sort(key=lambda x: int(x["tab_number"]))

# -------------------------------
# Сохранение
# -------------------------------
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"Готово! Файл сохранён: {OUTPUT_FILE}")