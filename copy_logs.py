#!/usr/bin/python3.11
import os
import random
import re
import time
from pathlib import Path
from typing import BinaryIO

import chardet
import requests
import schedule
from tqdm import tqdm

URL_BASE = 'https://storage.googleapis.com/wowarenalogs-log-files-prod/'
BASE_DIR = os.getcwd()
KEYS_FILE = Path(BASE_DIR) / 'keys.txt'
LOGS_DIR = Path(BASE_DIR) / 'logs'
'''
KEYS_FILE = Path('D:/Projetos_Git/Meus-testes/logs_internet/keys.txt')
LOGS_DIR = Path('D:/Projetos_Git/Meus-testes/logs_internet/logs')
'''
# Define o tamanho máximo do trecho do arquivo de log a ser lido
MAX_BYTES = 50000000


def get_xml() -> requests.Response:
    """Busca o XML no servidor remoto."""
    response = requests.get(URL_BASE)
    response.raise_for_status()
    return response


def get_keys_from_response(response: requests.Response) -> set:
    # Retorna um conjunto de chaves do XML.
    return set(re.findall(r'<Key>(.*?)</Key>', response.content.decode()))


def download_log_file(log_key: str, response: requests.Response, progress_bar: tqdm, bytes_total: int) -> None:
    """
    Baixa um arquivo de log de uma determinada chave e o salva no disco.
    """
    url = URL_BASE + log_key
    time.sleep(random.uniform(4, 5))
    log_file_path = LOGS_DIR / f'{log_key}.txt'

    if not log_file_path.exists() or not is_log_file_complete(log_file_path, response):
        response = requests.get(url, stream=True)

        with open(log_file_path, 'wb') as file:
            download_file(response, file, progress_bar,
                          log_file_path=log_file_path, bytes_total=bytes_total)

        with open(log_file_path, 'rb') as file:
            log_bytes = file.read(MAX_BYTES)
            encoding = detect_encoding(log_bytes)

        with open(log_file_path, 'w', encoding='utf-8') as file:
            file.write(log_bytes.decode(encoding))

        if is_log_file_complete(log_file_path, response):
            update_keys_file(log_key)
        else:
            log_file_path.unlink()

    else:
        update_keys_file(log_key)


def download_file(response: requests.Response, file: BinaryIO,
                  progress_bar: tqdm, log_file_path: Path, bytes_total:
                  int) -> None:
    """
    Baixa um arquivo de log de uma determinada chave e o salva em um arquivo binário.
    """
    bytes_downloaded = 0
    start_time = time.time()

    for chunk in response.iter_content(chunk_size=1024):
        if chunk:
            file.write(chunk)
            file.flush()
            bytes_downloaded += len(chunk)
            progress_bar.update(len(chunk))
            progress_bar.set_description(
                f'Downloading {log_file_path.name} {bytes_downloaded/bytes_total:.0%})')

    elapsed_time = time.time() - start_time
    speed = (bytes_downloaded / elapsed_time) / (1024 * 1024)
    progress = f'{log_file_path} - {speed:.2f} MB/s'
    tqdm.write(progress)


def detect_encoding(log_bytes: bytes) -> str:
    """
    Detecta a codificação de caracteres de um arquivo de log.
    """
    encoding = chardet.detect(log_bytes)['encoding']
    return encoding if encoding else 'utf-8'


def is_log_file_complete(file_path: Path, response: requests.Response) -> bool:
    """Verifica se um arquivo de log está completo."""
    expected_size = int(response.headers.get('Content-Length', 0))
    return file_path.stat().st_size >= expected_size


def check_logs_on_disk(response: requests.Response) -> None:
    """Verifica se todos os arquivos de log correspondentes a cada chave 
    listada no XML estão presentes no disco."""
    keys_xml = get_keys_from_response(response)
    missing_logs = keys_xml - set([f.stem for f in LOGS_DIR.glob('*.txt')])

    if missing_logs:
        print(f'Os seguintes logs estão faltando no disco: {missing_logs}')
    else:
        print('Todos os logs estão presentes no disco.')


def update_keys_file(key: str) -> None:
    """Atualiza o arquivo keys.txt com a nova chave, caso ela ainda não esteja presente no arquivo."""
    with open(KEYS_FILE, 'r') as f:
        keys = set(f.read().splitlines())
    if key not in keys:
        with open(KEYS_FILE, 'a') as f:
            f.write(key + '\n')


def main() -> None:
    """Baixa os logs para as chaves especificadas no servidor remoto."""

    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir(parents=True)

    print('Baixando o XML...')

    response = get_xml()

    keys_xml = get_keys_from_response(response)

    keys_downloaded = set([f.stem for f in LOGS_DIR.glob('*.txt')])

    new_keys = keys_xml - keys_downloaded

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


def run_job():
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
    # Se algun erro ocorrer, pare a execução
