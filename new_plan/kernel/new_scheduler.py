from datetime import datetime, timedelta, time
from typing import List, Optional, Tuple
from prepare_data.models import ScheduleData, RouteSchedule, AssignedShift, DriverSummary, SimulationResult, Driver


class DriverState:
    def __init__(self, driver: Driver, year: int, month_num: int):
        self.driver = driver
        self.available_from: datetime = datetime(year, month_num, 1, 0, 0)
        self.last_shift_end: Optional[datetime] = None

        self.last_shift_num: Optional[int] = None

        self.hours_worked: float = 0.0
        self.shifts_worked: int = 0
        self.daily_status: dict[int, str] = {}

    def can_take_shift(self, shift_start: datetime, day_value: str, shift_num: int) -> bool:
        if day_value in ["В"]:
            return False

        if str(day_value) != str(shift_num):
            return False

        if shift_start < self.available_from:
            return False

        return True

    def assign(self, shift_start: datetime, shift_end: datetime, day: int, shift_num: int) -> Tuple[
        float, Optional[float]]:
        duration = (shift_end - shift_start).total_seconds() / 3600

        rest_before = None
        rest_str = "-"
        if self.last_shift_end:
            rest_before = (shift_start - self.last_shift_end).total_seconds() / 3600
            rest_str = f"{rest_before:.1f}ч"

        self.hours_worked += duration
        self.shifts_worked += 1
        self.last_shift_end = shift_end
        self.available_from = shift_end + timedelta(hours=12)

        self.last_shift_num = shift_num

        time_str = f"{shift_start.strftime('%H:%M')}-{shift_end.strftime('%H:%M')}"
        self.daily_status[day] = f"({time_str})\nРаб: {duration:.1f}ч\nОтд: {rest_str}"

        return duration, rest_before


class SchedulerEngine:
    def __init__(self, data: ScheduleData, transport: List[RouteSchedule]):
        self.year = data.year
        self.month_name = data.month

        months = {"Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
                  "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12}
        self.month_num = months.get(self.month_name, 10)

        self.transport = transport

        self.states = [DriverState(d, self.year, self.month_num) for d in data.drivers]

    def _make_datetime(self, day: int, dep: time, arr: time) -> Tuple[datetime, datetime]:
        start = datetime(self.year, self.month_num, day, dep.hour, dep.minute)
        end = datetime(self.year, self.month_num, day, arr.hour, arr.minute)

        if end < start:
            end += timedelta(days=1)
        return start, end

    def _get_daily_shifts(self, day: int, day_type: str) -> List[dict]:
        shifts = []
        for route in self.transport:
            if route.day_type != day_type:
                continue

            for tram in route.trams:
                if tram.shift_1:
                    start, end = self._make_datetime(day, tram.shift_1.departure, tram.shift_1.arrival)
                    shifts.append({"route": route.route, "tram": tram.number, "num": 1, "start": start, "end": end})
                if tram.shift_2:
                    start, end = self._make_datetime(day, tram.shift_2.departure, tram.shift_2.arrival)
                    shifts.append({"route": route.route, "tram": tram.number, "num": 2, "start": start, "end": end})

        shifts.sort(key=lambda x: x["start"])
        return shifts




def run_simulation(drivers_data: ScheduleData, transport_data: List[RouteSchedule]) -> SimulationResult:
    engine = SchedulerEngine(drivers_data, transport_data)
    return engine.run()
