"""Reporting helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from scheduler import calendar_pl
from scheduler.domain import Employee, Settings, ShiftType
from scheduler.solver import Assignment


def summarize_employees(
    employees: list[Employee],
    assignments: list[Assignment],
    shifts: dict[str, ShiftType],
    month_days: list[date],
    settings: Settings | None = None,
) -> list[dict[str, object]]:
    if settings is None:
        settings = Settings()

    workdays = sum(
        1
        for day in month_days
        if not calendar_pl.is_weekend(day) and not calendar_pl.is_holiday(day)
    )

    shift_by_code = shifts
    assignments_by_employee: dict[str, list[Assignment]] = defaultdict(list)
    for assignment in assignments:
        assignments_by_employee[assignment.employee_id].append(assignment)

    summaries: list[dict[str, object]] = []
    for employee in employees:
        total_hours = 0.0
        night_count = 0
        weekend_count = 0
        shift_24h_count = 0
        for assignment in assignments_by_employee.get(employee.id, []):
            shift = shift_by_code[assignment.shift_code]
            total_hours += shift.duration_h
            if shift.is_24h:
                shift_24h_count += 1
            if shift.end_time <= shift.start_time and not shift.is_24h:
                night_count += 1
            if calendar_pl.is_weekend(assignment.date) or calendar_pl.is_holiday(
                assignment.date
            ):
                weekend_count += 1

        if employee.typ_umowy == "UOP" and employee.auto_target and employee.etat:
            target_hours = employee.etat * workdays * 7.5833
        else:
            target_hours = employee.cel_godz_miesiac

        summaries.append(
            {
                "employee_id": employee.id,
                "name": employee.name,
                "grupa": employee.grupa,
                "typ_umowy": employee.typ_umowy,
                "total_hours": round(total_hours, 2),
                "night_count": night_count,
                "weekend_count": weekend_count,
                "shift_24h_count": shift_24h_count,
                "target_hours": target_hours,
                "min_hours": employee.min_godz_miesiac,
                "max_hours": employee.max_godz_miesiac,
            }
        )

    return summaries
