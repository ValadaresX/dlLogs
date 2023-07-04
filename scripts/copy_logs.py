import os

# import random
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import chardet
import requests

# import schedule
from tqdm import tqdm

from .url import url_base

#  Configuração do diretório
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
    Faz uma solicitação GET a url_base e retorna o conteúdo da resposta em
    formato de string decodificada de acordo com a codificação detectada.

    Essa função não recebe nenhum parâmetro e sempre retorna uma cadeia de
    caracteres.

    Returns:
        str: O conteúdo da resposta em formato de string decodificada de
        acordo com a codificação detectada.
    """
    response = requests.get(url_base)
    encoding = chardet.detect(response.content)["encoding"]
    return response.content.decode(encoding)


def filter_key_tag(data_xml: str) -> set:
    """
    Filtra os dados XML e extrai as chaves contidas nas tags <Key>.

    Args:
        data_xml (str): Os dados XML a serem filtrados.

    Returns:
        set[str]: Um conjunto de chaves extraídas dos dados XML.

    Example:
        >>> data = "<Contents><Key>00011f1647ad1b3ee67683f1b632da97</Key></Contents>"
        >>> filter_key_tag(data)
        {'00000123456789'}
    """
    pattern = r"<Key>(.*?)</Key>"
    found_keys = re.findall(pattern, data_xml)
    return set(found_keys)


def get_new_keys(found_keys: set[str], url_base: str, logs_dir: Path) -> set:
    """
    Retorna um conjunto contendo as chaves que estão presentes em
    'found_keys', mas não existem como arquivos de log no diretório 'logs_dir'.

    Args:
        found_keys (set[str]): Conjunto de chaves encontradas.
        url_base (str): URL base para construir as chaves ausentes.
        logs_dir (Path): Diretório de logs onde procurar os arquivos.

    Returns:
        set[str]: Conjunto contendo as chaves ausentes que não têm
        correspondentes nos arquivos de log.

    Example:
        found_keys = {"00000123456789", "00000123456789", "00000123456789"}
        url_base = "https://example.com/"
        logs_dir = Path("logs/")
        result = get_new_keys(found_keys, url_base, logs_dir)
        print(result)  # Output: {"https://example.com/00000123456789"
        , "https://example.com/00000123456789"}
    """
    new_keys = set()
    for key in found_keys:
        log_file_path = logs_dir / f"{key}.txt"
        if not log_file_path.exists():
            new_keys.add(url_base + key)
    return new_keys


def download_text_files(new_keys, logs_dir):
    """
    Faz o download de arquivos de texto das URLs fornecidas em 'new_keys' e os
    salva no diretório 'logs_dir'.

    Args:
        new_keys (list[str]): Lista de URLs dos arquivos a serem baixados.
        logs_dir (str): Diretório onde os arquivos de log serão salvos.

    Raises:
        ValueError: Se 'new_keys' estiver vazio ou não contiver URLs válidas.

    Example:
        >>> new_keys = ["https://example.com/00000123456789"
        , "https://example.com/00000123456789"]
        >>> logs_dir = "/path/to/logs"
        >>> download_text_files(new_keys, logs_dir)
        Existem 2 registros para baixar.

    """

    if not new_keys:
        raise ValueError("Não há novos registros para download.")

    print(f"Existem {len(new_keys)} registros para baixar.")

    time.sleep(2)

    for url in new_keys:
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError("O parâmetro 'new_keys' deve conter apenas URLs válidas.")

        response = requests.get(url, stream=True)

        total_size = int(response.headers.get("content-length", 0))

        pbar = tqdm(total=total_size, unit="iB", unit_scale=True)

        log_bytes = b""
        for data in response.iter_content(chunk_size=1024):
            log_bytes += data
            pbar.update(len(data))

        pbar.close()

        encoding = chardet.detect(log_bytes)["encoding"]

        log_text = log_bytes.decode(encoding)

        filename = os.path.join(logs_dir, os.path.basename(url))
        with open(filename, "w", encoding="utf-8") as f:
            f.write(log_text)

    print("Registros de log baixados com sucesso!!!")


"""

def main():
    # Executar o script teste
    data = get_remote_xml_data()
    found_keys = filter_key_tag(data)
    new_keys = get_new_keys(found_keys, url_base, logs_dir)
    download_text_files(new_keys, logs_dir)


if __name__ == "__main__":
    main()

"""
