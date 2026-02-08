"""CLI for the schedule engine bootstrap."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from scheduler.demand import build_demands
from scheduler.export_excel import export_schedule_excel
from scheduler.io_excel import EmployeeLoadError, load_employees, load_shifts
from scheduler.solver import solve_schedule


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scheduler bootstrap CLI")
    parser.add_argument("--input", required=True, help="Path to input Excel file")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format")
    parser.add_argument("--out", required=True, help="Path to output Excel file")
    parser.add_argument(
        "--print-employees",
        action="store_true",
        help="Print normalized employees table",
    )
    parser.add_argument(
        "--print-shifts",
        action="store_true",
        help="Print normalized shifts table",
    )
    parser.add_argument(
        "--print-demands",
        action="store_true",
        help="Print demand summary (count and top 20 rows)",
    )
    return parser.parse_args(argv)


def _format_table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "(no rows)"
    headers = list(rows[0].keys())
    str_rows = [[str(row.get(header, "")) for header in headers] for row in rows]
    widths = [len(header) for header in headers]
    for row in str_rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))
    header_line = " | ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers))
    separator_line = "-+-".join("-" * width for width in widths)
    data_lines = [
        " | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))
        for row in str_rows
    ]
    return "\n".join([header_line, separator_line, *data_lines])


def _render_table(rows: list[dict[str, object]]) -> str:
    if importlib.util.find_spec("pandas"):
        import pandas as pd

        df = pd.DataFrame(rows)
        return df.to_string(index=False)
    return _format_table(rows)


def _load_employees_or_exit(input_path: Path) -> list[object]:
    try:
        return load_employees(input_path)
    except EmployeeLoadError as exc:
        print("Bledy w arkuszu 'pracownicy' (pierwsze 5):")
        for issue in exc.issues[:5]:
            print(f"- wiersz {issue['row']}, pole {issue['field']}: {issue['message']}")
        raise SystemExit(1) from exc


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    input_path = Path(args.input)
    if not input_path.is_file():
        raise SystemExit(f"ERROR: input file not found: {input_path}")
    if args.print_employees:
        employees = _load_employees_or_exit(input_path)
        rows = [employee.model_dump() for employee in employees]
        print(_render_table(rows))
    if args.print_shifts:
        shifts = load_shifts(input_path)
        rows = [shift.model_dump() for shift in shifts.values()]
        print(_render_table(rows))
    if args.print_demands:
        shifts = load_shifts(input_path)
        demands = build_demands(args.month, shifts)
        rows = [demand.model_dump() for demand in demands]
        print(f"Demands total: {len(rows)}")
        if rows:
            print(_render_table(rows[:20]))
    employees = _load_employees_or_exit(input_path)
    shifts = load_shifts(input_path)
    demands = build_demands(args.month, shifts)
    solve_result = solve_schedule(employees, demands, shifts)
    export_schedule_excel(
        args.out,
        args.month,
        employees,
        shifts,
        solve_result.assignments,
        solve_result,
    )
    print("OK: bootstrap")


if __name__ == "__main__":
    main()
