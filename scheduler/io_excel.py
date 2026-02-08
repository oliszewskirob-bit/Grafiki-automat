"""Excel I/O helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from scheduler.domain import Employee, ShiftType, normalize_group


def _read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name)


def _colmap(df: pd.DataFrame) -> dict[str, str]:
    """
    Mapuje kolumny Excela na klucze logiczne.
    Działa case-insensitive i ignoruje spacje/myślniki.
    """
    def norm(s: str) -> str:
        return str(s).strip().lower().replace(" ", "").replace("-", "")

    wanted: dict[str, list[str]] = {
        "pracownik_id": ["pracownik_id", "id", "pracownikid"],
        "imie_nazwisko": ["imie_nazwisko", "imięinazwisko", "imieinazwisko", "nazwisko"],
        "stanowisko": ["stanowisko", "rola"],
        "grupa": ["grupa", "group"],
        "typ_umowy": ["typ_umowy", "typumowy", "umowa"],
        "etat": ["etat"],
        "moze_24h": ["moze_24h", "moze24h", "24h", "czy24h"],
        "PN-PT": ["pnpt", "pn-pt", "pnpt", "ponpt", "pon-pt"],
        "MR": ["mr"],
        "TK": ["tk"],
        "max_godz_tydz": ["max_godz_tydz", "maxgodztydz", "maxtyg", "maxty", "maxtygodniowo"],
        "cel_godz_miesiac": ["cel_godz_miesiac", "celgodzmiesiac", "cel", "target"],
        "min_godz_miesiac": ["min_godz_miesiac", "mingodzmiesiac", "min"],
        "max_godz_miesiac": ["max_godz_miesiac", "maxgodzmiesiac", "max"],
    }

    actual = {norm(c): c for c in df.columns}
    mapping: dict[str, str] = {}
    for key, aliases in wanted.items():
        for a in aliases:
            na = norm(a)
            if na in actual:
                mapping[key] = actual[na]
                break
    return mapping


def _to_bool(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)) and not pd.isna(x):
        return bool(int(x))
    s = str(x).strip().lower()
    return s in {"tak", "t", "true", "1", "x", "yes", "y"}


def load_group_settings(path: str | Path) -> dict[str, int]:
    source = Path(path)
    df = _read_sheet(source, "ustawienia_grup")
    if df.empty:
        return {}
    df = df.rename(columns=str).copy()
    result: dict[str, int] = {}
    for _, row in df.iterrows():
        raw = row.get("grupa", "")
        grupa = normalize_group(raw) if raw is not None else ""
        grupa = str(grupa).strip()
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
    cmap = _colmap(df)

    records = df.where(pd.notna(df), None).to_dict(orient="records")
    employees: list[Employee] = []

    for record in records:
        # Wyciągnij pola z możliwych nazw kolumn
        def get(key: str, default=None):
            col = cmap.get(key)
            return record.get(col, default) if col else default

        raw_grupa = get("grupa", "")
        grupa_norm = normalize_group(raw_grupa)

        # Skills liczone, nie czytane wprost
        skills: set[str] = set()
        if str(grupa_norm) == "ELEKTRORADIOLOG":
            if _to_bool(get("MR")):
                skills.add("MR")
            if _to_bool(get("TK")):
                skills.add("TK")
        elif str(grupa_norm) == "PIELEGNIARKA":
            skills.add("ZDO")

        # Zbuduj rekord pod model Employee (klucze muszą pasować do domain.Employee)
        normalized: dict[str, Any] = {
            "pracownik_id": get("pracownik_id"),
            "imie_nazwisko": get("imie_nazwisko"),
            "stanowisko": get("stanowisko"),
            "grupa": grupa_norm,
            "typ_umowy": get("typ_umowy"),
            "etat": get("etat"),
            "moze_24h": _to_bool(get("moze_24h", False)),
            "PN-PT": _to_bool(get("PN-PT", False)),
            "skills": skills,
            "max_godz_tydz": get("max_godz_tydz"),
            "cel_godz_miesiac": get("cel_godz_miesiac"),
            "min_godz_miesiac": get("min_godz_miesiac"),
            "max_godz_miesiac": get("max_godz_miesiac"),
            "okres_rozliczeniowy_mies": group_settings.get(str(grupa_norm), 1),
        }

        employees.append(Employee.model_validate(normalized))

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
