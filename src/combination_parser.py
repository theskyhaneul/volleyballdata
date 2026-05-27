"""[3ATTACKCOMBINATION] 섹션 파서."""

from __future__ import annotations

from dataclasses import dataclass

from .dvw_parser import DvwFile

IDX_CODE = 0
IDX_FIELD_START = 1
IDX_FIELD_END = 4
IDX_DESCRIPTION = 4
IDX_OTHER_START = 5


@dataclass
class CombinationRow:
    """공격 콤비네이션 1행."""

    code: str
    field: str
    description: str
    other: str


def _parse_combination_line(line: str) -> CombinationRow | None:
    parts = line.split(";")
    if not parts or not parts[0].strip():
        return None

    code = parts[IDX_CODE].strip()
    field_parts = parts[IDX_FIELD_START:IDX_FIELD_END]
    field = ";".join(p for p in field_parts)

    description = parts[IDX_DESCRIPTION].strip() if len(parts) > IDX_DESCRIPTION else ""

    other_start = IDX_OTHER_START
    if len(parts) > other_start and parts[other_start] == "":
        other_start = IDX_OTHER_START + 1
    other = ";".join(parts[other_start:]) if len(parts) > other_start else ""

    return CombinationRow(code=code, field=field, description=description, other=other)


def parse_attack_combinations(dvw: DvwFile) -> list[CombinationRow]:
    rows: list[CombinationRow] = []
    for line in dvw.lines("3ATTACKCOMBINATION"):
        if not line.strip():
            continue
        row = _parse_combination_line(line)
        if row:
            rows.append(row)
    return rows
