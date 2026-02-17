"""
Backup Equipment
Backs up project to specified directory
"""

import os
import shutil
import tarfile
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def create_backup(source_dir: Path, backup_path: Path, exclude_patterns: list):
    """
    Create a tar.gz backup of source directory.

    Args:
        source_dir: Directory to backup
        backup_path: Path for backup file
        exclude_patterns: Patterns to exclude

    Returns:
        Backup file size in MB
    """
    def exclude_filter(tarinfo):
        """Filter function for tarfile."""
        for pattern in exclude_patterns:
            if pattern in tarinfo.name:
                return None
        return tarinfo

    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name, filter=exclude_filter)

    return backup_path.stat().st_size / (1024 * 1024)


def cleanup_old_backups(backup_dir: Path, keep_days: int):
    """
    Delete backups older than keep_days.

    Args:
        backup_dir: Directory containing backups
        keep_days: Keep backups from last N days

    Returns:
        List of deleted backups
    """
    deleted = []
    cutoff_date = datetime.now() - timedelta(days=keep_days)

    for backup_file in backup_dir.glob("nexus-ai-team-*.tar.gz"):
        try:
            file_stat = backup_file.stat()
            file_mtime = datetime.fromtimestamp(file_stat.st_mtime)

            if file_mtime < cutoff_date:
                file_size_mb = file_stat.st_size / (1024 * 1024)
                backup_file.unlink()
                deleted.append({
                    "file": backup_file.name,
                    "size_mb": round(file_size_mb, 2),
                    "age_days": (datetime.now() - file_mtime).days
                })
                logger.info(f"Deleted old backup: {backup_file.name}")

        except Exception as e:
            logger.error(f"Failed to delete {backup_file}: {e}")

    return deleted


def main(
    backup_dir="/home/leonard/backups/nexus-ai-team",
    exclude_patterns=None,
    keep_days=7
):
    """
    Create project backup.

    Args:
        backup_dir: Directory to store backups
        exclude_patterns: Patterns to exclude from backup
        keep_days: Keep backups from last N days

    Returns:
        Backup report
    """
    if exclude_patterns is None:
        exclude_patterns = [
            "*.pyc",
            "__pycache__",
            "node_modules",
            ".git",
            "nexus.db",
            "venv",
            ".venv"
        ]

    report = {
        "timestamp": datetime.now().isoformat(),
        "status": "success",
        "backup_file": None,
        "backup_size_mb": 0,
        "deleted_backups": [],
        "error": None
    }

    try:
        # Get project directory
        project_dir = Path(__file__).parent.parent.parent

        # Create backup directory
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"nexus-ai-team-{timestamp}.tar.gz"

        logger.info(f"Creating backup: {backup_file}")

        # Create backup
        backup_size_mb = create_backup(project_dir, backup_file, exclude_patterns)

        report["backup_file"] = str(backup_file)
        report["backup_size_mb"] = round(backup_size_mb, 2)

        logger.info(f"Backup created: {backup_size_mb:.2f} MB")

        # Clean up old backups
        deleted = cleanup_old_backups(backup_path, keep_days)
        report["deleted_backups"] = deleted

        # Summary
        report["summary"] = (
            f"Backup created: {backup_size_mb:.2f} MB, "
            f"Deleted: {len(deleted)} old backups"
        )

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        report["status"] = "error"
        report["error"] = str(e)
        report["summary"] = f"Backup failed: {str(e)}"

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = main()
    print(f"Status: {result['status']}")
    print(f"Summary: {result['summary']}")
    if result['backup_file']:
        print(f"Backup file: {result['backup_file']}")
