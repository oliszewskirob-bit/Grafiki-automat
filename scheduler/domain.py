from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import date, time
from typing import Optional, Set

from pydantic import BaseModel, Field, field_validator


class Group(str, Enum):
    ELEKTRORADIOLOG = "ELEKTRORADIOLOG"
    PIELEGNIARKA = "PIELEGNIARKA"


def normalize_group(value: object) -> str:
    if value is None:
        return ""
    v = str(value).strip().lower()
    if v in {"elektroradiolog", "er", "elektroradiolodzy", "elektroradiologzy"}:
        return "ELEKTRORADIOLOG"
    if v in {"pielęgniarka", "pielegniarka", "piel", "pielegniarki", "zdo"}:
        return "PIELEGNIARKA"
    # jeśli ktoś wpisał już docelową wartość
    if v in {"elektroradiolog".lower(), "pielegniarka".lower()}:
        return v.upper()
    return str(value).strip()


class Employee(BaseModel):
    pracownik_id: Optional[str] = None
    imie_nazwisko: Optional[str] = None
    stanowisko: Optional[str] = None

    grupa: Group
    typ_umowy: Optional[str] = None
    etat: Optional[float] = None

    moze_24h: bool = False
    # Excel ma klucz "PN-PT" więc trzymamy alias:
    PN_PT: bool = Field(default=False, alias="PN-PT")

    skills: Set[str] = Field(default_factory=set)

    max_godz_tydz: Optional[float] = None
    cel_godz_miesiac: Optional[float] = None
    min_godz_miesiac: Optional[float] = None
    max_godz_miesiac: Optional[float] = None

    okres_rozliczeniowy_mies: int = 1

    @field_validator("grupa", mode="before")
    @classmethod
    def _norm_group(cls, v):
        return normalize_group(v)

    @field_validator("skills", mode="before")
    @classmethod
    def _skills_to_set(cls, v):
        if v is None:
            return set()
        if isinstance(v, set):
            return v
        if isinstance(v, list) or isinstance(v, tuple):
            return {str(x) for x in v if x is not None and str(x).strip() != ""}
        if isinstance(v, str):
            # np. "MR+TK" lub "MR, TK"
            s = v.replace("+", ",")
            parts = [p.strip() for p in s.split(",")]
            return {p for p in parts if p}
        return set()

    @field_validator("typ_umowy", mode="before")
    @classmethod
    def _norm_umowa(cls, v):
        if v is None:
            return None
        s = str(v).strip().upper()
        # dopuszczamy warianty
        if s in {"UOP", "UMOWA O PRACE", "UMOWAOPRACE"}:
            return "UOP"
        if s in {"B2B", "KONTRAKT"}:
            return "B2B"
        if s in {"ZLECENIE", "UMOWA ZLECENIE", "UZ"}:
            return "ZLECENIE"
        return s


class ShiftType(BaseModel):
    code: str = Field(alias="shift_code")
    grupa: Optional[str] = None
    modalnosc: Optional[str] = None

    start: Optional[str] = None
    koniec: Optional[str] = None
    czas_h: Optional[float] = None
    czy_24h: bool = False

    @field_validator("czy_24h", mode="before")
    @classmethod
    def _to_bool(cls, v):
        if v is None:
            return False
        s = str(v).strip().lower()
        return s in {"tak", "t", "true", "1", "x", "yes", "y"}


class Demand(BaseModel):
    date: date
    shift_code: str
    min_staff: int = 1
    target_staff: int = 1
    required_modalnosc: Optional[str] = None
    grupa: Optional[str] = None
    
class Settings(BaseModel):
    timezone: str = "Europe/Warsaw"

    # Wagi miękkich reguł (na start neutralne, żeby nic nie wywracało)
    w_max_hours_over: int = 1000
    w_min_hours_under: int = 500
    w_target_hours_dev: int = 50

    w_b2b_48h_week_over: int = 300
    w_balance_nights: int = 30
    w_balance_weekends: int = 30
    w_balance_24h: int = 30

    # Tolerancje
    uop_target_tolerance_hours: float = 8.0
