"""PDF isolado; capacidade limitada e configuração no Core."""
import subprocess
import sys
from pathlib import Path
from threading import BoundedSemaphore
from core.db import db
from model.core.system_config import SystemConfig
from .report_layout_service import ReportError

_slots = BoundedSemaphore(2)


def _setting(key, default, low, high):
    # Leitura própria: não mantém a transação do consumidor durante o PDF.
    with db.engine.connect() as connection:
        row = connection.execute(db.select(SystemConfig.value, SystemConfig.value_type).where(SystemConfig.key == 'reports.' + key)).first()
    try:
        value = SystemConfig._cast(row.value, row.value_type) if row else default
    except (TypeError, ValueError):
        value = default
    if type(value) is not int or not low <= value <= high:
        return default
    return value


def render_pdf(html):
    if len(html.encode()) > 2 * 1024 * 1024:
        raise ReportError('reports.error.size', status=413)
    timeout = _setting('pdf_timeout_seconds', 30, 5, 120)
    memory = _setting('pdf_memory_mb', 1024, 256, 2048)
    if not _slots.acquire(blocking=False):
        raise ReportError('reports.error.capacity', status=429)
    root = Path(__file__).resolve().parents[4]
    try:
        try:
            result = subprocess.run([sys.executable, '-m', 'addons.addon_reports.root.services.report_pdf_worker', str(memory), str(timeout)],
                input=html.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, cwd=root)
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise ReportError('reports.error.pdf', status=503) from exc
        if result.returncode != 0 or not result.stdout.startswith(b'%PDF-') or len(result.stdout) > 10 * 1024 * 1024:
            raise ReportError('reports.error.pdf', status=503)
        return result.stdout
    finally:
        _slots.release()
