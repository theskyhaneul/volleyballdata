"""[3PLAYERS-H] / [3PLAYERS-V] 섹션 파서."""

from __future__ import annotations

from dataclasses import dataclass

from .dvw_parser import DvwFile

# Data Volley 3PLAYERS 행 필드 인덱스
IDX_JERSEY = 1  # 등번호 (예: 1번)
IDX_SET_SCORE_START = 3
IDX_PLAYER_ID = 8  # 선수 번호 (예: KGC-001 → 코드 01)
IDX_NAME = 9
IDX_ROLE = 12


@dataclass
class PlayerRow:
    """선수 1명의 세트별 득점."""

    number: int
    name: str
    player_id: str
    set_scores: list[str]
    total: int
    role: str = ""

    @property
    def display_name(self) -> str:
        if self.role.upper() == "L":
            return f"{self.name} (L)"
        return self.name


@dataclass
class TeamPlayers:
    """팀 선수 목록."""

    code: str
    name: str
    label: str
    players: list[PlayerRow]
    set_count: int


def _count_played_sets(dvw: DvwFile) -> int:
    """[3SET]에서 실제 진행된 세트 수를 추정합니다."""
    count = 0
    for line in dvw.lines("3SET"):
        parts = line.split(";")
        if parts and parts[0].strip().lower() == "true" and len(parts) > 1 and parts[1].strip():
            count += 1
    return max(count, 1)


def _parse_teams(dvw: DvwFile) -> list[tuple[str, str]]:
    teams: list[tuple[str, str]] = []
    for line in dvw.lines("3TEAMS"):
        if not line.strip():
            continue
        parts = line.split(";")
        code = parts[0].strip() if parts else ""
        name = parts[1].strip() if len(parts) > 1 else code
        if code:
            teams.append((code, name))
    return teams


def _format_score(raw: str) -> str:
    value = raw.strip()
    if not value:
        return "-"
    return value


def _score_to_int(raw: str) -> int | None:
    value = raw.strip()
    if not value or value == "*":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_player_line(line: str, set_count: int) -> PlayerRow | None:
    parts = line.split(";")
    if len(parts) <= IDX_NAME:
        return None

    number_raw = parts[IDX_JERSEY].strip()
    if not number_raw.isdigit():
        return None

    set_raw = parts[IDX_SET_SCORE_START : IDX_SET_SCORE_START + set_count]
    while len(set_raw) < set_count:
        set_raw.append("")

    set_scores = [_format_score(v) for v in set_raw]
    total = sum(v for v in (_score_to_int(x) for x in set_raw) if v is not None)

    role = parts[IDX_ROLE].strip() if len(parts) > IDX_ROLE else ""
    name = parts[IDX_NAME].strip()
    player_id = parts[IDX_PLAYER_ID].strip() if len(parts) > IDX_PLAYER_ID else ""

    return PlayerRow(
        number=int(number_raw),
        name=name or player_id,
        player_id=player_id,
        set_scores=set_scores,
        total=total,
        role=role,
    )


def parse_players_section(lines: list[str], set_count: int) -> list[PlayerRow]:
    players: list[PlayerRow] = []
    for line in lines:
        if not line.strip():
            continue
        row = _parse_player_line(line, set_count)
        if row:
            players.append(row)
    players.sort(key=lambda p: (-p.total, p.number))
    return players


def parse_team_players(
    dvw: DvwFile,
    section: str,
    label: str,
    team_index: int,
) -> TeamPlayers:
    set_count = _count_played_sets(dvw)
    teams = _parse_teams(dvw)
    code, name = ("", label)
    if team_index < len(teams):
        code, name = teams[team_index]

    players = parse_players_section(dvw.lines(section), set_count)
    return TeamPlayers(code=code, name=name, label=label, players=players, set_count=set_count)


def parse_home_players(dvw: DvwFile) -> TeamPlayers:
    return parse_team_players(dvw, "3PLAYERS-H", "홈팀", team_index=0)


def parse_away_players(dvw: DvwFile) -> TeamPlayers:
    return parse_team_players(dvw, "3PLAYERS-V", "어웨이팀", team_index=1)
