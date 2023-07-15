import datetime
import shlex
import time


# Estou atualizando essa funcao com os dados do aquivo "wowpedia.md"
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
    """
    Analisa os sinalizadores de unidade e os mapeia para seus respectivos nomes.

    Args:
        flag (str): O sinalizador de unidade.

    Returns:
        str: O nome correspondente ao sinalizador de unidade.

    Raises:
        KeyError: Se o sinalizador de unidade fornecido não for reconhecido.
    """
    if isinstance(flag, str):
        f = int(flag, 0)
    else:
        f = flag

    res = []
    if f == 0:
        return res

    flag_map = {
        0x00004000: "TYPE_OBJECT",
        0x00002000: "TYPE_GUARDIAN",
        0x00001000: "TYPE_PET",
        0x00000800: "TYPE_NPC",
        0x00000400: "TYPE_PLAYER",
        0x00000200: "CONTROL_NPC",
        0x00000100: "CONTROL_PLAYER",
        0x00000040: "REACTION_HOSTILE",
        0x00000020: "REACTION_NEUTRAL",
        0x00000010: "REACTION_FRIENDLY",
        0x00000008: "AFFILIATION_OUTSIDER",
        0x00000004: "AFFILIATION_RAID",
        0x00000002: "AFFILIATION_PARTY",
        0x00000001: "AFFILIATION_MINE",
        0x08000000: "RAIDTARGET8",
        0x04000000: "RAIDTARGET7",
        0x02000000: "RAIDTARGET6",
        0x01000000: "RAIDTARGET5",
        0x00800000: "RAIDTARGET4",
        0x00400000: "RAIDTARGET3",
        0x00200000: "RAIDTARGET2",
        0x00100000: "RAIDTARGET1",
        0x00080000: "MAINASSIST",
        0x00040000: "MAINTANK",
        0x00020000: "FOCUS",
        0x00010000: "TARGET",
    }

    for k, v in flag_map.items():
        if (f & k) > 0:
            res.append(v)

    # print f, '->', repr(res)
    return res


def parse_school_flag(school):
    """
    Analisa os sinalizadores escolares e os mapeia para seus respectivos nomes.

    Args:
        school (str): O sinalizador escolar.

    Returns:
        str: O nome correspondente ao sinalizador escolar.

    Raises:
        KeyError: Se o sinalizador escolar fornecido não for reconhecido.
    """
    s = int(school, 0) if isinstance(school, str) else school

    res = []
    school_map = {
        0x1: "Physical",
        0x2: "Holy",
        0x4: "Fire",
        0x8: "Nature",
        0x10: "Frost",
        0x20: "Shadow",
        0x40: "Arcane",
    }

    for k, v in school_map.items():
        if (s & k) > 0:
            res.append(v)

    return res


"""
---------------------------------------------------------
Prefix Parser Set
---------------------------------------------------------
"""


class SpellParser:
    """
    Classe que analisa uma linha que contém informações sobre um evento de feitiço.

    Atributos:
        Nenhum

    Métodos:
        parse(cols): Analisa a lista de colunas fornecida e
        retorna um dicionário contendoas informações
        ortográficas analisadas e uma lista das colunas restantes.

    Exemplo:
        parser = SpellParser()
        cols = ["12345", "Fireball", "Fire", "Some", "Extra", "Columns"]
        result = parser.parse(cols)
        print(result)
        # Output: (
        #   {
        #       "spellId": "12345",
        #       "spellName": "Fireball",
        #       "spellSchool": "Fire"
        #   },
        #   ["Some", "Extra", "Columns"]
        # )
    """

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
    """
    Uma classe que analisa eventos ambientais.

    Atributos:
        Nenhum

    Métodos:
        __init__(self)
            Inicializa uma instância da classe EnvParser.

        parse(self, cols)
            Analisa as colunas fornecidas e retorna uma tupla
            contendo os dados analisados.

    Exemplo:
        parser = EnvParser()
        cols = ['FIRE', 'Some data']
        result = parser.parse(cols)
        print(result) # Saída: ({"environmentalType": "FIRE"}, ['Some data'])
    """

    def __init__(self):
        pass

    def parse(self, cols):
        return ({"environmentalType": cols[0]}, cols[1:])


class SwingParser:
    """
    Esta classe representa um SwingParser.

    Atributos:
        Nenhum

    Métodos:
        __init__(): Inicializa uma nova instância da classe SwingParser.
        parse(cols): Analisa as colunas fornecidas e retorna uma tupla
        contendo um dicionário vazio e as colunas.

    Uso:
        parser = SwingParser()
        resultado = parser.parse(cols)
    """

    def __init__(self):
        pass

    def parse(self, cols):
        """
        Analisa as colunas fornecidas e retorna uma tupla
        contendo um dicionário vazio e as colunas.

        Args:
            cols (lista): As colunas a serem analisadas.

        Retorna:
            tuple: Uma tupla contendo um dicionário vazio e as colunas.
        """
        return ({}, cols)


"""
---------------------------------------------------------
Suffix Parser Set
---------------------------------------------------------
"""


class DamageParser:
    def __init__(self):
        pass

    def parse(self, cols):
        cols = cols[8:]
        """
        Analisa as informações de dano das colunas fornecidas.

        Args:
            cols (lista): Uma lista de colunas que contém as informações de danos.

        Retorna:
            dict: Um dicionário que contém os dados de dano
                analisados com as seguintes chaves:
                - "amount": A quantidade de dano.
                - "overkill": O valor de overkill.
                - "school" (escola): A escola de dano.
                - "resisted" (resistido): A quantidade de dano resistido.
                - "blocked" (bloqueado): A quantidade de dano bloqueado.
                - "absorbed" (absorvido): A quantidade de dano absorvido.
                - "critical" (crítico): Um booleano que indica se o dano foi crítico.
                - "glancing" (de relance): Um booleano que indica se o
                dano foi de relance.
                - "crushing" (esmagador): Um booleano que
                indica se o dano foi esmagador.
        """
        return {
            "amount": int(cols[0]),
            "overkill": cols[1],
            "school": parse_school_flag(cols[2]),
            "resisted": int(cols[3]),
            "blocked": float(cols[4]),
            "absorbed": float(cols[5]),
            "critical": (cols[6] != "nil"),
            "glancing": (cols[7] != "nil"),
            "crushing": (cols[8] != "nil"),
        }


class MissParser:
    def __init__(self):
        pass

    def parse(self, cols):
        """
        Analisa as colunas de uma linha com um evento de falha e retorna um
        dicionário com os dados analisados.

        Args:
            cols (lista): Uma lista de colunas da linha de registro.

        Retorna:
            dict: Um dicionário com os dados analisados. As chaves e os valores
            no dicionário são os seguintes:
                - "missType" (str): O tipo de erro.
                - "isOffHand" (str): (Opcional) Indica se a falha ocorreu
                   com a arma de off-hand.
                - "amountMissed" (int): (Opcional) A quantidade de dano perdido.
        """
        obj = {"missType": cols[0]}
        if len(cols) > 1:
            obj["isOffHand"] = cols[1]
        if len(cols) > 2:
            obj["amountMissed"] = int(cols[2])
        return obj


class HealParser:
    """
    Uma classe que analisa colunas de dados relacionadas a eventos de cura.

    Atributos:
        Nenhum

    Métodos:
        __init__(self): Inicializa uma instância do HealParser.
        parse(self, cols): Analisa as colunas de dados fornecidas e retorna
        um dicionário com os valores analisados.
    Example:
        parser = HealParser()
        cols = ["col1", "col2", "col3", "col4", "col5", "col6",
        "col7", "col8", "amount", "overhealing", "absorbed", "critical"]
        parsed_data = parser.parse(cols)
        print(parsed_data)  # Output: {'amount': int(cols[8]),
        'overhealing': int(cols[9]), 'absorbed': int(cols[10]),
        'critical': (cols[11] != "nil")}
    """

    def __init__(self):
        pass

    def parse(self, cols):
        """
        Analisa as colunas de dados fornecidas e retorna um
        dicionário com os valores analisados.

        Args:
            cols (lista): As colunas de dados a serem analisadas.

        Retorna:
            dict: Um dicionário que contém os valores analisados.

        Example:
            parser = HealParser()
            cols = ["col1", "col2", "col3", "col4", "col5", "col6",
            "col7", "col8", "amount", "overhealing", "absorbed", "critical"]
            parsed_data = parser.parse(cols)
            print(parsed_data)  # Output: {'amount': int(cols[8]),
            'overhealing': int(cols[9]), 'absorbed': int(cols[10]),
            'critical': (cols[11] != "nil")}
        """
        cols = cols[8:]
        return {
            "amount": int(cols[0]),
            "overhealing": int(cols[1]),
            "absorbed": int(cols[2]),
            "critical": (cols[3] != "nil"),
        }


class EnergizeParser:
    """Essa classe define um objeto EnergizeParser para analisar um tipo específico de
    tipo específico de evento em dados de registro de combate.

    Atributos:
        Nenhum

    Métodos:
        __init__(self): Inicializa uma instância da classe EnergizeParser.
        parse(self, cols): Analisa as colunas de dados fornecidas
        e retorna um dicionário com as informações analisadas.

    Example:
        energize_parser = EnergizeParser()
        cols = ["timestamp", "event", "source", "target", "amount", "powerType", ...]
        parsed_data = energize_parser.parse(cols)
        print(parsed_data)  # Output: {"amount": 100, "powerType": "Mana"}

    """

    def __init__(self):
        pass

    def parse(self, cols):
        """Analisa as colunas de dados fornecidas e retorna um dicionário
        com as informações analisadas.

        Args:
            cols (lista): Uma lista de colunas que contém os dados a serem analisados.

        Retorna:
            dict: Um dicionário com as informações analisadas,
            incluindo os valores "amount" e "powerType".

        """
        cols = cols[8:]
        return {
            "amount": int(cols[0]),
            "powerType": resolv_power_type(cols[1]),
        }


class DrainParser:
    def __init__(self):
        pass

    def parse(self, cols):
        """
        Analisa as colunas fornecidas e retorna um dicionário que
        contém os dados analisados.

        Args:
            cols (lista): Uma lista de colunas a serem analisadas.

        Retorna:
            dict: Um dicionário que contém os dados analisados com as seguintes chaves:
                - "amount": O valor analisado (convertido em um número inteiro).
                - "powerType": O tipo de potência analisado (resolvido usando a função
                  função `resolv_power_type`).
                - "extraAmount": O valor extra analisado
                  (convertido em um número inteiro).

        Raises:
            None

        Example:
            >>> parser = DrainParser()
            >>> cols = ["10", "1", "5"]
            >>> result = parser.parse(cols)
            >>> print(result)
            {
                "amount": 10,
                "powerType": "mana",
                "extraAmount": 5
            }
        """
        if len(cols) != 3:
            print(cols)
        return {
            "amount": int(cols[0]),
            "powerType": resolv_power_type(cols[1]),
            "extraAmount": int(cols[2]),
        }


class LeechParser:
    """
    Classe responsável pela análise de eventos Leech a partir de dados de registro.

    Métodos:
        __init__(self): Inicializa o objeto LeechParser.

        parse(self, cols): Analisa as colunas de um evento Leech e retorna um
        dicionário com os dados analisados.

    Example:
        parser = LeechParser()
        cols = ["100", "Mana", "50"]
        result = parser.parse(cols)
        print(result)  # Output: {"amount": 100, "powerType": "Mana", "extraAmount": 50}
    """

    def __init__(self):
        pass

    def parse(self, cols):
        """
        Analisa as colunas de um evento Leech e retorna um dicionário
        com os dados analisados.

        Args:
            cols (lista): Uma lista de colunas de um evento Leech.

        Retorna:
            dict: Um dicionário com os dados analisados, incluindo o valor,
            powerType e extraAmount.

        Raises:
            None.

        Example:
            parser = LeechParser()
            cols = ["100", "Mana", "50"]
            result = parser.parse(cols)
            print(result)  # Output: {"amount": 100, "powerType": "Mana",
            "extraAmount": 50}
        """
        if len(cols) != 3:
            print(cols)
        return {
            "amount": int(cols[0]),
            "powerType": resolv_power_type(cols[1]),
            "extraAmount": int(cols[2]),
        }


class SpellBlockParser:
    """
    Classe responsável pela análise dos eventos do tipo "SpellBlock" no registro.

    Args:
        Nenhum

    Atributos:
        Nenhum

    Métodos:
        __init__(): Inicializa o objeto SpellBlockParser.
        parse(cols): Analisa as colunas de um evento SpellBlock e retorna um dicionário
        dicionário com os dados analisados.

    Exemplo:
        parser = SpellBlockParser()
        cols = ["123456", "Spell Name", "School of Magic"]
        result = parser.parse(cols)
        print(result) # Saída: {'extraSpellID': '123456', 'extraSpellName':
        'Spell Name', 'extraSchool': 'School of Magic'}
    """

    def __init__(self):
        pass

    def parse(self, cols):
        """
        Parses the columns of a SpellBlock event and returns a
        dictionary with the parsed data.

        Args:
            cols (list): List of columns from a SpellBlock event.

        Returns:
            dict: Dictionary with the parsed data.

        Raises:
            None
        """
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
    """
    Classe responsável por analisar eventos de ataque extra.

    Methods:
        __init__(self): Inicializa a classe.
        parse(self, cols): Analisa os dados do evento de ataque extra.

    Args:
        cols (list): Lista de colunas contendo os dados do evento.

    Returns:
        dict: Um dicionário contendo a quantidade de ataques extras.

    Example:
        >>> parser = ExtraAttackParser()
        >>> cols = ["2"]
        >>> result = parser.parse(cols)
        >>> print(result)  # Output: {"amount": 2}
    """

    def __init__(self):
        pass

    def parse(self, cols):
        if len(cols) != 1:
            print(cols)
        return {"amount": int(cols[0])}


class AuraParser:
    """
    Classe responsável por analisar eventos de aura.

    Methods:
        __init__(self): Inicializa a classe.
        parse(self, cols): Analisa os dados do evento de aura.

    Args:
        cols (list): Lista de colunas contendo os dados do evento.

    Returns:
        dict: Um dicionário contendo as informações do evento de aura.

    Example:
        >>> parser = AuraParser()
        >>> cols = ["Buff", "10", "Extra1", "Extra2"]
        >>> result = parser.parse(cols)
        >>> print(result)  # Output: {"auraType": "Buff", "amount": 10,
        "auraExtra1": "Extra1", "auraExtra2": "Extra2"}
    """

    def __init__(self):
        pass

    def parse(self, cols):
        if len(cols) > 4:
            print(self.raw)
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
    """
    Classe responsável por analisar eventos de aura.

    Métodos:
        __init__(self): Inicializa a classe.
        parse(self, cols): Analisa os dados do evento de aura.

    Args:
        cols (list): Lista de colunas contendo os dados do evento.

    Returns:
        dict: Um dicionário contendo as informações do evento de aura.

    Example:
        >>> parser = AuraDoseParser()
        >>> cols = ["Buff", "10", "Extra1", "Extra2"]
        >>> result = parser.parse(cols)
        >>> print(result)  # Output: {"auraType": "Buff", "amount": 10,
        "auraExtra1": "Extra1", "auraExtra2": "Extra2"}
    """

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
        """
        Classe responsável por analisar o sufixo 'AuraBroken' encontrado em eventos.

        Args:
            Nenhum.

        Returns:
            Nenhum.

        """

    def parse(self, cols):
        """
        Método responsável por analisar os dados do sufixo 'AuraBroken' em um evento.

        Args:
            cols (list): Lista contendo as colunas CSV do evento.

        Returns:
            dict: Dicionário contendo os dados analisados do evento, incluindo:
                  - 'extraSpellID': O ID do feitiço extra que quebrou a aura.
                  - 'extraSpellName': O nome do feitiço extra que quebrou a aura.
                  - 'extraSchool': A escola do feitiço extra que quebrou a aura.
                  - 'auraType': O tipo de aura que foi quebrada.

        """
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
        """
        Analisa as colunas fornecidas e retorna um dicionário
        com as informações analisadas.

        Args:
            cols (list): Uma lista de colunas que contém
            os dados a serem analisados.

        Retorna:
            dict: Um dicionário com as informações analisadas,
            incluindo o valor "failedType".

        Example:
            parser = CastFailedParser()
            cols = ["Interrupted"]
            result = parser.parse(cols)
            print(result)  # Output: {"failedType": "Interrupted"}
        """
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
    """Classe responsável por analisar eventos de encantamento.

    Métodos:
        __init__(self): Inicializa a classe.
        parse(self, cols): Analisa os dados do evento de encantamento.

    Args:
        cols (list): Lista de colunas contendo os dados do evento.

    Returns:
        dict: Um dicionário contendo as informações do evento de encantamento.

    Exemplo:
        >>> parser = EnchantParser()
        >>> cols = ["Encantamento", "123", "Nome do Item"]
        >>> result = parser.parse(cols)
        >>> print(result)  # Saída: {"spellName": "Encantamento", "itemID":
        "123", "itemName": "Nome do Item"}
    """

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
        """
        Método responsável por analisar os dados do evento EncountParser.

        Args:
            cols (list): Uma lista contendo os campos do evento.

        Returns:
            dict: Um dicionário contendo as informações analisadas do
                evento, com as seguintes chaves:
                - "encounterID": O ID do encontro.
                - "encounterName": O nome do encontro.
                - "difficultyID": O ID da dificuldade do encontro.
                - "groupSize": O tamanho do grupo.
                - "success" (opcional): Um valor booleano indicando se o e
                ncontro foi bem-sucedido.
        """
        obj = {
            "encounterID": cols[0],
            "encounterName": cols[1],
            "difficultyID": cols[2],
            "groupSize": cols[3],
        }
        if len(cols) == 5:
            obj["success"] = cols[4] == "1"
        return obj


class VoidParser:
    """
    Classe responsável por analisar uma linha com um evento de tipo "Void".

    Atributos:
        Nenhum

    Métodos:
        __init__(self):
            Inicializa uma instância da classe VoidParser.

        parse(self, cols):
            Analisa as colunas fornecidas e retorna um dicionário vazio e as colunas.

    Exemplo:
        parser = VoidParser()
        cols = ["timestamp", "event", "source", "target", "extra_data"]
        result = parser.parse(cols)
        print(result)  # Saída: ({}, ["timestamp", "event",
        "source", "target", "extra_data"])
    """

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
    """
    Classe responsável por analisar um sufixo de evento do tipo "Void".

    Atributos:
        Nenhum

    Métodos:
        __init__(self):
            Inicializa uma instância da classe VoidSuffixParser.

        parse(self, cols):
            Analisa as colunas fornecidas e retorna um dicionário vazio.

    Exemplo:
        parser = VoidSuffixParser()
        cols = ["timestamp", "event", "source", "target", "extra_data"]
        result = parser.parse(cols)
        print(result)  # Saída: {}
    """

    def __init__(self):
        pass

    def parse(self, cols):
        return {}


class Parser:
    """Classe responsável por analisar os dados do log de combate do World of Warcraft.

    Args:
        ev_prefix (dict): Dicionário que mapeia os prefixos de evento para as
        classes de analisador correspondentes.
        ev_suffix (dict): Dicionário que mapeia os sufixos de evento para as
        classes de analisador correspondentes.
        sp_event (dict): Dicionário que mapeia os eventos especiais para as
        classes de analisador correspondentes.
        enc_event (dict): Dicionário que mapeia os eventos de encontro para
        as classes de analisador correspondentes.

    Methods:
        parse_line(line): Analisa uma única linha do arquivo de log e retorna
        um dicionário com os dados do evento analisado.
        parse_cols(ts, cols): Analisa um registro de data e hora e uma lista
        de colunas CSV e retorna um dicionário com os dados do evento analisado.
        read_file(fname): Lê um arquivo de log linha por linha e produz os
        dados do evento analisados.

    """

    def __init__(self):
        self.ev_prefix = {
            "SWING": SwingParser(),
            "SPELL_BUILDING": SpellParser(),
            "SPELL_PERIODIC": SpellParser(),
            "SPELL": SpellParser(),
            "RANGE": SpellParser(),
            "ENVIRONMENTAL": EnvParser(),
            "ARENA_MATCH_START": ArenaMatchStartParser(),
            "ARENA_MATCH_END": ArenaMatchEndParser(),
        }
        self.ev_suffix = {
            "_DAMAGE": DamageParser(),
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

    def parse_line(self, line):
        """
        Analisa uma linha do arquivo de log.

        Args:
            line (str): A linha do arquivo de log a ser analisada.

        Returns:
            dict: Um dicionário contendo os dados analisados do evento.

        Raises:
            Exception: Se o formato da linha for inválido.

        """
        terms = line.split(" ")
        print(terms)  # Teste
        if len(terms) < 4:
            raise Exception("invalid format, " + line)

        # split timestamp
        s = "{2} {0[0]:02d}/{0[1]:02d} {1}".format(
            list(map(int, terms[0].split("/"))),
            terms[1][:-4],
            datetime.datetime.today().year,
        )
        d = datetime.datetime.strptime(s, "%Y %m/%d %H:%M:%S")
        ts = time.mktime(d.timetuple()) + float(terms[1][-4:])

        # split CSV data
        csv_txt = " ".join(terms[3:]).strip()
        splitter = shlex.shlex(csv_txt, posix=True)
        splitter.whitespace = ","
        splitter.whitespace_split = True
        cols = list(splitter)
        obj = self.parse_cols(ts, cols)
        """
        if obj["event"] == "SPELL_AURA_APPLIED":
            print(obj)
            for i in range(len(cols)):
                print(i), cols[i]
        """
        return obj

    def parse_cols(self, ts, cols):
        """
        Analisa uma lista de colunas CSV e determina o tipo de evento.

        Args:
            ts (float): O timestamp do evento.
            cols (list): A lista de colunas CSV do evento.

        Returns:
            dict: Um dicionário contendo os dados analisados do evento.

        Raises:
            Exception: Se o formato da lista de colunas for inválido.

        """
        event = cols[0]

        if self.enc_event.get(event):
            obj = {
                "timestamp": ts,
                "event": event,
            }
            obj.update(self.enc_event[event].parse(cols[1:]))
            return obj
        # Se o evento for "ARENA_MATCH_START" ou "COMBATANT_INFO" pule o evento
        if (
            event == "ARENA_MATCH_START"
            or event == "COMBATANT_INFO"
            or event == "ARENA_MATCH_END"
        ):
            return {}

        if len(cols) < 8:
            raise Exception("invalid format, " + repr(cols))
        obj = {
            "timestamp": ts,
            "event": event,
            "sourceGUID": cols[1],
            "sourceName": cols[2],
            "sourceFlags": parse_unit_flag(cols[3]),
            "sourceFlags2": parse_unit_flag(cols[4]),
            "destGUID": cols[5],
            "destName": cols[6],
            "destFlags": parse_unit_flag(cols[7]),
            "destFlags2": parse_unit_flag(cols[8]),
        }

        suffix = ""
        prefix_psr = None
        suffix_psr = None

        matches = []
        for k, p in self.ev_prefix.items():
            if event.startswith(k):
                matches.append(k)

        if len(matches) > 0:
            prefix = max(matches, key=len)
            prefix_psr = self.ev_prefix[prefix]
            suffix = event[len(prefix) :]
            suffix_psr = self.ev_suffix[suffix]
        else:
            for k, psrs in self.sp_event.items():
                if event == k:
                    (prefix_psr, suffix_psr) = psrs
                    break

        if prefix_psr is None or suffix_psr is None:
            raise Exception("Unknown event format, " + repr(cols))

        (res, remain) = prefix_psr.parse(cols[9:])
        obj.update(res)
        suffix_psr.raw = cols
        obj.update(suffix_psr.parse(remain))

        # if obj['destName'] == 'Muret' and obj['event'] == 'SPELL_HEAL':
        """
        if obj['event'] == 'SPELL_DISPEL':
            print obj
        """

        return obj

    def read_file(self, fname):
        """
        Lê um arquivo e produz cada linha após analisá-lo.
        Parâmetros:
            fname (str): O nome do arquivo a ser lido.
        Fornece:
            LineType: Um objeto que representa cada linha após a análise.
        Retorna:
            Nenhum
        """
        for line in open(fname, "r"):
            yield self.parse_line(line)


if __name__ == "__main__":
    import sys

    p = Parser()
    for arg in sys.argv[1:]:
        for a in p.read_file(arg):
            pass
