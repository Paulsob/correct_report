import json
from pathlib import Path


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def merge_schedules(weekday_data, weekend_data):
    # создаём словарь: маршрут -> данные
    weekday_dict = {r["маршрут"]: r for r in weekday_data}
    weekend_dict = {r["маршрут"]: r for r in weekend_data}

    all_routes = sorted(set(weekday_dict) | set(weekend_dict))

    result = []

    for route in all_routes:
        # сначала рабочий
        if route in weekday_dict:
            result.append(weekday_dict[route])

        # потом выходной
        if route in weekend_dict:
            result.append(weekend_dict[route])

    return result


def main():
    base_dir = Path(__file__).resolve().parent.parent / "input_data"

    weekday_file = base_dir / "raw_data" / "new_raw_schedule.json"
    weekend_file = base_dir / "raw_data" / "new_raw_schedule_weekend.json"

    output_file = base_dir / "raw_data" / "new_raw_schedule.json"

    weekday_data = load_json(weekday_file)
    weekend_data = load_json(weekend_file)

    merged = merge_schedules(weekday_data, weekend_data)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Готово: {output_file}")


if __name__ == "__main__":
    main()