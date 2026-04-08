import json
import os
import copy

# --- ПУТЬ К ТВОЕМУ СЫРОМУ ФАЙЛУ 3х2х3х1 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
# Укажи точный путь до сырого файла, который нужно вылечить
RAW_FILE = os.path.join(PROJECT_DIR, "input_data", "raw_data", "2026", "10", "3x2x3x1_10_drivers_october.json")


def fix_data():
    print(f"Читаем сырой файл: {RAW_FILE}")
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    original_drivers = data.get("drivers", [])

    if len(original_drivers) < 9:
        print("❌ Ошибка: В файле меньше 9 водителей!")
        return

    print("1. Берем первых 9 уникальных водителей...")
    base_9_drivers = original_drivers[:9]

    perfect_block_of_18 = []

    # Добавляем оригинальную девятку в идеальный блок
    for d in base_9_drivers:
        perfect_block_of_18.append(copy.deepcopy(d))

    print("2. Создаем 9 напарников (инвертируем смены 1 <-> 2)...")
    for d in base_9_drivers:
        inverse_driver = copy.deepcopy(d)

        # Инвертируем смены в списке дней
        for day_dict in inverse_driver["days"]:
            if str(day_dict["value"]) == "1":
                day_dict["value"] = "2"
            elif str(day_dict["value"]) == "2":
                day_dict["value"] = "1"
            # "В" остается "В"

        perfect_block_of_18.append(inverse_driver)

    print("3. Размножаем идеальный блок из 18 человек на 40 копий (720 водителей)...")
    final_720_drivers = []
    tab_counter = 1  # Задаем новые уникальные табельные номера

    for _ in range(40):
        for d in perfect_block_of_18:
            new_driver = copy.deepcopy(d)
            new_driver["tab_number"] = tab_counter
            tab_counter += 1
            final_720_drivers.append(new_driver)

    # Сохраняем вылеченные данные обратно
    data["drivers"] = final_720_drivers

    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"🎉 Готово! Файл перезаписан. Теперь там {len(final_720_drivers)} математически идеальных водителей.")


if __name__ == "__main__":
    fix_data()