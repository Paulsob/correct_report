# new_run_simulation.py
"""
Запуск симуляции: читает drivers и route_template из папки data, запускает build_schedule,
печатает в консоль и сохраняет json результат в outputs/.
"""

import json
from pathlib import Path
from new_scheduler import build_schedule, pretty_print_schedule
from new_scheduler import get_candidates_for_first_shift_day1
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUTPUT = BASE / "outputs"
OUTPUT.mkdir(exist_ok=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path: Path):
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main():
    drivers_file = Path("10_drivers_october.json")
    route_file = Path("schedule.json")

    drivers_data = load_json(drivers_file)
    drivers = drivers_data["drivers"]
    route_template = load_json(route_file)[0]

    schedule = build_schedule(drivers, route_template)

    print(type(drivers))
    print(drivers[0])

    candidates = get_candidates_for_first_shift_day1(drivers)

    print("Кандидаты на утреннюю смену 1 дня:")
    for c in candidates:
        print(c)

    schedule = build_schedule(drivers, route_template)

    # печать в консоль (для первичной проверки)
    pretty_print_schedule(schedule)

    # сохранить результат
    out_path = OUTPUT / f"schedule_{route_template.get('route', 'r')}_{route_template.get('month', 'm')}.json"
    save_json(schedule, out_path)
    print(f"\nSaved schedule -> {out_path}")


if __name__ == "__main__":
    main()
