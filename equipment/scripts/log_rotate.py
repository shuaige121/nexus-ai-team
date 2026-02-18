"""
Log Rotate Equipment
Rotates and cleans up old log files
"""

import gzip
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def compress_file(file_path: Path) -> Path:
    """
    Compress a file with gzip.

    Args:
        file_path: Path to file to compress

    Returns:
        Path to compressed file
    """
    gz_path = file_path.with_suffix(file_path.suffix + ".gz")
    with open(file_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    return gz_path


def main(
    log_dir: str = "logs",
    max_age_days: int = 30,
    max_size_mb: int = 100,
) -> dict:
    """
    Rotate and clean up log files.

    Args:
        log_dir: Directory containing log files
        max_age_days: Delete compressed logs older than this many days
        max_size_mb: Compress log files larger than this size

    Returns:
        Rotation report
    """
    timestamp = datetime.now().isoformat()
    log_path = Path(log_dir)

    if not log_path.exists():
        logger.warning(f"Log directory does not exist: {log_dir}")
        return {
            "status": "error",
            "error": f"Log directory does not exist: {log_dir}",
            "timestamp": timestamp,
            "summary": f"Log directory does not exist: {log_dir}",
        }

    datetime.now() - timedelta(days=max_age_days)
    compressed: list[dict] = []
    deleted: list[dict] = []
    errors: list[str] = []
    total_freed_mb: float = 0.0

    # Compress large log files
    for log_file in log_path.glob("**/*.log"):
        try:
            size_mb = log_file.stat().st_size / (1024 * 1024)
            if size_mb > max_size_mb and not log_file.name.endswith(".gz"):
                logger.info(f"Compressing {log_file.name} ({size_mb:.2f} MB)")
                gz_path = compress_file(log_file)
                log_file.unlink()
                compressed.append({
                    "name": str(log_file.name),
                    "original_size_mb": round(size_mb, 2),
                })
                total_freed_mb += size_mb - gz_path.stat().st_size / (1024 * 1024)
        except Exception as e:
            logger.error(f"Failed to process {log_file}: {e}")
            errors.append(f"Failed to process {log_file}: {e}")

    # Delete old compressed logs
    for gz_file in log_path.glob("**/*.log.gz"):
        try:
            mtime = datetime.fromtimestamp(gz_file.stat().st_mtime)
            if (datetime.now() - mtime).days > max_age_days:
                logger.info(f"Deleting old compressed log: {gz_file.name}")
                gz_file.unlink()
                deleted.append({"name": str(gz_file.name)})
        except Exception as e:
            logger.error(f"Failed to delete {gz_file}: {e}")
            errors.append(f"Failed to delete {gz_file}: {e}")

    summary = f"Compressed: {len(compressed)}, Deleted: {len(deleted)}, Freed: {round(total_freed_mb, 2)} MB"
    logger.info(f"Log rotation completed: {summary}")

    return {
        "status": "success",
        "timestamp": timestamp,
        "compressed": compressed,
        "deleted": deleted,
        "total_freed_mb": round(total_freed_mb, 2),
        "errors": errors,
        "summary": summary,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = main()
    print(f"Summary: {result['summary']}")
    if result["compressed"]:
        print(f"\nCompressed {len(result['compressed'])} files")
    if result["deleted"]:
        print(f"Deleted {len(result['deleted'])} old files")
    if result["errors"]:
        print(f"\nErrors: {result['errors']}")
