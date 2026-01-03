from pathlib import Path
from typing import Any

from convert_logs import CombatLogProcessor, parse_events, read_lines


def _run_events(lines: list[str], base_dir: Path) -> list[dict[str, Any]]:
    sample_file = base_dir / "aura_sample.txt"
    sample_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    processor = CombatLogProcessor()
    return list(parse_events(read_lines(sample_file), processor, sample_file))


def test_aura_refresh_without_amount(tmp_path: Path) -> None:
    line = (
        '1/1 00:00:00.000  SPELL_AURA_REFRESH,'
        'SrcGUID,"Src",0x0,0x0,'
        'DstGUID,"Dst",0x0,0x0,'
        '123,"Spell",0x1,BUFF'
    )
    events = _run_events([line], tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "SPELL_AURA_REFRESH"
    assert event["auraType"] == "BUFF"
    assert "amount" not in event


def test_aura_refresh_with_amount(tmp_path: Path) -> None:
    line = (
        '1/1 00:00:00.000  SPELL_AURA_REFRESH,'
        'SrcGUID,"Src",0x0,0x0,'
        'DstGUID,"Dst",0x0,0x0,'
        '456,"Spell",0x1,DEBUFF,7'
    )
    events = _run_events([line], tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "SPELL_AURA_REFRESH"
    assert event["auraType"] == "DEBUFF"
    assert event["amount"] == 7


def test_aura_dose_applied_and_removed(tmp_path: Path) -> None:
    line_applied = (
        '1/1 00:00:00.000  SPELL_AURA_APPLIED_DOSE,'
        'SrcGUID,"Src",0x0,0x0,'
        'DstGUID,"Dst",0x0,0x0,'
        '789,"Spell",0x1,BUFF,3'
    )
    line_removed = (
        '1/1 00:00:00.000  SPELL_AURA_REMOVED_DOSE,'
        'SrcGUID,"Src",0x0,0x0,'
        'DstGUID,"Dst",0x0,0x0,'
        '789,"Spell",0x1,DEBUFF,1'
    )
    events = _run_events([line_applied, line_removed], tmp_path)
    assert len(events) == 2

    applied = events[0]
    assert applied["event"] == "SPELL_AURA_APPLIED_DOSE"
    assert applied["auraType"] == "BUFF"
    assert applied["newDose"] == 3

    removed = events[1]
    assert removed["event"] == "SPELL_AURA_REMOVED_DOSE"
    assert removed["auraType"] == "DEBUFF"
    assert removed["newDose"] == 1
