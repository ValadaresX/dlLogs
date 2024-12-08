# tests/test_convert_logs.py

import datetime
import logging
import os
import sys
import time

import pytest

# Adicionar o diretório 'scripts' ao sys.path para permitir a importação
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from convert_logs import Parser  # Importar a classe Parser do script principal

# Configurar o logging para evitar poluição nos testes
logging.disable(logging.CRITICAL)


@pytest.fixture
def parser():
    return Parser()


def create_timestamp(year, month, day, time_str, fractional_seconds):
    """
    Função auxiliar para criar um timestamp.
    """
    s = f"{year}/{month:02d}/{day:02d} {time_str}"
    dt = datetime.datetime.strptime(s, "%Y/%m/%d %H:%M:%S")
    ts = time.mktime(dt.timetuple()) + fractional_seconds
    return ts


def test_parse_line_valid(parser, monkeypatch):
    """
    Testa parse_line com uma linha de log válida.
    """
    # Exemplo de linha de log válida
    log_line = "12/25 13:45:30.1234 SPELL,12345,Fireball,67890,Player-1,Target-1,0x00000001,0x00000002,Damage,Fire,1000,nil,nil,nil"

    # Mocking datetime para ter um ano consistente
    class MockDateTime(datetime.datetime):
        @classmethod
        def today(cls):
            return cls(2024, 4, 27)

    monkeypatch.setattr(datetime, "datetime", MockDateTime)

    expected_timestamp = create_timestamp(2024, 12, 25, "13:45:30", 0.1234)

    # Mock the print function to suppress output during tests
    monkeypatch.setattr("builtins.print", lambda x: None)

    result = parser.parse_line(log_line)

    expected_result = {
        "timestamp": expected_timestamp,
        "event": "SPELL",
        "sourceGUID": "67890",
        "sourceName": "Player-1",
        "sourceFlags": ["AFFILIATION_MINE"],
        "sourceRaidFlags": ["AFFILIATION_PARTY"],
        "destGUID": "Target-1",
        "destName": "Target-1",
        "destFlags": ["AFFILIATION_MINE"],
        "destRaidFlags": ["AFFILIATION_PARTY"],
        "spellId": "12345",
        "spellName": "Fireball",
        "spellSchool": ["Fire"],
        "amount": 1000,
        "overkill": "nil",
        "school": ["Fire"],
        "resisted": 0.0,
        "blocked": 0.0,
        "absorbed": 0.0,
        "critical": False,
        "glancing": False,
        "crushing": False,
    }

    # Comparar o dicionário completo
    assert result == expected_result


def test_parse_line_invalid_format(parser):
    """
    Testa parse_line com uma linha de log em formato inválido.
    """
    invalid_log_line = "12/25 13:45 SPELL,Incomplete,Data"

    with pytest.raises(Exception) as exc_info:
        parser.parse_line(invalid_log_line)

    assert "Invalid format" in str(exc_info.value)


def test_parse_cols_spell_event(parser):
    """
    Testa parse_cols com um evento SPELL.
    """
    ts = create_timestamp(2024, 12, 25, "13:45:30", 0.1234)
    cols = [
        "SPELL",
        "12345",  # spellId
        "Fireball",  # spellName
        "67890",  # sourceGUID
        "Player-1",  # sourceName
        "0x00000001",  # sourceFlags
        "0x00000002",  # sourceRaidFlags
        "Target-1",  # destGUID
        "Target-1",  # destName
        "0x00000001",  # destFlags
        "0x00000002",  # destRaidFlags
        "Damage",
        "Fire",
        "1000",
        "nil",
        "nil",
        "nil",
    ]

    result = parser.parse_cols(ts, cols)

    expected_result = {
        "timestamp": ts,
        "event": "SPELL",
        "sourceGUID": "67890",
        "sourceName": "Player-1",
        "sourceFlags": ["AFFILIATION_MINE"],
        "sourceRaidFlags": ["AFFILIATION_PARTY"],
        "destGUID": "Target-1",
        "destName": "Target-1",
        "destFlags": ["AFFILIATION_MINE"],
        "destRaidFlags": ["AFFILIATION_PARTY"],
        "spellId": "12345",
        "spellName": "Fireball",
        "spellSchool": ["Fire"],
        "amount": 1000,
        "overkill": "nil",
        "school": ["Fire"],
        "resisted": 0.0,
        "blocked": 0.0,
        "absorbed": 0.0,
        "critical": False,
        "glancing": False,
        "crushing": False,
    }

    assert result == expected_result


def test_parse_cols_unknown_event(parser):
    """
    Testa parse_cols com um evento desconhecido.
    """
    ts = time.time()
    cols = [
        "UNKNOWN_EVENT",
        "data1",
        "data2",
        "data3",
        "data4",
        "data5",
        "data6",
        "data7",
        "data8",
        "data9",
    ]

    result = parser.parse_cols(ts, cols)

    expected_result = {"timestamp": ts, "event": "UNKNOWN_EVENT"}

    assert result == expected_result


def test_parse_cols_insufficient_columns(parser, caplog):
    """
    Testa parse_cols com colunas insuficientes para um evento SPELL.
    """
    ts = time.time()
    cols = [
        "SPELL",
        "12345",
        "Fireball",
        "67890",
        "Player-1",
        "0x00000001",
        # Faltando colunas
    ]

    with caplog.at_level(logging.ERROR):
        result = parser.parse_cols(ts, cols)
        assert result == {}
        assert "Invalid format for event SPELL: insufficient columns" in caplog.text


def test_parse_cols_combatant_info(parser):
    """
    Testa parse_cols com um evento COMBATANT_INFO.
    """
    ts = create_timestamp(2024, 4, 27, "12:00:00", 0.0000)
    cols = [
        "COMBATANT_INFO",
        "Player-1",
        "1",  # faction
        "150",  # strength
        "200",  # agility
        "250",  # stamina
        "300",  # intelligence
        "50",  # dodge
        "60",  # parry
        "70",  # block
        "80",  # critMelee
        "90",  # critRanged
        "100",  # critSpell
        "110",  # speed
        "120",  # lifesteal
        "130",  # hasteMelee
        "140",  # hasteRanged
        "150",  # hasteSpell
        "160",  # avoidance
        "170",  # mastery
        "180",  # versatilityDamageDone
        "190",  # versatilityHealingDone
        "200",  # versatilityDamageTaken
        "210",  # armor
        "65",  # currentSpecID
        # Talents, PVP Talents, Equipped Items, Auras, PVP Stats (simplificados)
        "(1)",
        "(1001)",
        "(2)",  # class_talents
        "(2001)",
        "(2002)",
        "(3)",  # class_talents
        "(3001)",
        "(3002)",
        "(4)",  # class_talents
        "(4001)",
        "(4002)",
        "(5)",  # class_talents
        "(5001)",
        "(5002)",
        "(6)",  # class_talents
        "(6001)",
        "(6002)",
        "(7)",  # class_talents
        "(7001)",
        "(7002)",
        "(8)",  # class_talents
        "(8001)",
        "(8002)",
        "(9)",  # class_talents
        "(9001)",
        "(9002)",
        "(10)",  # class_talents
        # PVP Talents
        "(10001)",
        "(10002)",
        # Equipped Items
        "(11111,200,300,400,500)",
        "(22222,210,310,410,510)",
        # Interesting Auras
        "Player-1",
        "12345",
        "Player-2",
        "67890",
        # PVP Stats
        "50",
        "2",
        "1500",
        "3",
    ]

    result = parser.parse_cols(ts, cols)

    expected_result = {
        "timestamp": ts,
        "event": "COMBATANT_INFO",
        "playerguid": "Player-1",
        "faction": 1,
        "character_stats": {
            "strength": 150,
            "agility": 200,
            "stamina": 250,
            "intelligence": 300,
            "dodge": 50,
            "parry": 60,
            "block": 70,
            "critMelee": 80,
            "critRanged": 90,
            "critSpell": 100,
            "speed": 110,
            "lifesteal": 120,
            "hasteMelee": 130,
            "hasteRanged": 140,
            "hasteSpell": 150,
            "avoidance": 160,
            "mastery": 170,
            "versatilityDamageDone": 180,
            "versatilityHealingDone": 190,
            "versatilityDamageTaken": 200,
            "armor": 210,
        },
        "currentSpecID": {"id": 65, "class": "Paladin", "spec": "Holy"},
        "classTalents": [
            {"talentId": 1, "spellId": 1001, "rank": 2},
            {"talentId": 2001, "spellId": 2002, "rank": 3},
            {"talentId": 3001, "spellId": 3002, "rank": 4},
            {"talentId": 4001, "spellId": 4002, "rank": 5},
            {"talentId": 5001, "spellId": 5002, "rank": 6},
            {"talentId": 6001, "spellId": 6002, "rank": 7},
            {"talentId": 7001, "spellId": 7002, "rank": 8},
            {"talentId": 8001, "spellId": 8002, "rank": 9},
            {"talentId": 9001, "spellId": 9002, "rank": 10},
        ],
        "pvpTalents": {"pvp_talent_1": 10001, "pvp_talent_2": 10002},
        "equippedItems": [
            {
                "item_id": 11111,
                "item_level": 200,
                "enchantments": [300, 400, 500],
                "bonus_list": [],
                "gems": [],
            },
            {
                "item_id": 22222,
                "item_level": 210,
                "enchantments": [310, 410, 510],
                "bonus_list": [],
                "gems": [],
            },
        ],
        "interestingAuras": [
            {"player_guid": "Player-1", "spell_id": 12345},
            {"player_guid": "Player-2", "spell_id": 67890},
        ],
        "pvpStats": {"honor_level": 50, "season": 2, "rating": 1500, "tier": 3},
    }

    assert result == expected_result


def test_parse_line_with_special_characters(parser, monkeypatch):
    """
    Testa parse_line com caracteres especiais que precisam ser substituídos.
    """
    log_line = "01/01 00:00:00.0000 Rated Solo Shuffle (123,456) SPELL,11111,Ice Lance,22222,Player-2,Target-2,0x00000004,0x00000008,DAMAGE,Arcane,500,nil,nil,nil"

    # Mocking datetime para ter um ano consistente
    class MockDateTime(datetime.datetime):
        @classmethod
        def today(cls):
            return cls(2024, 4, 27)

    monkeypatch.setattr(datetime, "datetime", MockDateTime)

    expected_timestamp = create_timestamp(2024, 1, 1, "00:00:00", 0.0000)

    # Mock the print function to suppress output durante os testes
    monkeypatch.setattr("builtins.print", lambda x: None)

    result = parser.parse_line(log_line)

    expected_result = {
        "timestamp": expected_timestamp,
        "event": "SPELL",
        "sourceGUID": "22222",
        "sourceName": "Player-2",
        "sourceFlags": ["AFFILIATION_RAID"],
        "sourceRaidFlags": ["AFFILIATION_OUTSIDER"],
        "destGUID": "Target-2",
        "destName": "Target-2",
        "destFlags": ["AFFILIATION_RAID"],
        "destRaidFlags": ["AFFILIATION_OUTSIDER"],
        "spellId": "11111",
        "spellName": "Ice Lance",
        "spellSchool": ["Arcane"],  # Supondo que "Arcane" seja corretamente mapeado
        "amount": 500,
        "overkill": "nil",
        "school": ["Arcane"],  # Depende da implementação de parse_school_flag
        "resisted": 0.0,
        "blocked": 0.0,
        "absorbed": 0.0,
        "critical": False,
        "glancing": False,
        "crushing": False,
    }

    assert result == expected_result


def test_parse_cols_heal_event(parser):
    """
    Testa parse_cols com um evento HEAL.
    """
    ts = create_timestamp(2024, 6, 15, "18:30:45", 0.5678)
    cols = [
        "HEAL",
        "33333",  # spellId
        "Healing Touch",  # spellName
        "44444",  # sourceGUID
        "Healer-1",  # sourceName
        "0x00000010",  # sourceFlags
        "0x00000020",  # sourceRaidFlags
        "55555",  # destGUID
        "Target-2",  # destName
        "0x00000040",  # destFlags
        "0x00000080",  # destRaidFlags
        "nil",
        "nil",
        "nil",
        "nil",
        "nil",
        "nil",
        "nil",
        "nil",
        "5000",  # amount
        "1000",  # overhealing
        "0",  # absorbed
        "nil",  # critical
    ]

    result = parser.parse_cols(ts, cols)

    expected_result = {
        "timestamp": ts,
        "event": "HEAL",
        "sourceGUID": "44444",
        "sourceName": "Healer-1",
        "sourceFlags": ["REACTION_FRIENDLY"],
        "sourceRaidFlags": ["REACTION_NEUTRAL"],
        "destGUID": "55555",
        "destName": "Target-2",
        "destFlags": ["REACTION_HOSTILE"],
        "destRaidFlags": ["REACTION_MASK"],
        "amount": 5000,
        "overhealing": 1000,
        "absorbed": 0,
        "critical": False,
    }

    assert result == expected_result
