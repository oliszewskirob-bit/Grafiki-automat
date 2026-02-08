"""CP-SAT solver orchestration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from ortools.sat.python import cp_model

from scheduler.constraints_hard import (
    add_max_consecutive_days,
    add_min_coverage,
    add_one_shift_per_day,
    add_rest_constraints,
    build_decision_vars,
    eligible_for_shift,
)
from scheduler.constraints_soft import add_soft_constraints
from scheduler.domain import Demand, Employee, Settings, ShiftType


@dataclass(frozen=True)
class Assignment:
    date: date
    shift_code: str
    employee_id: str
    name: str


@dataclass(frozen=True)
class SolveResult:
    feasible: bool
    assignments: list[Assignment]
    report: str | None = None


def _collect_days(demands: Iterable[Demand]) -> list[date]:
    return sorted({demand.date for demand in demands})


def _candidate_counts(
    demands: list[Demand],
    employees: list[Employee],
    shifts: dict[str, ShiftType],
) -> dict[tuple[date, str], int]:
    counts: dict[tuple[date, str], int] = {}
    for demand in demands:
        shift = shifts[demand.shift_code]
        count = sum(1 for employee in employees if eligible_for_shift(employee, shift))
        counts[(demand.date, demand.shift_code)] = count
    return counts


def solve_schedule(
    employees: list[Employee],
    demands: list[Demand],
    shifts: dict[str, ShiftType],
    settings: Settings | None = None,
) -> SolveResult:
    if not demands:
        return SolveResult(feasible=True, assignments=[], report=None)

    days = _collect_days(demands)
    model = cp_model.CpModel()
    variables = build_decision_vars(model, employees, days, shifts)

    add_min_coverage(model, demands, days, employees, shifts, variables)
    add_one_shift_per_day(model, employees, days, shifts, variables)
    add_rest_constraints(model, employees, days, shifts, variables)
    add_max_consecutive_days(model, employees, days, shifts, variables)
    add_soft_constraints(model, employees, days, shifts, variables, settings=settings)

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        candidate_counts = _candidate_counts(demands, employees, shifts)
        shortage = defaultdict(list)
        for demand in demands:
            available = candidate_counts[(demand.date, demand.shift_code)]
            if available < demand.min_staff:
                shortage[demand.date].append(
                    f"{demand.shift_code}: {available}/{demand.min_staff}"
                )
        if shortage:
            lines = ["Brak kandydatow dla demandow:"]
            for day in sorted(shortage):
                lines.append(f"- {day}: {', '.join(shortage[day])}")
            report = "\n".join(lines)
        else:
            report = "Model infeasible: brak szczegolowych wskazowek."
        return SolveResult(feasible=False, assignments=[], report=report)

    assignments: list[Assignment] = []
    day_index = {day: idx for idx, day in enumerate(days)}
    for demand in demands:
        d_idx = day_index[demand.date]
        for e_idx, employee in enumerate(employees):
            key = (e_idx, d_idx, demand.shift_code)
            var = variables.get(key)
            if var is None:
                continue
            if solver.value(var) == 1:
                assignments.append(
                    Assignment(
                        date=demand.date,
                        shift_code=demand.shift_code,
                        employee_id=employee.id,
                        name=employee.name,
                    )
                )
    return SolveResult(feasible=True, assignments=assignments, report=None)
