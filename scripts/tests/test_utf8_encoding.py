import json
from pathlib import Path

from convert_logs import CombatLogProcessor, parse_events, read_lines

SAMPLE_LINES = [
    '11/4/2025 23:23:15.979-8  SPELL_AURA_REMOVED,Pet-0-4215-1552-14159-1863-010391DC80,"艾尔拉恩",0x1111,0x80000080,Pet-0-4215-1552-14159-1863-010391DC80,"艾尔拉恩",0x1111,0x80000080,32727,"竞技场准备",0x1,BUFF',
    '11/4/2025 23:23:16.154-8  SPELL_AURA_APPLIED,Player-11-0E9CADCB,"Rilil-Tichondrius-US",0x548,0x80000000,Player-11-0E9CADCB,"Rilil-Tichondrius-US",0x548,0x80000000,465,"虔诚光环",0x2,BUFF',
    '10/31/2025 21:37:08.7653  SPELL_AURA_REMOVED,Pet-0-3151-2759-11175-165189-01033C26F0,"НеХазанов",0x1111,0x80000000,Pet-0-3151-2759-11175-165189-01033C26F0,"НеХазанов",0x1111,0x80000000,32727,"Подготовка арены",0x1,BUFF',
    '10/31/2025 21:37:08.7653  SPELL_AURA_REMOVED,Pet-0-3151-2759-11175-165189-01033C26CA,"Ребрышки",0x1111,0x80000000,Pet-0-3151-2759-11175-165189-01033C26CA,"Ребрышки",0x1111,0x80000000,32727,"Подготовка арены",0x1,BUFF',
    '10/31/2025 21:37:08.9233  SPELL_AURA_APPLIED,Player-1403-0B0E43AB,"Maglustor-Draenor-EU",0x548,0x80000000,Player-1403-0B0E43AB,"Maglustor-Draenor-EU",0x548,0x80000000,404464,"Стиль полета: высший пилотаж",0x1,BUFF',
]


def test_utf8_multilingual_names(tmp_path: Path) -> None:
    """Garante que nomes e feitiços multilingues permaneçam íntegros em UTF-8.

    Args:
        tmp_path: Diretório temporário usado para gerar o arquivo de amostra.
    """
    sample_file = tmp_path / "utf8_misto.txt"
    sample_file.write_text("\n".join(SAMPLE_LINES) + "\n", encoding="utf-8")

    processor = CombatLogProcessor()
    events = list(parse_events(read_lines(sample_file), processor))

    assert len(events) == len(SAMPLE_LINES)

    source_names = [e.get("sourceName") for e in events]
    spell_names = [e.get("spellName") for e in events]

    for expected in ["艾尔拉恩", "НеХазанов", "Ребрышки"]:
        assert expected in source_names

    for expected_spell in ["竞技场准备", "虔诚光环", "Подготовка арены", "Стиль полета: высший пилотаж"]:
        assert expected_spell in spell_names

    assert all("�" not in name for name in source_names if name)
    assert all("�" not in spell for spell in spell_names if spell)

    json.dumps(events, ensure_ascii=False)
