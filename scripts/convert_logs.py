# Imports padrão da biblioteca
import csv
import datetime
import io
import json
import logging
import os
import re
import time
from multiprocessing import Pool, cpu_count
from pathlib import Path

# Imports de terceiros
from colorama import Fore, Style, init
from tqdm import tqdm
from utils import check_and_create_directories, process_files


def resolv_power_type(pt):
    """
    Mapeia os tipos de poder usados no jogo para seus respectivos nomes.

    Args:
        pt (str): A abreviação do tipo de poder.

    Returns:
        str: O nome do tipo de poder correspondente.

    Raises:
        KeyError: Se o tipo de poder fornecido não for reconhecido.
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


def parse_unit_flag(flag):
    if isinstance(flag, str):
        f = int(flag, 0)
    else:
        f = flag

    res = []
    if f == 0:
        return res

    flag_map = {
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
        0x00800000: "NONE",  # Whether the unit does not exist.
        0x0FF00000: "SPECIAL_MASK",
    }

    for k, v in flag_map.items():
        if (f & k) > 0:
            res.append(v)

    # print f, '->', repr(res)
    return res


def parse_school_flag(school):
    s = int(school, 0) if isinstance(school, str) else school

    school_map = {
        0x1: "Physical",
        0x2: "Holy",
        0x4: "Fire",
        0x8: "Nature",
        0x10: "Frost",
        0x20: "Shadow",
        0x40: "Arcane",
    }

    return [v for k, v in school_map.items() if s & k]


"""
---------------------------------------------------------
Prefix Parser Set
---------------------------------------------------------
"""


class SpellParser:
    def __init__(self):
        pass

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
    def __init__(self):
        pass

    def parse(self, cols):
        return ({"environmentalType": cols[0]}, cols[1:])


class SwingParser:
    def __init__(self):
        pass

    def parse(self, cols):
        return ({}, cols)


"""
---------------------------------------------------------
Suffix Parser Set
---------------------------------------------------------
"""


class SupportParser:
    def __init__(self):
        pass

    def parse(self, cols):
        # Extrair o GUID do jogador de suporte e outros
        # dados relevantes específicos de '_SUPPORT'
        return {
            "supportPlayerGUID": cols[
                -1
            ]  # Assumindo que o GUID do jogador de suporte é sempre o último elemento
            # Outros campos conforme necessário
        }


class WorldPrefixParser:
    def __init__(self):
        pass

    def parse(self, cols):
        # Você pode extrair informações adicionais aqui, se necessário
        return ({}, cols[1:])  # Retornar um dicionário vazio e o restante dos dados


class WorldMarkerParser:
    def __init__(self):
        pass

    def parse(self, cols):
        return {
            "mapId": int(cols[1]),  # Extrair mapId
            "markerId": int(cols[2]),  # Extrair markerId
            "x": float(cols[3]),  # Extrair coordenada x
            "y": float(cols[4]),  # Extrair coordenada y
        }


class DamageParser:
    def __init__(self):
        pass

    def parse(self, cols):
        cols = cols[8:]
        try:
            return {
                "amount": int(cols[0]),
                "overkill": cols[1],
                "school": parse_school_flag(cols[2]),
                "resisted": float(cols[3]),  # Usar float() para conversão
                "blocked": float(cols[4]),
                "absorbed": float(cols[5]),
                "critical": (cols[6] != "nil"),
                "glancing": (cols[7] != "nil"),
                "crushing": (cols[8] != "nil"),
            }
        except ValueError as e:
            logging.error(f"Erro ao analisar ENVIRONMENTAL_DAMAGE: {e}")
            # Lidar com o erro (ex: retornar dicionário vazio)
            return {}


class MissParser:
    def __init__(self):
        pass

    def parse(self, cols):
        obj = {"missType": cols[0]}
        if len(cols) > 1:
            obj["isOffHand"] = cols[1]
        if len(cols) > 2:
            obj["amountMissed"] = int(cols[2])
        return obj


class HealParser:
    def __init__(self):
        pass

    def parse(self, cols):
        cols = cols[8:]
        return {
            "amount": int(cols[0]),
            "overhealing": int(cols[1]),
            "absorbed": int(cols[2]),
            "critical": (cols[3] != "nil"),
        }


class HealAbsorbedParser:
    def __init__(self):
        pass

    def parse(self, cols):
        # Extrair informações relevantes
        return {
            "casterGUID": cols[0],
            "casterName": cols[1],
            "casterFlags": parse_unit_flag(cols[2]),
            "casterRaidFlags": parse_unit_flag(cols[3]),
            "absorbSpellId": cols[4],
            "absorbSpellName": cols[5],
            "absorbSpellSchool": parse_school_flag(cols[6]),
            "amount": int(cols[7]),
            "totalAmount": int(cols[8]),  # Parâmetro adicional da documentação
            "critical": cols[8] != "nil",
        }


class EnergizeParser:
    def __init__(self):
        pass

    def parse(self, cols):
        cols = cols[8:]
        return {
            "amount": int(cols[0]),
            "powerType": resolv_power_type(cols[1]),
        }


class DrainParser:
    def __init__(self):
        pass

    def parse(self, cols):
        amount = int(cols[11])
        powerType = resolv_power_type(cols[12])
        maxPower = float(cols[13])  # Converter para float
        extraAmount = int(cols[14])  # Ajustar índice para 14
        return {
            "amount": amount,
            "powerType": powerType,
            "maxPower": maxPower,  # Adicionar ao dicionário
            "extraAmount": extraAmount,
        }


class LeechParser:
    def __init__(self):
        pass

    def parse(self, cols):
        if len(cols) != 3:
            print(cols)
        return {
            "amount": int(cols[0]),
            "powerType": resolv_power_type(cols[1]),
            "extraAmount": int(cols[2]),
        }


class SpellBlockParser:
    def __init__(self):
        pass

    def parse(self, cols):
        if len(cols) != 3 and len(cols) != 4:
            print(cols)
        obj = {
            "extraSpellID": cols[0],
            "extraSpellName": cols[1],
            "extraSchool": parse_school_flag(cols[2]),
        }
        if len(cols) == 4:
            obj["auraType"] = cols[3]
        return obj


class ExtraAttackParser:
    def __init__(self):
        pass

    def parse(self, cols):
        if len(cols) != 1:
            print(cols)
        return {"amount": int(cols[0])}


class AuraParser:
    def __init__(self):
        pass

    def parse(self, cols):
        if len(cols) > 4:
            # print(self.raw)
            print(cols)

        obj = {
            "auraType": cols[0],
        }
        # 'auraSchool': cols[1],
        # 'auraType': cols[2],

        if len(cols) >= 2:
            obj["amount"] = int(cols[1])
        if len(cols) >= 3:
            obj["auraExtra1"] = cols[2]  # Not sure this column
        if len(cols) >= 4:
            obj["auraExtra2"] = cols[3]  # Not sure this column
        return obj


class AuraDoseParser:
    def __init__(self):
        pass

    def parse(self, cols):
        obj = {
            "auraType": cols[0],
        }
        if len(cols) == 2:
            obj["powerType"] = resolv_power_type(cols[1])
        return obj


class AuraBrokenParser:
    def __init__(self):
        pass

    def parse(self, cols):
        if len(cols) != 4:
            print(cols)
        return {
            "extraSpellID": cols[0],
            "extraSpellName": cols[1],
            "extraSchool": parse_school_flag(cols[2]),
            "auraType": cols[3],
        }


class CastFailedParser:
    def __init__(self):
        pass

    def parse(self, cols):
        if len(cols) != 1:
            print(cols)
        return {
            "failedType": cols[0],
        }


"""
---------------------------------------------------------
Special Event Parser Set
---------------------------------------------------------
"""


class EnchantParser:
    def __init__(self):
        pass

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
    def __init__(self):
        pass

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
    def __init__(self):
        pass

    def parse(self, cols):
        return ({}, cols)


class ArenaMatchStartParser:
    def parse(self, cols):
        obj = {
            "instanceID": cols[0],
            "unk": cols[1],
            "matchType": cols[2],
            "teamId": cols[3],
        }
        return obj


class ArenaMatchEndParser:
    def parse(self, cols):
        obj = {
            "winningTeam": cols[0],
            "matchDuration": cols[1],
            "newRatingTeam1": cols[2],
            "newRatingTeam2": cols[3],
        }
        return obj


class VoidSuffixParser:
    def __init__(self):
        pass

    def parse(self, cols):
        return {}


class SpellAbsorbedParser:
    def __init__(self):
        pass

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
            # "_SUPPORT": SupportParser(),
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

    def parse_line(self, line):
        # Substituição de espaços em "Rated Solo Shuffle" por underscores
        line = line.replace("Rated Solo Shuffle", "Rated_Solo_Shuffle")

        # Substituição de vírgulas por @ em números entre parênteses
        line = re.sub(r"\(([\d,@]+)\)", lambda m: m.group().replace(",", "@"), line)

        # Divisão da linha em termos
        terms = line.split(" ")

        # Verificação do formato
        if len(terms) < 4:
            raise Exception(f"Formato inválido: {line}")

        # Processamento do timestamp
        month, day = map(int, terms[0].split("/"))
        year = datetime.datetime.today().year
        s = f"{year:02d}/{month:02d}/{day:02d} {terms[1][:-4]}"
        d = datetime.datetime.strptime(s, "%Y/%m/%d %H:%M:%S")
        ts = time.mktime(d.timetuple()) + float(terms[1][-4:])

        # Processamento dos dados CSV
        csv_txt = " ".join(terms[3:]).strip()
        csv_file = io.StringIO(csv_txt)
        reader = csv.reader(csv_file, delimiter=",")
        cols = next(reader)
        obj = self.parse_cols(ts, cols)
        # Todo o print do log
        # print(obj)
        # time.sleep(10)

        """
        if obj["event"] == "SPELL_AURA_APPLIED":
            print(obj)
            for i in range(len(cols)):
                print(i), cols[i]
        """

        return obj

    def parse_cols(self, ts, cols):
        """
        Analisa as colunas de um evento de log e retorna um dicionário
        com as informações extraídas.

        Args:
            ts (float): O timestamp do evento.
            cols (list): Uma lista de strings
            representando as colunas do evento.

        Returns:
            dict: Um dicionário com as informações extraídas do evento,
            ou um dicionário vazio se ocorrer um erro.
        """

        event = cols[0]

        # Tratamento inicial para eventos específicos
        if event in ("WORLD_MARKER_PLACED", "WORLD_MARKER_REMOVED"):
            logging.debug(f"Ignorando evento: {event}")
            return {}  # Retornar dicionário vazio para eventos ignorados

        obj = {"timestamp": ts, "event": event}

        try:
            # Eventos com tratamento especial
            if event == "COMBATANT_INFO":
                return self.parse_combatant_info(ts, cols)

            # Eventos com mapeamento direto
            event_map = {
                **self.enc_event,
                **self.arena_event,
                **self.combat_player_info,
            }
            if event in event_map:
                parsed_data = event_map[event].parse(cols[1:])
                obj.update(parsed_data)
                return obj

            # Validação do número de colunas
            if len(cols) < 9:
                logging.error(
                    "Formato inválido para evento %s: número de colunas insuficiente (%s < 9)",
                    event,
                    len(cols),
                )
                return {}

            # Informações dos combatentes

            try:
                source_flags = parse_unit_flag(cols[3])
                source_raid_flags = parse_unit_flag(cols[4])
            except ValueError as e:
                logging.error("Erro ao analisar flags de unidade: %s", e)
                return {}

            obj.update(
                {
                    "sourceGUID": cols[1],
                    "sourceName": cols[2],
                    "sourceFlags": source_flags,
                    "sourceRaidFlags": source_raid_flags,
                    "destGUID": cols[5],
                    "destName": cols[6],
                    "destFlags": source_flags,  # Reutilizar o valor
                    "destRaidFlags": source_raid_flags,  # Reutilizar o valor
                }
            )

            # Busca de parser de sufixo
            suffix_parser = self.ev_suffix.get(event)
            if suffix_parser:
                try:
                    obj.update(suffix_parser.parse(cols[9:]))
                except ValueError as e:
                    logging.error("Erro ao analisar sufixo do evento: %s", e)
                    return {}
                return obj

            # Busca de prefixo e sufixo
            prefix_map = {
                prefixo: self.ev_prefix[prefixo]
                for prefixo in sorted(self.ev_prefix, key=len, reverse=True)
            }
            for prefixo in sorted(prefix_map, key=len, reverse=True):
                if event.startswith(prefixo):
                    break
            else:
                prefixo = None

            if prefixo:
                suffixo = event[len(prefixo) :]
                suffix_parser = self.ev_suffix.get(suffixo)
                if suffix_parser:
                    try:
                        resultado, restante = prefix_map[prefixo].parse(cols[9:])
                        obj.update(resultado)
                        suffix_parser.raw = cols
                        obj.update(suffix_parser.parse(restante))
                    except ValueError as e:
                        logging.error(
                            "Erro ao analisar prefixo ou sufixo do evento: %s", e
                        )
                        return {}
                else:
                    logging.error("Sufixo de evento desconhecido: %s", suffixo)
                    return {}
            else:
                # Tratamento de eventos especiais
                parser_tuple = self.sp_event.get(event)
                if parser_tuple:
                    try:
                        prefixo_parser, sufixo_parser = parser_tuple
                        resultado, restante = prefixo_parser.parse(cols[9:])
                        obj.update(resultado)
                        obj.update(sufixo_parser.parse(restante))
                    except ValueError as e:
                        logging.error("Erro ao analisar evento especial: %s", e)
                        return {}
                else:
                    logging.error("Formato de evento desconhecido: %s", event)
                    return {}

        except ValueError as e:
            logging.error(
                "Erro ao analisar evento: %s\nLinha: %s\nErro: %s",
                event,
                ",".join(cols),
                e,
            )
            return {}

        return obj

    def read_file(self, fname):
        """
        Lê um arquivo de log e retorna um gerador de dicionários com as
        informações de cada evento.

        Args:
            fname (str): O nome do arquivo de log.

        Returns:
            Generator: Um gerador de dicionários com as informações de
            cada evento, ou um gerador vazio se o arquivo estiver corrompido.
        """
        if not os.path.exists(fname):
            logging.error("Arquivo não encontrado: %s", fname)
            return

        try:
            with open(fname, "r", encoding="utf-8", buffering=8192) as file:
                first_line = file.readline()  # Ler a primeira linha

                # Verificação de arquivo corrompido
                if not first_line or first_line.isspace() or "\x00" in first_line:
                    logging.warning("Arquivo corrompido: %s", fname)
                    return  # Pular o arquivo corrompido

                if "ARENA_MATCH_START" not in first_line:
                    logging.warning("Arquivo com formato inválido: %s", fname)
                    return  # Ignorar o arquivo

                yield self.parse_line(first_line)  # Processar a primeira linha

                for line in file:
                    if line.strip():  # Ignora linhas vazias ou com espaços
                        try:
                            yield self.parse_line(line)
                        except ValueError as e:
                            logging.error(
                                "Erro ao analisar linha no arquivo %s: %s", fname, e
                            )
                            logging.error("Linha com erro: %s", line)
                            return  # Abandonar o arquivo se uma exceção for encontrada
        except IOError as e:
            logging.error("Erro ao ler o arquivo: %s", e)

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

        # Caso o spec_id não seja encontrado, podemos
        # retornar um dicionário com uma mensagem de erro
        return {"id": spec_id, "class": "Unknown", "spec": "Unknown"}

    def process_cols(self, cols, group_type):
        # Combinação de lista em uma string única
        combined_string = ",".join(cols).replace("@", ",")

        # Função para identificar delimitadores
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

        # Identificando e armazenando os agrupamentos
        delimiters = {"open": ["[", "("], "close": ["]", ")"]}
        groups = find_delimiters(combined_string, delimiters)

        # Determinando a presença dos "Artifact Traits"
        artifact_traits_present = len(groups) > 4

        # Mapeamento dinâmico dos tipos de agrupamentos para seus índices na tupla
        group_mapping = {
            "class_talents": 0,
            "pvp_talents": 1,
            "artifact_traits": 2 if artifact_traits_present else None,
            "equipped_items": 3 if artifact_traits_present else 2,
            "interesting_auras": 4 if artifact_traits_present else 3,
        }

        # Função para extrair um agrupamento específico
        def extract_group(combined_string, group_indices, index):
            start, end = group_indices[index]
            return combined_string[start + 1 : end].split(",", end - start - 1)

        # Tratando o caso especial de pvpStats
        if group_type == "pvpStats":
            return combined_string.split(",")[-4:]

        # Extraindo o agrupamento desejado de forma dinâmica
        index = group_mapping.get(group_type)
        if index is not None:
            group_data = extract_group(combined_string, groups, index)
        else:
            group_data = []  # Caso o tipo de grupo não esteja mapeado

        return group_data

    def extract_class_talents(self, cols):
        # Extrair os dados brutos dos talentos de classe
        class_talents_raw = self.process_cols(cols, "class_talents")

        # Lista para armazenar os dicionários de talentos processados
        class_talents = []

        # Processar cada conjunto de três elementos na lista de dados brutos
        for i in range(0, len(class_talents_raw), 3):
            # Obter o grupo atual de três elementos
            talent_group = class_talents_raw[i : i + 3]

            # Remover os caracteres '(' e ')' e converter para inteiros
            talent_id, spell_id, rank = [int(part.strip("()")) for part in talent_group]

            # Criar o dicionário para o talento atual
            talent_info = {"talentId": talent_id, "spellId": spell_id, "rank": rank}

            # Adicionar o dicionário à lista de talentos
            class_talents.append(talent_info)

        return class_talents

    def extract_pvp_talents(self, cols):
        # Extrair os dados brutos dos talentos PvP usando process_cols
        pvp_talents_raw = self.process_cols(cols, "pvp_talents")

        # Dicionário para armazenar as informações dos talentos PvP processados
        pvp_talents_info = {}

        # Processar cada talento na lista de dados brutos
        for i, talent in enumerate(pvp_talents_raw):
            # Remover os caracteres '(' e ')' e converter para inteiro
            talent_id = int(talent.strip("()"))

            # Adicionando o talento ao dicionário com a chave apropriada
            talent_key = f"pvp_talent_{i + 1}"
            pvp_talents_info[talent_key] = talent_id

        return pvp_talents_info

    def extract_equipped_items(self, cols):
        equipped_items_raw = self.process_cols(cols, "equipped_items")
        reconstructed_dicts = []
        temp_item = ""
        parenthesis_count = 0

        for i, item_part in enumerate(equipped_items_raw):
            temp_item += item_part

            # Verificação modificada para inserção de vírgulas
            if i < len(equipped_items_raw) - 1:
                if not (
                    item_part.endswith(")")
                    and equipped_items_raw[i + 1].startswith("(")
                ) or (item_part == "()" and equipped_items_raw[i + 1] == "()"):
                    temp_item += ","

            parenthesis_count += item_part.count("(")
            parenthesis_count -= item_part.count(")")

            if parenthesis_count == 0 and temp_item:
                # Aplica o pós-processamento diretamente aqui
                temp_item = temp_item.replace("()()", "(),()").replace(")(", "),(")

                # Converte o item em um dicionário
                parts = temp_item.strip("()").split(",")
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
                temp_item = ""

        if parenthesis_count != 0:
            raise ValueError("Unbalanced parentheses in input")

        return reconstructed_dicts

    def extract_interesting_auras(self, cols):
        auras_raw = self.process_cols(cols, "interesting_auras")
        auras_extracted = []

        # Verifica se a lista está vazia ou contém elementos vazios
        if not auras_raw or all(element == "" for element in auras_raw):
            return auras_extracted

        # Processamento de pares de GUIDs de jogador e IDs de feitiço
        for i in range(0, len(auras_raw), 2):
            player_guid = auras_raw[i]
            spell_id = auras_raw[i + 1]

            # Verifica se os elementos do par são válidos
            if player_guid and spell_id.isdigit():
                aura_dict = {"player_guid": player_guid, "spell_id": int(spell_id)}
                auras_extracted.append(aura_dict)

        return auras_extracted

    def extract_pvp_stats(self, cols):
        pvp_stats_raw = self.process_cols(cols, "pvpStats")

        if len(pvp_stats_raw) != 4:
            error_message = (
                f"Erro: número de itens esperado em 'pvp_stats_raw' é 4, "
                f"encontrado: {len(pvp_stats_raw)}.\n"
                f"Conteúdo da lista: {pvp_stats_raw}"
            )
            # Lançar exceção customizada com a mensagem de erro
            raise error_message

        pvp_stats = [int(stat) for stat in pvp_stats_raw]

        pvp_stats_dict = {
            "honor_level": pvp_stats[0],
            "season": pvp_stats[1],
            "rating": pvp_stats[2],
            "tier": pvp_stats[3],
        }

        return pvp_stats_dict

    def parse_combatant_info(self, ts, cols):
        # print(80 * "-")
        # print(cols)
        # print(80 * "-")

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
    # Remover todos os handlers existentes
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Adicionar apenas o FileHandler
    logging.basicConfig(
        level=logging.WARN,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file)],
    )


def process_single_file(args):
    parser, file_path, output_dir = args
    setup_logging()  # Certifique-se de configurar o logging em cada processo filho
    output_file_path = output_dir / f"{file_path.stem}.json"
    try:
        data_generator = parser.read_file(str(file_path))
        first_item = next(data_generator, None)

        if first_item:
            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write("[")
                json.dump(first_item, f, ensure_ascii=False, indent=4)

                for data in data_generator:
                    f.write(", ")
                    json.dump(data, f, ensure_ascii=False, indent=4)
                f.write("]")

            logging.info("Arquivo JSON gravado: %s", output_file_path)

    except Exception as e:
        logging.error("Erro ao processar %s: %s", file_path, e)


init(autoreset=True)  # Inicializa o Colorama para resetar cores automaticamente


def process_files(parser, txt_files, output_dir, max_workers=None):
    """Processa múltiplos arquivos em paralelo.

    Args:
        parser (Parser): O objeto Parser para leitura dos arquivos.
        txt_files (list): Lista de caminhos para os arquivos de entrada.
        output_dir (Path): O caminho para o diretório de saída.
        max_workers (int, optional): Número máximo de processos a serem usados
        para paralelismo. Default é o número de CPUs.
    """
    if max_workers is None:
        max_workers = min(
            4, cpu_count()
        )  # Limita a 4 processos ou o número de CPUs disponíveis

    with Pool(processes=max_workers) as pool:
        args = [(parser, file_path, output_dir) for file_path in txt_files]
        for _ in tqdm(
            pool.imap_unordered(process_single_file, args),
            total=len(txt_files),
            desc=f"{Fore.GREEN}🔄 Converting files...{Style.RESET_ALL}",
            bar_format="{l_bar}%s{bar}%s{r_bar}"
            % (Fore.LIGHTGREEN_EX, Style.RESET_ALL),
            colour=None,
        ):
            pass


def main():
    """Função principal que gerencia a criação do diretório de saída,
    configuração de logging e processamento dos arquivos de entrada.
    """
    setup_logging()
    input_dir = Path(r"D:\Projetos_Git\dlLogs\scripts\logs_test")
    output_dir = Path(r"D:\Projetos_Git\dlLogs\scripts\output_json")
    check_and_create_directories(input_dir, output_dir)

    parser = Parser()  # Inicializar o objeto Parser aqui
    txt_files = list(input_dir.glob("*.txt"))
    total_files = len(txt_files)
    logging.debug("Iniciando processamento de %s arquivos.", total_files)

    process_files(parser, txt_files, output_dir)


if __name__ == "__main__":
    main()
