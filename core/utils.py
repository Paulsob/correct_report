import sys
import os
import json
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def load_reference_data():
    ref_dir = os.path.join(config.BASE_DIR, "input_data", "02_reference")

    route_models_dict = {}
    try:
        with open(os.path.join(ref_dir, "route_types.json"), "r", encoding="utf-8") as f:
            route_types_list = json.load(f)
        for item in route_types_list:
            route_num = str(item.get("маршрут"))
            models = []
            for tram_info in item.get("трамваи", []):
                models.extend(tram_info.get("модели", []))
            route_models_dict[route_num] = list(set(models))
    except FileNotFoundError:
        print("route_types.json не найден. Проверки моделей отключены.")

    permits_dict = {}
    try:
        with open(os.path.join(ref_dir, "permits_synthetic.json"), "r", encoding="utf-8") as f:
            permits_raw = json.load(f)
        if isinstance(permits_raw, list):
            for p in permits_raw:
                tab = str(p.get("tab_number"))
                if tab:
                    permits_dict[tab] = {
                        "routes": p.get("routes", []),
                        "models": p.get("models", [])
                    }
        elif isinstance(permits_raw, dict):
            permits_dict = permits_raw
    except FileNotFoundError:
        print("permits_synthetic.json не найден. Проверки допусков отключены.")

    return route_models_dict, permits_dict


def load_absences_data():
    """Загружает данные об отсутствиях из absences.json"""
    abs_path = getattr(config, "ABSENCES_FILE", os.path.join(config.OPERATIONAL_DIR, "absences.json"))
    if os.path.exists(abs_path):
        with open(abs_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def is_absent(tab_number, current_date_str, absences_data):
    """Проверяет, попадает ли текущая дата в период отсутствия водителя"""
    for record in absences_data:
        if str(record.get("tab_number")) == str(tab_number):
            if record["start_date"] <= current_date_str <= record["end_date"]:
                return True
    return False


def is_qualified(driver, route_num, required_models, permits_data):
    tab_num = str(driver.get('tab_number'))
    driver_permits = permits_data.get(tab_num, {})

    allowed_routes = driver_permits.get("routes", [])
    route_ok = (str(route_num) in allowed_routes) or ("ALL" in allowed_routes) or (not allowed_routes)

    allowed_driver_models = driver_permits.get("models", [])
    model_ok = True
    if required_models and allowed_driver_models and "ALL" not in allowed_driver_models:
        model_ok = any(m in allowed_driver_models for m in required_models)

    return route_ok and model_ok


def count_permits(tab_num, permits_data):
    """Возвращает общее количество допусков у водителя (маршруты + модели)"""
    p = permits_data.get(str(tab_num), {})
    return len(p.get("routes", [])) + len(p.get("models", []))


def calculate_dynamic_quotas(trams_data, buffer_weekend=2):
    """Считает лимиты и квоты для гибридного распределения"""
    weekday_shifts = 0
    weekend_shifts = 0
    for route in trams_data:
        day_type = route.get("день")
        if not day_type: continue
        route_shifts = sum(1 for t in route.get("трамваи", []) if t.get("смена_1") or t.get("смена_2"))
        if day_type == "рабочий":
            weekday_shifts += route_shifts
        elif day_type in ("выходной", "праздник"):
            weekend_shifts += route_shifts

    return {
        "limit_weekday": max(1, weekday_shifts),
        "limit_weekend": weekend_shifts + buffer_weekend,
        "weekday_shifts": weekday_shifts,
        "weekend_shifts": weekend_shifts,
        "recommended_secondary": max(0, weekday_shifts - (weekend_shifts + buffer_weekend))
    }


def load_matrix_data(schedule_type):
    with open(config.MATRICES_FILE, "r", encoding="utf-8") as f:
        all_matrices = json.load(f)
    if schedule_type not in all_matrices:
        raise ValueError(f"Ошибка: График '{schedule_type}' не найден!")
    matrix_data = all_matrices[schedule_type]
    active_matrix = {int(k): v for k, v in matrix_data["matrix"].items()}
    return active_matrix, matrix_data["cycle_length"]


def get_required_role(cycle_day, target_slot, active_matrix):
    day_index = cycle_day - 1
    for role, days_list in active_matrix.items():
        if days_list[day_index] == target_slot:
            return role
    return None


def get_day_type(day, year, month, custom_holidays=None):
    if custom_holidays is None:
        custom_holidays = []
    if day in custom_holidays or date(year, month, day).weekday() >= 5:
        return "выходной"
    return "рабочий"
