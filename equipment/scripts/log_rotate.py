"""
Log Rotate Equipment
Rotates and cleans up old log files
"""

import os
import gzip
import shutil
import logging
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
    compressed_path = file_path.with_suffix(file_path.suffix + '.gz')

    with open(file_path, 'rb') as f_in:
        with gzip.open(compressed_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    return compressed_path


def main(log_dir="logs", max_age_days=30, max_size_mb=100):
    """
    Rotate and clean up log files.

    Args:
        log_dir: Directory containing log files
        max_age_days: Delete compressed logs older than this many days
        max_size_mb: Compress log files larger than this size

    Returns:
        Rotation report
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "compressed": [],
        "deleted": [],
        "total_freed_mb": 0,
        "errors": []
    }

    log_path = Path(log_dir)

    if not log_path.exists():
        logger.warning(f"Log directory does not exist: {log_dir}")
        return report

    # Get cutoff date for deletion
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    max_size_bytes = max_size_mb * 1024 * 1024

    try:
        # Process log files
        for file_path in log_path.glob("**/*.log"):
            try:
                file_stat = file_path.stat()
                file_size_mb = file_stat.st_size / (1024 * 1024)

                # Compress large files
                if file_stat.st_size > max_size_bytes and not file_path.name.endswith('.gz'):
                    logger.info(f"Compressing {file_path.name} ({file_size_mb:.2f} MB)")

                    compressed_path = compress_file(file_path)
                    original_size = file_path.stat().st_size
                    compressed_size = compressed_path.stat().st_size

                    # Delete original
                    file_path.unlink()

                    freed_mb = (original_size - compressed_size) / (1024 * 1024)
                    report["compressed"].append({
                        "file": str(file_path.name),
                        "original_size_mb": round(file_size_mb, 2),
                        "compressed_size_mb": round(compressed_size / (1024 * 1024), 2),
                        "freed_mb": round(freed_mb, 2)
                    })
                    report["total_freed_mb"] += freed_mb

            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                report["errors"].append({
                    "file": str(file_path),
                    "error": str(e)
                })

        # Delete old compressed logs
        for file_path in log_path.glob("**/*.log.gz"):
            try:
                file_stat = file_path.stat()
                file_mtime = datetime.fromtimestamp(file_stat.st_mtime)

                if file_mtime < cutoff_date:
                    file_size_mb = file_stat.st_size / (1024 * 1024)
                    logger.info(f"Deleting old compressed log: {file_path.name}")

                    file_path.unlink()

                    report["deleted"].append({
                        "file": str(file_path.name),
                        "size_mb": round(file_size_mb, 2),
                        "age_days": (datetime.now() - file_mtime).days
                    })
                    report["total_freed_mb"] += file_size_mb

            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                report["errors"].append({
                    "file": str(file_path),
                    "error": str(e)
                })

    except Exception as e:
        logger.error(f"Log rotation failed: {e}")
        report["errors"].append({"error": str(e)})

    # Summary
    report["summary"] = (
        f"Compressed: {len(report['compressed'])}, "
        f"Deleted: {len(report['deleted'])}, "
        f"Freed: {report['total_freed_mb']:.2f} MB"
    )

    logger.info(f"Log rotation completed: {report['summary']}")

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = main()
    print(f"Summary: {result['summary']}")
    if result['compressed']:
        print(f"\nCompressed {len(result['compressed'])} files")
    if result['deleted']:
        print(f"Deleted {len(result['deleted'])} old files")
    if result['errors']:
        print(f"\nErrors: {len(result['errors'])}")
