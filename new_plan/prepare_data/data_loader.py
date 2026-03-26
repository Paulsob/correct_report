import json
from pathlib import Path
from typing import List
from .models import ScheduleData, RouteSchedule

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def load_schedule_data(filename: str = "10_drivers_october.json") -> ScheduleData:
    filepath = DATA_DIR / filename

    if not filepath.exists():
        raise FileNotFoundError(f"Файл {filepath} не найден")

    with open(filepath, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    try:
        validated_data = ScheduleData.model_validate(raw_data)
        print(f"Данные загружены: {validated_data.month} {validated_data.year}, "
              f"водителей: {len(validated_data.drivers)}")
        return validated_data

    except Exception as e:
        print(f"Ошибка валидации JSON:\n{e}")
        raise


def load_transport_schedule(filename: str = "schedule.json") -> List[RouteSchedule]:
    filepath = DATA_DIR / filename

    if not filepath.exists():
        raise FileNotFoundError(f"Файл не найден: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    try:
        validated_data = [RouteSchedule.model_validate(item) for item in raw_data]
        print(f"Расписание транспорта загружено: {len(validated_data)} маршрут(ов/дней)")
        return validated_data

    except Exception as e:
        print(f"Ошибка валидации расписания транспорта:\n{e}")
        raise
