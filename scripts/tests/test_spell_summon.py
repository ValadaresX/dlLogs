from pathlib import Path
from typing import Any

from convert_logs import CombatLogProcessor, parse_events, read_lines


def _run_events(lines: list[str], base_dir: Path) -> list[dict[str, Any]]:
    sample = base_dir / "spell_summon_sample.txt"
    sample.write_text("\n".join(lines) + "\n", encoding="utf-8")
    processor = CombatLogProcessor()
    return list(parse_events(read_lines(sample), processor, sample))


def test_spell_summon_incomplete_is_dropped(tmp_path: Path) -> None:
    # Linha truncada: falta o bloco do feitiço (spellId, spellName, spellSchool).
    bad_line = (
        '1/1 00:00:00.000  SPELL_SUMMON,'
        'Player-1-AAAA,"Src",0x512,0x0,'
        'Creature-0-0-0-0-12345-000000000000,"Pet",0xa28,0x0'
    )
    # Linha completa logo depois: deve ser processada normalmente.
    good_line = (
        '1/1 00:00:00.001  SPELL_SUMMON,'
        'Player-1-AAAA,"Src",0x512,0x0,'
        'Creature-0-0-0-0-12346-000000000000,"Pet2",0xa28,0x0,'
        '317776,"Army of the Damned",0x20'
    )
    events = _run_events([bad_line, good_line], tmp_path)
    # A linha truncada deve ser ignorada e não abortar o arquivo.
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "SPELL_SUMMON"
    assert event["spellId"] == 317776
    assert event["spellName"] == "Army of the Damned"
    assert event["spellSchool"] == 32  # 0x20 decimal
