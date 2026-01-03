from pathlib import Path

from convert_logs import CombatLogProcessor, parse_events, read_lines


def test_timestamp_malformed_is_skipped(tmp_path: Path) -> None:
    bad = '<personal hologram="">'
    good = '1/1 00:00:00.000  WORLD_MARKER_REMOVED,SKULL'
    sample = tmp_path / 'bad_ts.txt'
    sample.write_text(f"{bad}\n{good}\n", encoding='utf-8')
    proc = CombatLogProcessor()
    events = list(parse_events(read_lines(sample), proc, sample))
    assert len(events) == 1
    assert events[0]['event'] == 'WORLD_MARKER_REMOVED'
