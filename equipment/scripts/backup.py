"""
Backup Equipment
Backs up project to specified directory
"""

import logging
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def create_backup(
    source_dir: str,
    backup_path: str,
    exclude_patterns: list[str] = None,
) -> float:
    """
    Create a tar.gz backup of source directory.

    Args:
        source_dir: Directory to backup
        backup_path: Path for backup file
        exclude_patterns: Patterns to exclude

    Returns:
        Backup file size in MB
    """
    if exclude_patterns is None:
        exclude_patterns = []
    def exclude_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
        """Filter function for tarfile."""
        for pattern in exclude_patterns:
            if pattern in tarinfo.name:
                return None
        return tarinfo

    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(source_dir, filter=exclude_filter)

    return Path(backup_path).stat().st_size / (1024 * 1024)


def cleanup_old_backups(backup_dir: Path, keep_days: int = 7) -> list[dict]:
    """
    Delete backups older than keep_days.

    Args:
        backup_dir: Directory containing backups
        keep_days: Keep backups from last N days

    Returns:
        List of deleted backups
    """
    deleted: list[dict] = []
    datetime.now() - timedelta(days=keep_days)

    for backup_file in backup_dir.glob("nexus-ai-team-*.tar.gz"):
        try:
            mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if (datetime.now() - mtime).days > keep_days:
                size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)
                backup_file.unlink()
                deleted.append({"name": backup_file.name, "size_mb": size_mb})
                logger.info(f"Deleted old backup: {backup_file.name}")
        except Exception as e:
            logger.error(f"Failed to delete {backup_file}: {e}")

    return deleted


def main(
    backup_dir: str = "/home/leonard/backups/nexus-ai-team",
    exclude_patterns: list[str] | None = None,
    keep_days: int = 7,
) -> dict:
    """
    Create project backup.

    Args:
        backup_dir: Directory to store backups
        exclude_patterns: Patterns to exclude from backup
        keep_days: Keep backups from last N days

    Returns:
        Backup report
    """
    timestamp = datetime.now().isoformat()
    status = "success"
    source_dir = Path(__file__).parent.parent

    backup_path_dir = Path(backup_dir)
    backup_path_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_path_dir / f"nexus-ai-team-{date_str}.tar.gz"

    try:
        logger.info(f"Creating backup: {backup_file}")
        size_mb = create_backup(
            str(source_dir),
            str(backup_file),
            exclude_patterns or [],
        )

        deleted_backups = cleanup_old_backups(backup_path_dir, keep_days)

        summary = f"Backup created: {round(size_mb, 2):.2f} MB, Deleted: {len(deleted_backups)} old backups"
        logger.info(f"Backup created: {size_mb:.2f} MB")

        return {
            "status": status,
            "timestamp": timestamp,
            "backup_file": str(backup_file),
            "backup_size_mb": round(size_mb, 2),
            "deleted_backups": deleted_backups,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return {
            "status": "error",
            "timestamp": timestamp,
            "error": str(e),
            "summary": f"Failed: {e}",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = main()
    print(f"Status: {result['status']}")
    print(f"Summary: {result['summary']}")
    if "backup_file" in result:
        print(f"Backup file: {result['backup_file']}")
