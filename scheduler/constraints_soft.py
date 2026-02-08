"""Soft constraints and objective for CP-SAT model."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from ortools.sat.python import cp_model

from scheduler import calendar_pl
from scheduler.domain import Employee, Settings, ShiftType

MINUTES_PER_HOUR = 60
WEEKLY_LIMIT_MINUTES = 48 * MINUTES_PER_HOUR
UOP_DAILY_HOURS = 7.5833


def _minutes_from_hours(hours: float | None) -> int | None:
    if hours is None:
        return None
    return int(round(hours * MINUTES_PER_HOUR))


def _shift_minutes(shift: ShiftType) -> int:
    return int(round(shift.duration_h * MINUTES_PER_HOUR))


def _count_workdays(days: list[date]) -> int:
    return sum(
        1
        for day in days
        if not calendar_pl.is_weekend(day) and not calendar_pl.is_holiday(day)
    )


def _get_weight(settings: Settings, key: str, default: float) -> int:
    return int(round(settings.wagi_miekkie.get(key, default)))


def _employee_target_minutes(employee: Employee, workdays: int) -> int | None:
    if employee.typ_umowy == "UOP" and employee.auto_target:
        if employee.etat is None:
            return None
        hours = employee.etat * workdays * UOP_DAILY_HOURS
        return _minutes_from_hours(hours)
    return _minutes_from_hours(employee.cel_godz_miesiac)


def _employee_min_max_minutes(employee: Employee) -> tuple[int | None, int | None]:
    return (
        _minutes_from_hours(employee.min_godz_miesiac),
        _minutes_from_hours(employee.max_godz_miesiac),
    )


def add_soft_constraints(
    model: cp_model.CpModel,
    employees: list[Employee],
    days: list[date],
    shifts: dict[str, ShiftType],
    variables: dict[tuple[int, int, str], cp_model.IntVar],
    settings: Settings | None = None,
) -> None:
    if settings is None:
        settings = Settings()

    shift_minutes = {code: _shift_minutes(shift) for code, shift in shifts.items()}
    max_shift_minutes = max(shift_minutes.values(), default=0)
    total_days = len(days)
    total_max_minutes = total_days * max_shift_minutes
    workdays = _count_workdays(days)

    penalty_terms: list[cp_model.LinearExpr] = []

    weight_max = _get_weight(settings, "max_hours", 1000.0)
    weight_min = _get_weight(settings, "min_hours", 500.0)
    weight_target = _get_weight(settings, "target_hours", 100.0)
    weight_weekly = _get_weight(settings, "weekly_48h", 500.0)
    weight_balance = _get_weight(settings, "balance", 50.0)

    shift_codes = list(shifts.keys())
    day_index = {day: idx for idx, day in enumerate(days)}

    total_group_counts: dict[tuple[str, str], cp_model.IntVar] = {}
    employee_metric_counts: dict[tuple[int, str], cp_model.IntVar] = {}

    for e_idx, employee in enumerate(employees):
        total_minutes = model.new_int_var(0, total_max_minutes, f"minutes_e{e_idx}")
        minute_terms = []
        for d_idx, _day in enumerate(days):
            for shift_code in shift_codes:
                key = (e_idx, d_idx, shift_code)
                var = variables.get(key)
                if var is None:
                    continue
                minute_terms.append(var * shift_minutes[shift_code])
        if minute_terms:
            model.add(total_minutes == sum(minute_terms))
        else:
            model.add(total_minutes == 0)

        min_minutes, max_minutes = _employee_min_max_minutes(employee)
        target_minutes = _employee_target_minutes(employee, workdays)

        if max_minutes is not None:
            diff = model.new_int_var(-total_max_minutes, total_max_minutes, f"excess_diff_e{e_idx}")
            model.add(diff == total_minutes - max_minutes)
            excess = model.new_int_var(0, total_max_minutes, f"excess_e{e_idx}")
            model.add_max_equality(excess, [diff, 0])
            penalty_terms.append(weight_max * excess)

        if min_minutes is not None:
            diff = model.new_int_var(-total_max_minutes, total_max_minutes, f"short_diff_e{e_idx}")
            model.add(diff == min_minutes - total_minutes)
            shortage = model.new_int_var(0, total_max_minutes, f"short_e{e_idx}")
            model.add_max_equality(shortage, [diff, 0])
            penalty_terms.append(weight_min * shortage)

        if target_minutes is not None:
            deviation = model.new_int_var(0, total_max_minutes, f"dev_target_e{e_idx}")
            model.add_abs_equality(deviation, total_minutes - target_minutes)
            penalty_terms.append(weight_target * deviation)

        if employee.typ_umowy in {"B2B", "ZLECENIE"}:
            _add_weekly_limit_penalties(
                model,
                e_idx,
                days,
                shift_codes,
                shift_minutes,
                variables,
                weight_weekly,
                penalty_terms,
            )

        _add_balance_counts(
            model,
            employee,
            e_idx,
            days,
            shift_codes,
            shifts,
            variables,
            employee_metric_counts,
        )

    _add_balance_penalties(
        model,
        employees,
        employee_metric_counts,
        weight_balance,
        penalty_terms,
        total_group_counts,
        len(days),
    )

    if penalty_terms:
        model.minimize(sum(penalty_terms))


def _add_weekly_limit_penalties(
    model: cp_model.CpModel,
    e_idx: int,
    days: list[date],
    shift_codes: list[str],
    shift_minutes: dict[str, int],
    variables: dict[tuple[int, int, str], cp_model.IntVar],
    weight: int,
    penalty_terms: list[cp_model.LinearExpr],
) -> None:
    weeks: dict[tuple[int, int], list[int]] = defaultdict(list)
    for d_idx, day in enumerate(days):
        weeks[(day.isocalendar().year, day.isocalendar().week)].append(d_idx)

    max_week_minutes = len(days) * max(shift_minutes.values(), default=0)

    for _, indices in weeks.items():
        week_minutes_terms = []
        for d_idx in indices:
            for shift_code in shift_codes:
                key = (e_idx, d_idx, shift_code)
                var = variables.get(key)
                if var is None:
                    continue
                week_minutes_terms.append(var * shift_minutes[shift_code])
        if not week_minutes_terms:
            continue
        week_minutes = model.new_int_var(0, max_week_minutes, f"week_minutes_e{e_idx}_{indices[0]}")
        model.add(week_minutes == sum(week_minutes_terms))
        diff = model.new_int_var(-max_week_minutes, max_week_minutes, f"week_diff_e{e_idx}_{indices[0]}")
        model.add(diff == week_minutes - WEEKLY_LIMIT_MINUTES)
        excess = model.new_int_var(0, max_week_minutes, f"week_excess_e{e_idx}_{indices[0]}")
        model.add_max_equality(excess, [diff, 0])
        penalty_terms.append(weight * excess)


def _add_balance_counts(
    model: cp_model.CpModel,
    employee: Employee,
    e_idx: int,
    days: list[date],
    shift_codes: list[str],
    shifts: dict[str, ShiftType],
    variables: dict[tuple[int, int, str], cp_model.IntVar],
    employee_metric_counts: dict[tuple[int, str], cp_model.IntVar],
) -> None:
    metrics = {
        "night": lambda shift: shift.end_time <= shift.start_time and not shift.is_24h,
        "weekend": lambda shift: False,
        "shift_24h": lambda shift: shift.is_24h,
    }

    for metric in metrics:
        max_count = len(days)
        count_var = model.new_int_var(0, max_count, f"{metric}_count_e{e_idx}")
        terms = []
        for d_idx, day in enumerate(days):
            is_weekend = calendar_pl.is_weekend(day) or calendar_pl.is_holiday(day)
            for shift_code in shift_codes:
                shift = shifts[shift_code]
                if shift.grupa != employee.grupa:
                    continue
                if metric == "weekend" and not is_weekend:
                    continue
                if metric != "weekend" and not metrics[metric](shift):
                    continue
                key = (e_idx, d_idx, shift_code)
                var = variables.get(key)
                if var is None:
                    continue
                terms.append(var)
        if terms:
            model.add(count_var == sum(terms))
        else:
            model.add(count_var == 0)
        employee_metric_counts[(e_idx, metric)] = count_var


def _add_balance_penalties(
    model: cp_model.CpModel,
    employees: list[Employee],
    employee_metric_counts: dict[tuple[int, str], cp_model.IntVar],
    weight: int,
    penalty_terms: list[cp_model.LinearExpr],
    total_group_counts: dict[tuple[str, str], cp_model.IntVar],
    days_len: int,
) -> None:
    if not employees:
        return

    group_members: dict[str, list[int]] = defaultdict(list)
    for idx, employee in enumerate(employees):
        group_members[employee.grupa].append(idx)

    for group, indices in group_members.items():
        group_size = len(indices)
        for metric in ("night", "weekend", "shift_24h"):
            total_max = len(indices) * days_len
            total_var = model.new_int_var(0, total_max, f"total_{metric}_{group}")
            terms = [employee_metric_counts[(idx, metric)] for idx in indices]
            if terms:
                model.add(total_var == sum(terms))
            else:
                model.add(total_var == 0)
            for idx in indices:
                count_var = employee_metric_counts[(idx, metric)]
                dev = model.new_int_var(0, total_max * group_size, f"dev_{metric}_{group}_{idx}")
                model.add_abs_equality(dev, count_var * group_size - total_var)
                penalty_terms.append(weight * dev)
            total_group_counts[(group, metric)] = total_var
