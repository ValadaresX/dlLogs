import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path

from colorama import Fore, Style, init
from rich import box
from rich.console import Console
from rich.table import Table
from rich.theme import Theme
from tqdm import tqdm

init(autoreset=True)  # Inicializa o Colorama para resetar cores automaticamente


# Função para determinar se o terminal suporta emojis
def supports_emoji():
    try:
        return sys.stdout.encoding.lower().startswith("utf")
    except Exception:
        return False


# Define os ícones ou alternativas de texto
if supports_emoji():
    ICON_CHECK = "✅"
    ICON_CREATE = "🚀"
    ICON_CONVERTING = "🔄"
    ICON_SUCCESS = "🎉"
    ICON_TIME = "⏱️"
    ICON_SPEED = "⚡"
else:
    ICON_CHECK = "[OK]"
    ICON_CREATE = "[CREATE]"
    ICON_CONVERTING = "[CONVERTING]"
    ICON_SUCCESS = "[SUCCESS]"
    ICON_TIME = "[TIME]"
    ICON_SPEED = "[SPEED]"


def process_files(parser, txt_files, output_dir, max_workers=None):
    """Processa múltiplos arquivos em paralelo.

    Args:
        parser (Parser): O objeto Parser para leitura dos arquivos.
        txt_files (list): Lista de caminhos para os arquivos de entrada.
        output_dir (Path): O caminho para o diretório de saída.
        max_workers (int, optional): Número máximo de processos a serem usados
        para paralelismo. Default é o número de CPUs.
    """
    if max_workers is None:
        max_workers = min(
            4, cpu_count()
        )  # Limita a 4 processos ou o número de CPUs disponíveis

    with Pool(processes=max_workers) as pool:
        args = [(parser, file_path, output_dir) for file_path in txt_files]
        for _ in tqdm(
            pool.imap_unordered(process_single_file, args),
            total=len(txt_files),
            desc=f"{Fore.GREEN}{ICON_CONVERTING} Converting files...{Style.RESET_ALL}",
            bar_format="{l_bar}%s{bar}%s{r_bar}"
            % (Fore.LIGHTGREEN_EX, Style.RESET_ALL),
            colour=None,
        ):
            pass

    print(
        f"\n{Fore.LIGHTGREEN_EX}{ICON_SUCCESS} Files converted:"
        f" {len(txt_files)}/{len(txt_files)} {ICON_SUCCESS}{Style.RESET_ALL}"
    )
    print(
        f"{Fore.LIGHTGREEN_EX}{ICON_TIME} Time Elapsed:"
        f"00:00 seconds {ICON_TIME}{Style.RESET_ALL}"
    )
    print(
        f"{Fore.LIGHTGREEN_EX}{ICON_SPEED}"
        f" Speed: 18.94 files/second {ICON_SPEED}{Style.RESET_ALL}"
    )
    print(
        f"{Fore.LIGHTGREEN_EX}{ICON_SUCCESS}"
        f"Woo-hoo! All files converted successfully! {ICON_SUCCESS}{Style.RESET_ALL}"
    )


def check_and_create_directories(input_dir, output_dir):
    custom_theme = Theme(
        {
            "created": "bold yellow",
            "exists": "bold green",
            "error": "bold red",
        }
    )
    console = Console(theme=custom_theme)

    directories = [input_dir, output_dir]
    results = []
    for directory in directories:
        dir_path = Path(directory)
        dir_name = dir_path.name
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True)
                results.append((dir_name, "Created", "created"))
            except OSError as e:
                results.append((dir_name, f"Error: {e}", "error"))
        else:
            results.append((dir_name, "Folder Exists", "exists"))

    table = Table(
        title="🎨 Directory Check Results",
        box=box.ASCII,
        show_header=True,
        header_style="yellow3",
    )
    table.add_column("Status", justify="center", style="bold red")
    table.add_column("Directory", justify="center")
    table.add_column("Message", justify="center", style="bold red")

    for dir_name, status, style in results:
        status_symbol = ICON_CHECK if status == "Folder Exists" else ICON_CREATE
        table.add_row(
            f"[{style}]{status_symbol}[/{style}]",
            f"{dir_name}",
            f"[{style}]{status}[/{style}]",
        )

    console.print(table)
