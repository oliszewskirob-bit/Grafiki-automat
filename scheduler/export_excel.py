"""Excel export helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl.utils import get_column_letter

from scheduler import calendar_pl
from scheduler.domain import Employee, ShiftType
from scheduler.report import summarize_employees
from scheduler.solver import Assignment, SolveResult


def _auto_fit_columns(worksheet) -> None:
    for column_cells in worksheet.columns:
        values = [str(cell.value) if cell.value is not None else "" for cell in column_cells]
        max_length = max((len(value) for value in values), default=0)
        column_letter = get_column_letter(column_cells[0].column)
        worksheet.column_dimensions[column_letter].width = min(max_length + 2, 60)


def _apply_sheet_formatting(worksheet) -> None:
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    _auto_fit_columns(worksheet)


def export_schedule_excel(
    path: str | Path,
    month: str,
    employees: list[Employee],
    shifts: dict[str, ShiftType],
    assignments: list[Assignment],
    solve_result: SolveResult,
) -> None:
    output_path = Path(path)
    days = calendar_pl.month_days(month)
    shift_codes = list(shifts.keys())

    assignments_by_day_shift: dict[tuple[date, str], list[str]] = defaultdict(list)
    for assignment in assignments:
        assignments_by_day_shift[(assignment.date, assignment.shift_code)].append(
            assignment.name
        )

    grafik_rows: list[dict[str, object]] = []
    for day in days:
        row: dict[str, object] = {"data": day}
        for shift_code in shift_codes:
            names = assignments_by_day_shift.get((day, shift_code), [])
            row[shift_code] = ", ".join(sorted(names))
        grafik_rows.append(row)

    grafik_df = pd.DataFrame(grafik_rows)

    summary_df = pd.DataFrame(
        summarize_employees(employees, assignments, shifts, days)
    )

    if solve_result.feasible:
        violations_df = pd.DataFrame(
            [{"naruszenie": solve_result.report or "OK"}]
        )
    else:
        violations_df = pd.DataFrame(
            [{"naruszenie": solve_result.report or "Brak rozwiazania"}]
        )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        grafik_df.to_excel(writer, sheet_name="grafik", index=False)
        summary_df.to_excel(writer, sheet_name="podsumowanie", index=False)
        violations_df.to_excel(writer, sheet_name="naruszenia", index=False)

        for sheet_name in ("grafik", "podsumowanie", "naruszenia"):
            worksheet = writer.sheets[sheet_name]
            _apply_sheet_formatting(worksheet)
