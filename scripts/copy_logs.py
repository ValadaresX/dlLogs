import os
import random
import re
import time
import urllib.parse
from pathlib import Path

import requests
from chardet import detect
from tqdm import tqdm

#  Configuração do diretorios
url_base = "https://storage.googleapis.com/wowarenalogs-log-files-prod/"

KEYS_FILE = Path.cwd() / "keys.txt"

logs_dir = Path.cwd() / "logs"


def get_status_code(response: requests.Response) -> int:
    """
    Faz uma solicitação GET à URL especificada e retorna o
    código de status da resposta.

    :param response: Um objeto Response da biblioteca requests.
    :type response: requests.Response
    :return: O código de status da resposta.
    :rtype: int
    """
    return response.status_code


def get_remote_xml_data() -> str:
    """
    Faz uma solicitação GET a url_base e retorna o conteúdo da resposta
    em formato de string decodificada de acordo com a codificação detectada.
    Essa função não recebe nenhum parâmetro e sempre retorna
    uma cadeia de caracteres.

    :return: O conteúdo da resposta em formato de string decodificada
             de acordo com a codificação detectada.
    :rtype: str
    """
    response = requests.get(url_base)
    encoding = detect(response.content)["encoding"]
    return response.content.decode(encoding)


def filter_key_tag(data_xml: str) -> set:
    """
    Filtra os dados XML e extrai as chaves contidas nas tags <Key>
    Args:
        data_xml (str): Os dados XML a serem filtrados.
    Returns:
        set: Um conjunto de chaves extraídas dos dados XML.
    Example:
        >>> data = "<Contents><Key>00011f1647ad1b3ee67683f1b632da97</Key></Contents>"
        >>> filter_key_tag(data)
        {'key1', 'key2'}
    """
    pattern = r"<Key>(.*?)</Key>"
    found_keys = re.findall(pattern, data_xml)
    return set(found_keys)
    # set = {"0000032d4670450f735dbde7d1fd0c3b", "00000948a8751f20ef7405c3b3bec537"}


def get_new_keys(found_keys: set[str], url_base: str, logs_dir: Path) -> set:
    """
    Recebe um conjunto de chaves no formato XML e uma base de URL como
    entrada e retorna um novo conjunto de chaves com a base de URL
    anexado a cada chave. O conjunto de entrada não é modificado.
    Verifica se todos os logs já existem no diretório de logs.

    param existing_keys: Um conjunto de chaves no formato XML.
    Tipo existing_keys: set
    param url_base: Uma cadeia de caracteres que representa a URL
                    base a ser anexada a cada chave.
    Tipo url_base: str
    param logs_dir: Um objeto Path que representa o
                    diretório em que os registros são armazenados.
    Tipo logs_dir: Path
    :return: Um novo conjunto de chaves com a base de URL anexada a cada chave.
    :rtype: set
    """
    new_keys = set()
    for key in found_keys:
        log_file_path = logs_dir / f"{key}.txt"
        if not log_file_path.exists():
            new_keys.add(url_base + key)
    return new_keys


def download_text_files(new_keys: set[str], logs_dir: Path, pbar: tqdm) -> None:
    # Verificar se o parâmetro não é vazio
    if not new_keys:
        raise ValueError("Não há novos registros para download.")
    # Informa quantos registros serão baixados
    print(f"Existem {len(new_keys)} registros para baixar.")
    # Usa time para espera 3 segundos
    time.sleep(50)

    # Verificar se o parâmetro não uma URL válida
    for url in new_keys:
        if not urllib.parse.urlparse(url).scheme:
            raise ValueError("O parâmetro 'new_keys' deve conter apenas URLs válidos.")

    with requests.get(new_keys, stream=True) as response:
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        pbar.total = total_size
        pbar.refresh()

        log_bytes = b"".join([fragment for fragment in response.iter_content(5000000)])
        encoding = detect(log_bytes)["encoding"]
        log_text = log_bytes.decode(encoding)

    with logs_dir.open("w", encoding="utf-8") as file:
        file.write(log_text)

    print("Registros de log baixados com sucesso!!")


# Teste do script
def main():
    dados = get_remote_xml_data()
    filtro = filter_key_tag(dados)
    novas_chaves = get_new_keys(filtro, url_base, logs_dir)
    pbar = tqdm(total=100)
    download_text_files(novas_chaves, logs_dir, pbar)


if __name__ == "__main__":
    main()

"""

#  Fixa a codificação de caracteres de um arquivo de log.
def fix_encoding(log_file_path: Path) -> None:
    with log_file_path.open("rb") as file:
        log_bytes = file.read(max_bytes)

        encoding = detect_encoding(log_bytes)

    with log_file_path.open("w", encoding="utf-8") as file:
        file.write(log_bytes.decode(encoding))


# Detecta a codificação de caracteres de um arquivo de log.
def detect_encoding(log_bytes: bytes) -> str:
    encoding = chardet.detect(log_bytes)["encoding"]

    return encoding if encoding else "utf-8"


# Verifica se um arquivo de log está completo.
def is_log_file_complete(file_path: Path, response: requests.Response) -> bool:
    expected_size = int(response.headers.get("Content-Length", 0))

    return file_path.stat().st_size >= expected_size


# Verifica se arquivos de log correspondentes às chaves do XML estão no disco.
def check_logs_on_disk(response: requests.Response) -> None:
    keys_xml = get_keys_from_response(response)

    missing_logs = keys_xml - set([f.stem for f in logs_dir.glob("*.txt")])

    if missing_logs:
        print(f"Os seguintes logs estão faltando no disco: {missing_logs}")

    else:
        print("Todos os logs estão presentes no disco.")


# Atualiza keys.txt com nova chave, se ainda não presente no arquivo.
def update_keys_file(key: str) -> None:
    with open(KEYS_FILE, "r") as f:
        keys = set(f.read().splitlines())

    if key not in keys:
        with open(KEYS_FILE, "a") as f:
            f.write(key + "\n")


# Baixa novos logs do servidor remoto.
def download_new_logs() -> None:
    new_keys = get_new_keys()

    if new_keys:
        print(f"Baixando {len(new_keys)} novos logs...")

        total_size = 0

        for key in new_keys:
            url = URL_BASE + key

            response = requests.head(url)

            total_size += int(response.headers.get("Content-Length", 0))

        with tqdm(
            total=total_size,
            unit_scale=True,
            unit="B",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        ) as progress_bar:
            for key in new_keys:
                download_log_file(key, response, progress_bar, bytes_total=total_size)

    else:
        print("Todos os logs estão presentes no disco.")




# Executão do script no intervalo entre 8 a 10 horas
def run_job():
    random_seconds = random.uniform(8 * 3600, 10 * 3600)

    total_time = int(random_seconds)

    with tqdm(total=total_time, desc="Próxima execução...") as pbar:
        while total_time > 0:
            time.sleep(1)

            pbar.update(1)

            total_time -= 1
    main()


# Baixa os logs para as chaves especificadas no servidor remoto.
def main() -> None:
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True)

    print("Baixando o XML...")

    download_new_logs()


if __name__ == "__main__":
    main()

    while True:
        run_job()
"""
