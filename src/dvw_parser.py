"""Data Volley (.dvw) 파일 파서."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


GAME_INFO_END_SECTION = "3PLAYERS-H"
GAME_DATA_START_SECTION = "3SCOUT"


@dataclass
class DvwFile:
    """파싱된 DVW 파일."""

    path: Path
    sections: dict[str, list[str]] = field(default_factory=dict)
    section_order: list[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return self.path.name

    def lines(self, section: str) -> list[str]:
        return self.sections.get(section, [])

    def text(self, section: str) -> str:
        return "\n".join(self.lines(section))

    def sections_before(self, anchor: str = GAME_INFO_END_SECTION) -> list[tuple[str, list[str]]]:
        """파일 순서대로 anchor 섹션 이전까지의 섹션을 반환합니다."""
        result: list[tuple[str, list[str]]] = []
        for name in self.section_order:
            if name == anchor:
                break
            result.append((name, self.sections.get(name, [])))
        return result

    def sections_from(self, anchor: str = GAME_DATA_START_SECTION) -> list[tuple[str, list[str]]]:
        """파일 순서대로 anchor 섹션부터 끝까지의 섹션을 반환합니다."""
        result: list[tuple[str, list[str]]] = []
        started = False
        for name in self.section_order:
            if name == anchor:
                started = True
            if started:
                result.append((name, self.sections.get(name, [])))
        return result


def _read_text(path: Path) -> str:
    for encoding in ("cp949", "euc-kr", "utf-8", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="latin-1", errors="replace")


def parse_dvw(path: str | Path) -> DvwFile:
    """DVW 파일을 섹션별로 파싱합니다."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    raw = _read_text(file_path)
    sections: dict[str, list[str]] = {}
    section_order: list[str] = []
    current: str | None = None

    for line in raw.splitlines():
        if line.startswith("[3") and line.endswith("]"):
            current = line[1:-1]  # e.g. "3MATCH"
            sections[current] = []
            section_order.append(current)
        elif current is not None:
            sections[current].append(line)

    return DvwFile(path=file_path, sections=sections, section_order=section_order)
