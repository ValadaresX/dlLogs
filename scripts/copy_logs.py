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


def get_remote_xml_data(last_modified=None):
    """Obtém dados XML remotos e detecta a codificação."""
    headers = {"If-Modified-Since": last_modified} if last_modified else {}
    response = requests.get(url_base, headers=headers)

    if response.status_code == 304:
        return None, last_modified

    encoding = chardet.detect(response.content)["encoding"]
    if not encoding:
        raise ValueError("Não foi possível determinar a codificação dos dados.")

    last_modified = response.headers.get("Last-Modified")
    conteudo_xml = response.content.decode(encoding)
    return conteudo_xml, last_modified


def filter_key_tag(data_xml: str) -> set:
    """Filtra e retorna as chaves encontradas no XML."""
    pattern = r"<Key>(.*?)</Key>"
    return set(re.findall(pattern, data_xml))


def get_new_keys(found_keys: set, logs_dir: Path) -> set:
    """Obtém novas chaves que não estão presentes no diretório de logs."""
    arquivos_existentes = {
        f.name.split("_", 1)[-1].rsplit(".", 1)[0]
        for f in logs_dir.iterdir()
        if f.is_file()
    }
    return {url_base + key for key in found_keys if key not in arquivos_existentes}


def download_file(url: str, logs_dir: Path):
    """Faz o download de um arquivo de log e o salva no diretório de logs."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        log_text = response.text
        filename = logs_dir / f"{time.localtime().tm_year}_{os.path.basename(url)}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(log_text)
    except requests.exceptions.RequestException as e:
        print(f"\033[91mErro ao baixar arquivo {url}: {e}\033[0m")


def download_text_files(new_keys: set, logs_dir: Path) -> bool:
    """Faz o download de todos os novos arquivos de log."""
    if not new_keys:
        return False
    with ThreadPoolExecutor(max_workers=5) as executor:
        list(
            tqdm(
                executor.map(lambda url: download_file(url, logs_dir), new_keys),
                total=len(new_keys),
                desc="Baixando logs",
            )
        )
    print("\033[92mRegistros de log baixados com sucesso!\033[0m")
    return True


def execute_main(last_modified=None):
    """Executa a função principal para obter e baixar novos logs."""
    data, last_modified = get_remote_xml_data(last_modified)
    if data is None:
        return False, last_modified
    found_keys = filter_key_tag(data)
    new_keys = get_new_keys(found_keys, logs_dir)
    success = download_text_files(new_keys, logs_dir)
    return success, last_modified


def run():
    """Executa o processo principal e agenda a próxima execução."""
    last_modified = None
    while True:
        success, last_modified = execute_main(last_modified)
        if not success:
            print("\033[91mNão há novos registros para download. Reagendando...\033[0m")
        intervalo = random.uniform(7, 9) * 3600
        print(f"\033[94mPróxima execução em {intervalo / 3600:.2f} horas\033[0m")
        time.sleep(intervalo)


if __name__ == "__main__":
    print("\033[91mExecutando main pela primeira vez...\033[0m")
    run()
