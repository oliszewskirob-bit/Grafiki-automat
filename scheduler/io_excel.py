"""Excel I/O helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scheduler.domain import Employee, ShiftType


def _read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name)


def load_group_settings(path: str | Path) -> dict[str, int]:
    source = Path(path)
    df = _read_sheet(source, "ustawienia_grup")
    if df.empty:
        return {}
    df = df.rename(columns=str).copy()
    result: dict[str, int] = {}
    for _, row in df.iterrows():
        grupa = str(row.get("grupa", "")).strip()
        if not grupa:
            continue
        okres = row.get("okres_rozliczeniowy_mies")
        if pd.isna(okres):
            continue
        result[grupa] = int(okres)
    return result


def load_employees(path: str | Path) -> list[Employee]:
    source = Path(path)
    df = _read_sheet(source, "pracownicy")
    if df.empty:
        return []
    group_settings = load_group_settings(source)
    records = df.where(pd.notna(df), None).to_dict(orient="records")
    employees: list[Employee] = []
    for record in records:
        grupa = str(record.get("grupa", "")).strip()
        record["okres_rozliczeniowy_mies"] = group_settings.get(grupa, 1)
        employees.append(Employee.model_validate(record))
    return employees


def load_shifts(path: str | Path) -> dict[str, ShiftType]:
    source = Path(path)
    df = _read_sheet(source, "typy_zmian")
    if df.empty:
        return {}
    records = df.where(pd.notna(df), None).to_dict(orient="records")
    shifts: dict[str, ShiftType] = {}
    for record in records:
        shift = ShiftType.model_validate(record)
        shifts[shift.code] = shift
    return shifts
