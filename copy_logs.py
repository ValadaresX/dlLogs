#!/usr/bin/python3.11
import logging
import os
import random
import re
import time
from pathlib import Path

import chardet
import requests
from tqdm import tqdm

# Configuração básica de logging
logging.getLogger('urllib3').setLevel(logging.INFO)
logging.StreamHandler()


URL_BASE = 'https://storage.googleapis.com/wowarenalogs-log-files-prod/'
BASE_DIR = os.getcwd()
KEYS_FILE = Path(BASE_DIR) / 'keys.txt'
LOGS_DIR = Path(BASE_DIR) / 'logs'


MAX_BYTES = 50000000  # Define o tamanho máximo do trecho do arquivo de log a ser lido


def get_xml() -> requests.Response:  # Busca o XML no servidor remoto
    response = requests.get(URL_BASE)
    response.raise_for_status()
    return response


# Retorna um conjunto de chaves do XML.
def get_keys_from_response(response: requests.Response) -> set:
    return set(re.findall(r'<Key>(.*?)</Key>', response.content.decode()))


# Faz o download de um arquivo de registro de uma determinada chave e o salva no disco.
def download_log_file(log_key: str, response: requests.Response, progress_bar: tqdm, bytes_total: int) -> None:
    url = URL_BASE + log_key
    log_file_path = LOGS_DIR / f'{log_key}.txt'

    if not log_file_path.exists() or not is_log_file_complete(log_file_path, response):
        response = requests.get(url, stream=True)
        download_file(response, log_file_path, progress_bar, bytes_total)
        fix_encoding(log_file_path)
        if is_log_file_complete(log_file_path, response):
            update_keys_file(log_key)
        else:
            log_file_path.unlink()
    else:
        update_keys_file(log_key)


def download_file(response: requests.Response, log_file_path: str, progress_bar: tqdm, bytes_total: int) -> None:
    with open(log_file_path, 'wb') as file:
        for chunk in response.iter_content(1024):
            file.write(chunk)
            progress_bar.update(len(chunk))


def fix_encoding(log_file_path: Path) -> None:
    with log_file_path.open('rb') as file:
        log_bytes = file.read(MAX_BYTES)
        encoding = detect_encoding(log_bytes)
    with log_file_path.open('w', encoding='utf-8') as file:
        file.write(log_bytes.decode(encoding))


# Detecta a codificação de caracteres de um arquivo de log.
def detect_encoding(log_bytes: bytes) -> str:
    encoding = chardet.detect(log_bytes)['encoding']
    return encoding if encoding else 'utf-8'


# Verifica se um arquivo de log está completo.
def is_log_file_complete(file_path: Path, response: requests.Response) -> bool:
    expected_size = int(response.headers.get('Content-Length', 0))
    return file_path.stat().st_size >= expected_size


def check_logs_on_disk(response: requests.Response) -> None:
    # Verifica se todos os arquivos de log correspondentes a cada chave listada no XML estão presentes no disco.
    keys_xml = get_keys_from_response(response)
    missing_logs = keys_xml - set([f.stem for f in LOGS_DIR.glob('*.txt')])

    if missing_logs:
        print(f'Os seguintes logs estão faltando no disco: {missing_logs}')
    else:
        print('Todos os logs estão presentes no disco.')


# Atualiza o arquivo keys.txt com a nova chave, caso ela ainda não esteja presente no arquivo.
def update_keys_file(key: str) -> None:
    with open(KEYS_FILE, 'r') as f:
        keys = set(f.read().splitlines())
    if key not in keys:
        with open(KEYS_FILE, 'a') as f:
            f.write(key + '\n')


def download_new_logs() -> None:  # Baixa novos logs do servidor remoto.
    new_keys = get_new_keys()
    if new_keys:
        print(f'Baixando {len(new_keys)} novos logs...')
        total_size = 0
        for key in new_keys:
            url = URL_BASE + key
            response = requests.head(url)
            total_size += int(response.headers.get('Content-Length', 0))
        with tqdm(total=total_size, unit_scale=True, unit='B', bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as progress_bar:
            for key in new_keys:
                download_log_file(key, response, progress_bar,
                                  bytes_total=total_size)
    else:
        print('Todos os logs estão presentes no disco.')


def get_new_keys() -> set:
    """Retorna um conjunto de novas chaves."""
    response = get_xml()
    keys_xml = get_keys_from_response(response)
    keys_downloaded = set([f.stem for f in LOGS_DIR.glob('*.txt')])
    return keys_xml - keys_downloaded


def main() -> None:
    """Baixa os logs para as chaves especificadas no servidor remoto."""

    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir(parents=True)

    print('Baixando o XML...')

    download_new_logs()


def run_job():  # Executão do script no intervalo entre 8 a 10 horas
    random_seconds = random.uniform(8 * 3600, 10 * 3600)
    total_time = int(random_seconds)
    with tqdm(total=total_time, desc="Próxima execução...") as pbar:
        while total_time > 0:
            time.sleep(1)
            pbar.update(1)
            total_time -= 1
    main()


if __name__ == '__main__':
    main()
    while True:
        run_job()
