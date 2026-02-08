"""Hard constraint builders for CP-SAT model."""

from __future__ import annotations

from datetime import datetime, timedelta

from ortools.sat.python import cp_model

from scheduler.domain import Demand, Employee, ShiftType


def eligible_for_shift(employee: Employee, shift: ShiftType) -> bool:
    if employee.grupa != shift.grupa:
        return False
    if shift.is_24h and not employee.moze_24h:
        return False
    if shift.modalnosc == "MR" and "MR" not in employee.skills:
        return False
    if shift.modalnosc == "TK" and "TK" not in employee.skills:
        return False
    if shift.modalnosc == "ZDO" and "ZDO" not in employee.skills:
        return False
    if shift.modalnosc == "ALL" and employee.grupa != "ELEKTRORADIOLOG":
        return False
    return True


def build_decision_vars(
    model: cp_model.CpModel,
    employees: list[Employee],
    days: list,  # list[date]
    shifts: dict[str, ShiftType],
) -> dict[tuple[int, int, str], cp_model.IntVar]:
    variables: dict[tuple[int, int, str], cp_model.IntVar] = {}
    for e_idx, employee in enumerate(employees):
        for d_idx, _day in enumerate(days):
            for shift_code, shift in shifts.items():
                if not eligible_for_shift(employee, shift):
                    continue
                name = f"x_e{e_idx}_d{d_idx}_s{shift_code}"
                variables[(e_idx, d_idx, shift_code)] = model.new_bool_var(name)
    return variables


def add_min_coverage(
    model: cp_model.CpModel,
    demands: list[Demand],
    days: list,  # list[date]
    employees: list[Employee],
    shifts: dict[str, ShiftType],
    variables: dict[tuple[int, int, str], cp_model.IntVar],
) -> None:
    day_index = {day: idx for idx, day in enumerate(days)}
    for demand in demands:
        d_idx = day_index[demand.date]
        shift = shifts[demand.shift_code]
        eligible_vars = [
            variables[(e_idx, d_idx, demand.shift_code)]
            for e_idx, employee in enumerate(employees)
            if eligible_for_shift(employee, shift)
            and (e_idx, d_idx, demand.shift_code) in variables
        ]
        if eligible_vars:
            model.add(sum(eligible_vars) >= demand.min_staff)
        else:
            model.add(0 >= demand.min_staff)


def add_one_shift_per_day(
    model: cp_model.CpModel,
    employees: list[Employee],
    days: list,  # list[date]
    shifts: dict[str, ShiftType],
    variables: dict[tuple[int, int, str], cp_model.IntVar],
) -> None:
    shift_codes = list(shifts.keys())
    for e_idx, _employee in enumerate(employees):
        for d_idx, _day in enumerate(days):
            day_vars = [
                variables[key]
                for shift_code in shift_codes
                if (key := (e_idx, d_idx, shift_code)) in variables
            ]
            if day_vars:
                model.add(sum(day_vars) <= 1)


def _shift_end_datetime(day, shift: ShiftType) -> datetime:
    start_dt = datetime.combine(day, shift.start_time)
    end_dt = datetime.combine(day, shift.end_time)
    if shift.end_time <= shift.start_time:
        end_dt += timedelta(days=1)
    if shift.is_24h and shift.end_time == shift.start_time:
        end_dt = start_dt + timedelta(days=24)
    return end_dt


def add_rest_constraints(
    model: cp_model.CpModel,
    employees: list[Employee],
    days: list,  # list[date]
    shifts: dict[str, ShiftType],
    variables: dict[tuple[int, int, str], cp_model.IntVar],
    min_rest_hours: int = 11,
) -> None:
    shift_codes = list(shifts.keys())
    for e_idx, _employee in enumerate(employees):
        for d_idx, day in enumerate(days[:-1]):
            next_day = days[d_idx + 1]
            for shift_code_a in shift_codes:
                shift_a = shifts[shift_code_a]
                key_a = (e_idx, d_idx, shift_code_a)
                if key_a not in variables:
                    continue
                end_a = _shift_end_datetime(day, shift_a)
                for shift_code_b in shift_codes:
                    shift_b = shifts[shift_code_b]
                    key_b = (e_idx, d_idx + 1, shift_code_b)
                    if key_b not in variables:
                        continue
                    start_b = datetime.combine(next_day, shift_b.start_time)
                    rest_hours = (start_b - end_a).total_seconds() / 3600.0
                    if rest_hours < min_rest_hours:
                        model.add(variables[key_a] + variables[key_b] <= 1)


def add_max_consecutive_days(
    model: cp_model.CpModel,
    employees: list[Employee],
    days: list,  # list[date]
    shifts: dict[str, ShiftType],
    variables: dict[tuple[int, int, str], cp_model.IntVar],
    max_days: int = 6,
) -> None:
    shift_codes = list(shifts.keys())
    window_size = max_days + 1
    if len(days) < window_size:
        return
    for e_idx, _employee in enumerate(employees):
        for start in range(0, len(days) - window_size + 1):
            work_vars = []
            for d_idx in range(start, start + window_size):
                day_vars = [
                    variables[key]
                    for shift_code in shift_codes
                    if (key := (e_idx, d_idx, shift_code)) in variables
                ]
                if day_vars:
                    work_vars.extend(day_vars)
            if work_vars:
                model.add(sum(work_vars) <= max_days)
