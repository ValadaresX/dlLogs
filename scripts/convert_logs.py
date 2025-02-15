import ast
import json
import logging
import os
import re
import sys
import time
from datetime import datetime  # Certifique-se de importar datetime
from functools import lru_cache
from multiprocessing import Pool, cpu_count
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table
from rich.theme import Theme
from tqdm import tqdm

if str(getattr(sys.stdout, "encoding", "")).lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    stream=sys.stdout,
    encoding="utf-8",  # Garante que a saída seja em UTF-8
)

TIMESTAMP_REGEX = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}(?:/\d{4})?)\s+"
    r"(?P<time>\d{1,2}:\d{2}:\d{2}\.\d+)"  # permite 3 ou mais dígitos após o ponto
    r"(?P<offset>[+-]\d+)?\s+(?P<rest>.*)$"
)
# Cache para evitar chamar strptime repetidamente
TIMESTAMP_CACHE = {}

# Define icons
ICON_CHECK = "[OK]"
ICON_CREATE = "[CREATE]"
ICON_CONVERTING = "[CONVERTING]"
ICON_SUCCESS = "[SUCCESS]"
ICON_TIME = "[TIME]"
ICON_SPEED = "[SPEED]"

# Pré-computa o mapeamento de flags para parse_unit_flag
_UNIT_FLAG_MAP = {
    0x00000001: "AFFILIATION_MINE",
    0x00000002: "AFFILIATION_PARTY",
    0x00000004: "AFFILIATION_RAID",
    0x00000008: "AFFILIATION_OUTSIDER",
    0x0000000F: "AFFILIATION_MASK",
    0x00000010: "REACTION_FRIENDLY",
    0x00000020: "REACTION_NEUTRAL",
    0x00000040: "REACTION_HOSTILE",
    0x000000F0: "REACTION_MASK",
    0x00000100: "CONTROL_PLAYER",
    0x00000200: "CONTROL_NPC",
    0x00000300: "CONTROL_MASK",
    0x00000400: "TYPE_PLAYER",
    0x00000800: "TYPE_NPC",
    0x00001000: "TYPE_PET",
    0x00002000: "TYPE_GUARDIAN",
    0x00004000: "TYPE_OBJECT",
    0x0000FC00: "TYPE_MASK",
    0x00010000: "TARGET",
    0x00020000: "FOCUS",
    0x00040000: "MAINTANK",
    0x00080000: "MAINASSIST",
    0x00800000: "NONE",
    0xFF000000: "SPECIAL_MASK",
}

# Pré-computa o mapeamento de school flags
_SCHOOL_FLAG_MAP = {
    0x1: "Physical",
    0x2: "Holy",
    0x4: "Fire",
    0x8: "Nature",
    0x10: "Frost",
    0x20: "Shadow",
    0x40: "Arcane",
}


@lru_cache(maxsize=None)
def parse_unit_flag_cached(flag: int) -> list:
    return [_UNIT_FLAG_MAP[k] for k in _UNIT_FLAG_MAP if flag & k]


def parse_unit_flag(flag):
    """
    Converte o parâmetro 'flag' para inteiro (se for string) e utiliza o
    cache para interpretar os flags.
    Captura apenas ValueError e TypeError durante a conversão.
    """
    try:
        f = int(flag, 0) if isinstance(flag, str) else flag
    except (ValueError, TypeError):
        f = 0
    return parse_unit_flag_cached(f)


@lru_cache(maxsize=None)
def parse_school_flag_cached(school: int) -> list:
    return [_SCHOOL_FLAG_MAP[k] for k in _SCHOOL_FLAG_MAP if school & k]


def parse_school_flag(school):
    """
    Converte o parâmetro 'school' para inteiro (se for string)
    e utiliza o cache para interpretar os flags de escola.
    Captura apenas ValueError e TypeError durante a conversão.

    Args:
        school (int or str): The school flag.

    Returns:
        list: A list of school names.
    """
    try:
        s = int(school, 0) if isinstance(school, str) else school
    except (ValueError, TypeError):
        s = 0
    return parse_school_flag_cached(s)


def resolv_power_type(pt):
    """
    Map game power types to their respective names.

    Args:
        pt (int): The abbreviation of the power type.

    Returns:
        str: The corresponding power type name.
    """
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
        14: "obsolete",
        15: "obsolete2",
        16: "arcane charges",
        17: "fury",
        18: "pain",
        19: "essence",
        20: "rune blood",
        21: "rune frost",
        22: "rune unholy",
        23: "alternate quest",
        24: "alternate encounter",
        25: "alternate mount",
        26: "num power types",
    }
    return pt_map.get(pt)


class SpellParser:
    def parse(self, cols):
        return (
            {
                "spellId": cols[0],
                "spellName": cols[1].strip('"'),
                "spellSchool": parse_school_flag(cols[2]),
            },
            cols[3:],
        )


class EnvParser:
    def parse(self, cols):
        return ({"environmentalType": cols[0]}, cols[1:])


class SwingParser:
    def parse(self, cols):
        return ({}, cols)


class WorldPrefixParser:
    def parse(self, cols):
        return ({}, cols[1:])


class WorldMarkerParser:
    def parse(self, cols):
        return {
            "mapId": int(cols[1]),
            "markerId": int(cols[2]),
            "x": float(cols[3]),
            "y": float(cols[4]),
        }


class DamageParser:
    def parse(self, cols):
        # Suporte para logs legados com menos de 25 colunas (por exemplo, 9 ou 10 colunas)
        if len(cols) < 25:
            if len(cols) >= 9:
                try:
                    return {
                        "amount": int(cols[0]),
                        "overkill": cols[1],
                        "school": parse_school_flag(cols[2]),
                        "resisted": float(cols[3]) if cols[3] != "nil" else 0.0,
                        "blocked": float(cols[4]) if cols[4] != "nil" else 0.0,
                        "absorbed": float(cols[5]) if cols[5] != "nil" else 0.0,
                        "critical": cols[6] != "nil",
                        "glancing": cols[7] != "nil",
                        "crushing": cols[8] != "nil",
                    }
                except (ValueError, TypeError, IndexError) as error:
                    logging.error(
                        "Erro ao converter log legado no DamageParser: %s", error
                    )
                    logging.debug("Contexto legado: %s", cols)
                    return {}
            else:
                logging.error(
                    "Colunas insuficientes para DamageParser em log legado: %s colunas recebidas.",
                    len(cols),
                )
                logging.debug("Contexto legado: %s", cols)
                return {}

        # Lógica para a versão mais nova do log (mínimo de 25 colunas)
        def parse_val(value, type_cast, field_name, index):
            try:
                if value == "nil":
                    return 0 if type_cast == int else 0.0
                return type_cast(value)
            except (ValueError, TypeError) as error:
                error_msg = "Campo %s (índice %s) valor '%s': %s" % (
                    field_name,
                    index,
                    value,
                    str(error).split(":")[-1].strip(),
                )
                logging.error("%s", error_msg)
                logging.debug("Contexto completo: %s", cols)
                return 0

        return {
            "amount": parse_val(cols[16], int, "amount", 16),
            "overkill": cols[17],
            "school": parse_school_flag(cols[18]),
            "resisted": parse_val(cols[19], float, "resisted", 19),
            "blocked": parse_val(cols[20], float, "blocked", 20),
            "absorbed": parse_val(cols[21], float, "absorbed", 21),
            "critical": cols[22] != "nil",
            "glancing": cols[23] != "nil",
            "crushing": cols[24] != "nil",
        }


class MissParser:
    def parse(self, cols):
        obj = {
            "missType": cols[0],
            "isOffHand": None if cols[1].lower() == "nil" else cols[1],
        }

        # Processa campos adicionais de forma concisa
        for i, val in enumerate(cols[2:], start=2):
            if i == 2:
                try:
                    obj["amountMissed"] = int(val)
                except (ValueError, IndexError):
                    obj["unknownField"] = val
            else:
                obj.setdefault("extraFields", []).append(val)

        return obj


class HealParser:
    def parse(self, cols):
        cols = cols[8:]

        def parse_i(x):
            return 0 if x == "nil" else int(x)

        return {
            "amount": parse_i(cols[0]),
            "overhealing": parse_i(cols[1]),
            "absorbed": parse_i(cols[2]),
            "critical": cols[3] != "nil",
        }


class HealAbsorbedParser:
    def parse(self, cols):
        def parse_i(x):
            return 0 if x == "nil" else int(x)

        return {
            "casterGUID": cols[0],
            "casterName": cols[1],
            "casterFlags": parse_unit_flag(cols[2]),
            "casterRaidFlags": parse_unit_flag(cols[3]),
            "absorbSpellId": cols[4],
            "absorbSpellName": cols[5],
            "absorbSpellSchool": parse_school_flag(cols[6]),
            "amount": parse_i(cols[7]),
            "totalAmount": parse_i(cols[8]),
            "critical": cols[8] != "nil",
        }


class EnergizeParser:
    def parse(self, cols):
        cols = cols[8:]

        def parse_i(x):
            return 0 if x == "nil" else int(x)

        return {
            "amount": parse_i(cols[0]),
            "powerType": resolv_power_type(cols[1]),
        }


class DrainParser:
    def parse(self, cols):
        def parse_i(x):
            return 0 if x == "nil" else int(x)

        def parse_f(x):
            return 0.0 if x == "nil" else float(x)

        amount = parse_i(cols[11])
        powerType = resolv_power_type(cols[12])
        maxPower = parse_f(cols[13])
        extraAmount = parse_f(cols[14])
        return {
            "amount": amount,
            "powerType": powerType,
            "maxPower": maxPower,
            "extraAmount": extraAmount,
        }


class LeechParser:
    def parse(self, cols):
        def parse_i(x):
            return 0 if x == "nil" else int(x)

        return {
            "amount": parse_i(cols[0]),
            "powerType": resolv_power_type(cols[1]),
            "extraAmount": parse_i(cols[2]),
        }


class SpellBlockParser:
    def parse(self, cols):
        obj = {
            "extraSpellID": cols[0],
            "extraSpellName": cols[1],
            "extraSchool": parse_school_flag(cols[2]),
        }
        if len(cols) == 4:
            obj["auraType"] = cols[3]
        return obj


class ExtraAttackParser:
    def parse(self, cols):
        def parse_i(x):
            return 0 if x == "nil" else int(x)

        return {"amount": parse_i(cols[0])}


class AuraParser:
    def parse(self, cols: list) -> dict:
        """
        Analisa os parâmetros do evento de aura.

        Retorna um dicionário contendo:
          - auraType (primeiro elemento)
          - amount (tenta converter para inteiro; se não for
            numérico, mantém o valor original)
          - auraExtra1 e auraExtra2 se presentes.
        """

        def safe_int(x: str):
            try:
                return int(x)
            except (ValueError, TypeError):
                return x  # retorna o valor original se não puder ser convertido

        obj = {"auraType": cols[0]}
        if len(cols) >= 2:
            obj["amount"] = safe_int(cols[1])
        if len(cols) >= 3:
            obj["auraExtra1"] = cols[2]
        if len(cols) >= 4:
            obj["auraExtra2"] = cols[3]
        if len(cols) >= 5:  # Novo campo para set bonuses
            obj["sourceType"] = cols[4]
        return obj


class AuraDoseParser:
    def parse(self, cols):
        obj = {"auraType": cols[0]}
        if len(cols) == 2:
            obj["powerType"] = resolv_power_type(cols[1])
        return obj


class AuraBrokenParser:
    def parse(self, cols):
        return {
            "extraSpellID": cols[0],
            "extraSpellName": cols[1],
            "extraSchool": parse_school_flag(cols[2]),
            "auraType": cols[3],
        }


class CastFailedParser:
    def parse(self, cols):
        return {"failedType": cols[0].strip('"')}


class EnchantParser:
    def parse(self, cols):
        return (
            {
                "spellName": cols[0],
                "itemID": cols[1],
                "itemName": cols[2],
            },
            cols,
        )


class EncountParser:
    def parse(self, cols):
        obj = {
            "encounterID": cols[0],
            "encounterName": cols[1],
            "difficultyID": cols[2],
            "groupSize": cols[3],
            "fightTime": cols[5],
        }
        if len(cols) == 5:
            obj["success"] = cols[4] == "1"
        return obj


class VoidParser:
    def parse(self, cols):
        return ({}, cols)


class ArenaMatchStartParser:
    def parse(self, cols):
        """
        Processa os dados do evento ARENA_MATCH_START.

        Args:
            cols: Lista de colunas do evento

        Returns:
            dict: Dicionário com os dados processados
        """
        try:
            return {
                "instance_id": int(cols[0]),  # Convertendo para int e usando snake_case
                "match_type": cols[2],  # Pulando cols[1] que é 'unk'
                "team_id": int(cols[3]),  # Convertendo para int e usando snake_case
            }
        except (IndexError, ValueError) as e:
            return {
                "event": "ARENA_MATCH_START",
                "error": f"Erro ao processar linha: {str(e)}",
                "raw_data": cols,
            }


class ArenaMatchEndParser:
    def parse(self, cols):
        return {
            "winningTeam": cols[0],
            "matchDuration": cols[1],
            "newRatingTeam1": cols[2],
            "newRatingTeam2": cols[3],
        }


class VoidSuffixParser:
    def parse(self, cols):
        return {}


class SpellAbsorbedParser:
    def parse(self, cols):
        try:
            has_data = len(cols) >= 11
            return {
                "absorbSpellId": cols[7] if has_data else None,
                "absorbSpellName": cols[8] if has_data else None,
                "absorbSpellSchool": parse_school_flag(cols[9]) if has_data else [],
                "absorberGUID": cols[3] if has_data else None,
                "absorberName": cols[4] if has_data else None,
                "absorberFlags": parse_unit_flag(cols[5]) if has_data else [],
                "absorberRaidFlags": parse_unit_flag(cols[6]) if has_data else [],
                "amount": int(cols[10], 0) if has_data and cols[10] != "nil" else 0,
                "critical": cols[11] != "nil" if has_data and len(cols) > 11 else False,
            }
        except Exception as error:
            logging.error("SpellAbsorbedParser: %s", str(error).split(":")[-1].strip())
            return {}


class Parser:
    def __init__(self):
        self.ev_prefix = {
            "SWING": SwingParser(),
            "SPELL_BUILDING": SpellParser(),
            "SPELL_PERIODIC": SpellParser(),
            "SPELL": SpellParser(),
            "RANGE": SpellParser(),
            "ENVIRONMENTAL": EnvParser(),
            "WORLD": WorldPrefixParser(),
        }
        # Pré-computa a lista de prefixos ordenados do maior para o menor comprimento.
        self.sorted_prefix_list = sorted(self.ev_prefix, key=len, reverse=True)

        self.ev_suffix = {
            "_MARKER_PLACED": WorldMarkerParser(),
            "_HEAL_ABSORBED": HealAbsorbedParser(),
            "_DAMAGE_SUPPORT": DamageParser(),
            "_HEAL_SUPPORT": HealParser(),
            "_ABSORBED_SUPPORT": SpellAbsorbedParser(),
            "_DAMAGE": DamageParser(),
            "_DAMAGE_LANDED": DamageParser(),
            "_DAMAGE_LANDED_SUPPORT": DamageParser(),
            "_MISSED": MissParser(),
            "_HEAL": HealParser(),
            "_ENERGIZE": EnergizeParser(),
            "_DRAIN": DrainParser(),
            "_LEECH": LeechParser(),
            "_INTERRUPT": SpellBlockParser(),
            "_DISPEL": SpellBlockParser(),
            "_DISPEL_FAILED": SpellBlockParser(),
            "_STOLEN": SpellBlockParser(),
            "_EXTRA_ATTACKS": ExtraAttackParser(),
            "_AURA_APPLIED": AuraParser(),
            "_AURA_REMOVED": AuraParser(),
            "_AURA_APPLIED_DOSE": AuraDoseParser(),
            "_AURA_REMOVED_DOSE": AuraDoseParser(),
            "_AURA_REFRESH": AuraDoseParser(),
            "_AURA_BROKEN": AuraParser(),
            "_AURA_BROKEN_SPELL": AuraBrokenParser(),
            "_CAST_START": VoidSuffixParser(),
            "_CAST_SUCCESS": VoidSuffixParser(),
            "_CAST_FAILED": CastFailedParser(),
            "_INSTAKILL": VoidSuffixParser(),
            "_DURABILITY_DAMAGE": VoidSuffixParser(),
            "_DURABILITY_DAMAGE_ALL": VoidSuffixParser(),
            "_CREATE": VoidSuffixParser(),
            "_SUMMON": VoidSuffixParser(),
            "_RESURRECT": VoidSuffixParser(),
            "_ABSORBED": SpellAbsorbedParser(),
            "_EMPOWER_START": VoidSuffixParser(),
            "_EMPOWER_END": VoidSuffixParser(),
            "_EMPOWER_INTERRUPT": VoidSuffixParser(),
        }
        self.combat_player_info = {
            "COMBATANT_INFO": CombatantInfoParser(self),
        }
        self.sp_event = {
            "DAMAGE_SHIELD": (SpellParser(), DamageParser()),
            "DAMAGE_SPLIT": (SpellParser(), DamageParser()),
            "DAMAGE_SHIELD_MISSED": (SpellParser(), MissParser()),
            "ENCHANT_APPLIED": (EnchantParser(), VoidSuffixParser()),
            "ENCHANT_REMOVED": (EnchantParser(), VoidSuffixParser()),
            "PARTY_KILL": (VoidParser(), VoidSuffixParser()),
            "UNIT_DIED": (VoidParser(), VoidSuffixParser()),
            "UNIT_DESTROYED": (VoidParser(), VoidSuffixParser()),
        }
        self.enc_event = {
            "ENCOUNTER_START": EncountParser(),
            "ENCOUNTER_END": EncountParser(),
        }
        self.arena_event = {
            "ARENA_MATCH_START": ArenaMatchStartParser(),
            "ARENA_MATCH_END": ArenaMatchEndParser(),
        }

    def parse_timestamp(self, line: str) -> tuple[float, str]:
        line_hash = hash(line)
        if line_hash in TIMESTAMP_CACHE:
            return TIMESTAMP_CACHE[line_hash]
        m = TIMESTAMP_REGEX.match(line)
        if not m:
            raise ValueError(f"Formato inválido: {line}")
        date_part, time_part, offset_str, rest = (
            m.group("date"),
            m.group("time"),
            m.group("offset"),
            m.group("rest"),
        )
        dt_str = (
            f"{date_part}/{datetime.now().year} {time_part}"
            if date_part.count("/") == 1
            else f"{date_part} {time_part}"
        )
        ts = datetime.strptime(dt_str, "%m/%d/%Y %H:%M:%S.%f").timestamp() + (
            int(offset_str) if offset_str else 0
        )
        TIMESTAMP_CACHE[line_hash] = (ts, rest)
        return ts, rest

    def parse_line(self, line: str) -> dict:
        """
        Analisa uma linha do log de combate e retorna um objeto estruturado.
        Versão otimizada que reduz alocações de memória e operações redundantes.
        """
        # Cache do regex compilado como variável de classe
        if not hasattr(self, "_SPLIT_REGEX"):
            self._SPLIT_REGEX = re.compile(r",(?![^\[]*\])")

        try:
            # Extrai timestamp e texto sem strip desnecessário
            ts, csv_text = self.parse_timestamp(line)

            # Split direto usando regex compilado, sem strip redundante
            columns = self._SPLIT_REGEX.split(csv_text)

            # Validação rápida sem len()
            if not columns[0]:
                raise ValueError("CSV vazio")

            return self.parse_cols(ts, columns)

        except (IndexError, AttributeError) as error:
            raise ValueError(f"Erro ao processar a linha: {line}") from error

    def parse_cols(self, ts: float, cols: list) -> dict:
        """
        Analisa as colunas extraídas de uma linha de evento e as converte em um
        objeto detalhado.
        Este método recebe o timestamp do evento e uma lista de colunas
        extraídas do CSV, identifica o tipo de evento e aplica o
        parser apropriado para obter os detalhes do evento. Ele lida com
        eventos específicos, como combate, arenas e encontros, e
        lida com prefixos e sufixos para analisar eventos complexos.

        Args:
            ts (float): Timestamp do evento em segundos desde a época.
            cols (list): Lista de strings representando as colunas do evento,
                         extraídas do CSV.

        Returns:
            dict: Um dicionário contendo os dados estruturados do evento,
                  incluindo informações sobre os participantes, tipo de evento e
                  dados específicos do evento.

        Raises:
            ValueError: Se ocorrer um erro ao analisar os dados do evento ou
                        se o formato das colunas for inesperado.
        """
        event = cols[0]
        if event in ("WORLD_MARKER_PLACED", "WORLD_MARKER_REMOVED"):
            return {}
        obj = {"timestamp": ts, "event": event}
        try:
            if event == "COMBATANT_INFO":
                return self.parse_combatant_info(ts, cols)
            special_obj = self._handle_special_events(ts, cols, obj)
            if special_obj is not None:
                return special_obj
            obj = self._parse_base_parameters(cols, obj)
            obj = self._handle_prefix_suffix_events(cols, obj)
        except ValueError as e:
            raise ValueError(
                "Erro ao processar a linha: %s\nLine: %s\nErro: %s"
                % (event, ",".join(cols), e)
            ) from e
        return obj

    def _handle_special_events(self, ts: float, cols: list, obj: dict) -> dict | None:
        """
        Trata eventos especiais que não seguem o formato padrão.
        """
        event = cols[0]
        if event == "COMBATANT_INFO":
            return self.parse_combatant_info(ts, cols[1:])
        elif event in self.enc_event:
            obj.update(self.enc_event[event].parse(cols[1:]))
            return obj
        elif event in self.arena_event:
            obj.update(self.arena_event[event].parse(cols[1:]))
            return obj
        elif event == "ZONE_CHANGE":
            # Para ZONE_CHANGE, o formato esperado é:
            # ["ZONE_CHANGE", zoneId, zoneName, zoneFlag]
            if len(cols) < 4:
                raise ValueError(
                    f"Formato inválido para o evento ZONE_CHANGE: número insuficiente de colunas ({len(cols)} < 4)"
                )
            return {
                "timestamp": ts,
                "event": "ZONE_CHANGE",
                "zoneId": cols[1],
                "zoneName": cols[2],
                "zoneFlag": cols[3],
            }
        return None

    def _parse_base_parameters(self, cols: list, obj: dict) -> dict:
        """
        Analisa os parâmetros base de um evento (GUIDs, nomes, flags).
        """
        event = cols[0]

        # Define número mínimo de colunas por evento usando dict para acesso O(1)
        colunas_minimas = {
            "SPELL_DAMAGE": 17,
            "SPELL_HEAL": 17,
            "RANGE_DAMAGE": 17,
            "RANGE_MISSED": 17,
            "SPELL_PERIODIC_DAMAGE": 17,
            "SPELL_PERIODIC_HEAL": 17,
            "SWING_MISSED": 11,
        }

        required_columns = colunas_minimas.get(event, 9)
        if len(cols) < required_columns:
            raise ValueError(
                f"Formato inválido para {event}: "
                f"colunas insuficientes ({len(cols)} < {required_columns})"
            )

        obj.update(
            {
                "sourceGUID": cols[1],
                "sourceName": cols[2].strip('"'),
                "sourceFlags": parse_unit_flag(cols[3]),
                "sourceRaidFlags": parse_unit_flag(cols[4]),
                "destGUID": cols[5],
                "destName": cols[6].strip('"'),
                "destFlags": parse_unit_flag(cols[7]),
                "destRaidFlags": parse_unit_flag(cols[8]),
            }
        )
        return obj

    def _handle_prefix_suffix_events(self, cols: list, obj: dict) -> dict:
        """
        Lida com eventos que possuem prefixos e sufixos.

        Args:
            cols (list): Lista de colunas do evento.
            obj (dict): Objeto base para o evento.

        Returns:
            dict: Objeto atualizado com os dados do evento prefixado/sufixado.
        """
        event = cols[0]

        # Tenta encontrar um sufixo primeiro
        suffix_parser = self.ev_suffix.get(event)
        if suffix_parser:
            obj.update(suffix_parser.parse(cols[9:]))
            return obj

        # Se não houver sufixo, procura por um prefixo
        prefix = self._find_prefix(event)
        if prefix:
            return self._parse_prefix_suffix(prefix, event, cols, obj)

        # Se não houver prefixo nem sufixo, tenta os eventos especiais
        parser_tuple = self.sp_event.get(event)
        if parser_tuple:
            prefix_parser, suffix_parser = parser_tuple
            result, remaining = prefix_parser.parse(cols[9:])
            obj.update(result)
            obj.update(suffix_parser.parse(remaining))
            return obj

        # Se nada for encontrado, levanta um erro
        raise ValueError(f"Formato de evento desconhecido: {event}")

    def _find_prefix(self, event: str) -> str | None:
        """
        Encontra o prefixo mais longo que corresponde ao início do evento utilizando
        a lista pré-ordenada de prefixos.
        """
        for prefix in self.sorted_prefix_list:
            if event.startswith(prefix):
                return prefix
        return None

    def _parse_prefix_suffix(
        self, prefix: str, event: str, cols: list, obj: dict
    ) -> dict:
        """
        Analisa um evento com prefixo e sufixo.

        Args:
            prefix (str): Prefixo do evento.
            event (str): Nome do evento completo.
            cols (list): Lista de colunas do evento.
            obj (dict): Objeto base para o evento.

        Returns:
            dict: Objeto atualizado com os dados do evento.
        """
        suffix = event[len(prefix) :]
        suffix_parser = self.ev_suffix.get(suffix)
        if not suffix_parser:
            raise ValueError(f"Sufixo de evento desconhecido: {suffix}")

        prefix_parser = self.ev_prefix[prefix]
        result, remaining = prefix_parser.parse(cols[9:])
        obj.update(result)
        suffix_parser.raw = cols  # Atribui os dados brutos ao parser de sufixo
        obj.update(suffix_parser.parse(remaining))
        return obj

    def read_file(self, fname):
        if not os.path.exists(fname):
            logging.error("File not found: %s", fname)
            return
        try:
            with open(fname, "r", encoding="utf-8", buffering=8192) as file:
                first_line = file.readline()
                if not first_line or first_line.isspace() or "\x00" in first_line:
                    logging.warning("Corrupted file: %s", fname)
                    return
                if "ARENA_MATCH_START" not in first_line:
                    logging.warning("Invalid file format: %s", fname)
                    return
                yield self.parse_line(first_line)
                for line in file:
                    if line.strip():
                        try:
                            yield self.parse_line(line)
                        except (OSError, ValueError) as error:
                            logging.error("Error processing %s: %s", fname, error)
                            logging.error("Line with error: %s", line)
                            return
        except IOError as e:
            logging.error("Error reading file: %s", e)

    def extract_spec_info(self, spec_id):
        data = [
            {
                "Class": "Death Knight",
                "Specs": {
                    250: "Blood",
                    251: "Frost",
                    252: "Unholy",
                    1455: "Initial",
                },
            },
            {
                "Class": "Demon Hunter",
                "Specs": {
                    577: "Havoc",
                    581: "Vengeance",
                    1456: "Initial",
                },
            },
            {
                "Class": "Druid",
                "Specs": {
                    102: "Balance",
                    103: "Feral",
                    104: "Guardian",
                    105: "Restoration",
                    1447: "Initial",
                },
            },
            {
                "Class": "Evoker",
                "Specs": {
                    1467: "Devastation",
                    1468: "Preservation",
                    1473: "Augmentation",
                    1465: "Initial",
                },
            },
            {
                "Class": "Hunter",
                "Specs": {
                    253: "Beast Mastery",
                    254: "Marksmanship",
                    255: "Survival",
                    1448: "Initial",
                },
            },
            {
                "Class": "Mage",
                "Specs": {
                    62: "Arcane",
                    63: "Fire",
                    64: "Frost",
                    1449: "Initial",
                },
            },
            {
                "Class": "Monk",
                "Specs": {
                    268: "Brewmaster",
                    270: "Mistweaver",
                    269: "Windwalker",
                    1450: "Initial",
                },
            },
            {
                "Class": "Paladin",
                "Specs": {
                    65: "Holy",
                    66: "Protection",
                    70: "Retribution",
                    1451: "Initial",
                },
            },
            {
                "Class": "Priest",
                "Specs": {
                    256: "Discipline",
                    257: "Holy",
                    258: "Shadow",
                    1452: "Initial",
                },
            },
            {
                "Class": "Rogue",
                "Specs": {
                    259: "Assassination",
                    260: "Outlaw",
                    261: "Subtlety",
                    1453: "Initial",
                },
            },
            {
                "Class": "Shaman",
                "Specs": {
                    262: "Elemental",
                    263: "Enhancement",
                    264: "Restoration",
                    1444: "Initial",
                },
            },
            {
                "Class": "Warlock",
                "Specs": {
                    265: "Affliction",
                    266: "Demonology",
                    267: "Destruction",
                    1454: "Initial",
                },
            },
            {
                "Class": "Warrior",
                "Specs": {
                    71: "Arms",
                    72: "Fury",
                    73: "Protection",
                    1446: "Initial",
                },
            },
        ]

        for player_class_data in data:
            if spec_id in player_class_data["Specs"]:
                return {
                    "id": spec_id,
                    "class": player_class_data["Class"],
                    "spec": player_class_data["Specs"][spec_id],
                }
        return {"id": spec_id, "class": "Unknown", "spec": "Unknown"}

    def process_cols_improved(self, cols):
        """
        Processa colunas de forma otimizada usando um único loop e detecção de padrões.
        Reduz iterações e alocações de memória.
        """
        resultado = {
            "class_talents": [],
            "pvp_talents": [],
            "artifact_traits": None,
            "equipped_items": [],
            "interesting_auras": [],
            "pvp_stats": cols[-4:],
        }

        i = 0
        tamanho = len(cols)

        while i < tamanho:
            coluna = cols[i]

            # Pula colunas vazias
            if not coluna:
                i += 1
                continue

            # Identifica o tipo de dado baseado no padrão de início/fim
            if coluna.startswith("["):
                # Equipped items: começa com [(
                if len(coluna) > 1 and coluna[1] == "(":
                    lista = resultado["equipped_items"]
                    fim = ")]"
                # Class talents: primeiro grupo com [
                elif not resultado["class_talents"]:
                    lista = resultado["class_talents"]
                    fim = "]"
                # Artifact traits: segundo grupo com [ sem (
                elif resultado["artifact_traits"] is None and (
                    len(coluna) < 2 or coluna[1] != "("
                ):
                    lista = []
                    resultado["artifact_traits"] = lista
                    fim = "]"
                # Interesting auras: último grupo com [
                else:
                    lista = resultado["interesting_auras"]
                    fim = "]"

                # Coleta tokens até encontrar o fim do grupo
                while not coluna.endswith(fim):
                    lista.append(coluna)
                    i += 1
                    coluna = cols[i]
                lista.append(coluna)

            # PvP talents: começa com (
            elif coluna.startswith("("):
                lista = resultado["pvp_talents"]
                while not coluna.endswith(")"):
                    lista.append(coluna)
                    i += 1
                    coluna = cols[i]
                lista.append(coluna)

            i += 1

        return resultado

    def process_class_talents(self, tokens):
        return {
            f"Class Talent {i+1}": {
                "talent_id": int(a.lstrip("([ ")),
                "talent_spec": int(b),
                "rank": int(c.rstrip(")] ")),
            }
            for i, (a, b, c) in enumerate(zip(tokens[0::3], tokens[1::3], tokens[2::3]))
        }

    def process_pvp_talents(self, tokens):
        t = [s.strip("()[]") for s in tokens if s.strip("()[]")]
        return {f"PvP Talent {i+1}": t[i] for i in range(len(t))}

    def process_artifact_traits(self, tokens):
        t = [s.strip("()[]") for s in (tokens or []) if s.strip("()[]")]
        keys = [
            "Artifact Trait ID 1",
            "Trait Effective Level 1",
            "Artifact Trait ID 2",
            "Artifact Trait ID 3",
            "Artifact Trait ID 4",
        ]
        return {
            keys[i] if i < len(keys) else f"Artifact Trait {i+1}": v
            for i, v in enumerate(t)
        }

    def process_equipped_items(self, tokens):
        try:
            concatenated = ",".join(tokens)
            items_list = ast.literal_eval(concatenated)

            processed_items = []
            for item in items_list:
                if not isinstance(item, tuple):
                    continue

                item_id = item[0]
                item_level = item[1]
                enchantments = item[2] if len(item) > 2 else ()
                bonus_list = item[3] if len(item) > 3 else ()
                gems = item[4] if len(item) > 4 else ()

                if not (isinstance(item_id, int) and isinstance(item_level, int)):
                    continue

                processed_items.append(
                    {
                        "item_id": item_id,
                        "item_level": item_level,
                        "enchantments": enchantments,
                        "bonus_list": bonus_list,
                        "gems": gems,
                    }
                )

            return processed_items
        except (SyntaxError, ValueError, IndexError) as e:
            print(f"Erro ao processar itens equipados: {e}")
            return []

    def process_interesting_auras(self, tokens):
        clean_tokens = [token.strip("()[]") for token in tokens if token.strip("()[]")]
        return {
            f"Aura {index+1}": {
                "sourceGUID": clean_tokens[2 * index],
                "auraId": clean_tokens[2 * index + 1],
            }
            for index in range(len(clean_tokens) // 2)
        }

    def process_pvp_stats(self, tokens):
        t = [s.strip("()[]") for s in tokens if s.strip("()[]")]
        return {"Honor Level": t[0], "Season": t[1], "Rating": t[2], "Tier": t[3]}

    def parse_combatant_info(self, ts, cols):
        try:
            fixed = cols[1:25]
            grp = self.process_cols_improved(cols[25:])
        except Exception as e:
            raise ValueError(f"Erro nos campos de COMBATANT_INFO: {e}") from e

        try:
            stats = [
                "strength",
                "agility",
                "stamina",
                "intelligence",
                "dodge",
                "parry",
                "block",
                "critMelee",
                "critRanged",
                "critSpell",
                "speed",
                "lifesteal",
                "hasteMelee",
                "hasteRanged",
                "hasteSpell",
                "avoidance",
                "mastery",
                "versatilityDamageDone",
                "versatilityHealingDone",
                "versatilityDamageTaken",
                "armor",
            ]

            info = {
                "timestamp": ts,
                "event": "COMBATANT_INFO",
                "playerguid": fixed[0],
                "faction": int(fixed[1]),
                "character_stats": {k: int(fixed[i + 2]) for i, k in enumerate(stats)},
                "currentSpecID": self.extract_spec_info(int(fixed[23])),
            }

            mappings = [
                ("class_talents", "classTalents"),
                ("pvp_talents", "pvpTalents"),
                ("artifact_traits", "artifactTraits"),
                ("equipped_items", "equippedItems"),
                ("interesting_auras", "interestingAuras"),
                ("pvp_stats", "pvpStats"),
            ]

            for src, dest in mappings:
                info[dest] = getattr(self, f"process_{src}")(grp[src])

        except Exception as e:
            raise ValueError(f"Erro no processamento de COMBATANT_INFO: {e}") from e

        return info


class CombatantInfoParser:
    def __init__(self, parser):
        self.parser = parser

    def parse(self, ts, cols):
        return self.parser.parse_combatant_info(ts, cols)


def setup_logging(log_file="convert_logs.log"):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging.WARN,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file)],
    )


def process_single_file(args):
    parser, file_path, output_dir = args
    setup_logging()
    output_file_path = output_dir / f"{file_path.stem}.json"

    if output_file_path.exists():
        return
    try:
        logging.debug("Processing file: %s", file_path)
        # Acumula todos os eventos do log em uma única lista
        events = list(parser.read_file(str(file_path)))
        if events:
            with open(output_file_path, "w", encoding="utf-8") as f:
                # Escreve todos os eventos de uma vez, otimizando o I/O
                json.dump(events, f, ensure_ascii=False, indent=4)
            logging.info("JSON file written: %s", output_file_path)

    except (OSError, ValueError) as error:
        logging.error("Error processing %s: %s", file_path, error)


def process_files(parser, txt_files, output_dir, max_workers=None):
    if max_workers is None:
        max_workers = min(4, cpu_count())
    with Pool(processes=max_workers) as pool:
        args = [(parser, file_path, output_dir) for file_path in txt_files]
        for _ in tqdm(
            pool.imap_unordered(process_single_file, args),
            total=len(txt_files),
            desc=f"{ICON_CONVERTING}...",
            bar_format="{l_bar}%s{bar}%s{r_bar}" % ("", ""),
            colour=None,
        ):
            pass


def check_and_create_directories(input_dir, output_dir):
    custom_theme = Theme(
        {
            "ok": "bold green",
            "created": "bold yellow",
            "error": "bold red",
            "header": "bold bright_white",
            "directory": "cyan",
        }
    )

    console = Console(theme=custom_theme, force_terminal=True)

    directories = [("Input", input_dir), ("Output", output_dir)]

    table = Table(
        title="Verificação de Diretórios",
        box=box.SQUARE,
        header_style="header",
        style="bright_white",
        border_style="dim",
        title_style="bold bright_white",
        expand=True,
    )

    table.add_column("Status", justify="center", width=10)
    table.add_column("Diretório", style="directory")
    table.add_column("Tipo", justify="center")
    table.add_column("Itens", justify="right")

    for name, path in directories:
        try:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                status = "[ok][OK][/]"
                items = "-"
            else:
                status = "[ok][OK][/]"
                items = str(len(list(path.glob("*"))))

            table.add_row(status, str(path), name, items)
        except OSError as error:
            table.add_row("[error][ERROR][/]", str(path), name, f"Erro: {str(error)}")

    console.print(table)


def run_benchmark(parser, test_file, iterations=3, warmup=0):
    """Versão otimizada para teste rápido de performance."""
    result = {"timings": [], "stats": {}}

    # Warmup
    if warmup > 0:
        for _ in range(warmup):
            list(parser.read_file(str(test_file)))

    # Medição principal
    with tqdm(total=iterations, desc="Teste de Performance", unit="exec") as pbar:
        for _ in range(iterations):
            start_time = time.perf_counter()
            list(parser.read_file(str(test_file)))  # Processa o arquivo
            elapsed = time.perf_counter() - start_time
            result["timings"].append(elapsed)
            pbar.update(1)
            pbar.set_postfix_str(f"Último: {elapsed:.2f}s")

    # Cálculos estatísticos
    if result["timings"]:
        result["stats"] = {
            "avg": sum(result["timings"]) / iterations,
            "best": min(result["timings"]),
            "worst": max(result["timings"]),
        }
    else:
        result["stats"] = {"avg": 0, "best": 0, "worst": 0}

    return result


def save_benchmark_history(history, file="benchmark_history.json"):
    """Salva histórico de benchmarks para análise temporal"""
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except (OSError, TypeError, ValueError) as e:  # Exceções reais do json.dump
        logging.error("Erro salvando histórico: %s", e)


def load_benchmark_history(file="benchmark_history.json"):
    """Carrega histórico de benchmarks existente"""
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logging.error("Erro carregando histórico: %s", e)
        return []


def print_benchmark_report(stats):
    """Relatório unificado de performance"""
    console = Console()
    table = Table(
        title="Resultado do Teste de Performance",
        box=box.SQUARE,
        header_style="bold bright_white",
        style="bright_white",
        border_style="dim",
        title_style="bold bright_white",
    )

    table.add_column("Métrica", style="cyan", justify="left")
    table.add_column("Valor", style="green", justify="right")

    table.add_row("Tempo Médio", f"{stats['avg']:.2f}s")
    table.add_row("Melhor Tempo", f"{stats['best']:.2f}s")
    table.add_row("Pior Tempo", f"{stats['worst']:.2f}s")

    console.print(table)


def main():
    setup_logging()
    input_dir = Path(r"E:\LogsWOW\logs")
    output_dir = Path(r"D:\Projetos_Git\dlLogs\scripts\output_json")

    # 1. Verificação de diretórios (compatível com PowerShell)
    check_and_create_directories(input_dir, output_dir)

    # 2. Configuração do parser
    parser = Parser()

    # 3. Execução do benchmark com múltiplos arquivos
    console = Console()
    console.print("\n[bold]Iniciando teste de performance...[/]\n")

    # Lista de arquivos para teste
    test_files = [
        "0026580d3a9a5e6909e407211cbe51e2.txt",
        "0000786585380b93ff1e96666f012779.txt",
        "20250127_124219_000f1b00a113541251d77acec2912d75.txt",
    ]

    # Executar benchmark para cada arquivo
    for file_name in test_files:
        benchmark_file = input_dir / file_name
        if not benchmark_file.exists():
            console.print(f"[red]Arquivo de teste não encontrado: {file_name}[/red]")
            continue

        console.print(f"\n[bold]Testando arquivo: {file_name}[/bold]")
        result = run_benchmark(parser, benchmark_file)
        print_benchmark_report(result["stats"])

    # 5. Confirmação do usuário
    console.print("\n[bold]Deseja processar TODOS os logs?[/bold]")
    console.print("[yellow]ATENÇÃO: Esta operação pode demorar horas![/yellow]")
    console.print(
        "[dim](Digite S para continuar ou qualquer outra tecla para cancelar)[/dim]"
    )

    if input().strip().upper() != "S":
        console.print("[red]Operação cancelada pelo usuário[/red]")
        return

    # 6. Processamento principal
    txt_files = list(input_dir.glob("*.txt"))
    with console.status("[bold green]Processando arquivos...[/]", spinner="line"):
        process_files(parser, txt_files, output_dir)

    console.print("[bold green]✅ Processo concluído com sucesso![/]")


if __name__ == "__main__":
    main()
