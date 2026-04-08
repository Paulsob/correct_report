import json
import random
import os
from collections import defaultdict

INPUT_FILE = "../input_data/tabel.json"
OUTPUT_FILE = "../input_data/prepared_tabel.json"

ALL_ROUTES = ["9", "20", "21", "47", "48", "55", "61"]


def get_competence_distribution(total_drivers):
    c_10 = round(total_drivers * 0.10)
    c_25 = round(total_drivers * 0.25)
    c_50 = round(total_drivers * 0.50)
    c_15 = total_drivers - (c_10 + c_25 + c_50)

    distribution = []
    distribution.extend(['10'] * c_10)
    distribution.extend(['25'] * c_25)
    distribution.extend(['50'] * c_50)
    distribution.extend(['15'] * c_15)

    random.shuffle(distribution)
    return distribution


def assign_competencies(driver, category):
    driver['allowed_trams'] = ["ALL"]

    if category == '10':
        driver['allowed_routes'] = random.sample(ALL_ROUTES, 1)
    elif category == '25':
        driver['allowed_routes'] = list(ALL_ROUTES)
    elif category == '50':
        driver['allowed_routes'] = random.sample(ALL_ROUTES, 3)
    elif category == '15':
        driver['allowed_routes'] = random.sample(ALL_ROUTES, len(ALL_ROUTES) - 1)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_FILE)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    drivers_by_schedule = defaultdict(list)
    for driver in data.get('drivers', []):
        schedule = driver.get('schedule_type')
        if schedule:
            drivers_by_schedule[schedule].append(driver)

    stats = defaultdict(lambda: defaultdict(int))
    category_stats = {'10': 0, '25': 0, '50': 0, '15': 0}

    for schedule_type, drivers in drivers_by_schedule.items():
        total_drivers = len(drivers)
        if total_drivers == 0:
            continue

        categories = get_competence_distribution(total_drivers)

        for cat in categories:
            category_stats[cat] += 1

        for i, driver in enumerate(drivers):
            assign_competencies(driver, categories[i])

            for route in driver['allowed_routes']:
                stats[schedule_type][route] += 1

    print("Распределение компетенций (всего водителей):")
    print(f"{category_stats['10']} водителей допущены до 1 маршрута и 1 типа ПС (10%)")
    print(f"{category_stats['25']} водителей допущены до всех маршрутов и ПС парка (25%)")
    print(f"{category_stats['50']} водителей допущены до 3 маршрутов и 3 типов ПС (50%)")
    print(f"{category_stats['15']} водителей не имеют допуска до 1 маршрута и 1 типа ПС (15%)")
    print("\n")

    for schedule_type, route_stats in stats.items():
        print(f"для {schedule_type}:")
        for route in ALL_ROUTES:
            count = route_stats.get(route, 0)
            print(f"{count} водителей знают {route} маршрут")
        print()

    output_path = os.path.join(script_dir, OUTPUT_FILE)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()