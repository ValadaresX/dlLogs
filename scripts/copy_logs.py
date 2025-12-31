import json
import os
import random
import re
import time
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set, Tuple

import chardet
import requests
from tqdm import tqdm

from url import url_base

# --- CYBERPUNK UI ENGINE ---
class UI:
    """Interface Visual estilo Cyberpunk/Terminal Hacker."""
    
    # Paleta Neon (High Intensity ANSI)
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Cores Principais
    NEON_PINK = "\033[95m"    # Títulos, Alertas Críticos
    NEON_CYAN = "\033[96m"    # Bordas, Info de Sistema
    NEON_GREEN = "\033[92m"   # Sucesso, Downloads
    NEON_YELLOW = "\033[93m"  # Avisos, Standby
    NEON_BLUE = "\033[94m"    # Detalhes, Metadata
    NEON_RED = "\033[91m"     # Erros
    WHITE = "\033[97m"        # Texto Principal
    GREY = "\033[90m"         # Texto Secundário/Bordas fracas

    # Ícones
    ICON_SYS = "⚡"
    ICON_NET = "⯈"
    ICON_DL = "⬇"
    ICON_WAIT = "⏳"
    
    # Estado Global
    SESSION_DOWNLOADS = 0

    @staticmethod
    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def header(status_main: str, status_sub: str = ""):
        """Dashboard fixo com visual Cyberpunk."""
        UI.clear_screen()
        # Obtém largura, fallback para 80 se falhar
        col_size = shutil.get_terminal_size((80, 20)).columns
        width = col_size
        
        # Topo
        print(f"{UI.NEON_CYAN}╔{'═' * (width - 2)}╗{UI.RESET}")
        
        # Título
        title = f"{UI.BOLD} LOG_SYNC_PROTOCOL_V2 {UI.RESET}"
        pad_title = (width - 2 - len(" LOG_SYNC_PROTOCOL_V2 ")) // 2
        
        # Correção de padding para evitar quebra de linha em terminais estreitos
        right_pad = width - 2 - pad_title - len(" LOG_SYNC_PROTOCOL_V2 ")
        if right_pad < 0: right_pad = 0

        print(f"{UI.NEON_CYAN}║{UI.RESET}{' ' * pad_title}{UI.NEON_PINK}{title}{UI.RESET}{' ' * right_pad}{UI.NEON_CYAN}║{UI.RESET}")
        
        # Divisor Tech
        print(f"{UI.NEON_CYAN}╠{'═' * (width - 2)}╣{UI.RESET}")
        
        # Dados da Sessão
        lbl_sess = f"{UI.GREY}SESSION_DATA:{UI.RESET}"
        val_sess = f"{UI.NEON_GREEN}{UI.SESSION_DOWNLOADS:03d}{UI.RESET}"
        
        lbl_stat = f"{UI.GREY}SYSTEM_STATUS:{UI.RESET}"
        val_stat = f"{UI.WHITE}{status_main}{UI.RESET}"
        
        # Monta a linha de status
        line_content = f" {UI.ICON_SYS} {lbl_sess} [{val_sess}]   {lbl_stat} [{val_stat}] {status_sub}"
        
        # Calcula padding real (removendo caracteres ANSI invisíveis para alinhar borda)
        # Estimativa simples de comprimento visível
        visible_text = f" {UI.ICON_SYS} SESSION_DATA: [000]   SYSTEM_STATUS: [{status_main}] {status_sub}"
        pad_right = width - 4 - len(visible_text)
        if pad_right < 0: pad_right = 0
        
        print(f"{UI.NEON_CYAN}║{UI.RESET}{line_content}{' ' * pad_right}{UI.NEON_CYAN}║{UI.RESET}")
        print(f"{UI.NEON_CYAN}╚{'═' * (width - 2)}╝{UI.RESET}\n")

    @staticmethod
    def log(prefix: str, msg: str, color_prefix: str = NEON_CYAN, color_msg: str = WHITE):
        """Imprime linha de log colorida sem quebrar layout."""
        # Limpa linha atual e imprime
        sys.stdout.write(f"\r\033[K{UI.GREY}[{color_prefix}{prefix}{UI.GREY}] {UI.ICON_NET} {color_msg}{msg}{UI.RESET}")
        sys.stdout.flush()

    @staticmethod
    def countdown_bar(seconds: int):
        """Barra de espera estilo 'Cooldown'."""
        try:
            # FIX: Concatenamos as variáveis de cor fora da string literals 
            # para que o tqdm não tente interpretar "UI" como uma chave interna.
            fmt = "{desc} {bar} " + UI.NEON_CYAN + "{remaining}" + UI.RESET

            for _ in tqdm(
                range(seconds),
                desc=f"{UI.NEON_PINK}COOLDOWN{UI.RESET}",
                bar_format=fmt,
                colour="magenta", 
                leave=False,
                ascii="░▒▓█" 
            ):
                time.sleep(1)
        except KeyboardInterrupt:
            return

# --- Configurações de Diretórios ---
LOGS_DIR = Path.cwd() / "logs"
DOWNLOADED_LOGS_FILE = LOGS_DIR / "downloaded_logs.json"
os.makedirs(LOGS_DIR, exist_ok=True)


def load_downloaded_logs() -> Set[str]:
    if not DOWNLOADED_LOGS_FILE.exists(): return set()
    try:
        content = DOWNLOADED_LOGS_FILE.read_text(encoding="utf-8")
        downloaded_list = json.loads(content)
        return set(downloaded_list) if isinstance(downloaded_list, list) else set()
    except Exception:
        return set()


def update_downloaded_logs(new_keys: Set[str]) -> None:
    if not new_keys: return
    current_logs = load_downloaded_logs()
    current_logs.update(new_keys)
    try:
        with open(DOWNLOADED_LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(current_logs), f, indent=4)
    except IOError:
        pass


def get_remote_xml_data(last_modified: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    headers = {"If-Modified-Since": last_modified} if last_modified else {}
    
    try:
        UI.log("NET", "Establishing uplik...", UI.NEON_BLUE)
        response = requests.get(url_base, headers=headers, timeout=30)
    except requests.RequestException:
        UI.log("ERR", "Connection Failed", UI.NEON_RED, UI.NEON_RED)
        time.sleep(2)
        return None, last_modified

    if response.status_code == 304:
        UI.log("304", "No New Data / Cache Hit", UI.NEON_YELLOW, UI.GREY)
        time.sleep(2)
        return None, last_modified

    encoding = chardet.detect(response.content)["encoding"]
    if not encoding: return None, last_modified

    UI.log("OK", "Payload Received", UI.NEON_GREEN)
    return response.content.decode(encoding), response.headers.get("Last-Modified")


def extract_keys_from_xml(xml_content: str) -> Set[str]:
    return set(re.findall(r"<Key>(.*?)</Key>", xml_content))


def identify_new_downloads(found_keys: Set[str]) -> Tuple[Set[str], Set[str]]:
    already_downloaded = load_downloaded_logs()
    new_keys = found_keys - already_downloaded
    base_url = url_base.rstrip("/")
    download_urls = {f"{base_url}/{key}" for key in new_keys}
    return download_urls, new_keys


def download_single_file(url: str) -> Optional[str]:
    key = url.split("/")[-1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = LOGS_DIR / f"{timestamp}_{key}.txt"

    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return key
    except requests.RequestException:
        if file_path.exists():
            try:
                os.remove(file_path)
            except OSError: pass
        return None


def download_manager(urls: Set[str]) -> Set[str]:
    if not urls: return set()

    # Muda o header para modo ATIVO
    UI.header("ACTIVE", f"{UI.NEON_PINK}>> DOWNLOADING BATCH{UI.RESET}")
    success_keys = set()
    
    print("") # Espaçamento
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(download_single_file, url): url for url in urls}
        
        # Barra de progresso Cyberpunk (Verde neon)
        pbar = tqdm(
            futures, 
            total=len(urls),
            unit="file",
            desc=f"{UI.NEON_GREEN}TRANSFER{UI.RESET}",
            bar_format="{desc} {bar} {n_fmt}/{total_fmt} [{elapsed}]",
            colour="green",
            ascii="░▒▓█" # Estilo bloco sólido
        )
        
        for future in pbar:
            if result_key := future.result():
                success_keys.add(result_key)

    return success_keys


def routine_check(last_modified: Optional[str]) -> Tuple[bool, Optional[str]]:
    UI.header("SCANNING", f"{UI.NEON_BLUE}>> CHECKING SERVER{UI.RESET}")
    
    try:
        xml_data, new_last_modified = get_remote_xml_data(last_modified)
    except Exception:
        return False, last_modified

    if xml_data is None:
        return False, new_last_modified

    found_keys = extract_keys_from_xml(xml_data)
    urls_to_download, _ = identify_new_downloads(found_keys)

    if not urls_to_download:
        UI.log("SYNC", "System synchronized. No actions.", UI.NEON_GREEN, UI.GREY)
        time.sleep(2)
        return False, new_last_modified

    downloaded_keys = download_manager(urls_to_download)
    
    if downloaded_keys:
        update_downloaded_logs(downloaded_keys)
        UI.SESSION_DOWNLOADS += len(downloaded_keys)
        return True, new_last_modified

    return False, new_last_modified


def main_loop() -> None:
    last_modified = None
    UI.SESSION_DOWNLOADS = 0

    while True:
        success, last_modified = routine_check(last_modified)

        # Tempo de espera (6 a 8 horas)
        wait_seconds = random.randint(21600, 28800)
        next_run = (datetime.now() + timedelta(seconds=wait_seconds)).strftime('%H:%M')
        
        # Modo STANDBY
        UI.header("STANDBY", f"{UI.NEON_YELLOW}>> NEXT CYCLE: {next_run}{UI.RESET}")
        
        UI.countdown_bar(wait_seconds)


if __name__ == "__main__":
    try:
        # Configura título do terminal (Windows/Linux)
        if os.name == 'nt':
            os.system('title LOG SYNC PROTOCOL')
        else:
            sys.stdout.write("\x1b]2;LOG SYNC PROTOCOL\x07")
            
        main_loop()
    except KeyboardInterrupt:
        print(f"\n{UI.NEON_RED}>> SYSTEM HALT. DISCONNECTING...{UI.RESET}")
