import json
import os
import re
from collections import defaultdict


def parse_event_line(event_type, event_parts):
    event_data = {}
    event_data['type'] = event_type

    # Adicione aqui a lógica de análise para cada tipo de evento
    # Exemplo:
    if event_type == 'SPELL_AURA_APPLIED':
        event_data['source'] = event_parts[1].strip()
        event_data['target'] = event_parts[2].strip()
        # Adicione mais campos conforme necessário

    return event_data


def process_events(folder_path):
    events = []

    for file_name in os.listdir(folder_path):
        if file_name.endswith('.txt'):
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, 'r') as file:
                for line in file:
                    match = re.match(
                        r'\d{1,2}\/\d{1,2} \d{1,2}:\d{1,2}:\d{1,2}\.\d{1,}\s+(.+)', line)
                    if match:
                        event_data = match.group(1)
                        event_parts = event_data.split(',')
                        event_type = event_parts[0].strip()

                        # Analisa a linha com base no tipo de evento e no número de elementos
                        event = parse_event_line(event_type, event_parts)
                        events.append(event)

    return events


folder_path = 'D:\\Projetos_Git\\dlLogs\\logs'
events = process_events(folder_path)

# Converter a lista de eventos em uma string JSON
json_data = json.dumps(events, indent=2)

# Salvar a string JSON em um arquivo
with open('combat_log.json', 'w') as json_file:
    json_file.write(json_data)

print("Arquivo JSON gerado com sucesso.")
