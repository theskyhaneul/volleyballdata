"""[3SCOUT] 섹션 파서."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .combination_parser import parse_attack_combinations
from .dvw_parser import DvwFile
from .players_parser import _parse_teams

BASIC_SKILLS = {
    "S": "Serve",
    "R": "Receive",
    "E": "sEt",
    "A": "Attack",
    "B": "Block",
    "F": "FreeBall",
    "D": "Defense",
}

SHOT_TYPES = {
    "M": "Medium",
    "H": "High",
    "Q": "Quick",
    "U": "Super",
    "O": "Other",
    "T": "Tense",
}

RESULT_SYMBOLS = set("+-#!=/")


@dataclass
class ScoutRow:
    """스카우트 랠리 1행."""

    number: int
    team: str
    player_name: str
    basic_skill: str
    shot_type: str
    result: str
    combo: str
    time: str
    set_number: str
    raw_code: str


def _build_roster(dvw: DvwFile, section: str) -> dict[int, str]:
    roster: dict[int, str] = {}
    for line in dvw.lines(section):
        if not line.strip():
            continue
        parts = line.split(";")
        if len(parts) <= 9:
            continue
        jersey_raw = parts[1].strip()
        if not jersey_raw.isdigit():
            continue
        name = parts[9].strip()
        roster[int(jersey_raw)] = name
    return roster


def _build_combination_map(dvw: DvwFile) -> dict[str, str]:
    return {row.code: row.description for row in parse_attack_combinations(dvw)}


def _extract_time_and_set(line: str) -> tuple[str, str]:
    """세미콜론 구분 필드에서 시간(HH.MM.SS)과 바로 다음 세트 번호를 찾습니다."""
    parts = line.split(";")
    for index, part in enumerate(parts):
        value = part.strip()
        if re.match(r"^\d+\.\d{2}\.\d{2}$", value):
            set_value = parts[index + 1].strip() if index + 1 < len(parts) else ""
            return value, set_value
    return "", ""


def _is_scout_data_line(line: str) -> bool:
    if not line.strip() or ">LUp" in line:
        return False
    code = line.split(";", 1)[0]
    return bool(re.match(r"^[*a-z]\d{2}", code))


def _extract_combo_code(rest: str, combo_map: dict[str, str]) -> tuple[str, str]:
    """결과 이후 구간에서 콤비 코드(~~~ 제외)를 찾아 설명을 반환."""
    if not rest or rest.startswith("~~~"):
        return "", ""

    known_codes = sorted(combo_map.keys(), key=len, reverse=True)
    for code in known_codes:
        pos = rest.find(code)
        while pos != -1:
            prefix = rest[:pos]
            if prefix.endswith("~~~") or prefix.rstrip("~").endswith("~~~"):
                pos = rest.find(code, pos + len(code))
                continue
            return code, combo_map[code]
    return "", ""


def _parse_code_part(code_part: str, combo_map: dict[str, str]) -> tuple[str, str, str, str, str, str] | None:
    if len(code_part) < 4:
        return None

    team_char = code_part[0]
    player_no = code_part[1:3]
    if not player_no.isdigit():
        return None

    tail = code_part[3:]
    basic = ""
    shot = ""
    result = ""
    index = 0

    if index < len(tail) and tail[index] in BASIC_SKILLS:
        basic = tail[index]
        index += 1
    if index < len(tail) and tail[index] in SHOT_TYPES:
        shot = tail[index]
        index += 1
    if index < len(tail) and tail[index] in RESULT_SYMBOLS:
        result = tail[index]
        index += 1

    _combo_code, combo_desc = _extract_combo_code(tail[index:], combo_map)

    return (
        team_char,
        player_no,
        BASIC_SKILLS.get(basic, basic),
        SHOT_TYPES.get(shot, shot),
        result,
        combo_desc,
    )


def parse_scout_rows(dvw: DvwFile) -> list[ScoutRow]:
    teams = _parse_teams(dvw)
    home_name = teams[0][1] if teams else "홈팀"
    away_name = teams[1][1] if len(teams) > 1 else "어웨이팀"

    home_roster = _build_roster(dvw, "3PLAYERS-H")
    away_roster = _build_roster(dvw, "3PLAYERS-V")
    combo_map = _build_combination_map(dvw)

    rows: list[ScoutRow] = []
    row_number = 0
    for line in dvw.lines("3SCOUT"):
        if not _is_scout_data_line(line):
            continue

        code_part = line.split(";", 1)[0]
        parsed = _parse_code_part(code_part, combo_map)
        if not parsed:
            continue

        row_number += 1
        team_char, player_no, basic_skill, shot_type, result, combo_desc = parsed
        jersey = int(player_no)

        if team_char == "*":
            team = home_name
            player_name = home_roster.get(jersey, player_no)
        else:
            team = away_name
            player_name = away_roster.get(jersey, player_no)

        time_value, set_value = _extract_time_and_set(line)
        rows.append(
            ScoutRow(
                number=row_number,
                team=team,
                player_name=player_name,
                basic_skill=basic_skill,
                shot_type=shot_type,
                result=result,
                combo=combo_desc,
                time=time_value,
                set_number=set_value,
                raw_code=code_part,
            )
        )

    return rows


def _parse_time_parts(time_str: str) -> tuple[int, int, int] | None:
    """타임(HH.MM.SS)을 (시, 분, 초)로 파싱. 예: 19.01.43 → 19시 01분 43초."""
    if not time_str or time_str == "-":
        return None
    parts = time_str.strip().split(".")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None


def time_to_total_seconds(time_str: str) -> int | None:
    """시·분·초를 총 초로 변환."""
    parsed = _parse_time_parts(time_str)
    if parsed is None:
        return None
    hours, minutes, seconds = parsed
    return hours * 3600 + minutes * 60 + seconds


def seconds_to_units(seconds: int) -> int:
    """초 → 위치 값 (×1000, 예: 51초 → 51000, 73초 → 73000)."""
    return seconds * 1000


def elapsed_seconds_from_reference(reference: str, current: str) -> int | None:
    """1번 행 타임 대비 경과 초 (시·분·초 차이)."""
    ref_seconds = time_to_total_seconds(reference)
    cur_seconds = time_to_total_seconds(current)
    if ref_seconds is None or cur_seconds is None:
        return None
    return cur_seconds - ref_seconds


def compute_uniform_periods(row_count: int, base_length_seconds: int) -> list[int]:
    """기본 길이(초)를 모든 행에 동일 적용 (×1000)."""
    value = seconds_to_units(base_length_seconds)
    return [value for _ in range(row_count)]


def compute_positions_from_first_row(rows: list[ScoutRow]) -> list[int | str]:
    """1번 행 타임을 0으로 한 위치(초×1000)."""
    if not rows:
        return []

    reference_time = rows[0].time
    positions: list[int | str] = [0]

    for row in rows[1:]:
        diff = elapsed_seconds_from_reference(reference_time, row.time)
        if diff is None:
            positions.append("-")
        else:
            positions.append(seconds_to_units(diff))

    return positions
