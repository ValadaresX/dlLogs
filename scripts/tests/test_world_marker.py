from pathlib import Path
from typing import Any

from convert_logs import CombatLogProcessor, parse_events, read_lines


def _run_events(lines: list[str], base_dir: Path) -> list[dict[str, Any]]:
    sample = base_dir / "marker_sample.txt"
    sample.write_text("\n".join(lines) + "\n", encoding="utf-8")
    processor = CombatLogProcessor()
    return list(parse_events(read_lines(sample), processor, sample))


def test_world_marker_placed_basic(tmp_path: Path) -> None:
    line = "1/1 00:00:00.000  WORLD_MARKER_PLACED,1504,3,1460.55,1252.67"
    events = _run_events([line], tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "WORLD_MARKER_PLACED"
    assert event["mapId"] == 1504
    assert event["markerId"] == 3
    assert event["x"] == 1460.55
    assert event["y"] == 1252.67
    assert "z" not in event


def test_world_marker_placed_with_z_and_negative(tmp_path: Path) -> None:
    line = "1/1 00:00:00.000  WORLD_MARKER_PLACED,980,1,-10733.79,423.76,12.5"
    events = _run_events([line], tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["mapId"] == 980
    assert event["markerId"] == 1
    assert event["x"] == -10733.79
    assert event["y"] == 423.76
    assert event["z"] == 12.5


def test_world_marker_removed(tmp_path: Path) -> None:
    line = "1/1 00:00:00.000  WORLD_MARKER_REMOVED,SKULL"
    events = _run_events([line], tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "WORLD_MARKER_REMOVED"
    assert event["removed"] is True
    assert event["flag"] == "SKULL"


def test_world_marker_insufficient_data_returns_error(tmp_path: Path) -> None:
    # Falta coordenadas; deve retornar erro estruturado e não explodir.
    line = "1/1 00:00:00.000  WORLD_MARKER_PLACED,1504,3"
    events = _run_events([line], tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "WORLD_MARKER_PLACED"
    assert "error" in event
    assert event["error"].startswith("Insufficient data for WORLD_MARKER")
    assert event["data"] == ["1504", "3"]
