import json
import os
from datetime import datetime

import pandas as pd
from patch_dates import PATCH_DATES


def read_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (UnicodeDecodeError, json.JSONDecodeError, Exception) as e:
        log_error(f"Erro ao processar o arquivo {file_path}: {e}")
        return []


def write_json_file(data, file_path):
    try:
        with open(file_path, "w", encoding="utf-8") as outfile:
            json.dump(data, outfile, indent=4, ensure_ascii=False)
    except Exception as e:
        log_error(f"Erro ao escrever o arquivo {file_path}: {e}")


def encontrar_patch_version(timestamp):
    dt = datetime.fromtimestamp(timestamp)
    for year in sorted(PATCH_DATES.keys(), reverse=True):
        for patch, date_str in sorted(
            PATCH_DATES[year].items(), key=lambda x: x[1], reverse=True
        ):
            if dt >= datetime.strptime(date_str, "%Y-%m-%d"):
                return patch
    return "desconhecido"


def processar_evento(event, partida_atual, arvore_eventos):
    try:
        if event["event"] == "ARENA_MATCH_START":
            partida_finalizada = None
            if partida_atual:
                partida_finalizada = finalizar_partida(partida_atual, arvore_eventos)
            partida_nova = criar_nova_partida(event)
            return partida_finalizada, partida_nova
        atualizar_partida(event, partida_atual, arvore_eventos)
    except KeyError as e:
        log_error(f"Chave ausente {e} em evento: {event}")
    return None, partida_atual


def criar_nova_partida(event):
    return {
        "timestamp": event["timestamp"],
        "event": event["event"],
        "instanceID": event["instanceID"],
        "matchType": event.get("matchType", ""),
        "teamId": event.get("teamId", ""),
        "patch_version": encontrar_patch_version(event["timestamp"]),
        "combatants": [],
        "spells": [],
        "damage_events": [],
    }


def atualizar_partida(event, partida_atual, arvore_eventos):
    if event["event"] == "COMBATANT_INFO":
        partida_atual["combatants"].append(
            {
                "playerguid": event["playerguid"],
                "faction": event["faction"],
                "character_stats": event["character_stats"],
                "currentSpecID": event["currentSpecID"],
                "classTalents": event["classTalents"],
                "pvpTalents": event["pvpTalents"],
                "equippedItems": event["equippedItems"],
                "interestingAuras": event.get("interestingAuras", []),
                "pvpStats": event["pvpStats"],
            }
        )
    elif event["event"] in ["SPELL_DAMAGE", "SWING_DAMAGE"]:
        partida_atual["damage_events"].append(
            {
                "damage_timestamp": event["timestamp"],
                "sourceGUID": event.get("sourceGUID", None),
                "sourceName": event.get("sourceName", None),
                "destGUID": event.get("destGUID", None),
                "destName": event.get("destName", None),
                "spellId": event.get("spellId", None),
                "spellName": event.get("spellName", None),
                "amount": event.get("amount", None),
                "overkill": event.get("overkill", 0),
                "school": event.get("school", None),
                "critical": event.get("critical", False),
                "glancing": event.get("glancing", False),
                "crushing": event.get("crushing", False),
                "absorbed": event.get("absorbed", 0),
            }
        )
    else:
        partida_atual["spells"].append(event)
    atualizar_arvore_eventos(event, arvore_eventos)


def atualizar_arvore_eventos(event, arvore_eventos):
    if event["event"] in ["UNIT_DIED", "PARTY_KILL", "SPELL_INSTAKILL"]:
        if event["destGUID"] not in arvore_eventos:
            arvore_eventos[event["destGUID"]] = {"mortes": 0, "ressurreições": 0}
        arvore_eventos[event["destGUID"]]["mortes"] += 1
    elif event["event"] == "SPELL_RESURRECT":
        if event["destGUID"] not in arvore_eventos:
            arvore_eventos[event["destGUID"]] = {"mortes": 0, "ressurreições": 0}
        arvore_eventos[event["destGUID"]]["ressurreições"] += 1


def detectar_fim_partida(event):
    return event["event"] in ["ARENA_MATCH_START", "ARENA_MATCH_END"]


def calcular_duracao_partida(partida):
    timestamp_inicial = partida["timestamp"]
    if partida["damage_events"]:
        timestamp_final = partida["damage_events"][-1]["damage_timestamp"]
    elif partida["spells"]:
        timestamp_final = partida["spells"][-1]["timestamp"]
    else:
        timestamp_final = timestamp_inicial
    return timestamp_final - timestamp_inicial


def finalizar_partida(partida_atual, arvore_eventos):
    duracao = calcular_duracao_partida(partida_atual)
    partida_atual["duration"] = duracao
    partida_atual["event_tree"] = arvore_eventos
    return partida_atual


def log_error(message):
    print(message)


def padronizar_arquivo(file_path):
    data = read_json_file(file_path)
    partidas = []
    arvore_eventos = {}
    partida_atual = None

    for event in data:
        if detectar_fim_partida(event):
            if partida_atual:
                finalizada, partida_atual = processar_evento(
                    event, partida_atual, arvore_eventos
                )
                if finalizada:
                    partidas.append(finalizada)
                    arvore_eventos = {}
            else:
                _, partida_atual = processar_evento(event, None, arvore_eventos)
        else:
            _, partida_atual = processar_evento(event, partida_atual, arvore_eventos)

    if partida_atual:
        partidas.append(finalizar_partida(partida_atual, arvore_eventos))

    return partidas


def processar_arquivos(diretorio, limite=10):
    arquivos_padronizados = []
    arquivos = [f for f in os.listdir(diretorio) if f.endswith(".json")][:limite]
    for file_name in arquivos:
        caminho_arquivo = os.path.join(diretorio, file_name)
        partidas = padronizar_arquivo(caminho_arquivo)
        arquivos_padronizados.extend(partidas)
    return arquivos_padronizados


# Normalização

combatants_meta = [
    "timestamp",
    "event",
    "instanceID",
    "matchType",
    "teamId",
    "patch_version",
]
damage_meta = [
    "damage_events.damage_timestamp",
    "damage_events.sourceGUID",
    "damage_events.sourceName",
    "damage_events.destGUID",
    "damage_events.destName",
    "patch_version",
]


def normalize_combatants(data):
    try:
        df_combatants = pd.json_normalize(
            data, "combatants", combatants_meta, errors="ignore", sep="_"
        )
        return df_combatants
    except ValueError as e:
        log_error(f"Erro ao normalizar combatants: {e}")
        return pd.DataFrame()


def normalize_damage_events(data):
    try:
        df_damage = pd.json_normalize(
            data, "damage_events", damage_meta, errors="ignore", sep="_"
        )
        return df_damage
    except ValueError as e:
        log_error(f"Erro ao normalizar damage_events: {e}")
        return pd.DataFrame()


def normalizar_dados(dados_padronizados):
    df_combatants = normalize_combatants(dados_padronizados)
    df_damage = normalize_damage_events(dados_padronizados)
    return df_combatants, df_damage


def setup_display_options():
    pd.set_option("display.float_format", lambda x: "%.3f" % x)


def main():
    setup_display_options()
    diretorio = r"D:\Projetos_Git\dlLogs\scripts\output_json"
    dados_padronizados = processar_arquivos(diretorio, 10)
    write_json_file(dados_padronizados, "dados_padronizados_teste.json")

    df_combatants, df_damage = normalizar_dados(dados_padronizados)

    print("DataFrame de Combatentes:")
    print(df_combatants.head())

    print("\nDataFrame de Eventos de Dano:")
    print(df_damage.head())


if __name__ == "__main__":
    main()
