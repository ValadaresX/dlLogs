import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import chardet
import requests
from tqdm import tqdm

from url import url_base

#  Configuração do diretório
logs_dir = Path.cwd() / "logs"
if not os.path.exists(str(logs_dir)):
    os.makedirs(str(logs_dir))
    print("Foi criado o diretório logs.")


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
    response = requests.get(url_base)
    encoding = chardet.detect(response.content)["encoding"]
    if not encoding:
        raise ValueError("Não foi possível determinar a codificação dos dados.")
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
    new_keys = set()
    for key in found_keys:
        log_file_path = logs_dir / f"{key}.txt"
        if not log_file_path.exists():
            new_keys.add(url_base + key)
    return new_keys


def download_text_files(new_keys: set[str], logs_dir: Path) -> bool:
    if not new_keys:
        return False  # Retorna False se new_keys for vazia

    print(f"Existem {len(new_keys)} registros para baixar.")
    # time.sleep(2)

    total_size = 0
    for url in new_keys:
        response = requests.get(url, stream=True)
        total_size += int(response.headers.get("content-length", 0))

    pbar = tqdm(total=total_size, unit="iB", unit_scale=True)
    files_downloaded = 0

    for url in new_keys:
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError("O parâmetro 'new_keys' deve conter apenas URLs válidas.")

        response = requests.get(url, stream=True)

        log_bytes = b""
        for data in response.iter_content(chunk_size=1024):
            log_bytes += data
            pbar.update(len(data))

        encoding = chardet.detect(log_bytes)["encoding"]
        log_text = log_bytes.decode(encoding)

        filename = os.path.join(
            logs_dir,
            str(time.localtime().tm_year) + "_" + os.path.basename(url) + ".txt",
        )
        with open(filename, "w", encoding="utf-8") as f:
            f.write(log_text)

        files_downloaded += 1
        pbar.set_description(f"Downloading logs ({files_downloaded}/{len(new_keys)})")

    pbar.close()
    print("Registros de log baixados com sucesso!!!")
    return True


def main():
    data = get_remote_xml_data()
    found_keys = filter_key_tag(data)
    new_keys = get_new_keys(found_keys, url_base, logs_dir)
    return download_text_files(new_keys, logs_dir)  # Retorna True ou False


def format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours} horas, {minutes} minutos e {seconds} segundos"


def schedule_job():
    intervalo = random.uniform(7, 9)  # Gera um intervalo aleatório
    print(f"\033[94mPróxima execução em {intervalo:.2f} horas\033[0m")  # Azul
    next_run_in = intervalo * 3600  # Convertendo horas em segundos
    return next_run_in


def countdown(seconds):
    for remaining in range(int(seconds), 0, -1):  # Convertendo seconds para int aqui
        print(
            f"\r\033[92mTempo restante até a próxima execução: {format_duration(remaining)}\033[0m",
            end=" ",
        )  # Verde
        time.sleep(1)

    print()


def run():
    result = main()  # Execute main() imediatamente
    if not result:  # Se main() retornar False, reagende imediatamente
        print(
            "\033[91mNão há novos registros para download. Reagendando...\033[0m"
        )  # Vermelho
    next_run_in = schedule_job()
    countdown(next_run_in)


if __name__ == "__main__":
    print("Executando main pela primeira vez...")
    while True:
        run()  # Chame run() em cada iteração do loop
        time.sleep(
            1
        )  # Adicionado um atraso para evitar execução excessivamente rápida do loop
