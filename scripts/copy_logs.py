import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import chardet
import requests
from tqdm import tqdm

#  Configuração do diretórios
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
    encoding = chardet.detect(response.content)["encoding"]
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


def download_text_files(new_keys, logs_dir):
    # 1 - Verificar se o parâmetro new_keys não está vazio.
    if not new_keys:
        raise ValueError("Não há novos registros para download.")

    # 2 - Imprimir a quantidade de registros a serem baixados
    print(f"Existem {len(new_keys)} registros para baixar.")

    # 3 - Aguardar 2 segundos
    time.sleep(2)

    for url in new_keys:
        # 4 - Verificar se cada URL em new_keys é uma URL válida.
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError("O parâmetro 'new_keys' deve conter apenas URLs válidas.")

        # 5 - Fazer uma requisição HTTP GET para cada URL em new_keys
        response = requests.get(url, stream=True)

        # 6 - Verificar se a resposta da requisição possui um código de status de sucesso
        response.raise_for_status()

        # 7 - Obter o tamanho total do conteúdo da resposta
        total_size = int(response.headers.get("content-length", 0))

        # 8 - Atualizar o valor total do progress bar
        pbar = tqdm(total=total_size, unit="iB", unit_scale=True)

        log_bytes = b""
        for data in response.iter_content(chunk_size=1024):
            # 9 - Iterar sobre os fragmentos de conteúdo da resposta
            log_bytes += data
            pbar.update(len(data))

        pbar.close()

        # 10 - Concatenar os fragmentos de conteúdo em uma variável log_bytes do tipo bytes.
        # Já feito no loop acima

        # 11 - Detectar a codificação do conteúdo
        encoding = chardet.detect(log_bytes)["encoding"]

        # 12 - Decodificar log_bytes para uma string
        log_text = log_bytes.decode(encoding)

        # 13 - Abrir o arquivo em logs_dir em modo de escrita ("w")
        filename = os.path.join(logs_dir, os.path.basename(url))
        with open(filename, "w", encoding="utf-8") as f:
            # 14 - Escrever o conteúdo de log_text no arquivo.
            f.write(log_text)

        # 15 - Fechar o arquivo.
        # O arquivo é automaticamente fechado ao sair do bloco with

    print("Registros de log baixados com sucesso!")


def main():
    # Executar o script teste
    data = get_remote_xml_data()
    found_keys = filter_key_tag(data)
    new_keys = get_new_keys(found_keys, url_base, logs_dir)
    download_text_files(new_keys, logs_dir)


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
