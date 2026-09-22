"""
Push-to-Telegram database backups.

Complements scripts/backup_db.sh (which pulls a copy down to a laptop over
SSH): this module has the *bot itself* gzip a safe snapshot of its own
database and send it as a document to a Telegram chat (by default, the
owner's DM) via the Bot API. No server access, SSH keys, or extra
infrastructure required - just `!backup_now`, or the nightly schedule in
[backup] of config.toml.

SQLite is backed up with the standard library's own `sqlite3.backup()` API,
which is safe to run against a live, in-use database (same guarantee as the
`sqlite3 ... ".backup"` CLI command used by scripts/backup_db.sh). Postgres
and MySQL fall back to shelling out to pg_dump/mysqldump, mirroring the bash
script's logic, for parity when a deployment uses one of those instead.
"""

import asyncio
import gzip
import logging
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot
from aiogram.types import FSInputFile

from config import config

logger = logging.getLogger(__name__)

_SQLITE_PREFIX_RE = re.compile(r"^sqlite\+?[a-z0-9]*:///")


def _sqlite_path_from_url(db_url: str) -> Path:
    """Extract the on-disk path from a `sqlite(+driver):///path` URL."""
    raw_path = _SQLITE_PREFIX_RE.sub("", db_url)
    return Path(raw_path)


def _make_sqlite_snapshot(db_path: Path, out_path: Path) -> None:
    """Safe hot-copy of a SQLite database (blocking; run in a thread)."""
    source = sqlite3.connect(str(db_path))
    try:
        dest = sqlite3.connect(str(out_path))
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()


async def _dump_postgres(db_url: str, out_path: Path) -> bool:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        logger.error("Backup failed: pg_dump not found on this machine")
        return False

    pg_url = re.sub(r"^postgresql\+[a-z0-9]+://", "postgresql://", db_url)
    with open(out_path, "wb") as f:
        proc = await asyncio.create_subprocess_exec(
            pg_dump, "--no-owner", "--no-privileges", pg_url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("pg_dump failed: %s", stderr.decode(errors="replace"))
            return False
        f.write(stdout)
    return True


async def _dump_mysql(db_url: str, out_path: Path) -> bool:
    mysqldump = shutil.which("mysqldump")
    if not mysqldump:
        logger.error("Backup failed: mysqldump not found on this machine")
        return False

    parsed = urlparse(re.sub(r"^mysql\+[a-z0-9]+://", "mysql://", db_url))
    db_name = (parsed.path or "").lstrip("/")
    cmd = [
        mysqldump,
        "-h", parsed.hostname or "localhost",
        "-P", str(parsed.port or 3306),
        "-u", parsed.username or "root",
        db_name,
    ]
    env = {"MYSQL_PWD": parsed.password or ""}
    with open(out_path, "wb") as f:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("mysqldump failed: %s", stderr.decode(errors="replace"))
            return False
        f.write(stdout)
    return True


def _gzip_file(src: Path, dst: Path) -> None:
    with open(src, "rb") as f_in, gzip.open(dst, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)


async def build_backup_archive(tmp_dir: Path) -> tuple[Path, str] | None:
    """
    Build a gzipped backup archive in tmp_dir.

    Returns (archive_path, backend_name) or None on failure.
    """
    db_url = config.db.url
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if db_url.startswith("sqlite"):
        db_path = _sqlite_path_from_url(db_url)
        if not db_path.exists():
            logger.error("Backup failed: sqlite file not found at %s", db_path)
            return None
        raw_path = tmp_dir / f"shishka_backup_{timestamp}.sqlite3"
        try:
            await asyncio.to_thread(_make_sqlite_snapshot, db_path, raw_path)
        except Exception:
            logger.exception("Backup failed: could not snapshot sqlite database")
            return None
        backend = "sqlite"
    elif db_url.startswith(("postgres://", "postgresql://")):
        raw_path = tmp_dir / f"shishka_backup_{timestamp}.sql"
        if not await _dump_postgres(db_url, raw_path):
            return None
        backend = "postgres"
    elif db_url.startswith("mysql"):
        raw_path = tmp_dir / f"shishka_backup_{timestamp}.sql"
        if not await _dump_mysql(db_url, raw_path):
            return None
        backend = "mysql"
    else:
        logger.error("Backup failed: unrecognized DB_URL scheme: %s", db_url)
        return None

    archive_path = raw_path.with_suffix(raw_path.suffix + ".gz")
    try:
        await asyncio.to_thread(_gzip_file, raw_path, archive_path)
    finally:
        raw_path.unlink(missing_ok=True)

    return archive_path, backend


async def create_backup(bot: Bot, chat_id: int | None = None) -> bool:
    """
    Build a backup archive and send it to `chat_id` (default: config-driven).

    Returns True on success.
    """
    target_chat_id = chat_id or config.backup.chat_id or config.bot.owner
    if not target_chat_id:
        logger.error("Backup failed: no destination chat_id configured (backup.chat_id / bot.owner)")
        return False

    with tempfile.TemporaryDirectory(prefix="shishka_backup_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        result = await build_backup_archive(tmp_dir)
        if result is None:
            try:
                await bot.send_message(target_chat_id, "❌ Не удалось создать резервную копию базы данных. Подробности в логах.")
            except Exception:
                pass
            return False

        archive_path, backend = result
        size_mb = archive_path.stat().st_size / (1024 * 1024)

        try:
            await bot.send_document(
                target_chat_id,
                FSInputFile(archive_path),
                caption=(
                    f"💾 Резервная копия базы данных ({backend})\n"
                    f"📦 Размер: {size_mb:.2f} МБ\n"
                    f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ),
            )
            logger.info("Backup sent to chat %s (%s, %.2f MB)", target_chat_id, backend, size_mb)
            return True
        except Exception:
            logger.exception("Backup failed: could not send document to chat %s", target_chat_id)
            return False


async def run_backup_scheduler(bot: Bot) -> None:
    """Background task: send an automatic backup every [backup].interval_hours."""
    if not config.backup.enabled:
        logger.info("Automatic backups disabled (backup.enabled = false)")
        return

    interval_seconds = max(1, config.backup.interval_hours) * 3600
    logger.info("Automatic backup scheduler started (every %sh)", config.backup.interval_hours)

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await create_backup(bot)
        except asyncio.CancelledError:
            logger.info("Backup scheduler cancelled")
            raise
        except Exception:
            logger.exception("Backup scheduler iteration failed")
