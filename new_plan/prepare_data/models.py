from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import time, datetime


# Данные расписания
class ShiftTime(BaseModel):
    departure: time = Field(alias="отправление")
    arrival: time = Field(alias="прибытие")


class Tram(BaseModel):
    number: str = Field(alias="номер")
    shift_1: Optional[ShiftTime] = Field(None, alias="смена_1")
    shift_2: Optional[ShiftTime] = Field(None, alias="смена_2")


class RouteSchedule(BaseModel):
    route: int = Field(alias="маршрут")
    day_type: str = Field(alias="день")
    trams: List[Tram] = Field(alias="трамваи")


# Данные водителей
class DayRecord(BaseModel):
    day: int = Field(..., ge=1, le=31, description="День месяца")
    value: str = Field(..., description="Номер смены или выходной")


class Driver(BaseModel):
    tab_number: int = Field(..., gt=0, description="Табельный номер: 001")
    schedule: str = Field(..., description="Тип графика: 4х2")
    mode: str = Field(..., description="Режим работы: 1х2")
    days: List[DayRecord]


class ScheduleData(BaseModel):
    month: str
    year: int = Field(..., ge=2000, le=2100)
    drivers: List[Driver]


# Данные для отчета
class AssignedShift(BaseModel):
    date: str
    route: int
    tram_number: str
    shift_num: int

    start_time: datetime
    end_time: datetime
    duration_hours: float

    assigned_driver_tab: Optional[int] = None
    rest_before_shift_hours: Optional[float] = None
    available_from_next: Optional[datetime] = None


class DriverSummary(BaseModel):
    tab_number: int
    total_hours_worked: float = 0.0
    total_shifts_worked: int = 0
    daily_status: Dict[int, str] = {}


class SimulationResult(BaseModel):
    month: str
    year: int
    shifts_log: List[AssignedShift]
    drivers_log: List[DriverSummary]
    uncovered_shifts_count: int
