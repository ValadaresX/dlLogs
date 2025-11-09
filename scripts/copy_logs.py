import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import chardet
import requests
from tqdm import tqdm

from url import url_base

# Paleta de cores simples (ANSI)
C_RESET = "\033[0m"
C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_BLUE = "\033[94m"
C_YELLOW = "\033[93m"

# Símbolos de status
S_OK = f"[{C_GREEN}✓{C_RESET}]"
S_ERR = f"[{C_RED}✗{C_RESET}]"
S_INFO = f"[{C_BLUE}i{C_RESET}]"
S_WARN = f"[{C_YELLOW}!{C_RESET}]"

# Diretório de logs e arquivo de controle
logs_dir = Path.cwd() / "logs"
os.makedirs(logs_dir, exist_ok=True)

DOWNLOADED_LOGS_FILE = logs_dir / "downloaded_logs.json"


def load_downloaded_logs() -> set:
    """Carrega os nomes dos logs já baixados do arquivo JSON."""
    if not DOWNLOADED_LOGS_FILE.exists():
        print(
            f"{S_WARN} Aviso: {DOWNLOADED_LOGS_FILE.name} não encontrado. "
            "Criando um novo..."
        )
        return set()

    try:
        with open(DOWNLOADED_LOGS_FILE, "r", encoding="utf-8") as f:
            downloaded_list = json.load(f)

        if not isinstance(downloaded_list, list):
            print(
                f"{S_ERR} Erro: {DOWNLOADED_LOGS_FILE.name} não contém uma lista. "
                "Tratando como vazio."
            )
            return set()

        return set(downloaded_list)

    except json.JSONDecodeError:
        print(
            f"{S_ERR} Erro: {DOWNLOADED_LOGS_FILE.name} está corrompido ou vazio. "
            "Tratando como novo."
        )
        return set()
    except (FileNotFoundError, TypeError) as e:
        print(
            f"{S_ERR} Erro inesperado ao ler {DOWNLOADED_LOGS_FILE}: {e}. "
            "Tratando como vazio."
        )
        return set()


def update_downloaded_logs(successfully_downloaded_keys: set) -> None:
    """Atualiza o JSON com os novos logs baixados com sucesso."""
    if not successfully_downloaded_keys:
        return

    downloaded_logs_set = load_downloaded_logs()
    downloaded_logs_set.update(successfully_downloaded_keys)

    try:
        with open(DOWNLOADED_LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(downloaded_logs_set), f, indent=4)

        print(
            f"{S_OK} {len(successfully_downloaded_keys)} novos logs adicionados "
            f"ao {DOWNLOADED_LOGS_FILE.name}"
        )
    except IOError as e:
        print(f"{S_ERR} Erro crítico ao salvar {DOWNLOADED_LOGS_FILE}: {e}")


def get_remote_xml_data(
    last_modified: str | None = None,
) -> tuple[str | None, str | None]:
    """Obtém dados XML remotos e detecta a codificação."""
    headers = {"If-Modified-Since": last_modified} if last_modified else {}
    response = requests.get(url_base, headers=headers)

    if response.status_code == 304:
        # Nada modificado desde a última consulta
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


def get_new_keys(found_keys: set) -> tuple[set, set]:
    """Compara as chaves encontradas com o JSON de logs baixados."""
    downloaded_logs = load_downloaded_logs()

    # Chaves que estão no XML e ainda não estão no JSON
    new_key_names = found_keys - downloaded_logs

    base_url_sem_barra = url_base.rstrip("/")
    new_key_urls = {f"{base_url_sem_barra}/{key}" for key in new_key_names}

    return new_key_urls, new_key_names


def download_file(url: str, logs_dir: Path) -> str | None:
    """
    Baixa um único arquivo de log.
    Retorna o nome (chave) do arquivo em caso de sucesso, ou None em caso de falha.
    """
    try:
        file_name_key = url.split("/")[-1]

        # Mantém o comportamento original: prefixo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name_txt = f"{timestamp}_{file_name_key}.txt"
        file_path = logs_dir / file_name_txt

        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(file_path, "wb") as f:
            f.write(response.content)

        return file_name_key

    except requests.RequestException as e:
        # Esse print pode interferir levemente na barra do tqdm, mas é importante
        print(f"\n{S_ERR} Erro ao baixar {url}: {e}")
        if "file_path" in locals() and file_path.exists():
            os.remove(file_path)
        return None


def download_text_files(new_keys_urls: set, logs_dir: Path) -> set:
    """
    Faz o download de todos os novos arquivos de log.
    Retorna um set contendo apenas as chaves dos arquivos baixados com sucesso.
    """
    if not new_keys_urls:
        return set()

    successfully_downloaded_keys: set = set()

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(download_file, url, logs_dir): url for url in new_keys_urls
        }

        results_iterator = tqdm(
            future_to_url,
            total=len(new_keys_urls),
            desc=f"{S_INFO} Baixando logs",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]",
        )

        for future in results_iterator:
            key = future.result()
            if key is not None:
                successfully_downloaded_keys.add(key)

    if successfully_downloaded_keys:
        print(
            f"{S_OK} {len(successfully_downloaded_keys)}/{len(new_keys_urls)} "
            "registros de log baixados com sucesso!"
        )
    elif new_keys_urls:
        print(f"{S_ERR} Nenhum log pôde ser baixado ({len(new_keys_urls)} tentativas).")

    return successfully_downloaded_keys


def execute_main(last_modified: str | None = None) -> tuple[bool, str | None]:
    """Executa a função principal para obter e baixar novos logs."""
    try:
        data, last_modified = get_remote_xml_data(last_modified)
    except Exception as e:
        print(f"{S_ERR} Erro ao buscar dados XML: {e}")
        return False, last_modified

    if data is None:
        # Status 304 - Nada modificado
        return False, last_modified

    found_keys = filter_key_tag(data)
    if not found_keys:
        print(f"{S_WARN} Aviso: XML recebido, mas nenhuma <Key> encontrada.")
        return False, last_modified

    new_key_urls, _new_key_names = get_new_keys(found_keys)
    if not new_key_urls:
        # XML válido, mas nenhum log novo
        return False, last_modified

    successfully_downloaded_keys = download_text_files(new_key_urls, logs_dir)

    if successfully_downloaded_keys:
        update_downloaded_logs(successfully_downloaded_keys)
        return True, last_modified

    return False, last_modified


def run() -> None:
    """Executa o processo principal e agenda a próxima execução."""
    last_modified: str | None = None

    while True:
        success, last_modified = execute_main(last_modified)

        if not success:
            print(
                f"{S_INFO} Não há novos registros para download "
                "(ou downloads falharam). Reagendando..."
            )

        # Intervalo aleatório (jitter) em segundos: 6h a 8h
        min_wait = 6 * 60 * 60  # 6 horas
        max_wait = 8 * 60 * 60  # 8 horas
        wait_time = random.randint(min_wait, max_wait)

        wait_hours = wait_time // 3600
        wait_minutes = (wait_time % 3600) // 60

        print(
            f"{S_INFO} Aguardando {wait_hours} horas e "
            f"{wait_minutes} minutos para a próxima verificação..."
        )

        time.sleep(wait_time)


if __name__ == "__main__":
    run()
