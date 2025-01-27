import cProfile
import csv
import datetime
import io
import json
import logging
import os
import pstats
import time
from multiprocessing import Pool, cpu_count
from pathlib import Path

from colorama import Fore, Style
from rich import box
from rich.console import Console
from rich.table import Table
from rich.theme import Theme
from tqdm import tqdm

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


def parse_unit_flag(flag):
    """
    Parse unit flags used in the game.

    Args:
        flag (int or str): The unit flag.

    Returns:
        list: A list of flag descriptions.
    """
    f = int(flag, 0) if isinstance(flag, str) else flag
    return [_UNIT_FLAG_MAP.get(k) for k in _UNIT_FLAG_MAP if f & k]


def parse_school_flag(school):
    """
    Parse school flags used in the game.

    Args:
        school (int or str): The school flag.

    Returns:
        list: A list of school names.
    """
    s = int(school, 0) if isinstance(school, str) else school
    return [_SCHOOL_FLAG_MAP.get(k) for k in _SCHOOL_FLAG_MAP if s & k]


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
                "spellName": cols[1],
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
        cols = cols[8:]
        try:
            return {
                "amount": int(cols[0]) if cols[0] != "nil" else 0,
                "overkill": cols[1],
                "school": parse_school_flag(cols[2]),
                "resisted": float(cols[3]),
                "blocked": float(cols[4]),
                "absorbed": float(cols[5]),
                "critical": cols[6] != "nil",
                "glancing": cols[7] != "nil",
                "crushing": cols[8] != "nil",
            }
        except ValueError as e:
            logging.error(f"Error parsing ENVIRONMENTAL_DAMAGE: {e}")
            return {}


class MissParser:
    def parse(self, cols):
        obj = {"missType": cols[0]}
        if len(cols) > 1:
            obj["isOffHand"] = cols[1]
        if len(cols) > 2:
            obj["amountMissed"] = int(cols[2])
        return obj


class HealParser:
    def parse(self, cols):
        cols = cols[8:]
        return {
            "amount": int(cols[0]),
            "overhealing": int(cols[1]),
            "absorbed": int(cols[2]),
            "critical": cols[3] != "nil",
        }


class HealAbsorbedParser:
    def parse(self, cols):
        return {
            "casterGUID": cols[0],
            "casterName": cols[1],
            "casterFlags": parse_unit_flag(cols[2]),
            "casterRaidFlags": parse_unit_flag(cols[3]),
            "absorbSpellId": cols[4],
            "absorbSpellName": cols[5],
            "absorbSpellSchool": parse_school_flag(cols[6]),
            "amount": int(cols[7]),
            "totalAmount": int(cols[8]),
            "critical": cols[8] != "nil",
        }


class EnergizeParser:
    def parse(self, cols):
        cols = cols[8:]
        return {
            "amount": int(cols[0]),
            "powerType": resolv_power_type(cols[1]),
        }


class DrainParser:
    def parse(self, cols):
        amount = int(cols[11])
        powerType = resolv_power_type(cols[12])
        maxPower = float(cols[13])
        extraAmount = int(cols[14])
        return {
            "amount": amount,
            "powerType": powerType,
            "maxPower": maxPower,
            "extraAmount": extraAmount,
        }


class LeechParser:
    def parse(self, cols):
        return {
            "amount": int(cols[0]),
            "powerType": resolv_power_type(cols[1]),
            "extraAmount": int(cols[2]),
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
        return {"amount": int(cols[0])}


class AuraParser:
    def parse(self, cols):
        obj = {"auraType": cols[0]}
        if len(cols) >= 2:
            obj["amount"] = int(cols[1])
        if len(cols) >= 3:
            obj["auraExtra1"] = cols[2]
        if len(cols) >= 4:
            obj["auraExtra2"] = cols[3]
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
        return {"failedType": cols[0]}


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
        if len(cols) >= 20:
            return {
                "casterGUID": cols[0],
                "casterName": cols[1],
                "casterFlags": parse_unit_flag(cols[2]),
                "casterRaidFlags": parse_unit_flag(cols[3]),
                "absorbSpellId": cols[4],
                "absorbSpellName": cols[5],
                "absorbSpellSchool": parse_school_flag(cols[6]),
                "amount": int(cols[7]),
                "critical": cols[8] != "nil",
            }
        else:
            return {
                "casterGUID": None,
                "casterName": None,
                "casterFlags": [],
                "casterRaidFlags": [],
                "spellId": cols[1],
                "spellName": cols[2],
                "spellSchool": parse_school_flag(cols[3]),
                "amount": int(cols[4]),
                "critical": cols[-1] != "nil",
            }


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

    def parse_line(self, line: str) -> dict:
        """
        Parse a combat log line into a structured object.

        Args:
            line (str): A line of text representing a combat log event.

        Returns:
            dict: A dictionary containing the structured event data or error information.
        """
        try:
            # Replace special string to avoid splitting issues
            line = line.replace("Rated Solo Shuffle", "Rated_Solo_Shuffle")

            # Split into fixed parts and CSV
            terms = line.split(" ", 3)
            if len(terms) < 4:
                return {
                    "event": line.split(",")[
                        0
                    ],  # Pega o tipo do evento da linha inválida
                    "error": f"Formato inválido: {line}",
                    "raw_data": line,
                }

            # Parse date parts
            month, day = map(int, terms[0].split("/"))
            year = datetime.datetime.today().year

            # Extrair time_str e seconds
            time_str = terms[1][:-4]
            seconds = float(terms[1][-4:])

            # Create timestamp
            date_str = f"{year}/{month:02d}/{day:02d} {time_str}"
            date_obj = datetime.datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
            timestamp = time.mktime(date_obj.timetuple()) + seconds

            # Process CSV
            csv_text = terms[3].strip()
            csv_file = io.StringIO(csv_text)
            reader = csv.reader(csv_file, delimiter=",")
            columns = next(reader)

            return self.parse_cols(timestamp, columns)

        except Exception as e:
            # Se qualquer erro ocorrer durante o processamento,
            # retorna um dicionário com informações do erro
            event = line.split(",")[0] if "," in line else line
            return {"event": event, "error": str(e), "raw_data": line}

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

            obj = self._handle_special_events(ts, cols, obj)
            if obj:
                return obj

            obj = self._parse_base_parameters(cols, obj)

            obj = self._handle_prefix_suffix_events(cols, obj)

        except ValueError as e:
            raise ValueError(
                "Error parsing event: %s\nLine: %s\nError: %s"
                % (event, ",".join(cols), e)
            ) from e

        return obj

    def _handle_special_events(self, ts: float, cols: list, obj: dict) -> dict:
        """
        Lida com eventos especiais como COMBATANT_INFO, encontros e arenas.

        Args:
            ts (float): Timestamp do evento.
            cols (list): Lista de colunas do evento.
            obj (dict): Objeto base para o evento.

        Returns:
            dict: Objeto atualizado com os dados do evento especial,
            ou o objeto original se o evento não for especial.
        """
        event = cols[0]
        # Simplifica a lógica de mapeamento de eventos
        if event == "COMBATANT_INFO":
            obj.update(self.parse_combatant_info(ts, cols[1:]))
        elif event in self.enc_event:
            obj.update(self.enc_event[event].parse(cols[1:]))
        elif event in self.arena_event:
            obj.update(self.arena_event[event].parse(cols[1:]))
        return obj

    def _parse_base_parameters(self, cols: list, obj: dict) -> dict:
        """
        Analisa os parâmetros base de um evento (GUIDs, nomes, flags).

        Args:
            cols (list): Lista de colunas do evento.
            obj (dict): Objeto base para o evento.

        Returns:
            dict: Objeto atualizado com os parâmetros base.
        """
        # Adiciona uma verificação mais robusta para o comprimento das colunas
        if len(cols) < 9:
            raise ValueError(
                f"Formato inválido para o evento {cols[0]}: "
                f"número insuficiente de colunas ({len(cols)} < 9)"
            )

        # Simplifica a extração de flags
        obj.update(
            {
                "sourceGUID": cols[1],
                "sourceName": cols[2],
                "sourceFlags": parse_unit_flag(cols[3]),
                "sourceRaidFlags": parse_unit_flag(cols[4]),
                "destGUID": cols[5],
                "destName": cols[6],
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
        Encontra o prefixo mais longo que corresponde ao início do evento.

        Args:
            event (str): Nome do evento.

        Returns:
            str | None: O prefixo encontrado ou None se nenhum prefixo for encontrado.
        """
        for prefix in sorted(self.ev_prefix, key=len, reverse=True):
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
                        except ValueError as e:
                            logging.error("Error parsing line in file %s: %s", fname, e)
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

    def process_cols(self, cols, group_type):
        combined_string = ",".join(cols).replace("@", ",")

        def find_delimiters(combined_string, delimiters):
            groups = []
            stack = []
            start_index = -1

            for i, char in enumerate(combined_string):
                if char in delimiters["open"]:
                    stack.append(char)
                    if len(stack) == 1:
                        start_index = i
                elif char in delimiters["close"] and stack:
                    stack.pop()
                    if not stack:
                        groups.append((start_index, i))
            return groups

        delimiters = {"open": ["[", "("], "close": ["]", ")"]}
        groups = find_delimiters(combined_string, delimiters)
        artifact_traits_present = len(groups) > 4

        group_mapping = {
            "class_talents": 0,
            "pvp_talents": 1,
            "artifact_traits": 2 if artifact_traits_present else None,
            "equipped_items": 3 if artifact_traits_present else 2,
            "interesting_auras": 4 if artifact_traits_present else 3,
        }

        def extract_group(combined_string, group_indices, index):
            start, end = group_indices[index]
            return combined_string[start + 1 : end].split(",", end - start - 1)

        if group_type == "pvpStats":
            return combined_string.split(",")[-4:]

        index = group_mapping.get(group_type)
        if index is not None:
            group_data = extract_group(combined_string, groups, index)
        else:
            group_data = []
        return group_data

    def extract_class_talents(self, cols):
        class_talents_raw = self.process_cols(cols, "class_talents")
        class_talents = []
        for i in range(0, len(class_talents_raw), 3):
            talent_group = class_talents_raw[i : i + 3]
            talent_id, spell_id, rank = [int(part.strip("()")) for part in talent_group]
            talent_info = {"talentId": talent_id, "spellId": spell_id, "rank": rank}
            class_talents.append(talent_info)
        return class_talents

    def extract_pvp_talents(self, cols):
        pvp_talents_raw = self.process_cols(cols, "pvp_talents")
        pvp_talents_info = {}
        for i, talent in enumerate(pvp_talents_raw):
            talent_id = int(talent.strip("()"))
            talent_key = f"pvp_talent_{i + 1}"
            pvp_talents_info[talent_key] = talent_id
        return pvp_talents_info

    def extract_equipped_items(self, cols):
        """
        Extrai e reconstrói itens equipados a partir de dados brutos de coluna.

        Esse método processa uma lista de dados brutos de itens equipados, reconstruindo
        reconstruindo-a em dicionários estruturados para cada item. Ele lida com
        partes do item entre parênteses e garante que elas estejam corretamente
        balanceadas e formatados antes de extrair os detalhes relevantes.

        Args:
            cols (lista): Lista de cadeias de caracteres que representam as colunas do
            evento, extraídas do CSV.

        Retorna:
            list: Uma lista de dicionários, cada um representando um item equipado
                com as chaves 'item_id', 'item_level', 'enchantments', 'bonus_list',
                e 'gems'.

        Aumenta:
            ValueError: Se os parênteses nos dados brutos estiverem desequilibrados.
        """

        equipped_items_raw = self.process_cols(cols, "equipped_items")
        reconstructed_dicts = []
        temp_item_parts = []  # Utilizar lista para acumular partes do item
        parenthesis_count = 0
        n = len(equipped_items_raw)

        for i, item_part in enumerate(equipped_items_raw):
            temp_item_parts.append(item_part)
            # Atualizar o contador de parênteses
            parenthesis_count += item_part.count("(") - item_part.count(")")

            # Verificar se deve adicionar uma vírgula
            if i < n - 1:
                next_part = equipped_items_raw[i + 1]
                if not (item_part.endswith(")") and next_part.startswith("(")) or (
                    item_part == "()" and next_part == "()"
                ):
                    temp_item_parts.append(",")

            # Quando os parênteses estiverem balanceados, processar o item
            if parenthesis_count == 0 and temp_item_parts:
                temp_item = "".join(temp_item_parts)
                # Substituições específicas para garantir o formato correto
                temp_item = temp_item.replace("()()", "(),()").replace(")(", "),(")
                parts = temp_item.strip("()").split(",")

                # Construir o dicionário do item de forma mais eficiente
                item_dict = {
                    "item_id": int(parts[0]),
                    "item_level": int(parts[1]),
                    "enchantments": [
                        int(x) for x in parts[2].strip("()").split(",") if x
                    ],
                    "bonus_list": [
                        int(x) for x in parts[3].strip("()").split(",") if x
                    ],
                    "gems": [int(x) for x in parts[4].strip("()").split(",") if x],
                }
                reconstructed_dicts.append(item_dict)
                # Resetar as partes temporárias para o próximo item
                temp_item_parts = []

        # Verificar se os parênteses estão balanceados
        if parenthesis_count != 0:
            raise ValueError("Parênteses desbalanceados na entrada")

        return reconstructed_dicts

    def extract_interesting_auras(self, cols):
        auras_raw = self.process_cols(cols, "interesting_auras")
        auras_extracted = []
        if not auras_raw or all(element == "" for element in auras_raw):
            return auras_extracted
        for i in range(0, len(auras_raw), 2):
            player_guid = auras_raw[i]
            spell_id = auras_raw[i + 1]
            if player_guid and spell_id.isdigit():
                aura_dict = {"player_guid": player_guid, "spell_id": int(spell_id)}
                auras_extracted.append(aura_dict)
        return auras_extracted

    def extract_pvp_stats(self, cols):
        pvp_stats_raw = self.process_cols(cols, "pvpStats")
        if len(pvp_stats_raw) != 4:
            error_message = (
                f"Error: expected 4 items in 'pvp_stats_raw', "
                f"found: {len(pvp_stats_raw)}.\n"
                f"List content: {pvp_stats_raw}"
            )
            raise ValueError(error_message)
        pvp_stats = [int(stat) for stat in pvp_stats_raw]
        pvp_stats_dict = {
            "honor_level": pvp_stats[0],
            "season": pvp_stats[1],
            "rating": pvp_stats[2],
            "tier": pvp_stats[3],
        }
        return pvp_stats_dict

    def parse_combatant_info(self, ts, cols):

        info = {
            "timestamp": ts,
            "event": "COMBATANT_INFO",
            "playerguid": cols[1],
            "faction": int(cols[2]),
            "character_stats": {
                "strength": int(cols[3]),
                "agility": int(cols[4]),
                "stamina": int(cols[5]),
                "intelligence": int(cols[6]),
                "dodge": int(cols[7]),
                "parry": int(cols[8]),
                "block": int(cols[9]),
                "critMelee": int(cols[10]),
                "critRanged": int(cols[11]),
                "critSpell": int(cols[12]),
                "speed": int(cols[13]),
                "lifesteal": int(cols[14]),
                "hasteMelee": int(cols[15]),
                "hasteRanged": int(cols[16]),
                "hasteSpell": int(cols[17]),
                "avoidance": int(cols[18]),
                "mastery": int(cols[19]),
                "versatilityDamageDone": int(cols[20]),
                "versatilityHealingDone": int(cols[21]),
                "versatilityDamageTaken": int(cols[22]),
                "armor": int(cols[23]),
            },
            "currentSpecID": self.extract_spec_info(int(cols[24])),
            "classTalents": self.extract_class_talents(cols),
            "pvpTalents": self.extract_pvp_talents(cols),
            "equippedItems": self.extract_equipped_items(cols),
            "interestingAuras": self.extract_interesting_auras(cols),
            "pvpStats": self.extract_pvp_stats(cols),
        }

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
        logging.debug(f"Processing file: {file_path}")
        data_generator = parser.read_file(str(file_path))
        first_item = next(data_generator, None)

        if first_item:
            logging.debug(f"First item: {first_item}")
            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write("[")
                json.dump(first_item, f, ensure_ascii=False, indent=4)
                for data in data_generator:
                    f.write(", ")
                    json.dump(data, f, ensure_ascii=False, indent=4)
                f.write("]")

            logging.info("JSON file written: %s", output_file_path)

    except Exception as e:
        logging.error("Error processing %s: %s", file_path, e)


def process_files(parser, txt_files, output_dir, max_workers=None):
    if max_workers is None:
        max_workers = min(4, cpu_count())
    with Pool(processes=max_workers) as pool:
        args = [(parser, file_path, output_dir) for file_path in txt_files]
        for _ in tqdm(
            pool.imap_unordered(process_single_file, args),
            total=len(txt_files),
            desc=f"{Fore.GREEN}{ICON_CONVERTING}...{Style.RESET_ALL}",
            bar_format="{l_bar}%s{bar}%s{r_bar}"
            % (Fore.LIGHTGREEN_EX, Style.RESET_ALL),
            colour=None,
        ):
            pass


def check_and_create_directories(input_dir, output_dir):
    custom_theme = Theme(
        {
            "created": "bold yellow",
            "exists": "bold green",
            "error": "bold red",
        }
    )
    console = Console(theme=custom_theme)

    results = []
    for directory in [input_dir, output_dir]:
        dir_path = Path(directory)
        dir_name = dir_path.name
        if dir_path.exists():
            results.append((dir_name, "Folder Exists", "exists"))
        else:
            try:
                dir_path.mkdir(parents=True)
                results.append((dir_name, "Created", "created"))
            except OSError as e:
                results.append((dir_name, f"Error: {e}", "error"))

    table = Table(
        title="Directory Check Results",
        box=box.ASCII,
        show_header=True,
        header_style="yellow3",
    )
    table.add_column("Status", justify="center", style="bold red")
    table.add_column("Directory", justify="center")
    table.add_column("Message", justify="center", style="bold red")

    for dir_name, status, style in results:
        status_symbol = ICON_CREATE if status != "Folder Exists" else ICON_CHECK
        table.add_row(
            f"[{style}]{status_symbol}[/{style}]",
            f"{dir_name}",
            f"[{style}]{status}[/{style}]",
        )

    console.print(table)


def run_verification_test(parser, test_input_file, expected_output_file):
    console = Console()
    console.print(f"Execução do teste de verificação em {test_input_file.name}...")

    # Inicializa o profiler
    profiler = cProfile.Profile()
    profiler.enable()

    start_time = time.perf_counter()  # Inicia a contagem de tempo
    data_generated = list(parser.read_file(str(test_input_file)))
    end_time = time.perf_counter()  # Finaliza a contagem de tempo

    profiler.disable()
    duration = end_time - start_time  # Calcula a duração em segundos

    # Cria um objeto Stats a partir do profiler
    stats = pstats.Stats(profiler).sort_stats("cumulative")

    # Exibe os 10 principais gargalos
    stats.print_stats(10)

    expected_output_path = Path(expected_output_file)
    if not expected_output_path.exists():
        console.print(
            f"[red]O arquivo de saída esperado não foi encontrado: {expected_output_file}[/red]"
        )
        return False, duration
    with open(expected_output_file, "r", encoding="utf-8") as f:
        data_expected = json.load(f)
    if data_generated == data_expected:
        console.print(
            f"[green]{ICON_SUCCESS} O teste de verificação foi aprovado![/green]"
        )
        console.print(f"Tempo gasto: {duration:.2f} segundos.")
        return True, duration
    else:
        console.print(f"[red]{ICON_SUCCESS} O teste de verificação falhou![/red]")
        console.print(f"Time taken: {duration:.2f} segundos.")
        return False, duration


def main():
    """Função principal que gerencia a criação do diretório de saída,
    configuração de logging e processamento dos arquivos de entrada.
    """
    setup_logging()
    input_dir = Path(r"E:\LogsWOW\logs")
    output_dir = Path(r"D:\Projetos_Git\dlLogs\scripts\output_json")
    check_and_create_directories(input_dir, output_dir)

    parser = Parser()
    txt_files = list(input_dir.glob("*.txt"))
    total_files = len(txt_files)
    logging.debug("niciando o processamento de %s arquivos.", total_files)

    # Define test files
    test_input_file = input_dir / "0026580d3a9a5e6909e407211cbe51e2.txt"
    expected_output_file = output_dir / "0026580d3a9a5e6909e407211cbe51e2.json"

    # Run verification test
    test_passed = run_verification_test(parser, test_input_file, expected_output_file)
    if not test_passed:
        logging.error("Falha no teste de verificação. Saindo.")
        return

    # Ask user to continue
    console = Console()
    console.print("Deseja continuar processando o diretório atual? (S/N)")
    choice = input().strip().upper()
    if choice != "S":
        console.print("Saindo...")
        return

    process_files(parser, txt_files, output_dir)


if __name__ == "__main__":
    main()
