import json
from datetime import datetime


def read_log_file(filepath: str) -> set:
    timestamps = set()
    with open(filepath, "r") as file:
        for line in file:
            if line.strip():
                parts = line.split(" ", 3)
                date_time_str = f"{datetime.now().year}/{parts[0]} {parts[1]}"
                timestamp = datetime.strptime(
                    date_time_str, "%Y/%m/%d %H:%M:%S.%f"
                ).timestamp()
                timestamps.add(timestamp)
    return timestamps


def read_json_file(filepath: str) -> set:
    with open(filepath, "r") as file:
        data = json.load(file)
        return {entry["timestamp"] for entry in data}


def compare_timestamps(text_timestamps: set, json_timestamps: set) -> bool:
    return text_timestamps == json_timestamps


def verify_conversion(text_log_path: str, json_path: str) -> bool:
    text_timestamps = read_log_file(text_log_path)
    json_timestamps = read_json_file(json_path)
    return compare_timestamps(text_timestamps, json_timestamps)


# Uso da função
text_log_path = "dados_brutos_teste_v3.txt"
json_path = "output.json"
conversion_verified = verify_conversion(text_log_path, json_path)
print("Conversão verificada:", conversion_verified)
