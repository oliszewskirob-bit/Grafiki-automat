"""Demand calculation."""

from __future__ import annotations

from collections.abc import Iterable

from scheduler import calendar_pl
from scheduler.domain import Demand, ShiftType


def _find_shifts(
    shifts: Iterable[ShiftType],
    *,
    grupa: str,
    modalnosc: str | None = None,
    is_24h: bool | None = None,
) -> list[ShiftType]:
    result: list[ShiftType] = []
    for shift in shifts:
        if shift.grupa != grupa:
            continue
        if modalnosc is not None and shift.modalnosc != modalnosc:
            continue
        if is_24h is not None and shift.is_24h != is_24h:
            continue
        result.append(shift)
    return sorted(result, key=lambda item: item.start_time)


def build_demands(
    month: str,
    shifts: dict[str, ShiftType],
    calendar_module=calendar_pl,
) -> list[Demand]:
    days = calendar_module.month_days(month)
    shift_values = list(shifts.values())

    er_24h = _find_shifts(
        shift_values, grupa="ELEKTRORADIOLOG", is_24h=True
    )
    if not er_24h:
        raise ValueError("Brak zmiany 24h dla ELEKTRORADIOLOG")

    er_mr = _find_shifts(
        shift_values, grupa="ELEKTRORADIOLOG", modalnosc="MR", is_24h=False
    )
    er_tk = _find_shifts(
        shift_values, grupa="ELEKTRORADIOLOG", modalnosc="TK", is_24h=False
    )
    if not er_mr:
        raise ValueError("Brak zmiany dziennej MR dla ELEKTRORADIOLOG")
    if len(er_tk) < 2:
        raise ValueError("Brak zmian dziennych/nocnych TK dla ELEKTRORADIOLOG")

    nurse_shifts = _find_shifts(
        shift_values, grupa="PIELEGNIARKA", modalnosc="ZDO", is_24h=False
    )
    if len(nurse_shifts) < 2:
        raise ValueError("Brak zmian dziennych/nocnych ZDO dla PIELEGNIARKA")

    demands: list[Demand] = []
    for day in days:
        is_weekend = calendar_module.is_weekend(day)
        is_holiday = calendar_module.is_holiday(day)

        if is_weekend or is_holiday:
            shift = er_24h[0]
            demands.append(
                Demand(
                    date=day,
                    shift_code=shift.code,
                    min_staff=1,
                    target_staff=1,
                    required_modalnosc=shift.modalnosc,
                    grupa=shift.grupa,
                )
            )
        else:
            mr_shift = er_mr[0]
            tk_day = er_tk[0]
            tk_night = er_tk[-1]
            for shift, min_staff, target_staff in (
                (mr_shift, 1, 2),
                (tk_day, 1, 1),
                (tk_night, 1, 1),
            ):
                demands.append(
                    Demand(
                        date=day,
                        shift_code=shift.code,
                        min_staff=min_staff,
                        target_staff=target_staff,
                        required_modalnosc=shift.modalnosc,
                        grupa=shift.grupa,
                    )
                )

        nurse_day = nurse_shifts[0]
        nurse_night = nurse_shifts[-1]
        for shift in (nurse_day, nurse_night):
            demands.append(
                Demand(
                    date=day,
                    shift_code=shift.code,
                    min_staff=1,
                    target_staff=1,
                    required_modalnosc=shift.modalnosc,
                    grupa=shift.grupa,
                )
            )

    return demands
