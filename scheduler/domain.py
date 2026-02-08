"""Domain models mapped from Excel inputs."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

class Group(str, Enum):
    ELEKTRORADIOLOG = "ELEKTRORADIOLOG"
    PIELEGNIARKA = "PIELEGNIARKA"


def normalize_group(value: Any) -> Group:
    if isinstance(value, Group):
        return value
    if value is None:
        raise ValueError("Grupa jest wymagana")
    text = str(value).strip().casefold()
    mapping = {
        "elektroradiolog": Group.ELEKTRORADIOLOG,
        "er": Group.ELEKTRORADIOLOG,
        "pielęgniarka": Group.PIELEGNIARKA,
        "pielęgniarki": Group.PIELEGNIARKA,
        "piel": Group.PIELEGNIARKA,
    }
    if text in mapping:
        return mapping[text]
    for group in Group:
        if text == group.value.casefold():
            return group
    raise ValueError(f"Nieprawidlowa grupa: {value!r}")


GroupName = Group
ContractType = Literal["UOP", "B2B", "ZLECENIE"]


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().upper()
    if text in {"TAK", "YES", "TRUE", "1"}:
        return True
    if text in {"NIE", "NO", "FALSE", "0", ""}:
        return False
    raise ValueError(f"Nieprawidlowa wartosc bool: {value!r}")


def _parse_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    if value is None:
        raise ValueError("Czas nie moze byc pusty")
    text = str(value).strip()
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError as exc:
        raise ValueError(f"Nieprawidlowy format czasu (HH:MM): {value!r}") from exc


class Employee(BaseModel):
    id: str = Field(alias="pracownik_id")
    name: str = Field(alias="imie_nazwisko")
    stanowisko: str
    grupa: GroupName
    typ_umowy: ContractType
    etat: float | None = None
    moze_24h: bool
    pn_pt: bool = Field(alias="PN-PT")
    skills: set[str]
    max_godz_tydz: float | None = None
    cel_godz_miesiac: float | None = None
    auto_target: bool = False
    min_godz_miesiac: float | None = None
    max_godz_miesiac: float | None = None
    okres_rozliczeniowy_mies: int

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }

    @model_validator(mode="before")
    @classmethod
    def _inject_auto_target(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        raw = values.get("cel_godz_miesiac")
        if isinstance(raw, str) and raw.strip().upper() == "AUTO":
            values["auto_target"] = True
        return values

    @field_validator("moze_24h", "pn_pt", mode="before")
    @classmethod
    def _validate_bool(cls, value: Any) -> bool:
        return _parse_bool(value)

    @field_validator("grupa", mode="before")
    @classmethod
    def _normalize_group(cls, value: Any) -> Group:
        return normalize_group(value)

    @field_validator("skills", mode="before")
    @classmethod
    def _build_skills(cls, value: Any, info: Any) -> set[str]:
        if isinstance(value, (set, list, tuple)):
            return set(value)
        data = info.data or {}
        mr = _parse_bool(data.get("MR"))
        tk = _parse_bool(data.get("TK"))
        group = data.get("grupa")
        skills: set[str] = set()
        if group == Group.ELEKTRORADIOLOG:
            if mr:
                skills.add("MR")
            if tk:
                skills.add("TK")
            if mr and tk:
                skills.add("ALL")
        if group == Group.PIELEGNIARKA:
            skills.add("ZDO")
        return skills

    @field_validator("cel_godz_miesiac", mode="before")
    @classmethod
    def _parse_target(cls, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().upper()
        if text == "AUTO":
            return None
        return float(text.replace(",", "."))

    @model_validator(mode="after")
    def _validate_contract(self) -> "Employee":
        if self.typ_umowy == "UOP" and self.etat is None:
            raise ValueError("UOP wymaga etatu")
        if self.grupa == Group.ELEKTRORADIOLOG and not self.skills:
            raise ValueError("Brak kwalifikacji MR/TK dla ELEKTRORADIOLOG")
        if self.auto_target:
            self.cel_godz_miesiac = None
        return self


class ShiftType(BaseModel):
    code: str = Field(alias="shift_code")
    grupa: GroupName
    modalnosc: str
    start_time: time = Field(alias="start")
    end_time: time = Field(alias="koniec")
    duration_h: float = Field(alias="czas_h")
    is_24h: bool = Field(alias="czy_24h")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _parse_time_fields(cls, value: Any) -> time:
        return _parse_time(value)

    @field_validator("is_24h", mode="before")
    @classmethod
    def _parse_is_24h(cls, value: Any) -> bool:
        return _parse_bool(value)


class Demand(BaseModel):
    date: date
    shift_code: str
    min_staff: int
    target_staff: int
    required_modalnosc: str
    grupa: GroupName


class Settings(BaseModel):
    timezone: str = "Europe/Warsaw"
    wagi_miekkie: dict[str, float] = Field(
        default_factory=lambda: {
            "max_hours": 1000.0,
            "min_hours": 500.0,
            "target_hours": 100.0,
            "weekly_48h": 500.0,
            "balance": 50.0,
        }
    )
    tolerancje: dict[str, float] = Field(default_factory=dict)
