import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import chardet
import requests
from tqdm import tqdm

from url import url_base

# Configuração do diretório
logs_dir = Path.cwd() / "logs"
os.makedirs(logs_dir, exist_ok=True)


def get_remote_xml_data() -> str:
    response = requests.get(url_base)
    encoding = chardet.detect(response.content)["encoding"]
    if not encoding:
        raise ValueError("Não foi possível determinar a codificação dos dados.")
    return response.content.decode(encoding)


def filter_key_tag(data_xml: str) -> set:
    pattern = r"<Key>(.*?)</Key>"
    found_keys = re.findall(pattern, data_xml)
    return set(found_keys)


def get_new_keys(found_keys: set, url_base: str, logs_dir: Path) -> set:
    new_keys = set()
    for key in found_keys:
        log_file_path = logs_dir / f"{key}.txt"
        if not log_file_path.exists():
            new_keys.add(url_base + key)
    return new_keys


def download_file(url: str, logs_dir: Path):
    response = requests.get(url)
    log_text = response.text
    filename = logs_dir / f"{time.localtime().tm_year}_{os.path.basename(url)}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(log_text)


def download_text_files(new_keys: set, logs_dir: Path) -> bool:
    if not new_keys:
        return False

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(download_file, url, logs_dir) for url in new_keys]
        for future in tqdm(futures, total=len(futures), desc="Downloading logs"):
            future.result()  # Aguardar a conclusão de cada futuro

    print("Registros de log baixados com sucesso!!!")
    return True


def main():
    data = get_remote_xml_data()
    found_keys = filter_key_tag(data)
    new_keys = get_new_keys(found_keys, url_base, logs_dir)
    return download_text_files(new_keys, logs_dir)


def format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours} horas, {minutes} minutos e {seconds} segundos"


def schedule_job():
    intervalo = random.uniform(7, 9)
    print(f"\033[94mPróxima execução em {intervalo:.2f} horas\033[0m")
    return intervalo * 3600


def countdown(seconds):
    for remaining in range(int(seconds), 0, -1):
        print(
            f"\r\033[92mTempo restante até a próxima execução: {format_duration(remaining)}\033[0m",
            end=" ",
        )
        time.sleep(1)
    print()


def run():
    if not main():
        print("\033[91mNão há novos registros para download. Reagendando...\033[0m")
    next_run_in = schedule_job()
    countdown(next_run_in)


if __name__ == "__main__":
    print("Executando main pela primeira vez...")
    while True:
        run()
