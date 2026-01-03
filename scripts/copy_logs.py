"""Biblioteca de sincronização de logs com API pública baseada em eventos."""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from collections.abc import Iterator

# ThreadPool removido para downloads sequenciais
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from random import randint
from typing import TYPE_CHECKING

import chardet
import requests

from url import url_base as default_url_base

if TYPE_CHECKING:
    from collections.abc import Callable
    from threading import Event


class EventType(Enum):
    """Tipos de eventos emitidos pelo sync_logs."""

    STATUS = auto()
    DOWNLOAD = auto()
    ERROR = auto()
    COMPLETE = auto()


@dataclass(slots=True, frozen=True)
class SyncConfig:
    """Configuração imutável para sincronização."""

    url_base: str = default_url_base
    logs_dir: Path = field(default_factory=lambda: Path.cwd() / "logs")
    check_interval: tuple[int, int] = (21600, 28800)
    max_workers: int = 5
    dry_run: bool = False
    max_retries: int = 3


@dataclass(slots=True, frozen=True)
class SyncEvent:
    """Evento emitido durante sincronização."""

    type: EventType
    message: str = ""
    current: int = 0
    total: int = 0
    key: str = ""
    success: bool = True
    stats: dict[str, int] = field(default_factory=dict)


# --- Persistência ---


def _load_downloaded_logs(logs_dir: Path) -> set[str]:
    """Carrega conjunto de logs já baixados com dedup contra arquivos locais."""
    downloaded_file = logs_dir / "downloaded_logs.json"
    if not downloaded_file.exists():
        return set()
    with suppress(json.JSONDecodeError, OSError):
        data = json.loads(downloaded_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            keys = set(data)
            existing = {
                parts[2].removesuffix(".txt")
                for name in (p.name for p in logs_dir.glob("*.txt"))
                if (parts := name.split("_", 2)) and len(parts) == 3
            }
            if missing := keys - existing:
                keys -= missing
                _save_downloaded_logs(logs_dir, keys)
            return keys
    return set()


def _save_downloaded_logs(logs_dir: Path, keys: set[str]) -> None:
    """Persiste conjunto de logs (merge incremental, grava só se mudou)."""
    downloaded_file = logs_dir / "downloaded_logs.json"
    current: set[str] = set()
    with suppress(json.JSONDecodeError, OSError):
        if downloaded_file.exists():
            data = json.loads(downloaded_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                current = set(data)
    if (merged := current | keys) != current:
        with suppress(OSError):
            downloaded_file.write_text(json.dumps(sorted(merged), indent=2), encoding="utf-8")


# --- Rede com Retry ---


def _request_with_retry(
    url: str, config: SyncConfig, *, stream: bool = False
) -> requests.Response | None:
    """Executa request com retry simples (backoff fixo 2s)."""
    for attempt in range(config.max_retries):
        try:
            response = requests.get(url, stream=stream, timeout=60)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == config.max_retries - 1:
                return None
            time.sleep(2)
    return None


def _fetch_remote_index(
    config: SyncConfig, last_modified: str | None
) -> tuple[str | None, str | None]:
    """Busca índice XML do servidor remoto."""
    headers = {"If-Modified-Since": last_modified} if last_modified else {}
    try:
        response = requests.get(config.url_base, headers=headers, timeout=30)
        match response.status_code:
            case 304:
                return None, last_modified
            case _:
                response.raise_for_status()
                encoding = chardet.detect(response.content).get("encoding", "utf-8")
                return response.content.decode(encoding or "utf-8"), response.headers.get("Last-Modified")
    except requests.RequestException:
        return None, last_modified


def _extract_keys(xml_content: str) -> set[str]:
    """Extrai keys do XML."""
    return set(re.findall(r"<Key>(.*?)</Key>", xml_content))


# --- Download ---


def _download_single(url: str, config: SyncConfig) -> tuple[str, bool]:
    """Baixa um único arquivo. Retorna (key, success)."""
    key = url.rsplit("/", 1)[-1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = config.logs_dir / f"{timestamp}_{key}.txt"

    if (response := _request_with_retry(url, config, stream=True)) is None:
        return key, False

    try:
        with file_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return key, True
    except OSError:
        with suppress(OSError):
            file_path.unlink()
        return key, False


# --- API Pública ---


def sync_logs(config: SyncConfig, last_modified: str | None = None, stop_event: Event | None = None) -> Iterator[SyncEvent]:  # noqa: C901
    """Generator principal de sincronização."""
    if stop_event and stop_event.is_set():
        return

    config.logs_dir.mkdir(parents=True, exist_ok=True)
    yield SyncEvent(EventType.STATUS, "Verificando servidor...")

    xml_content, new_last_modified = _fetch_remote_index(config, last_modified)

    if stop_event and stop_event.is_set():
        return

    if xml_content is None:
        msg = "Sem alterações" if new_last_modified else "Erro de conexão"
        yield SyncEvent(EventType.STATUS, msg)
        yield SyncEvent(EventType.COMPLETE, stats={"downloaded": 0, "skipped": 0, "errors": 0})
        return

    remote_keys = _extract_keys(xml_content)
    local_keys = _load_downloaded_logs(config.logs_dir)
    new_keys = remote_keys - local_keys
    if stop_event and stop_event.is_set():
        return

    if not new_keys:
        yield SyncEvent(EventType.STATUS, "Sistema sincronizado")
        yield SyncEvent(EventType.COMPLETE, stats={"downloaded": 0, "skipped": len(local_keys), "errors": 0})
        return

    yield SyncEvent(EventType.STATUS, f"Encontrados {len(new_keys)} novos logs")

    downloaded, errors = 0, 0
    urls = [f"{config.url_base.rstrip('/')}/{key}" for key in new_keys]

    if config.dry_run:
        for i, key in enumerate(new_keys, 1):
            if stop_event and stop_event.is_set():
                return
            yield SyncEvent(EventType.DOWNLOAD, f"[DRY-RUN] {key}", current=i, total=len(new_keys), key=key)
            downloaded += 1
        yield SyncEvent(EventType.COMPLETE, "Dry-run concluído", stats={"downloaded": downloaded, "skipped": 0, "errors": 0})
        return

    for i, url in enumerate(urls, 1):
        if stop_event and stop_event.is_set():
            yield SyncEvent(
                EventType.COMPLETE,
                "Cancelado",
                stats={"downloaded": downloaded, "skipped": 0, "errors": errors},
            )
            return
        key, success = _download_single(url, config)
        if success:
            downloaded += 1
            _save_downloaded_logs(config.logs_dir, {key})
        else:
            errors += 1
        yield SyncEvent(EventType.DOWNLOAD, key, current=i, total=len(urls), key=key, success=success)

    yield SyncEvent(
        EventType.COMPLETE,
        f"Concluído: {downloaded} baixados, {errors} erros",
        stats={"downloaded": downloaded, "skipped": 0, "errors": errors},
    )


def run_sync_loop(
    config: SyncConfig, observer: Callable[[SyncEvent], None] | None = None
) -> None:
    """Loop contínuo de sincronização."""
    last_modified: str | None = None
    while True:
        for event in sync_logs(config, last_modified):
            if observer:
                observer(event)
        wait = randint(*config.check_interval)
        if observer:
            observer(SyncEvent(EventType.STATUS, f"Próximo ciclo em {wait // 60}min"))
        time.sleep(wait)


# --- CLI ---


def _create_cli_observer(*, verbose: bool) -> Callable[[SyncEvent], None]:
    """Cria observer para CLI usando logging."""
    logger = logging.getLogger("sync_logs")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)

    def observer(event: SyncEvent) -> None:
        match event.type:
            case EventType.STATUS:
                logger.info("%s", event.message)
            case EventType.DOWNLOAD:
                logger.log(logging.INFO if event.success else logging.ERROR, "[%s] %s", "OK" if event.success else "FALHA", event.key)
            case EventType.ERROR:
                logger.error("%s", event.message)
            case EventType.COMPLETE:
                logger.info("Finalizado: %s baixados, %s erros", event.stats.get("downloaded", 0), event.stats.get("errors", 0))

    return observer


def main() -> int:
    """Entry point CLI."""
    parser = argparse.ArgumentParser(description="Sincroniza logs de servidor remoto")
    parser.add_argument("--url", default=default_url_base, help="URL base")
    parser.add_argument("--logs-dir", type=Path, default=Path.cwd() / "logs", help="Diretório destino")
    parser.add_argument("--workers", type=int, default=5, help="Threads")
    parser.add_argument("--interval", type=int, nargs=2, default=[21600, 28800], metavar=("MIN", "MAX"), help="Intervalo (s)")
    parser.add_argument("--dry-run", action="store_true", help="Simula downloads")
    parser.add_argument("--once", action="store_true", help="Executa um ciclo")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")

    args = parser.parse_args()
    config = SyncConfig(
        url_base=args.url,
        logs_dir=args.logs_dir,
        check_interval=tuple(args.interval),
        max_workers=args.workers,
        dry_run=args.dry_run,
    )

    observer = _create_cli_observer(verbose=args.verbose)
    exit_code = 0

    if args.once:
        for event in sync_logs(config):
            observer(event)
            if event.type == EventType.COMPLETE and event.stats.get("errors", 0) > 0:
                exit_code = 1
    else:
        try:
            run_sync_loop(config, observer)
        except KeyboardInterrupt:
            logging.getLogger("sync_logs").info("Interrompido pelo usuário")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
