"""Interface TUI para monitoramento de sincronização de logs."""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from random import randint
from threading import Event
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, ProgressBar, RichLog, Static
from textual.worker import Worker, WorkerState

from copy_logs import EventType, SyncConfig, SyncEvent, sync_logs
from url import url_base as default_url_base


@dataclass(slots=True, frozen=True)
class Theme:
    """Paleta de cores."""

    bg: str = "#0f172a"
    panel: str = "#1e293b"
    elevated: str = "#243b53"
    accent: str = "#6366f1"
    accent_light: str = "#a5b4fc"
    text: str = "#e2e8f0"
    muted: str = "#a1b1c4"
    border: str = "#334155"
    ok: str = "#34d399"
    warn: str = "#f59e0b"
    crit: str = "#ef4444"
    info: str = "#38bdf8"
    success_muted: str = "#064e3b"
    error_muted: str = "#450a0a"


THEME = Theme()

CSS = f"""
$bg: {THEME.bg};
$panel: {THEME.panel};
$elevated: {THEME.elevated};
$accent: {THEME.accent};
$accent-light: {THEME.accent_light};
$text: {THEME.text};
$muted: {THEME.muted};
$border: {THEME.border};
$ok: {THEME.ok};
$warn: {THEME.warn};
$crit: {THEME.crit};
$info: {THEME.info};
$success-muted: {THEME.success_muted};
$error-muted: {THEME.error_muted};

Screen {{ background: $bg; color: $text; }}
Header {{ background: $panel; color: $muted; }}
Footer {{ background: $panel; color: $muted; }}

#main {{ width: 100%; height: 100%; padding: 0 1; }}
#top {{ height: auto; min-height: 5; max-height: 7; }}
#metrics {{ height: 3; }}
#bottom {{ height: 1fr; min-height: 5; }}

.panel {{ background: $panel; border: solid $border; padding: 0 1; }}
.title {{ color: $accent-light; text-style: bold; }}

#status {{ width: 1fr; height: 100%; margin-right: 1; }}
#download {{ width: 1fr; height: 100%; margin-right: 1; }}
#timer {{ width: 1fr; height: 100%; }}

#status-line {{ height: 1; }}
#dot {{ width: 3; }}
.status-idle {{ color: $muted; }}
.status-ok {{ color: $ok; }}
.status-warn {{ color: $warn; }}
.status-crit {{ color: $crit; }}
#lbl {{ text-style: bold; }}
#dl-pct {{ color: $muted; text-align: right; width: 100%; }}

#pct {{ color: $muted; text-align: right; width: 100%; }}
#time {{ color: $accent; text-style: bold; text-align: center; width: 100%; }}

.metric {{ background: $elevated; border: solid $border; width: 1fr; height: 100%; padding: 0 1; content-align: center middle; }}
.metric:last-of-type {{ margin: 0; }}
#m1, #m2, #m3 {{ margin-right: 1; }}
.num {{ color: $accent-light; text-style: bold; }}
.txt {{ color: $muted; margin-left: 1; }}

#sys {{ width: 24; min-width: 20; height: 100%; margin-right: 1; }}
.lbl {{ color: $muted; }}
.val {{ color: $text; text-style: bold; }}
#disk-row {{ margin-bottom: 1; }}

#log-panel {{ width: 1fr; height: 100%; }}
#log {{ background: $panel; border: solid $border; height: 1fr; }}

ProgressBar {{ height: 1; width: 100%; padding: 0; }}
Bar > .bar--bar {{ color: $accent 30%; }}
Bar > .bar--complete {{ color: $accent; }}

ProgressBar.ok Bar > .bar--complete {{ color: $ok; }}
ProgressBar.warn Bar > .bar--complete {{ color: $warn; }}
ProgressBar.crit Bar > .bar--complete {{ color: $crit; }}
"""


class LogSyncApp(App):
    """Monitor de sincronização com integração real."""

    CSS = CSS
    TITLE = "Log Sync"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Sair", priority=True),
        Binding("r", "force_sync", "Sync"),
        Binding("l", "clear_log", "Limpar"),
    ]

    time_left: reactive[int] = reactive(0)
    syncing: reactive[bool] = reactive(default=False)
    session_downloaded: reactive[int] = reactive(0)
    session_errors: reactive[int] = reactive(0)
    batch_count: reactive[int] = reactive(0)

    def __init__(self, config: SyncConfig | None = None) -> None:
        super().__init__()
        self.config = config or SyncConfig(url_base=default_url_base)
        self._sync_worker: Worker[None] | None = None
        self._batch_start: datetime | None = None
        self.cycle = randint(*self.config.check_interval)
        self.time_left = self.cycle
        self.download_total = 0
        self.download_done = 0
        self._stop_event = Event()

    def compose(self) -> ComposeResult:
        """Layout da interface."""
        yield Header()
        with Vertical(id="main"):
            with Horizontal(id="top"):
                with Vertical(id="status", classes="panel"):
                    yield Label("STATUS", classes="title")
                    with Horizontal(id="status-line"):
                        yield Static("●", id="dot", classes="status-idle")
                        yield Label("IDLE", id="lbl", classes="status-idle")

                with Vertical(id="download", classes="panel"):
                    yield Label("DOWNLOAD", classes="title")
                    yield ProgressBar(total=1, show_eta=False, show_percentage=False, id="dl-pb")
                    yield Label("0%", id="dl-pct")

                with Vertical(id="timer", classes="panel"):
                    yield Label("SYNC", classes="title")
                    yield Static("00:00:00", id="time")
                    yield ProgressBar(total=self.cycle, show_eta=False, show_percentage=False, id="pb")
                    yield Label("0%", id="pct")

            with Horizontal(id="metrics"):
                for i, (val, txt) in enumerate([("0", "total"), ("0", "lote"), ("0", "erros"), ("0/s", "taxa")], 1):
                    with Horizontal(id=f"m{i}", classes="metric"):
                        yield Label(val, id=f"v{i}", classes="num")
                        yield Label(txt, classes="txt")

            with Horizontal(id="bottom"):
                with Vertical(id="sys", classes="panel"):
                    yield Label("DISCO", classes="title")
                    with Vertical(id="disk-row"):
                        yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="disk", classes="ok")
                        yield Label("...", id="disk-val", classes="val")
                    yield Label("Status", classes="lbl")
                    yield Label("OK", id="health", classes="val")

                with Vertical(id="log-panel", classes="panel"):
                    yield Label("LOG", classes="title")
                    yield RichLog(highlight=True, markup=True, id="log", wrap=True)

        yield Footer()

    def on_mount(self) -> None:
        """Inicialização."""
        self._log_widget = self.query_one("#log", RichLog)
        self._write("info", "Sistema pronto")
        self._set_status("idle", "AGUARDANDO")
        self._update_timer_display(reset_total=True)
        self._start_sync()
        self.set_interval(1.0, self._tick)
        self._update_disk()

    def _tick(self) -> None:
        """Loop principal (1s)."""
        if not self.syncing and self.time_left > 0:
            self.time_left -= 1
        elif not self.syncing:
            self._start_sync()
            self.time_left = 0

        h, rem = divmod(self.time_left, 3600)
        m, s = divmod(rem, 60)
        self.query_one("#time", Static).update(f"{h:02d}:{m:02d}:{s:02d}")
        self._update_timer_display()

        if self.time_left % 10 == 0:
            self._update_disk()

    def _start_sync(self) -> None:
        """Inicia sincronização em background."""
        if self.syncing:
            return
        self._stop_event.clear()
        self.syncing = True
        self._batch_start = datetime.now()
        self.batch_count = 0
        self.download_total = self.download_done = 0
        self._update_download_bar(0, 0)
        self._set_status("warn", "CHECANDO")
        self._sync_worker = self.run_worker(self._run_sync, thread=True, exclusive=True)

    def _run_sync(self) -> None:
        """Worker que executa a sincronização."""
        try:
            for event in sync_logs(self.config, stop_event=self._stop_event):
                if self._stop_event.is_set():
                    break
                self.call_from_thread(self._handle_event, event)
        except Exception as exc:
            self.call_from_thread(self._handle_event, SyncEvent(EventType.ERROR, f"Erro: {exc}"))
        finally:
            self.call_from_thread(self._finish_sync)

    def _finish_sync(self) -> None:
        """Finaliza ciclo de sync."""
        self.syncing = False

    def _handle_event(self, event: SyncEvent) -> None:
        """Processa evento de sincronização."""
        match event.type:
            case EventType.STATUS:
                self._write("info", event.message)
                self._set_status(self._status_level(event.message), event.message)

            case EventType.DOWNLOAD:
                self._write("success" if event.success else "error", f"[{'OK' if event.success else 'ERRO'}] {event.key}")
                if event.success:
                    self.session_downloaded += 1
                    self.batch_count += 1
                else:
                    self.session_errors += 1
                self._update_metrics()
                if event.total > 0:
                    self.download_total, self.download_done = event.total, event.current
                    self._update_download_bar(event.current, event.total)

            case EventType.COMPLETE:
                stats = event.stats
                self._write("success", f"Ciclo: {stats.get('downloaded', 0)} baixados, {stats.get('errors', 0)} erros")
                self._update_metrics()
                self._update_download_bar(self.download_total, self.download_total or 1)
                level = "ok" if stats.get("errors", 0) == 0 else "warn"
                self._set_status(level, "200 OK" if level == "ok" else "200 OK (erros)")
                self.cycle = randint(*self.config.check_interval)
                self.time_left = self.cycle
                self._update_timer_display(reset_total=True)

            case EventType.ERROR:
                self._write("error", event.message)
                self._set_status("crit", event.message or "ERRO")

    def _update_metrics(self) -> None:
        """Atualiza métricas na interface."""
        self.query_one("#v1", Label).update(str(self.session_downloaded))
        self.query_one("#v2", Label).update(str(self.batch_count))
        self.query_one("#v3", Label).update(str(self.session_errors))
        if self._batch_start and self.batch_count > 0:
            elapsed = (datetime.now() - self._batch_start).total_seconds()
            self.query_one("#v4", Label).update(f"{self.batch_count / max(elapsed, 1):.1f}/s")

    def _update_download_bar(self, current: int, total: int) -> None:
        """Atualiza barra de download."""
        pb = self.query_one("#dl-pb", ProgressBar)
        pb.total = max(1, total)
        pb.update(progress=current)
        pct = current * 100 // max(1, total)
        self.query_one("#dl-pct", Label).update(f"{pct}% ({current}/{total})")

    def _update_timer_display(self, *, reset_total: bool = False) -> None:
        """Atualiza barra e percentual do timer."""
        pb = self.query_one("#pb", ProgressBar)
        if reset_total:
            pb.total = max(1, self.cycle)
        done = 0 if self.syncing else max(0, self.cycle - self.time_left)
        pb.update(progress=done)
        self.query_one("#pct", Label).update(f"{done * 100 // max(1, self.cycle)}%")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Callback quando worker muda de estado."""
        if event.state == WorkerState.ERROR:
            self._write("error", "Erro no worker")
            self.syncing = False

    def _set_status(self, level: str, text: str) -> None:
        """Atualiza indicador de status."""
        level = level if level in {"idle", "ok", "warn", "crit"} else "idle"
        dot, lbl = self.query_one("#dot", Static), self.query_one("#lbl", Label)
        for cls in ("status-idle", "status-ok", "status-warn", "status-crit"):
            dot.remove_class(cls)
            lbl.remove_class(cls)
        dot.add_class(f"status-{level}")
        lbl.add_class(f"status-{level}")
        lbl.update(text)

    @staticmethod
    def _status_level(message: str) -> str:
        """Determina nível de status a partir da mensagem."""
        msg = message.lower()
        if "erro" in msg:
            return "crit"
        if "sem altera" in msg or "sincronizado" in msg:
            return "ok"
        if "verificando" in msg or "checando" in msg:
            return "warn"
        return "ok"

    def _update_disk(self) -> None:
        """Atualiza informações de disco."""
        try:
            total, used, _ = shutil.disk_usage(Path.cwd())
            pct = min(100.0, 100 * used / total)
            gb = 1024**3
            pb = self.query_one("#disk", ProgressBar)
            pb.update(progress=pct)
            pb.remove_class("ok", "warn", "crit")
            health = self.query_one("#health", Label)
            match pct:
                case p if p < 75:
                    pb.add_class("ok")
                    health.update("OK")
                    health.styles.color = THEME.ok
                case p if p < 90:
                    pb.add_class("warn")
                    health.update("ATENCAO")
                    health.styles.color = THEME.warn
                case _:
                    pb.add_class("crit")
                    health.update("CRITICO")
                    health.styles.color = THEME.crit
            self.query_one("#disk-val", Label).update(f"{used/gb:.1f}/{total/gb:.0f}GB")
        except OSError:
            pass

    def action_force_sync(self) -> None:
        """Força sincronização imediata."""
        self._write("info", "Sync manual solicitado")
        self.time_left = 1

    def action_clear_log(self) -> None:
        """Limpa log."""
        self._log_widget.clear()
        self._write("info", "Log limpo")

    def action_quit(self) -> None:
        """Sai cancelando o worker."""
        self._stop_event.set()
        if self._sync_worker:
            self._sync_worker.cancel()
            self._sync_worker = None
        self.syncing = False
        self.exit()

    def _write(self, level: str, msg: str) -> None:
        """Escreve no log com formatação."""
        colors = {"info": THEME.info, "success": THEME.ok, "warn": THEME.warn, "error": THEME.crit}
        backgrounds = {"success": THEME.success_muted, "error": THEME.error_muted}
        style = colors.get(level, THEME.accent_light)
        if bg := backgrounds.get(level):
            style = f"{style} on {bg}"
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_widget.write(f"[{THEME.muted}]{ts}[/] [{style}]{msg}[/]")


def main() -> None:
    """Entry point da TUI."""
    parser = argparse.ArgumentParser(description="TUI para sincronização de logs")
    parser.add_argument("--url", default=default_url_base, help="URL base")
    parser.add_argument("--logs-dir", type=Path, default=Path.cwd() / "logs", help="Diretório de logs")
    parser.add_argument("--interval", type=int, nargs=2, metavar=("MIN", "MAX"), default=(21600, 28800), help="Intervalo (s)")
    parser.add_argument("--workers", type=int, default=5, help="Threads")

    args = parser.parse_args()
    config = SyncConfig(
        url_base=args.url,
        logs_dir=args.logs_dir,
        check_interval=tuple(args.interval),
        max_workers=args.workers,
    )
    LogSyncApp(config).run()


if __name__ == "__main__":
    main()
