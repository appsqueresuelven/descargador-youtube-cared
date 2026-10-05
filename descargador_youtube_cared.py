from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import Qt, QThread, QTimer, QSettings, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton, QProgressBar, QSpinBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView, QLineEdit,
)

try:
    import yt_dlp
except Exception:
    yt_dlp = None


APP_NAME = "Descargador de YouTube - CARED"
ORG_NAME = "CARED"
WEBSITE_URL = "https://appsqueresuelven.blogspot.com"
APP_DATA = Path.home() / ".cared_descargador_youtube"
HISTORY_FILE = APP_DATA / "historial.json"
APP_DATA.mkdir(parents=True, exist_ok=True)


STYLE = r"""
QMainWindow, QDialog {
    background: #e9eaed;
    color: #1f2328;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QWidget#Root {
    background: #e9eaed;
    color: #1f2328;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QLabel {
    background: transparent;
}
QFrame#TopBar {
    background: #171717;
    border: none;
    border-bottom: 5px solid #ff0033;
}
QLabel#Title {
    background: transparent;
    color: #ffffff;
    font-size: 19pt;
    font-weight: 800;
}
QLabel#HeaderSubtle {
    background: transparent;
    color: #d6d6d6;
    font-size: 9pt;
}
QLabel#Credit {
    color: #ffffff;
    font-weight: 800;
    background: #ff0033;
    border-radius: 12px;
    padding: 7px 13px;
}
QFrame#LightCard {
    background: #ffffff;
    border: 1px solid #d2d4d8;
    border-radius: 14px;
}
QFrame#DarkCard {
    background: #242424;
    border: 1px solid #333333;
    border-radius: 14px;
}
QLabel#SectionTitle {
    color: #15171a;
    font-size: 10pt;
    font-weight: 800;
}
QLabel#FieldLabelLight {
    color: #25282c;
    font-size: 9pt;
    font-weight: 800;
}
QLabel#FieldLabelDark {
    color: #ffffff;
    font-size: 9pt;
    font-weight: 800;
}
QLabel#Subtle {
    color: #555b62;
    font-size: 9pt;
}
QLabel#DarkSubtle {
    color: #d7d7d7;
    font-size: 9pt;
}
QLineEdit, QTextEdit, QComboBox, QSpinBox {
    background: #ffffff;
    color: #17191c;
    border: 1px solid #aeb3ba;
    border-radius: 9px;
    padding: 6px 9px;
    selection-background-color: #ff0033;
    selection-color: #ffffff;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid #ff0033;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #17191c;
    selection-background-color: #ff0033;
    selection-color: #ffffff;
}
QPushButton {
    background: #f4f4f5;
    color: #202327;
    border: 1px solid #c7c9cd;
    border-radius: 11px;
    padding: 7px 12px;
    font-weight: 700;
}
QPushButton:hover {
    background: #e6e7e9;
    border-color: #aeb1b7;
}
QPushButton:pressed { background: #dadbdd; }
QPushButton#Primary {
    background: #ff0033;
    color: #ffffff;
    border: none;
    padding: 10px 18px;
    font-size: 10.5pt;
    font-weight: 900;
}
QPushButton#Primary:hover { background: #df002c; }
QPushButton#Dark {
    background: #353535;
    color: #ffffff;
    border: 1px solid #4a4a4a;
}
QPushButton#Dark:hover { background: #444444; }
QPushButton#Danger {
    background: #fff0f3;
    color: #c8002b;
    border: 1px solid #e8a8b6;
}
QPushButton:disabled {
    color: #8d9197;
    background: #dedfe2;
    border-color: #d0d2d5;
}
QTableWidget {
    border: 1px solid #cfd2d7;
    border-radius: 11px;
    gridline-color: #e5e6e9;
    background: #ffffff;
    color: #1c1f23;
    alternate-background-color: #f5f6f7;
    selection-background-color: #ffe0e7;
    selection-color: #111111;
}
QHeaderView::section {
    background: #232323;
    color: #ffffff;
    border: none;
    border-right: 1px solid #3c3c3c;
    padding: 7px;
    font-weight: 800;
}
QProgressBar {
    border: 1px solid #c8cbd0;
    border-radius: 7px;
    background: #e8e9ec;
    text-align: center;
    min-height: 17px;
    max-height: 17px;
    font-size: 8.5pt;
    font-weight: 900;
    color: #191b1e;
}
QProgressBar::chunk {
    background: #ff0033;
    border-radius: 6px;
}
QWidget#MarqueeBar {
    background: #202020;
    border-top: 3px solid #ff0033;
}
QLabel#MarqueeText {
    background: transparent;
    color: #ffffff;
    font-weight: 800;
}
"""


def human_time(seconds: Optional[float]) -> str:
    if seconds is None:
        return "--:--"
    try:
        sec = max(0, int(seconds))
    except Exception:
        return "--:--"
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def human_bytes_rate(value: Optional[float]) -> str:
    if not value:
        return "--"
    value = float(value)
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{value:.1f} {units[idx]}"


def safe_name(text: str, max_len: int = 160) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", text or "video")
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text[:max_len].rstrip(" .") or "video")


def find_ffmpeg() -> Optional[str]:
    app_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    for candidate in [app_dir / "ffmpeg.exe", app_dir / "ffmpeg", Path.cwd() / "ffmpeg.exe"]:
        if candidate.exists():
            return str(candidate)
    return shutil.which("ffmpeg")


def clean_youtube_video_url(raw: str) -> Optional[str]:
    """Convierte enlaces de video de YouTube en una URL limpia y elimina parámetros de radio/lista."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
        host = parsed.netloc.lower().replace("www.", "")
        if host == "youtu.be":
            video_id = parsed.path.strip("/").split("/")[0]
            return f"https://www.youtube.com/watch?v={video_id}" if video_id else None
        if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0].strip()
                return f"https://www.youtube.com/watch?v={video_id}" if video_id else None
            if parsed.path.startswith("/shorts/"):
                parts = parsed.path.split("/")
                if len(parts) >= 3 and parts[2]:
                    return f"https://www.youtube.com/watch?v={parts[2]}"
            if parsed.path.startswith("/live/"):
                parts = parsed.path.split("/")
                if len(parts) >= 3 and parts[2]:
                    return f"https://www.youtube.com/watch?v={parts[2]}"
            # Playlist pura: no la aceptamos en esta versión.
            if parsed.path == "/playlist":
                return None
    except Exception:
        return None
    return None


@dataclass
class VideoJob:
    key: str
    url: str
    title: str
    duration: Optional[float] = None
    video_id: str = ""


class QuietLogger:
    def debug(self, msg: str) -> None:
        pass
    def warning(self, msg: str) -> None:
        pass
    def error(self, msg: str) -> None:
        pass


class DownloadCoordinator(QThread):
    job_progress = Signal(str, int, str, str)
    job_meta = Signal(str, str, str)
    job_done = Signal(str, str, str)
    job_error = Signal(str, str)
    all_done = Signal(int, int, int)

    def __init__(
        self,
        jobs: list[VideoJob],
        folder: str,
        mode: str,
        quality: int,
        bitrate: int,
        max_workers: int,
        ffmpeg_path: Optional[str],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.jobs = jobs
        self.folder = Path(folder)
        self.mode = mode
        self.quality = quality
        self.bitrate = bitrate
        self.max_workers = max(1, min(3, int(max_workers)))
        self.ffmpeg_path = ffmpeg_path
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.cancel_event = threading.Event()
        self._counts_lock = threading.Lock()
        self._ok = 0
        self._failed = 0
        self._skipped = 0

    def pause(self) -> None:
        self.pause_event.clear()

    def resume(self) -> None:
        self.pause_event.set()

    def cancel(self) -> None:
        self.cancel_event.set()
        self.pause_event.set()

    def run(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        q: queue.Queue[VideoJob] = queue.Queue()
        for job in self.jobs:
            q.put(job)
        workers: list[threading.Thread] = []
        for _ in range(min(self.max_workers, len(self.jobs))):
            t = threading.Thread(target=self._worker_loop, args=(q,), daemon=True)
            t.start()
            workers.append(t)
        for t in workers:
            t.join()
        self.all_done.emit(self._ok, self._failed, self._skipped)

    def _worker_loop(self, q: queue.Queue[VideoJob]) -> None:
        while not self.cancel_event.is_set():
            try:
                job = q.get_nowait()
            except queue.Empty:
                break
            try:
                self._download_one(job)
            finally:
                q.task_done()

    def _download_one(self, job: VideoJob) -> None:
        self._wait_if_paused()
        if self.cancel_event.is_set():
            self._mark_skip(job.key, "Cancelado")
            return
        if yt_dlp is None:
            self._mark_error(job.key, "yt-dlp no está instalado")
            return

        started = time.time()
        tmp_stem = self.folder / f"CARED_TMP_{job.key}"
        captured_title = job.title
        captured_id = job.video_id
        captured_duration: Optional[float] = None
        meta_sent = False

        def emit_meta(info: dict[str, Any]) -> None:
            nonlocal captured_title, captured_id, captured_duration, meta_sent
            title = str(info.get("title") or captured_title or "Video")
            video_id = str(info.get("id") or captured_id or "")
            duration = info.get("duration")
            if isinstance(duration, (int, float)):
                captured_duration = float(duration)
            captured_title = title
            captured_id = video_id
            job.title = title
            job.video_id = video_id
            job.duration = captured_duration
            if not meta_sent or title != "Video":
                self.job_meta.emit(job.key, title, human_time(captured_duration))
                meta_sent = True

        def hook(data: dict[str, Any]) -> None:
            self._wait_if_paused()
            if self.cancel_event.is_set():
                raise RuntimeError("__CARED_CANCELLED__")
            info = data.get("info_dict") or {}
            if info:
                emit_meta(info)
            status = data.get("status")
            if status == "downloading":
                downloaded = data.get("downloaded_bytes") or 0
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                pct = int((downloaded / total) * 100) if total else 0
                ceiling = 84 if self.mode == "universal" else 97
                shown = max(1, min(ceiling, int(pct * ceiling / 100)))
                detail = f"{human_bytes_rate(data.get('speed'))} · faltan {human_time(data.get('eta'))} · {human_time(time.time() - started)}"
                self.job_progress.emit(job.key, shown, "Descargando", detail)
            elif status == "finished":
                shown = 84 if self.mode == "universal" else 97
                self.job_progress.emit(job.key, shown, "Procesando", f"Descarga lista · {human_time(time.time() - started)}")

        ffmpeg_dir = str(Path(self.ffmpeg_path).parent) if self.ffmpeg_path else None
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "logger": QuietLogger(),
            "outtmpl": str(tmp_stem) + ".%(ext)s",
            "windowsfilenames": True,
            "continuedl": True,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 20,
            "concurrent_fragment_downloads": 4,
            "progress_hooks": [hook],
            "noplaylist": True,
            "paths": {"home": str(self.folder)},
        }
        if ffmpeg_dir:
            opts["ffmpeg_location"] = ffmpeg_dir

        if self.mode == "mp3":
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": str(self.bitrate)},
                {"key": "FFmpegMetadata", "add_metadata": True},
            ]
        elif self.mode == "webm":
            opts["format"] = (
                f"bv*[height<=?{self.quality}][ext=webm]+ba[ext=webm]/"
                f"b[height<=?{self.quality}][ext=webm]/"
                f"bv*[height<=?{self.quality}]+ba/b[height<=?{self.quality}]"
            )
            opts["merge_output_format"] = "webm"
        else:
            opts["format"] = (
                f"bv*[height<=?{self.quality}][vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a]/"
                f"b[height<=?{self.quality}][vcodec^=avc1][ext=mp4]/"
                f"bv*[height<=?{self.quality}]+ba/b[height<=?{self.quality}]"
            )
            opts["merge_output_format"] = "mp4"

        try:
            self.job_progress.emit(job.key, 1, "Conectando", "Iniciando descarga…")
            with yt_dlp.YoutubeDL(opts) as ydl:
                # download() ya resuelve la información necesaria internamente; no hacemos extract_info previo.
                ydl.download([job.url])

            if self.cancel_event.is_set():
                self._cleanup_tmp(tmp_stem)
                self._mark_skip(job.key, "Cancelado")
                return

            ext = "mp3" if self.mode == "mp3" else ("webm" if self.mode == "webm" else "mp4")
            source = self._find_tmp_file(tmp_stem)
            if not source:
                raise RuntimeError("La descarga terminó, pero no se encontró el archivo temporal.")

            final_title = safe_name(captured_title or f"Video {captured_id}" or "Video")
            final_path = self.folder / f"{final_title}.{ext}"

            if final_path.exists():
                self._cleanup_tmp(tmp_stem)
                self.job_progress.emit(job.key, 100, "Omitido", "Ya existe en la carpeta")
                with self._counts_lock:
                    self._skipped += 1
                self.job_done.emit(job.key, str(final_path), "Omitido")
                return

            if self.mode == "universal":
                if not self.ffmpeg_path:
                    raise RuntimeError("FFmpeg es obligatorio para MP4 Universal.")
                converted = self.folder / f"CARED_TMP_{job.key}_UNIVERSAL.mp4"
                self._convert_universal(job, source, converted, started, captured_duration)
                try:
                    source.unlink(missing_ok=True)
                except Exception:
                    pass
                converted.replace(final_path)
            else:
                source.replace(final_path)

            self._cleanup_tmp(tmp_stem)
            self.job_progress.emit(job.key, 100, "Completado", f"Listo · {human_time(time.time() - started)}")
            with self._counts_lock:
                self._ok += 1
            self.job_done.emit(job.key, str(final_path), "Completado")
        except Exception as exc:
            self._cleanup_tmp(tmp_stem)
            if self.cancel_event.is_set() or "__CARED_CANCELLED__" in str(exc):
                self._mark_skip(job.key, "Cancelado")
            else:
                self._mark_error(job.key, self._friendly_error(exc))

    def _wait_if_paused(self) -> None:
        while not self.pause_event.is_set():
            if self.cancel_event.is_set():
                break
            time.sleep(0.15)

    def _find_tmp_file(self, tmp_stem: Path) -> Optional[Path]:
        candidates: list[Path] = []
        for p in tmp_stem.parent.glob(tmp_stem.name + ".*"):
            if not p.is_file():
                continue
            if p.suffix.lower() in {".part", ".ytdl", ".temp"}:
                continue
            candidates.append(p)
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]

    def _cleanup_tmp(self, tmp_stem: Path) -> None:
        for p in tmp_stem.parent.glob(tmp_stem.name + "*"):
            if p.is_file():
                try:
                    p.unlink()
                except Exception:
                    pass

    def _convert_universal(
        self,
        job: VideoJob,
        source: Path,
        target: Path,
        started: float,
        duration: Optional[float],
    ) -> None:
        if target.exists():
            target.unlink(missing_ok=True)
        cmd = [
            str(self.ffmpeg_path), "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(source),
            "-map", "0:v:0", "-map", "0:a:0?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats",
            str(target),
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, creationflags=creationflags,
        )
        try:
            assert proc.stdout is not None
            while True:
                self._wait_if_paused()
                if self.cancel_event.is_set():
                    proc.terminate()
                    raise RuntimeError("__CARED_CANCELLED__")
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                line = line.strip()
                pct = 90
                if line.startswith("out_time_ms=") and duration and duration > 0:
                    try:
                        seconds = int(line.split("=", 1)[1]) / 1_000_000.0
                        pct = 84 + int(max(0.0, min(1.0, seconds / duration)) * 15)
                    except Exception:
                        pct = 90
                if line.startswith("out_time_ms="):
                    self.job_progress.emit(
                        job.key, min(99, pct), "Convirtiendo",
                        f"MP4 Universal H.264 + AAC · {human_time(time.time() - started)}",
                    )
            code = proc.wait()
            if code != 0:
                err = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(err.strip() or "FFmpeg no pudo convertir el video.")
        finally:
            if self.cancel_event.is_set() and proc.poll() is None:
                proc.terminate()

    def _friendly_error(self, exc: Exception) -> str:
        msg = str(exc).strip()
        low = msg.lower()
        if "private video" in low or "private" in low:
            return "El video es privado o requiere acceso a una cuenta."
        if "unavailable" in low:
            return "El video no está disponible."
        if "sign in" in low or "confirm you're not a bot" in low or "confirm you’re not a bot" in low:
            return "YouTube está solicitando verificación de sesión. Actualiza yt-dlp o prueba nuevamente más tarde."
        if "unsupported url" in low:
            return "El enlace no es compatible o no corresponde a un video individual de YouTube."
        if "timed out" in low or "timeout" in low:
            return "YouTube tardó demasiado en responder. Revisa tu conexión e inténtalo otra vez."
        return msg[-900:] if msg else "Error desconocido durante la descarga."

    def _mark_error(self, key: str, message: str) -> None:
        with self._counts_lock:
            self._failed += 1
        self.job_error.emit(key, message)

    def _mark_skip(self, key: str, message: str) -> None:
        with self._counts_lock:
            self._skipped += 1
        self.job_progress.emit(key, 0, message, message)
        self.job_done.emit(key, "", message)


class MarqueeWidget(QWidget):
    def __init__(self, text: str, url: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.url = url
        self.offset = 0
        self.setObjectName("MarqueeBar")
        self.label = QLabel(text, self)
        self.label.setObjectName("MarqueeText")
        self.label.setCursor(Qt.PointingHandCursor)
        self.label.mousePressEvent = self._open_url  # type: ignore[assignment]
        self.setFixedHeight(29)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(35)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.offset = self.width()
        self.label.adjustSize()
        self.label.move(self.offset, 5)

    def _tick(self) -> None:
        self.offset -= 2
        if self.offset < -self.label.width():
            self.offset = self.width()
        self.label.move(self.offset, 5)

    def _open_url(self, event) -> None:
        QDesktopServices.openUrl(QUrl(self.url))


class HistoryDialog(QDialog):
    def __init__(self, parent: QWidget, history: list[dict[str, str]]):
        super().__init__(parent)
        self.setWindowTitle("Historial de descargas")
        self.resize(700, 390)
        lay = QVBoxLayout(self)
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Fecha", "Archivo", "Carpeta"])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for item in reversed(history[-100:]):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(item.get("date", "")))
            table.setItem(row, 1, QTableWidgetItem(item.get("title", "")))
            table.setItem(row, 2, QTableWidgetItem(item.get("folder", "")))
        lay.addWidget(table)
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignRight)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1050, 650)
        self.setMinimumSize(900, 560)
        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.jobs: list[VideoJob] = []
        self.row_by_key: dict[str, int] = {}
        self.downloader: Optional[DownloadCoordinator] = None
        self.ffmpeg_path = find_ffmpeg()
        self.history = self._load_history()
        self._build_ui()
        self._load_settings()
        self._update_mode_ui()
        self._dependency_status()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 10, 10, 8)
        outer.setSpacing(8)

        top = QFrame()
        top.setObjectName("TopBar")
        top.setFixedHeight(78)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(14, 8, 12, 8)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("Descargador de YouTube")
        title.setObjectName("Title")
        subtitle = QLabel("Videos y MP3 · descarga directa y compatible")
        subtitle.setObjectName("HeaderSubtle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        tl.addLayout(titles)
        tl.addStretch(1)
        credit = QLabel("Programa hecho por CARED")
        credit.setObjectName("Credit")
        tl.addWidget(credit)
        outer.addWidget(top)

        input_card = QFrame()
        input_card.setObjectName("LightCard")
        il = QVBoxLayout(input_card)
        il.setContentsMargins(10, 8, 10, 9)
        il.setSpacing(5)
        head = QHBoxLayout()
        label = QLabel("ENLACES")
        label.setObjectName("SectionTitle")
        head.addWidget(label)
        head.addStretch(1)
        hint = QLabel("Uno o varios videos, un enlace por línea")
        hint.setObjectName("Subtle")
        head.addWidget(hint)
        il.addLayout(head)
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_edit = QTextEdit()
        self.url_edit.setPlaceholderText("Pega aquí uno o varios enlaces de videos de YouTube…")
        self.url_edit.setFixedHeight(58)
        url_row.addWidget(self.url_edit, 1)
        self.download_btn = QPushButton("DESCARGAR")
        self.download_btn.setObjectName("Primary")
        self.download_btn.setFixedWidth(150)
        self.download_btn.setMinimumHeight(58)
        self.download_btn.clicked.connect(self.start_downloads)
        url_row.addWidget(self.download_btn)
        il.addLayout(url_row)
        outer.addWidget(input_card)

        options = QFrame()
        options.setObjectName("DarkCard")
        ol = QVBoxLayout(options)
        ol.setContentsMargins(10, 8, 10, 8)
        ol.setSpacing(5)
        row = QHBoxLayout()
        row.setSpacing(8)

        def add_field(title_text: str, widget: QWidget, stretch: int = 0) -> None:
            box = QVBoxLayout()
            box.setSpacing(3)
            lab = QLabel(title_text)
            lab.setObjectName("FieldLabelDark")
            box.addWidget(lab)
            box.addWidget(widget)
            row.addLayout(box, stretch)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("MP4 Universal · H.264 + AAC", "universal")
        self.mode_combo.addItem("MP4 rápido", "mp4")
        self.mode_combo.addItem("WEBM", "webm")
        self.mode_combo.addItem("Solo audio · MP3", "mp3")
        self.mode_combo.currentIndexChanged.connect(self._update_mode_ui)
        add_field("Formato", self.mode_combo, 2)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("4K · 2160p", 2160)
        self.quality_combo.addItem("1080p · Full HD", 1080)
        self.quality_combo.addItem("720p · Recomendado", 720)
        self.quality_combo.addItem("480p · Equipos antiguos", 480)
        add_field("Calidad", self.quality_combo, 1)

        self.bitrate_combo = QComboBox()
        for b in (128, 192, 256, 320):
            self.bitrate_combo.addItem(f"{b} kbps", b)
        add_field("MP3", self.bitrate_combo, 1)

        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 3)
        self.workers_spin.setValue(2)
        add_field("Simultáneas", self.workers_spin)

        folder_box = QVBoxLayout()
        folder_box.setSpacing(3)
        fl = QLabel("Carpeta")
        fl.setObjectName("FieldLabelDark")
        folder_box.addWidget(fl)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(5)
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        folder_row.addWidget(self.folder_edit, 1)
        choose = QPushButton("Elegir")
        choose.setObjectName("Dark")
        choose.clicked.connect(self.choose_folder)
        folder_row.addWidget(choose)
        open_b = QPushButton("Abrir")
        open_b.setObjectName("Dark")
        open_b.clicked.connect(self.open_folder)
        folder_row.addWidget(open_b)
        folder_box.addLayout(folder_row)
        row.addLayout(folder_box, 3)

        ol.addLayout(row)
        self.profile_note = QLabel("")
        self.profile_note.setObjectName("DarkSubtle")
        self.profile_note.setWordWrap(True)
        ol.addWidget(self.profile_note)
        outer.addWidget(options)

        queue_bar = QHBoxLayout()
        qtitle = QLabel("COLA DE DESCARGAS")
        qtitle.setObjectName("SectionTitle")
        queue_bar.addWidget(qtitle)
        self.summary_label = QLabel("0 elementos")
        self.summary_label.setObjectName("Subtle")
        queue_bar.addWidget(self.summary_label)
        queue_bar.addStretch(1)
        for text, slot in [
            ("Todos", self.select_all),
            ("Ninguno", self.select_none),
            ("Quitar", self.remove_selected),
            ("Limpiar", self.clear_finished),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            queue_bar.addWidget(b)
        outer.addLayout(queue_bar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["✓", "Título", "Duración", "Estado", "Progreso", "Velocidad / tiempo"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.resizeSection(4, 96)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        outer.addWidget(self.table, 1)

        action = QFrame()
        action.setObjectName("LightCard")
        ar = QHBoxLayout(action)
        ar.setContentsMargins(8, 6, 8, 6)
        ar.setSpacing(6)
        self.status_label = QLabel("Listo")
        self.status_label.setObjectName("Subtle")
        self.status_label.setWordWrap(True)
        ar.addWidget(self.status_label, 1)
        hist = QPushButton("Historial")
        hist.clicked.connect(self.show_history)
        ar.addWidget(hist)
        self.pause_btn = QPushButton("Pausar")
        self.pause_btn.clicked.connect(self.pause_downloads)
        self.pause_btn.setEnabled(False)
        ar.addWidget(self.pause_btn)
        self.resume_btn = QPushButton("Continuar")
        self.resume_btn.clicked.connect(self.resume_downloads)
        self.resume_btn.setEnabled(False)
        ar.addWidget(self.resume_btn)
        self.cancel_btn = QPushButton("Cancelar todo")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.clicked.connect(self.cancel_downloads)
        self.cancel_btn.setEnabled(False)
        ar.addWidget(self.cancel_btn)
        outer.addWidget(action)

        outer.addWidget(MarqueeWidget(f"Más programas en Apps que Resuelven   •   {WEBSITE_URL}", WEBSITE_URL))

    def _dependency_status(self) -> None:
        notes = []
        if yt_dlp is None:
            notes.append("yt-dlp no instalado")
        if not self.ffmpeg_path:
            notes.append("FFmpeg no detectado")
        if notes:
            self.status_label.setStyleSheet("color:#a04d00;font-weight:800;")
            self.status_label.setText("Atención: " + " · ".join(notes))
        else:
            self.status_label.setStyleSheet("color:#146c36;font-weight:800;")
            self.status_label.setText("Listo · yt-dlp y FFmpeg detectados")

    def _update_mode_ui(self) -> None:
        mode = self.mode_combo.currentData()
        is_mp3 = mode == "mp3"
        self.quality_combo.setEnabled(not is_mp3)
        self.bitrate_combo.setEnabled(is_mp3)
        notes = {
            "universal": "MP4 Universal: H.264 + AAC. Para autoradios o equipos antiguos recomiendo 720p o 480p.",
            "mp4": "MP4 rápido: prioriza compatibilidad sin recodificar cuando no es necesario.",
            "webm": "WEBM: eficiente, pero menos compatible con equipos antiguos.",
            "mp3": "MP3: descarga solo el audio y usa automáticamente el título del video como nombre.",
        }
        self.profile_note.setText(notes.get(mode, ""))

    def _extract_urls(self) -> tuple[list[str], list[str]]:
        raw_lines = [x.strip() for x in self.url_edit.toPlainText().splitlines() if x.strip()]
        clean: list[str] = []
        rejected: list[str] = []
        seen: set[str] = set()
        for raw in raw_lines:
            url = clean_youtube_video_url(raw)
            if not url:
                rejected.append(raw)
                continue
            if url not in seen:
                seen.add(url)
                clean.append(url)
        return clean, rejected

    def start_downloads(self) -> None:
        if self.downloader and self.downloader.isRunning():
            return
        if yt_dlp is None:
            QMessageBox.warning(self, "Falta yt-dlp", "yt-dlp no está instalado en este Python.\n\nEjecuta:\npy -3.12 -m pip install -U yt-dlp")
            return

        urls, rejected = self._extract_urls()
        if not urls:
            selected = self._selected_jobs()
            if selected:
                self._begin_downloads(selected)
                return
            msg = "Pega al menos un enlace de video de YouTube."
            if rejected:
                msg += "\n\nEsta versión no descarga playlists. Usa enlaces de videos individuales."
            QMessageBox.information(self, "Falta un video", msg)
            return

        existing_urls = {j.url for j in self.jobs}
        new_jobs: list[VideoJob] = []
        for i, url in enumerate(urls, 1):
            if url in existing_urls:
                continue
            job = VideoJob(key=uuid.uuid4().hex, url=url, title=f"Video {i}")
            self.jobs.append(job)
            self._append_job_row(job)
            new_jobs.append(job)
            existing_urls.add(url)

        self.url_edit.clear()
        self._refresh_summary()

        if rejected:
            self.status_label.setStyleSheet("color:#a04d00;font-weight:800;")
            self.status_label.setText(f"Se ignoraron {len(rejected)} enlace(s) no válidos o de playlist. Descargando los videos válidos.")

        if not new_jobs:
            self.status_label.setText("Esos videos ya están en la cola.")
            return

        self._begin_downloads(new_jobs)

    def _begin_downloads(self, selected: list[VideoJob]) -> None:
        if not selected:
            return
        folder = self.folder_edit.text().strip()
        if not folder:
            self.choose_folder()
            folder = self.folder_edit.text().strip()
            if not folder:
                return

        mode = self.mode_combo.currentData()
        if mode in {"universal", "mp3", "mp4", "webm"} and not self.ffmpeg_path:
            QMessageBox.warning(
                self,
                "FFmpeg no detectado",
                "Para combinar audio/video, convertir a MP4 Universal o crear MP3 necesitas FFmpeg.\n\n"
                "Coloca ffmpeg.exe y ffprobe.exe junto al archivo .py o agrega FFmpeg al PATH de Windows.",
            )
            return

        self._save_settings()
        for job in selected:
            row = self.row_by_key.get(job.key)
            if row is not None:
                bar = self.table.cellWidget(row, 4)
                if isinstance(bar, QProgressBar):
                    bar.setValue(0)
                    bar.setFormat("0%")
                self.table.item(row, 3).setText("En cola")
                self.table.item(row, 5).setText("--")

        self.downloader = DownloadCoordinator(
            jobs=selected,
            folder=folder,
            mode=mode,
            quality=int(self.quality_combo.currentData() or 720),
            bitrate=int(self.bitrate_combo.currentData() or 192),
            max_workers=self.workers_spin.value(),
            ffmpeg_path=self.ffmpeg_path,
            parent=self,
        )
        self.downloader.job_progress.connect(self._on_progress)
        self.downloader.job_meta.connect(self._on_meta)
        self.downloader.job_done.connect(self._on_job_done)
        self.downloader.job_error.connect(self._on_job_error)
        self.downloader.all_done.connect(self._on_all_done)
        self.downloader.start()

        self.download_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setStyleSheet("color:#1f2328;font-weight:800;")
        self.status_label.setText(f"Descargando {len(selected)} video(s)…")

    def _append_job_row(self, job: VideoJob) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.row_by_key[job.key] = row
        check = QTableWidgetItem()
        check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        check.setCheckState(Qt.Checked)
        check.setData(Qt.UserRole, job.key)
        self.table.setItem(row, 0, check)
        title = QTableWidgetItem(job.title)
        title.setToolTip(job.url)
        self.table.setItem(row, 1, title)
        self.table.setItem(row, 2, QTableWidgetItem("--:--"))
        self.table.setItem(row, 3, QTableWidgetItem("Listo"))
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFormat("0%")
        self.table.setCellWidget(row, 4, bar)
        self.table.setItem(row, 5, QTableWidgetItem("--"))

    def _on_meta(self, key: str, title: str, duration_text: str) -> None:
        row = self.row_by_key.get(key)
        if row is None:
            return
        self.table.item(row, 1).setText(title)
        self.table.item(row, 2).setText(duration_text)
        job = self._job_by_key(key)
        if job:
            job.title = title

    def choose_folder(self) -> None:
        start = self.folder_edit.text() or str(Path.home() / "Downloads")
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de descarga", start)
        if folder:
            self.folder_edit.setText(folder)
            self.settings.setValue("folder", folder)

    def open_folder(self) -> None:
        folder = self.folder_edit.text().strip()
        if not folder:
            return
        Path(folder).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def pause_downloads(self) -> None:
        if self.downloader and self.downloader.isRunning():
            self.downloader.pause()
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)
            self.status_label.setText("Descargas pausadas")

    def resume_downloads(self) -> None:
        if self.downloader and self.downloader.isRunning():
            self.downloader.resume()
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
            self.status_label.setText("Descargas reanudadas")

    def cancel_downloads(self) -> None:
        if self.downloader and self.downloader.isRunning():
            self.downloader.cancel()
            self.status_label.setText("Cancelando…")

    def _on_progress(self, key: str, pct: int, status: str, detail: str) -> None:
        row = self.row_by_key.get(key)
        if row is None:
            return
        self.table.item(row, 3).setText(status)
        self.table.item(row, 5).setText(detail)
        bar = self.table.cellWidget(row, 4)
        if isinstance(bar, QProgressBar):
            bar.setValue(pct)
            bar.setFormat(f"{pct}%")

    def _on_job_done(self, key: str, path: str, message: str) -> None:
        row = self.row_by_key.get(key)
        if row is not None:
            self.table.item(row, 3).setText(message)
            if message in {"Completado", "Omitido"}:
                bar = self.table.cellWidget(row, 4)
                if isinstance(bar, QProgressBar):
                    bar.setValue(100)
                    bar.setFormat("100%")
        if path and message == "Completado":
            job = self._job_by_key(key)
            self.history.append({
                "title": job.title if job else Path(path).name,
                "date": time.strftime("%Y-%m-%d %H:%M"),
                "folder": str(Path(path).parent),
                "path": path,
            })
            self.history = self.history[-200:]
            self._save_history()

    def _on_job_error(self, key: str, message: str) -> None:
        row = self.row_by_key.get(key)
        if row is not None:
            self.table.item(row, 3).setText("Error")
            self.table.item(row, 3).setToolTip(message)
            self.table.item(row, 5).setText(message[:140])
        self.status_label.setStyleSheet("color:#b00020;font-weight:800;")
        self.status_label.setText("Hubo un error. Pasa el cursor por el estado de la fila para ver el detalle.")

    def _on_all_done(self, ok: int, failed: int, skipped: int) -> None:
        self.download_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        color = "#a04d00" if failed else "#146c36"
        self.status_label.setStyleSheet(f"color:{color};font-weight:800;")
        self.status_label.setText(f"Finalizado: {ok} completado(s) · {failed} error(es) · {skipped} omitido(s)")

    def select_all(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)

    def select_none(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)

    def remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            item = self.table.item(row, 0)
            key = item.data(Qt.UserRole) if item else None
            self.table.removeRow(row)
            if key:
                self.jobs = [j for j in self.jobs if j.key != key]
        self._rebuild_row_map()
        self._refresh_summary()

    def clear_finished(self) -> None:
        remove = []
        for row in range(self.table.rowCount()):
            status = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
            if status in {"Completado", "Omitido", "Cancelado", "Error"}:
                remove.append(row)
        for row in reversed(remove):
            item = self.table.item(row, 0)
            key = item.data(Qt.UserRole) if item else None
            self.table.removeRow(row)
            if key:
                self.jobs = [j for j in self.jobs if j.key != key]
        self._rebuild_row_map()
        self._refresh_summary()

    def show_history(self) -> None:
        HistoryDialog(self, self.history).exec()

    def _selected_jobs(self) -> list[VideoJob]:
        keys: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                status = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
                if status not in {"Completado", "Omitido"}:
                    keys.append(str(item.data(Qt.UserRole)))
        wanted = set(keys)
        return [j for j in self.jobs if j.key in wanted]

    def _job_by_key(self, key: str) -> Optional[VideoJob]:
        for job in self.jobs:
            if job.key == key:
                return job
        return None

    def _rebuild_row_map(self) -> None:
        self.row_by_key.clear()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                self.row_by_key[str(item.data(Qt.UserRole))] = row

    def _refresh_summary(self) -> None:
        self.summary_label.setText(f"{self.table.rowCount()} elemento(s)")

    def _load_settings(self) -> None:
        self.folder_edit.setText(str(self.settings.value("folder", str(Path.home() / "Downloads"))))
        self.workers_spin.setValue(int(self.settings.value("workers", 2)))
        mode = str(self.settings.value("mode", "universal"))
        idx = self.mode_combo.findData(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        quality = int(self.settings.value("quality", 720))
        idx = self.quality_combo.findData(quality)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)
        bitrate = int(self.settings.value("bitrate", 192))
        idx = self.bitrate_combo.findData(bitrate)
        if idx >= 0:
            self.bitrate_combo.setCurrentIndex(idx)

    def _save_settings(self) -> None:
        self.settings.setValue("folder", self.folder_edit.text())
        self.settings.setValue("workers", self.workers_spin.value())
        self.settings.setValue("mode", self.mode_combo.currentData())
        self.settings.setValue("quality", self.quality_combo.currentData())
        self.settings.setValue("bitrate", self.bitrate_combo.currentData())

    def _load_history(self) -> list[dict[str, str]]:
        try:
            if HISTORY_FILE.exists():
                return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _save_history(self) -> None:
        try:
            HISTORY_FILE.write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        if self.downloader and self.downloader.isRunning():
            choice = QMessageBox.question(
                self, "Hay descargas activas", "Hay descargas en curso. ¿Quieres cancelarlas y cerrar?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if choice != QMessageBox.Yes:
                event.ignore()
                return
            self.downloader.cancel()
            self.downloader.wait(5000)
        self._save_settings()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
