"""
Conversor de logs de combate de WoW -> JSON estruturado.

Este arquivo atua como o "roteador" principal (Maestro), lendo os
arquivos de log e direcionando cada evento para seu parser simples.
O evento COMBATANT_INFO e delegado ao parser especializado em
parser_combatant_info.py.
"""

import hashlib
import logging
import os
import re
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntFlag
from functools import lru_cache, partial
from logging.handlers import RotatingFileHandler
from multiprocessing import cpu_count
from pathlib import Path
from typing import Any

import orjson
from tqdm import tqdm  # type: ignore[import-untyped]

from parser_combatant_info import CombatantInfoParser

logger = logging.getLogger("convert_logs")  # console/general logger
file_logger = logging.getLogger("convert_logs.file")  # arquivo convert_logs.log
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "output_json"
LOG_PATH = LOG_DIR / "convert_logs.log"
JSON_WRITE_BUFFER_BYTES: int = 2 * 1024 * 1024  # buffer de escrita
_PARSE_WARN_SAMPLE = 6

# Regex pré-compiladas para hot paths
_RE_TIMEZONE = re.compile(r"([+-]\d{1,2}(?::?\d{2})?)$")
_RE_YEAR_PREFIX = re.compile(r"^(?P<year>\d{4})")

@dataclass(frozen=True, slots=True)
class ParseWarningKey:
    event: str
    reason: str
    file_name: str
    cols: str


@dataclass(slots=True)
class ParserState:
    file_path: Path
    line_no: int = 0
    raw_line: str = ""
    warning_counts: defaultdict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    malformed_lines: int = 0
    skip_reason: str | None = None




def _configure_stdout() -> None:
    if str(getattr(sys.stdout, "encoding", "")).lower() != "utf-8" and hasattr(
        sys.stdout, "reconfigure"
    ):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            logger.warning("Nao foi possivel reconfigurar stdout para utf-8")


def _configure_logging(log_dir: Path = LOG_DIR, *, for_worker: bool = False) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_level = os.getenv("WOW_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, log_level, logging.WARNING)
    fmt = "%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s"
    log_path = LOG_PATH
    file_mode = "a" if for_worker else "w"
    file_handler = RotatingFileHandler(
        log_path,
        mode=file_mode,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
        delay=True,
    )
    file_handler.setLevel(logging.ERROR)
    handlers: list[logging.Handler] = [file_handler]
    if not for_worker:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=handlers,
        force=True,
    )
    logger.setLevel(level)
    file_logger.setLevel(level)
    logger.propagate = True
    file_logger.propagate = True


def _log_aggregated_errors(errors: dict[str, int]) -> None:
    for msg, count in errors.items():
        if count > 1:
            logger.error("%s (repetido %s vezes)", msg, count)
        else:
            logger.error("%s", msg)


def _make_warning_id(key: ParseWarningKey) -> str:
    raw = f"{key.event}|{key.reason}|{key.file_name}|{key.cols}"
    return hashlib.md5(raw.encode("utf-8", "replace")).hexdigest()[:8]




def _log_parse_warning(
    event_label: str,
    cols: list[str],
    exc: Exception,
    expected: str | None = None,
    state: ParserState | None = None,
) -> None:
    file_name = state.file_path.name if state else "<desconhecido>"
    line_no = state.line_no if state else -1
    raw_line = state.raw_line if state else ""
    reason = expected or str(exc)
    cols_repr = str(cols[:_PARSE_WARN_SAMPLE])
    key = ParseWarningKey(event=event_label, reason=reason, file_name=file_name, cols=cols_repr)
    warning_id = _make_warning_id(key)
    count = 1
    if state is not None:
        state.warning_counts[warning_id] += 1
        count = state.warning_counts[warning_id]
    line_info = line_no if line_no != -1 else "desconhecida"
    logger.warning(
        "Parse parcial em %s: %s | esperado=%s | cols=%s | arquivo=%s | linha=%s | id=%s | ocorrencias=%s | log=%s",
        event_label,
        exc,
        expected or "n/d",
        cols_repr,
        file_name,
        line_info,
        warning_id,
        count,
        raw_line[:500],
    )


def parse_timestamp_raw(
    line: str, year_hint: int | None, now: datetime | None = None
) -> tuple[float, str]:
    """Converte 'M/D[/(Y|YY)] HH:MM:SS.mmm...' em epoch + resto."""
    parts = line.split(None, 2)
    if len(parts) < 3:
        raise ValueError(f"Malformed timestamp: {line[:50]}")
    date_str, time_raw, rest = parts
    time_str = _RE_TIMEZONE.sub("", time_raw)

    current_time = now or datetime.now()
    try:
        date_parts = [int(p) for p in date_str.split("/")]
        month, day = date_parts[0], date_parts[1]
        year = year_hint or 2023
        if len(date_parts) >= 3:
            raw_year = date_parts[2]
            year = (
                raw_year + (2000 if raw_year < 70 else 1900)
                if raw_year < 100
                else raw_year
            )

        dt = datetime.strptime(
            f"{month}/{day}/{year} {time_str}", "%m/%d/%Y %H:%M:%S.%f"
        )

        if len(date_parts) < 3 and year_hint is None and (dt - current_time).days > 180:
            dt = dt.replace(year=dt.year - 1)

        return dt.timestamp(), rest
    except (ValueError, IndexError) as e:
        raise ValueError(f"Could not parse timestamp: {date_str} {time_str}") from e


class UnitFlag(IntFlag):
    AFFILIATION_MINE = 0x00000001
    AFFILIATION_PARTY = 0x00000002
    AFFILIATION_RAID = 0x00000004
    AFFILIATION_OUTSIDER = 0x00000008
    AFFILIATION_MASK = 0x0000000F
    REACTION_FRIENDLY = 0x00000010
    REACTION_NEUTRAL = 0x00000020
    REACTION_HOSTILE = 0x00000040
    REACTION_MASK = 0x000000F0
    CONTROL_PLAYER = 0x00000100
    CONTROL_NPC = 0x00000200
    CONTROL_MASK = 0x00000300
    TYPE_PLAYER = 0x00000400
    TYPE_NPC = 0x00000800
    TYPE_PET = 0x00001000
    TYPE_GUARDIAN = 0x00002000
    TYPE_OBJECT = 0x00004000
    TYPE_MASK = 0x0000FC00
    TARGET = 0x00010000
    FOCUS = 0x00020000
    MAINTANK = 0x00040000
    MAINASSIST = 0x00080000
    NONE = 0x00800000
    SPECIAL_MASK = 0xFF000000


class SchoolFlag(IntFlag):
    PHYSICAL = 0x1
    HOLY = 0x2
    FIRE = 0x4
    NATURE = 0x8
    FROST = 0x10
    SHADOW = 0x20
    ARCANE = 0x40


def clear_all_known_caches() -> None:
    """Exposto para testes/CLI: limpa caches LRU conhecidos."""
    parse_unit_flag_cached.cache_clear()
    parse_school_flag_cached.cache_clear()
    logger.debug("Caches globais limpos.")


@lru_cache(maxsize=1024)
def parse_unit_flag_cached(flag: int) -> list[str]:
    return [member.name for member in UnitFlag if flag & member and member.name]


def parse_unit_flag(flag_input: Any) -> list[str]:
    parsed_flag_as_int = parse_value(flag_input, int, default=0)
    return parse_unit_flag_cached(parsed_flag_as_int)


@lru_cache(maxsize=128)
def parse_school_flag_cached(school: int) -> list[str]:
    return [member.name for member in SchoolFlag if school & member and member.name]


def parse_school_flag(school_input: Any) -> list[str]:
    parsed_school_as_int = parse_value(school_input, int, default=0)
    return parse_school_flag_cached(parsed_school_as_int)


def parse_value(
    val: Any,
    typ: type = str,
    default: Any = None,
    pre: Callable[[str], Any] | None = None,
) -> Any:
    if val is None:
        return default
    try:
        text = str(val).strip()
    except Exception:
        return default
    if text.lower() == "nil":
        return default
    if pre is not None:
        return pre(text)
    try:
        if typ is int:
            return int(text, 0)
        if typ is float:
            return float(text)
        if typ is bool:
            parsed_int = parse_value(text, int, default=None)
            return bool(parsed_int) if parsed_int is not None else default
        if typ is str:
            return text
        return typ(text)
    except Exception:
        return default


_parse_int = partial(parse_value, typ=int)
_parse_float = partial(parse_value, typ=float)
_parse_bool_from_int = partial(parse_value, typ=bool)


def parse_int_or_default(s: str, default_val: int = 0) -> int:
    """Converte para int, retornando default em caso de 'nil' ou erro."""
    parsed = _parse_int(s, default=default_val)
    return default_val if parsed is None else parsed


def strip_quotes(s: str) -> str:
    """Remove aspas duplas nas extremidades."""
    try:
        return str(s).strip('"')
    except Exception:
        return str(s)


_to_int = partial(parse_value, typ=int, default=None)
_to_float = partial(parse_value, typ=float, default=None)
def _to_bool(val: Any) -> bool:
    """Converte valor para bool via int intermediário."""
    return bool(_parse_bool_from_int(val, default=None) or 0)


def _coerce_int_or_text(val: Any) -> Any:
    return parsed if (parsed := _parse_int(val, default=None)) is not None else strip_quotes(str(val))


_optional_int = partial(parse_value, typ=int, default=None)
_optional_float = partial(parse_value, typ=float, default=None)
_optional_bool = partial(parse_value, typ=bool, default=None)
def _strip_optional(val: Any) -> str | None:
    """Remove aspas de val ou retorna None se val for None."""
    return None if val is None else strip_quotes(str(val))


Spec = list[tuple[str, int, Callable[[Any], Any] | None]]
SpecSelector = Callable[[list[str]], Spec]


def _map_cols(cols: list[str], spec: Spec) -> dict[str, Any]:
    return {
        field: (
            pre(cols[idx])
            if pre and idx < len(cols)
            else cols[idx] if idx < len(cols) else None
        )
        for field, idx, pre in spec
    }


def _prepare_tasks(
    txt_files: list[Path], output_dir: Path
) -> tuple[list[tuple[Path, Path]], int]:
    tasks = [(fp, output_dir) for fp in txt_files]
    return tasks, 0


def resolve_power_type(pt: int) -> str:
    pt_map = {
        -2: "health",
        0: "mana",
        1: "rage",
        2: "focus",
        3: "energy",
        4: "combo points",
        5: "runes",
        6: "runic power",
        7: "soul shards",
        8: "lunar power",
        9: "holy power",
        10: "alternate",
        11: "maelstrom",
        12: "chi",
        13: "insanity",
        16: "arcane charges",
        17: "fury",
        18: "pain",
        19: "essence",
    }
    return pt_map.get(pt, "unknown")


def _extract_year_hint(file_path: Path) -> int | None:
    """Extrai ano (AAAA) do prefixo do nome do arquivo, se presente."""
    if not (match := _RE_YEAR_PREFIX.match(file_path.stem)):
        return None
    try:
        year = int(match.group("year"))
        return year if year >= 1970 else None
    except ValueError:
        return None


class LogEventParser:
    """Despachante explÃ­cito de eventos de combate."""

    def __init__(self) -> None:
        self.state: ParserState | None = None
        # Eventos "standalone" (parser recebe a linha inteira)
        self.standalone_events = {
            "ENCOUNTER_START": self.parse_encounter,
            "ENCOUNTER_END": self.parse_encounter,
            "ARENA_MATCH_START": self.parse_arena_start,
            "ARENA_MATCH_END": self.parse_arena_end,
            "WORLD_MARKER_PLACED": self.parse_world_marker,
            "WORLD_MARKER_REMOVED": self.parse_world_marker,
            "ZONE_CHANGE": self.parse_zone_change,
        }

        # Prefixos -> parser de prefixo
        self.event_prefix_parsers: dict[str, Callable[..., tuple[dict[str, Any], list[str]]]] = {
            "SWING": partial(self.passthrough_prefix, skip=0),
            "SPELL_BUILDING": self.parse_spell,
            "SPELL_PERIODIC": self.parse_spell,
            "SPELL": self.parse_spell,
            "RANGE": self.parse_spell,
            "ENVIRONMENTAL": partial(
                self.parse_environment_prefix, attr="environmentalType", idx=0, skip=1
            ),
        }
        # Sufixos padronizados
        self.event_suffix_parsers: dict[str, Callable[[list[str]], dict[str, Any]]] = {
            "_AURA_APPLIED": self.parse_aura,
            "_AURA_REMOVED": self.parse_aura,
            "_AURA_APPLIED_DOSE": self.parse_aura_dose,
            "_AURA_REMOVED_DOSE": self.parse_aura_dose,
            "_AURA_REFRESH": self.parse_aura_refresh,
            "_AURA_BROKEN": self.parse_aura,
            "_AURA_BROKEN_SPELL": self.parse_aura_broken,
            "_CAST_START": self.empty_suffix,
            "_CAST_SUCCESS": self.empty_suffix,
            "_CAST_FAILED": self.parse_cast_failed_suffix,
            "_INSTAKILL": self.empty_suffix,
            "_CREATE": self.empty_suffix,
            "_SUMMON": self.empty_suffix,
            "_RESURRECT": self.empty_suffix,
            "_ABSORBED": self.parse_spell_absorbed,
        }
        self.event_suffix_parsers.update(self._build_schema_suffix_parsers())

        # Eventos específicos com (prefixo, sufixo)
        dmg_suffix = self.event_suffix_parsers["_DAMAGE"]
        miss_suffix = self.event_suffix_parsers["_MISS"]
        self.special_events: dict[
            str,
            tuple[
                Callable[..., tuple[dict[str, Any], list[str]]],
                Callable[[list[str]], dict[str, Any]],
            ],
        ] = {
            "DAMAGE_SHIELD": (self.parse_spell, dmg_suffix),
            "DAMAGE_SPLIT": (self.parse_spell, dmg_suffix),
            "DAMAGE_SHIELD_MISSED": (self.parse_spell, miss_suffix),
            "ENCHANT_APPLIED": (self.parse_enchant, self.empty_suffix),
            "ENCHANT_REMOVED": (self.parse_enchant, self.empty_suffix),
            "PARTY_KILL": (partial(self.passthrough_prefix, skip=0), self.empty_suffix),
            "UNIT_DIED": (partial(self.passthrough_prefix, skip=0), self.empty_suffix),
            "UNIT_DESTROYED": (
                partial(self.passthrough_prefix, skip=0),
                self.empty_suffix,
            ),
        }

        # Dispatch pré-computado: event_name -> (prefix_handler, suffix_handler)
        self._dispatch_table: dict[str, tuple[Callable[..., tuple[dict[str, Any], list[str]]], Callable[[list[str]], dict[str, Any]]]] = {}
        prefixes = ("SPELL_BUILDING", "SPELL_PERIODIC", "ENVIRONMENTAL", "SWING", "SPELL", "RANGE")
        for prefix in prefixes:
            prefix_handler = self.event_prefix_parsers[prefix]
            for suffix, suffix_handler in self.event_suffix_parsers.items():
                event_name = f"{prefix}{suffix}"
                self._dispatch_table[event_name] = (prefix_handler, suffix_handler)

    @staticmethod
    def _schema_min_cols(spec: Spec) -> int:
        return 1 + max(idx for _, idx, _ in spec)

    def _schema_handler_generic(
        self, label: str, spec: Spec
    ) -> Callable[[list[str]], dict[str, Any]]:
        required = self._schema_min_cols(spec)

        def handler(cols: list[str]) -> dict[str, Any]:
            if len(cols) < required:
                _log_parse_warning(
                    label,
                    cols,
                    ValueError(f"Insufficient {label} data"),
                    expected=f">= {required} cols",
                    state=self.state,
                )
                return {"error": f"Insufficient {label} data", "data": cols}
            return _map_cols(cols, spec)

        return handler

    def _build_schema_suffix_parsers(
        self,
    ) -> dict[str, Callable[[list[str]], dict[str, Any]]]:
        def _parse_damage_suffix(cols: list[str]) -> dict[str, Any]:
            spec = choose_damage_spec(cols)
            mapped = _map_cols(cols, spec)
            payload = {k: v for k, v in mapped.items() if v is not None}
            if (school := payload.get("school")) is not None:
                payload["schoolNames"] = parse_school_flag(school)
            return payload

        def _parse_heal_suffix(cols: list[str]) -> dict[str, Any]:
            spec = choose_heal_spec(cols)
            mapped = _map_cols(cols, spec)
            return {k: v for k, v in mapped.items() if v is not None}

        def _parse_miss_suffix(cols: list[str]) -> dict[str, Any]:
            mapped = _map_cols(cols, MISS_SPEC)
            payload = {k: v for k, v in mapped.items() if v is not None}
            payload["amountMissed"] = payload.get("amountMissed") or payload.get(
                "amountResisted"
            )
            return payload

        def _parse_energize_suffix(cols: list[str]) -> dict[str, Any]:
            mapped = _map_cols(cols, ENERGIZE_SPEC)
            return {k: v for k, v in mapped.items() if v is not None}

        parsers: dict[str, Callable[[list[str]], dict[str, Any]]] = {
            "_DAMAGE": _parse_damage_suffix,
            "_DAMAGE_LANDED": _parse_damage_suffix,
            "_HEAL": _parse_heal_suffix,
            "_MISS": _parse_miss_suffix,
            "_ENERGIZE": _parse_energize_suffix,
            "_DRAIN": self._schema_handler_generic("DRAIN", DRAIN_SPEC),
            "_LEECH": self._schema_handler_generic("LEECH", LEECH_SPEC),
            "_EXTRA_ATTACKS": self._schema_handler_generic(
                "EXTRA_ATTACKS", EXTRA_ATTACKS_SPEC
            ),
            "_SPELL_BLOCK": self._schema_handler_generic(
                "SPELL_BLOCK", SPELL_BLOCK_SPEC
            ),
        }
        return parsers

    @staticmethod
    def passthrough_prefix(cols: list[str], skip: int = 0) -> tuple[dict[str, Any], list[str]]:
        return {}, cols[skip:]

    @staticmethod
    def parse_environment_prefix(
        cols: list[str], attr: str = "environmentalType", idx: int = 0, skip: int = 1
    ) -> tuple[dict[str, Any], list[str]]:
        return {attr: cols[idx]}, cols[skip:]

    def parse_spell(self, cols: list[str]) -> tuple[dict[str, Any], list[str]]:
        if len(cols) < 3:
            return {"error": "Spell data incomplete", "raw_cols": cols}, cols
        spell_school = parse_int_or_default(cols[2])
        payload = {
            "spellId": parse_int_or_default(cols[0]),
            "spellName": strip_quotes(cols[1]),
            "spellSchool": spell_school,
            "spellSchoolNames": parse_school_flag(school_input=spell_school),
        }
        return payload, cols[3:]

    def parse_aura(self, cols: list[str]) -> dict[str, Any]:
        if not cols:
            _log_parse_warning("AURA", cols, ValueError("No AURA data"), state=self.state)
            return {"error": "No AURA data"}
        try:
            r: dict[str, Any] = {"auraType": strip_quotes(cols[0])}
            if len(cols) > 1 and (amt := cols[1]) != "nil":
                r["amount"] = parse_int_or_default(amt)
            return r
        except (IndexError, ValueError, TypeError) as e:
            _log_parse_warning("AURA", cols, e, state=self.state)
            return {"error": f"Failed to parse aura data: {e}", "raw_cols": cols[:2]}

    def parse_aura_refresh(self, cols: list[str]) -> dict[str, Any]:
        if not cols:
            _log_parse_warning(
                "AURA_REFRESH",
                cols,
                ValueError("No aura refresh data"),
                expected="[auraType[, amount]]",
                state=self.state,
            )
            return {"error": "No aura refresh data"}
        payload: dict[str, Any] = {"auraType": strip_quotes(cols[0])}
        if len(cols) > 1 and (amt := cols[1]) != "nil":
            payload["amount"] = parse_int_or_default(amt)
        return payload

    def parse_aura_dose(self, cols: list[str]) -> dict[str, Any]:
        # AURA_DOSE deve ter exatamente [auraType, newDose]; qualquer outro formato é inválido.
        if len(cols) < 2:
            _log_parse_warning(
                "AURA_DOSE",
                cols,
                ValueError("Incomplete AURA_DOSE data"),
                state=self.state,
            )
            return {"error": "Incomplete AURA_DOSE data", "data": cols}
        try:
            return {
                "auraType": strip_quotes(cols[0]),
                "newDose": parse_int_or_default(cols[1]),
            }
        except (IndexError, ValueError) as e:
            _log_parse_warning("AURA_DOSE", cols, e, state=self.state)
            return {"error": f"Parse error: {e}", "data": cols}

    def parse_aura_broken(self, cols: list[str]) -> dict[str, Any]:
        if not cols or len(cols) < 4:
            _log_parse_warning(
                "AURA_BROKEN", cols, ValueError("No AURA_BROKEN data"), state=self.state
            )
            return {"error": "No AURA_BROKEN data"}
        try:
            return {
                "extraSpellId": parse_int_or_default(cols[0]),
                "extraSpellName": strip_quotes(cols[1]),
                "extraSchool": parse_int_or_default(cols[2]),
                "auraType": strip_quotes(cols[3]),
            }
        except (IndexError, ValueError) as e:
            _log_parse_warning("AURA_BROKEN", cols, e, state=self.state)
            return {"error": f"Parse error: {e}", "data": cols}

    def parse_enchant(self, cols: list[str]) -> tuple[dict[str, Any], list[str]]:
        if not cols or len(cols) < 3:
            return {}, cols
        enc = {
            "enchantName": strip_quotes(cols[0]),
            "itemId": parse_int_or_default(cols[1]),
            "itemName": strip_quotes(cols[2]),
        }
        return enc, cols[3:]

    def parse_encounter(self, cols: list[str]) -> dict[str, Any]:
        if not cols or len(cols) < 4:
            _log_parse_warning(
                "ENCOUNTER",
                cols,
                ValueError("Encounter data incomplete"),
                state=self.state,
            )
            return {"error": "Encounter data incomplete"}
        try:
            return {
                "encounterId": int(cols[0]),
                "encounterName": strip_quotes(cols[1]),
                "difficultyId": int(cols[2]),
                "groupSize": int(cols[3]),
            }
        except (ValueError, IndexError) as e:
            _log_parse_warning("ENCOUNTER", cols, e, state=self.state)
            return {"error": f"Failed to parse ENCOUNTER data: {e}"}

    def parse_arena_start(self, cols: list[str]) -> dict[str, Any]:
        if not cols or len(cols) < 4:
            return {"error": "Arena start data incomplete"}

        payload: dict[str, Any] = {
            "instanceId": _coerce_int_or_text(cols[0]),
            "mapId": _coerce_int_or_text(cols[1]),
            "matchType": strip_quotes(cols[2]),
        }
        if len(cols) > 3:
            payload["teamSize"] = _coerce_int_or_text(cols[3])
        if len(cols) > 4:
            payload["extraFields"] = [strip_quotes(tok) for tok in cols[4:]]
        return payload

    def parse_arena_end(self, cols: list[str]) -> dict[str, Any]:
        if not cols or len(cols) < 4:
            return {"error": "Arena end data incomplete"}
        return {
            "winningTeamId": int(cols[0]),
            "matchDuration": int(cols[1]),
            "newRatingTeam1": int(cols[2]),
            "newRatingTeam2": int(cols[3]),
        }

    def parse_spell_absorbed(self, cols: list[str]) -> dict[str, Any]:
        if not cols or len(cols) < 7:
            _log_parse_warning(
                "SPELL_ABSORBED",
                cols,
                ValueError("No spell absorbed data"),
                state=self.state,
            )
            return {"error": "No spell absorbed data"}
        try:
            return {
                "casterGuid": cols[0],
                "casterName": strip_quotes(cols[1]),
                "absorbSpellId": parse_int_or_default(cols[2]),
                "absorbSpellName": strip_quotes(cols[3]),
                "absorbedAmount": parse_int_or_default(cols[4]),
                "totalAbsorbed": parse_int_or_default(cols[5]),
                "isCritical": bool(parse_int_or_default(cols[6])),
            }
        except (IndexError, ValueError) as e:
            _log_parse_warning("SPELL_ABSORBED", cols, e, state=self.state)
            return {"error": f"Parse error: {e}", "data": cols}

    def parse_world_marker(self, cols: list[str]) -> dict[str, Any]:
        # Remoção: normalmente só vem o flag (ex.: SKULL).
        if len(cols) == 1:
            return {"removed": True, "flag": cols[0]}
        if len(cols) < 4:
            _log_parse_warning(
                "WORLD_MARKER",
                cols,
                ValueError("Insufficient data for WORLD_MARKER"),
                state=self.state,
            )
            return {"error": "Insufficient data for WORLD_MARKER", "data": cols}
        try:
            map_id = parse_value(cols[0], int, default=0)
            marker_id = parse_value(cols[1], int, default=0)
            x_coord = parse_value(cols[2], float, default=0.0)
            y_coord = parse_value(cols[3], float, default=0.0)
            payload: dict[str, Any] = {
                "mapId": map_id,
                "markerId": marker_id,
                "x": x_coord,
                "y": y_coord,
            }
            if len(cols) > 4:
                payload["z"] = parse_value(cols[4], float, default=0.0)
            return payload
        except (ValueError, IndexError) as e:
            _log_parse_warning("WORLD_MARKER", cols, e, state=self.state)
            return {"error": f"Parse error: {e}", "data": cols}

    def parse_zone_change(self, cols: list[str]) -> dict[str, Any]:
        if len(cols) < 3:
            return {"error": f"Invalid format for ZONE_CHANGE: {cols}"}
        r: dict[str, Any] = {
            "zoneId": cols[1],
            "zoneName": cols[2].strip("'\""),
        }
        if len(cols) >= 4:
            r["zoneFlag"] = cols[3]
        return r

    @staticmethod
    def empty_suffix(_: list[str]) -> dict[str, Any]:
        return {}

    @staticmethod
    def parse_cast_failed_suffix(cols: list[str]) -> dict[str, Any]:
        return {"failedType": strip_quotes(cols[0])}

    def _parse_base_parameters(
        self, cols: list[str], obj: dict[str, Any]
    ) -> dict[str, Any]:
        if len(cols) < 9:
            raise ValueError(f"Invalid format for {cols[0]}: insufficient columns")
        (
            source_guid,
            source_name,
            source_flags,
            source_raid_flags,
            dest_guid,
            dest_name,
            dest_flags,
            dest_raid_flags,
        ) = cols[1:9]
        obj.update({
            "sourceGUID": source_guid,
            "sourceName": strip_quotes(source_name),
            "sourceFlags": parse_unit_flag(source_flags),
            "sourceRaidFlags": parse_unit_flag(source_raid_flags),
            "destGUID": dest_guid,
            "destName": strip_quotes(dest_name),
            "destFlags": parse_unit_flag(dest_flags),
            "destRaidFlags": parse_unit_flag(dest_raid_flags),
        })
        return obj

    def _compose_event(
        self, obj: dict[str, Any], handlers: tuple[Any, Any], cols: list[str]
    ) -> dict[str, Any]:
        result = self._parse_base_parameters(cols, obj)
        prefix_handler, suffix_handler = handlers
        prefix_data, rest = prefix_handler(cols[9:])
        suffix_data = suffix_handler(rest)
        result.update(prefix_data)
        result.update(suffix_data)
        return result

    def _bind_if_needed(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Vincula função ao self se necessário (para partials e métodos não-bound)."""
        if getattr(fn, "__self__", None) is not None:
            return fn
        if hasattr(fn, "__code__") and fn.__code__.co_argcount >= 2:
            bound: Callable[..., Any] = fn.__get__(self, self.__class__)
            return bound
        return fn

    def _dispatch_by_prefix(
        self, event_name: str, base: dict[str, Any], cols: list[str]
    ) -> dict[str, Any] | None:
        """Tenta despachar evento por lookup direto em _dispatch_table. Retorna None se não encontrado."""
        if handlers := self._dispatch_table.get(event_name):
            prefix_handler, suffix_handler = handlers
            bound_handlers = (self._bind_if_needed(prefix_handler), self._bind_if_needed(suffix_handler))
            return self._compose_event(base, bound_handlers, cols)
        return None

    def _dispatch_standalone(
        self, event_name: str, base: dict[str, Any], cols: list[str]
    ) -> dict[str, Any] | None:
        """Despacha eventos standalone (sem prefixo/sufixo). Retorna None se não for standalone."""
        if parser := self.standalone_events.get(event_name):
            base.update(parser(cols[1:]))
            return base
        return None

    def _dispatch_special(
        self, event_name: str, base: dict[str, Any], cols: list[str]
    ) -> dict[str, Any] | None:
        """Despacha eventos especiais (DAMAGE_SHIELD, ENCHANT, etc). Retorna None se não for especial."""
        if handlers := self.special_events.get(event_name):
            prefix_handler, suffix_handler = handlers
            bound = (self._bind_if_needed(prefix_handler), self._bind_if_needed(suffix_handler))
            return self._compose_event(base, bound, cols)
        return None

    def dispatch(self, ts: float, cols: list[str]) -> dict[str, Any]:
        event_name = cols[0]
        base: dict[str, Any] = {"timestamp": ts, "event": event_name}

        if result := self._dispatch_standalone(event_name, base, cols):
            return result
        if result := self._dispatch_special(event_name, base, cols):
            return result
        if result := self._dispatch_by_prefix(event_name, base, cols):
            return result
        base["unparsed_params"] = cols[1:]
        return base


def choose_damage_spec(cols: list[str]) -> Spec:
    return DAMAGE_LONG_SPEC if len(cols) >= 10 else DAMAGE_SHORT_SPEC


def choose_heal_spec(cols: list[str]) -> Spec:
    return HEAL_LONG_SPEC if len(cols) >= 7 else HEAL_SHORT_SPEC


DAMAGE_LONG_SPEC: Spec = [
    ("target_guid", 0, _strip_optional),
    ("target_name", 1, _strip_optional),
    ("amount", 2, _optional_int),
    ("overkill", 3, _optional_int),
    ("school", 4, _optional_int),
    ("resisted", 5, _optional_int),
    ("blocked", 6, _optional_int),
    ("absorbed", 7, _optional_int),
    ("critical", 8, _optional_bool),
    ("glancing", 9, _optional_bool),
    ("crushing", 10, _optional_bool),
    ("is_off_hand", 11, _optional_bool),
    ("multistrike", 12, _optional_bool),
]
DAMAGE_SHORT_SPEC: Spec = [
    ("amount", 0, _optional_int),
    ("overkill", 1, _optional_int),
    ("school", 2, _optional_int),
    ("resisted", 3, _optional_int),
    ("blocked", 4, _optional_int),
    ("absorbed", 5, _optional_int),
    ("critical", 6, _optional_bool),
    ("glancing", 7, _optional_bool),
    ("crushing", 8, _optional_bool),
    ("is_off_hand", 9, _optional_bool),
]
HEAL_LONG_SPEC: Spec = [
    ("target_guid", 0, _strip_optional),
    ("target_name", 1, _strip_optional),
    ("amount", 2, _optional_int),
    ("overhealing", 3, _optional_int),
    ("absorbed", 4, _optional_int),
    ("critical", 5, _optional_bool),
    ("multistrike", 6, _optional_bool),
]
HEAL_SHORT_SPEC: Spec = [
    ("amount", 0, _optional_int),
    ("overhealing", 1, _optional_int),
    ("absorbed", 2, _optional_int),
    ("critical", 3, _optional_bool),
    ("multistrike", 4, _optional_bool),
]
MISS_SPEC: Spec = [
    ("missType", 0, _strip_optional),
    ("isOffHand", 1, _optional_bool),
    ("amountMissed", 2, _optional_int),
    ("amountAbsorbed", 3, _optional_int),
    ("amountResisted", 4, _optional_int),
]
ENERGIZE_SPEC: Spec = [
    ("amount", 0, _optional_float),
    ("power_type", 1, resolve_power_type),
    ("extra_amount", 2, _optional_float),
    ("max_power", 3, _optional_float),
]
DRAIN_SPEC: Spec = [
    ("amount", 0, _optional_int),
    ("powerType", 1, lambda v: resolve_power_type(parse_int_or_default(v))),
    ("extraAmount", 2, _optional_int),
]
LEECH_SPEC: Spec = [
    ("amount", 0, _optional_int),
    ("extraAmount", 1, _optional_int),
]
EXTRA_ATTACKS_SPEC: Spec = [
    ("amount", 0, _optional_int),
]
SPELL_BLOCK_SPEC: Spec = [
    ("extraSpellId", 0, _optional_int),
    ("extraSpellName", 1, _strip_optional),
    ("extraSchool", 2, _optional_int),
]


class CombatLogProcessor:
    def __init__(self, year_hint: int | None = None) -> None:
        # Parser especializado para COMBATANT_INFO e dispatcher explicito para demais eventos
        self.ci_parser = CombatantInfoParser()
        self.event_parser = LogEventParser()
        self.year_hint = year_hint
        self.state: ParserState | None = None
        self._current_file: Path | None = None

    def set_file_context(self, file_path: Path) -> None:
        self._current_file = file_path

    def set_state(self, state: ParserState) -> None:
        self.state = state
        self.event_parser.state = state

    def parse_line(self, line: str) -> dict[str, Any] | None:
        ts, csv_text = parse_timestamp_raw(line, self.year_hint)
        cols = csv_text.split(",")
        event_name = cols[0].strip()
        match event_name:
            case "":
                raise ValueError("Empty CSV or missing event after timestamp")
            case "COMBATANT_INFO":
                payload = self.ci_parser.parse(ts, csv_text)
                result: dict[str, Any] = {"timestamp": ts, "event": event_name}
                result.update(payload)
                return result
            case _:
                cols = [col.strip() for col in cols]
                match event_name:
                    case "SPELL_SUMMON" if len(cols) < 12:
                        _log_parse_warning(
                            "SPELL_SUMMON",
                            cols,
                            ValueError("Incomplete SPELL_SUMMON line"),
                            expected="source/dest (8 cols) + spellId, spellName, spellSchool",
                            state=self.state,
                        )
                        return None
                    case "ENCHANT_APPLIED" | "ENCHANT_REMOVED" if len(cols) < 9:
                        raise ValueError(f"Incomplete line for {event_name}")
                return self.parse_cols(ts, cols)

    def parse_cols(self, ts: float, cols: list[str]) -> dict[str, Any] | None:
        return self.event_parser.dispatch(ts, cols)


# -------------------- Pipeline de processamento --------------------

# Alias de compatibilidade para manter interface anterior.
CombatantInfoProcessor = CombatLogProcessor


@dataclass(slots=True)
class Config:
    input_dir: Path
    output_dir: Path
    max_workers: int | None


def load_config_from_env() -> Config:
    default_input = PROJECT_ROOT / "logs"
    input_dir = Path(os.getenv("WOW_LOG_INPUT_DIR", default_input))
    output_dir = LOG_DIR
    workers_env = os.getenv("WOW_MAX_WORKERS")
    max_workers = int(workers_env) if workers_env and workers_env.isdigit() else None
    return Config(
        input_dir=input_dir,
        output_dir=output_dir,
        max_workers=max_workers,
    )


def read_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Source: le o arquivo linha a linha."""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for idx, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if line:
                yield idx, line


class EventStream(Iterable[dict[str, Any]]):
    def __init__(self, generator: Iterator[dict[str, Any]], state: ParserState) -> None:
        self._generator = generator
        self.state = state

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return self._generator


def _extract_event_hint(line: str) -> str | None:
    parts = line.split(None, 2)
    if len(parts) < 3:
        return None
    csv_part = parts[2]
    event_name = csv_part.split(",", 1)[0].strip()
    return event_name or None


def parse_events(
    lines: Iterable[tuple[int, str]],
    parser: CombatLogProcessor,
    src: Path | None = None,
) -> EventStream:
    """Transform: converte texto em dict de evento."""
    src_path = src or Path("<desconhecido>")
    state = ParserState(file_path=src_path)
    if hasattr(parser, "set_state"):
        parser.set_state(state)

    def _gen() -> Iterator[dict[str, Any]]:
        for state.line_no, state.raw_line in lines:
            try:
                if parsed := parser.parse_line(state.raw_line):
                    # Auditoria opcional: hash curto da linha bruta; remova se nao precisar.
                    parsed["lh"] = hashlib.blake2s(
                        state.raw_line.encode("utf-8", "replace"), digest_size=4
                    ).hexdigest()
                    yield parsed
            except ValueError as exc:
                event_hint = _extract_event_hint(state.raw_line)
                if event_hint == "COMBATANT_INFO":
                    state.skip_reason = (
                        f"COMBATANT_INFO malformado na linha {state.line_no}: {exc}"
                    )
                else:
                    state.malformed_lines += 1
                    if state.malformed_lines >= 2:
                        state.skip_reason = (
                            f"Mais de uma linha malformada; ultima na linha {state.line_no}: {exc}"
                        )
                logger.warning(
                    "Linha ignorada (%s): %s | arquivo=%s | linha=%s",
                    exc,
                    state.raw_line.strip(),
                    src_path.name,
                    state.line_no,
                )
                if state.skip_reason:
                    logger.warning(
                        "Arquivo %s sera pulado: %s",
                        src_path.name,
                        state.skip_reason,
                    )
                    break
                continue

    return EventStream(_gen(), state)


def _write_events_streaming(
    parser: CombatLogProcessor, src: Path, dst: Path
) -> str | None:
    """Converte um .txt em NDJSON sem manter tudo em memoria."""
    lines = read_lines(src)
    parser.set_file_context(src)
    events = parse_events(lines, parser, src)
    tmp_dst = dst.with_suffix(dst.suffix + ".part")
    with tmp_dst.open("wb", buffering=JSON_WRITE_BUFFER_BYTES) as handle:
        for ev in events:
            handle.write(orjson.dumps(ev))
            handle.write(b"\n")

    state: ParserState | None = getattr(events, "state", None)
    if state and state.skip_reason:
        return state.skip_reason

    tmp_dst.replace(dst)
    return None


def process_single_file(args: tuple[Path, Path]) -> tuple[bool, list[str]]:
    _configure_stdout()
    _configure_logging(for_worker=True)
    file_path, output_dir = args
    output_file = output_dir / f"{file_path.stem}.json"
    parser = CombatLogProcessor(year_hint=_extract_year_hint(file_path))
    try:
        skip_reason = _write_events_streaming(parser, file_path, output_file)
        if skip_reason:
            msg = f"Arquivo {file_path.name} pulado: {skip_reason}"
            logger.warning("%s", msg)
            file_logger.warning("%s", msg)
            return False, [msg]
    except (OSError, ValueError) as exc:
        err_type = exc.__class__.__name__
        msg = f"Erro ao converter {file_path.name} [{err_type}]: {exc}"
        logger.exception("%s", msg)
        file_logger.exception("%s", msg)
        return False, [msg]
    except Exception as exc:  # pragma: no cover - fallback para erros inesperados
        err_type = exc.__class__.__name__
        msg = f"Erro inesperado ao converter {file_path.name} [{err_type}]: {exc}"
        logger.exception("%s", msg)
        file_logger.exception("%s", msg)
        return False, [msg]
    return True, []


def process_files(
    txt_files: list[Path],
    output_dir: Path,
    *,
    max_workers: int | None = None,
    max_files: int | None = None,
) -> None:
    workers_env = os.getenv("WOW_MAX_WORKERS")
    resolved_max_workers = (
        max(1, max_workers)
        if max_workers is not None
        else max(1, int(workers_env))
        if workers_env and workers_env.isdigit()
        else min(2, cpu_count())
    )

    args_list, skipped_existing = _prepare_tasks(txt_files, output_dir)
    if max_files is not None and max_files > 0:
        args_list = sorted(args_list, key=lambda t: t[0].stat().st_size)[:max_files]
    if skipped_existing:
        logger.info("Pulando %s arquivo(s) ja convertidos.", skipped_existing)
    if not args_list:
        logger.info("Nenhum arquivo novo para converter.")
        return

    converted, aggregated_errors = _run_conversion_batch(
        args_list, resolved_max_workers
    )

    skipped = len(args_list) - converted
    logger.info("Arquivos convertidos: %s; pulados: %s", converted, skipped)
    if aggregated_errors:
        _log_aggregated_errors(aggregated_errors)


def _run_conversion_batch(
    args_list: list[tuple[Path, Path]], max_workers: int
) -> tuple[int, dict[str, int]]:
    aggregated_errors: dict[str, int] = defaultdict(int)
    converted = 0
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for success, errors in tqdm(
            executor.map(process_single_file, args_list, chunksize=4),
            total=len(args_list),
            desc="Convertendo logs",
        ):
            converted += bool(success)
            for msg in errors:
                aggregated_errors[msg] += 1
    return converted, aggregated_errors


def check_and_create_directories(input_dir: Path, output_dir: Path) -> None:
    for name, path in [("Input", input_dir), ("Output", output_dir)]:
        path.mkdir(parents=True, exist_ok=True)
        logger.info("OK %s directory: %s", name, path)


def main() -> None:
    _configure_stdout()
    _configure_logging()
    cfg = load_config_from_env()
    check_and_create_directories(cfg.input_dir, cfg.output_dir)
    max_files = (
        int(sys.argv[1][1:])
        if len(sys.argv) > 1
        and sys.argv[1].startswith("-")
        and sys.argv[1][1:].isdigit()
        else None
    )
    process_files(
        list(cfg.input_dir.glob("*.txt")),
        cfg.output_dir,
        max_workers=cfg.max_workers,
        max_files=max_files,
    )
    logger.info("Conversao concluida com sucesso.")


if __name__ == "__main__":
    main()
