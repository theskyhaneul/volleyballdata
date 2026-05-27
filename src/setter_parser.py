"""[3SETTERCALL] 섹션 파서."""

from __future__ import annotations

from dataclasses import dataclass

from .dvw_parser import DvwFile

IDX_CODE = 0
IDX_DESCRIPTION = 2
IDX_OTHER_START = 4


@dataclass
class SetterCallRow:
    """세터 콜 1행."""

    code: str
    description: str
    other: str


def _parse_setter_line(line: str) -> SetterCallRow | None:
    parts = line.split(";")
    if not parts or not parts[0].strip():
        return None

    code = parts[IDX_CODE].strip()
    description = parts[IDX_DESCRIPTION].strip() if len(parts) > IDX_DESCRIPTION else ""

    other_start = IDX_OTHER_START
    if len(parts) > other_start and parts[other_start] == "":
        other_start += 1
    other = ";".join(parts[other_start:]) if len(parts) > other_start else ""

    return SetterCallRow(code=code, description=description, other=other)


def parse_setter_calls(dvw: DvwFile) -> list[SetterCallRow]:
    rows: list[SetterCallRow] = []
    for line in dvw.lines("3SETTERCALL"):
        if not line.strip():
            continue
        row = _parse_setter_line(line)
        if row:
            rows.append(row)
    return rows
