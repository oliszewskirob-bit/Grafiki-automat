"""Excel I/O helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import warnings

import pandas as pd
from pydantic import ValidationError

from scheduler.domain import Employee, ShiftType, normalize_group, Group


class EmployeeLoadError(Exception):
    def __init__(self, issues: list[dict[str, Any]], warnings_list: list[str]) -> None:
        super().__init__("Nieprawidlowe dane w arkuszu 'pracownicy'")
        self.issues = issues
        self.warnings_list = warnings_list


EMPLOYEE_WARNINGS: list[str] = []


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
        try:
            grupa_key = normalize_group(grupa).value
        except ValueError:
            grupa_key = grupa
        okres = row.get("okres_rozliczeniowy_mies")
        if pd.isna(okres):
            continue
        result[grupa_key] = int(okres)
    return result


def _normalize_header(value: Any) -> str:
    return "".join(char for char in str(value).casefold() if char not in {" ", "-", "_"})


def _build_column_map(columns: list[str]) -> dict[str, str]:
    return {_normalize_header(column): column for column in columns}


def _parse_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"tak", "true", "1", "x"}:
        return True
    if text in {"nie", "false", "0", ""}:
        return False
    return False


def _get_column_value(row: pd.Series, column_map: dict[str, str], aliases: list[str]) -> Any:
    for alias in aliases:
        key = _normalize_header(alias)
        if key in column_map:
            return row.get(column_map[key])
    return None


def _map_employee_record(
    row: pd.Series,
    column_map: dict[str, str],
    group_settings: dict[str, int],
    warnings_list: list[str],
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "pracownik_id": _get_column_value(row, column_map, ["pracownik_id", "id", "pracownik id"]),
        "imie_nazwisko": _get_column_value(
            row,
            column_map,
            ["imie_nazwisko", "imię i nazwisko", "imie i nazwisko", "nazwisko"],
        ),
        "stanowisko": _get_column_value(row, column_map, ["stanowisko", "rola"]),
        "grupa": _get_column_value(row, column_map, ["grupa", "group"]),
        "typ_umowy": _get_column_value(row, column_map, ["typ_umowy", "typ umowy", "umowa"]),
        "etat": _get_column_value(row, column_map, ["etat"]),
        "max_godz_tydz": _get_column_value(
            row, column_map, ["max_godz_tydz", "max godz tydz", "max tyg", "max tygodniowo"]
        ),
        "cel_godz_miesiac": _get_column_value(
            row, column_map, ["cel_godz_miesiac", "cel godz mies", "cel", "target"]
        ),
        "min_godz_miesiac": _get_column_value(
            row, column_map, ["min_godz_miesiac", "min godz mies", "min"]
        ),
        "max_godz_miesiac": _get_column_value(
            row, column_map, ["max_godz_miesiac", "max godz mies", "max"]
        ),
    }

    if _normalize_header("moze_24h") in column_map or _normalize_header("moze 24h") in column_map:
        record["moze_24h"] = _get_column_value(
            row, column_map, ["moze_24h", "moze 24h", "24h", "czy 24h"]
        )
    else:
        if "Brak kolumny 'moze_24h' - ustawiono domyslnie False." not in warnings_list:
            warnings_list.append("Brak kolumny 'moze_24h' - ustawiono domyslnie False.")
        record["moze_24h"] = False

    if _normalize_header("PN-PT") in column_map or _normalize_header("pn-pt") in column_map:
        record["pn_pt"] = _get_column_value(
            row, column_map, ["PN-PT", "pn-pt", "pn pt", "pnpt", "pon-pt"]
        )
    else:
        if "Brak kolumny 'PN-PT' - ustawiono domyslnie False." not in warnings_list:
            warnings_list.append("Brak kolumny 'PN-PT' - ustawiono domyslnie False.")
        record["pn_pt"] = False

    mr = _parse_bool(_get_column_value(row, column_map, ["MR", "mr"]))
    tk = _parse_bool(_get_column_value(row, column_map, ["TK", "tk"]))
    skills: set[str] = set()
    group_value = record.get("grupa")
    try:
        normalized_group = normalize_group(group_value)
    except ValueError:
        normalized_group = None
    if normalized_group == Group.ELEKTRORADIOLOG:
        if mr:
            skills.add("MR")
        if tk:
            skills.add("TK")
    if normalized_group == Group.PIELEGNIARKA:
        skills.add("ZDO")
    record["skills"] = skills
    group_key = normalized_group.value if isinstance(normalized_group, Group) else str(group_value or "").strip()
    record["okres_rozliczeniowy_mies"] = group_settings.get(group_key, 1)
    return record


def load_employees(path: str | Path) -> list[Employee]:
    source = Path(path)
    df = _read_sheet(source, "pracownicy")
    if df.empty:
        return []
    group_settings = load_group_settings(source)
    df = df.where(pd.notna(df), None)
    column_map = _build_column_map([str(col) for col in df.columns])
    employees: list[Employee] = []
    issues: list[dict[str, Any]] = []
    warnings_list: list[str] = []
    for idx, (_, row) in enumerate(df.iterrows()):
        record = _map_employee_record(row, column_map, group_settings, warnings_list)
        try:
            employees.append(Employee.model_validate(record))
        except ValidationError as exc:
            row_number = idx + 2
            for error in exc.errors():
                field = ".".join(str(part) for part in error.get("loc", []))
                issues.append(
                    {
                        "row": row_number,
                        "field": field or "unknown",
                        "message": error.get("msg", "Nieznany blad"),
                    }
                )
    EMPLOYEE_WARNINGS.clear()
    EMPLOYEE_WARNINGS.extend(warnings_list)
    if warnings_list:
        warnings.warn("\n".join(warnings_list), UserWarning)
    if issues:
        raise EmployeeLoadError(issues, warnings_list)
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
