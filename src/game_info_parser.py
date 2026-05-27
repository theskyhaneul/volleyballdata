"""게임정보 탭용 파서 ([3PLAYERS-H] 이전 섹션 중 일부)."""

from __future__ import annotations

from dataclasses import dataclass

from .dvw_parser import DvwFile, GAME_INFO_END_SECTION

SECTION_LABELS: dict[str, str] = {
    "3MATCH": "경기 정보",
    "3TEAMS": "팀 정보",
    "3SET": "세트 정보",
}

# 표시하지 않는 섹션
_SKIP_SECTIONS = frozenset({"3DATAVOLLEYSCOUT", "3MORE", "3COMMENTS"})


@dataclass
class KeyValueRow:
    key: str
    value: str


@dataclass
class GameInfoSection:
    name: str
    title: str
    rows: list[KeyValueRow]
    table_headers: list[str] | None = None
    table_rows: list[list[str]] | None = None


def _parse_teams(lines: list[str]) -> GameInfoSection:
    headers = ["코드", "팀명", "세트승", "감독", "스태프"]
    table_rows: list[list[str]] = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(";")
        table_rows.append(
            [
                parts[0] if len(parts) > 0 else "",
                parts[1] if len(parts) > 1 else "",
                parts[2] if len(parts) > 2 else "",
                parts[3] if len(parts) > 3 else "",
                parts[4] if len(parts) > 4 else "",
            ]
        )
    return GameInfoSection(
        name="3TEAMS",
        title=SECTION_LABELS["3TEAMS"],
        rows=[],
        table_headers=headers,
        table_rows=table_rows,
    )


def _get_team_names(dvw: DvwFile) -> tuple[str, str]:
    """3TEAMS 첫 줄=홈, 둘째 줄=어웨이 팀명."""
    team_lines = [line for line in dvw.lines("3TEAMS") if line.strip()]
    home_name = "홈팀"
    away_name = "어웨이팀"

    if team_lines:
        home_parts = team_lines[0].split(";")
        if len(home_parts) > 1 and home_parts[1].strip():
            home_name = home_parts[1].strip()
        elif home_parts[0].strip():
            home_name = home_parts[0].strip()

    if len(team_lines) > 1:
        away_parts = team_lines[1].split(";")
        if len(away_parts) > 1 and away_parts[1].strip():
            away_name = away_parts[1].strip()
        elif away_parts[0].strip():
            away_name = away_parts[0].strip()

    return home_name, away_name


def _winner_from_final_score(final_score: str, home_name: str, away_name: str) -> str:
    """
    최종점수 A-B: A가 크면 홈팀, B가 크면 어웨이팀.
    """
    text = final_score.strip()
    if not text:
        return "-"

    normalized = text.replace(" ", "")
    if "-" not in normalized:
        return "-"

    left, right = normalized.split("-", 1)
    try:
        score_a = int(left)
        score_b = int(right)
    except ValueError:
        return "-"

    if score_a > score_b:
        return home_name
    if score_b > score_a:
        return away_name
    return "-"


def _parse_sets(lines: list[str], home_name: str, away_name: str) -> GameInfoSection:
    headers = ["세트", "승리팀", "1", "2", "3", "최종점수", "경기시간"]
    table_rows: list[list[str]] = []
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        parts = line.split(";")
        col1 = parts[1].strip() if len(parts) > 1 else ""
        col2 = parts[2].strip() if len(parts) > 2 else ""
        col3 = parts[3].strip() if len(parts) > 3 else ""
        final_score = parts[4].strip() if len(parts) > 4 else ""
        duration = parts[5].strip() if len(parts) > 5 else ""
        winner = _winner_from_final_score(final_score, home_name, away_name)
        table_rows.append([str(index), winner, col1, col2, col3, final_score, duration])
    return GameInfoSection(
        name="3SET",
        title=SECTION_LABELS["3SET"],
        rows=[],
        table_headers=headers,
        table_rows=table_rows,
    )


def _parse_match(lines: list[str]) -> GameInfoSection:
    """첫 번째 비어 있지 않은 행에서 날짜·시즌·리그·라운드만 표시."""
    first = next((line for line in lines if line.strip()), "")
    rows: list[KeyValueRow] = []
    if not first:
        return GameInfoSection(name="3MATCH", title=SECTION_LABELS["3MATCH"], rows=[])

    parts = first.split(";")
    labels_and_indices = [
        ("날짜", 0),
        ("시즌", 2),
        ("리그", 3),
        ("라운드", 4),
    ]
    for label, idx in labels_and_indices:
        value = parts[idx].strip() if idx < len(parts) else ""
        rows.append(KeyValueRow(key=label, value=value if value else "-"))

    return GameInfoSection(name="3MATCH", title=SECTION_LABELS["3MATCH"], rows=rows)


def parse_game_info_sections(dvw: DvwFile) -> list[GameInfoSection]:
    """[3PLAYERS-H] 이전 중 경기·팀·세트 정보만 순서대로 반환."""
    home_name, away_name = _get_team_names(dvw)
    blocks: list[GameInfoSection] = []
    for name, lines in dvw.sections_before(GAME_INFO_END_SECTION):
        if name in _SKIP_SECTIONS:
            continue
        if name == "3TEAMS":
            blocks.append(_parse_teams(lines))
        elif name == "3SET":
            blocks.append(_parse_sets(lines, home_name, away_name))
        elif name == "3MATCH":
            blocks.append(_parse_match(lines))
    return blocks
