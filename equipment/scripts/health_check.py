"""
Health Check Equipment
Monitors system health: CPU, RAM, Disk, GPU
"""

import psutil
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_gpu_info() -> list[dict]:
    """Get GPU information if available."""
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        return [
            {
                "id": gpu.id,
                "name": gpu.name,
                "load": round(gpu.load, 2),
                "memory_used": gpu.memoryUsed,
                "memory_total": gpu.memoryTotal,
                "temperature": gpu.temperature,
            }
            for gpu in gpus
        ]
    except ImportError:
        logger.debug("GPUtil not available, skipping GPU check")
        return []
    except Exception as e:
        logger.warning(f"Failed to get GPU info: {e}")
        return []


def main(
    alert_cpu_threshold: int = 80,
    alert_ram_threshold: int = 80,
    alert_disk_threshold: int = 90,
) -> dict:
    """
    Check system health and return metrics.

    Args:
        alert_cpu_threshold: CPU usage % threshold for alerts
        alert_ram_threshold: RAM usage % threshold for alerts
        alert_disk_threshold: Disk usage % threshold for alerts

    Returns:
        Health check report
    """
    timestamp = datetime.now().isoformat()
    status = "healthy"
    metrics: dict = {}
    alerts: list[dict] = []

    # CPU
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    metrics["cpu"] = {
        "usage_percent": cpu_usage,
        "count": cpu_count,
        "frequency_mhz": round(cpu_freq.current) if cpu_freq else None,
    }
    if cpu_usage > alert_cpu_threshold:
        alerts.append({"severity": "warning", "message": f"CPU usage is high: {cpu_usage}%"})
        status = "warning"

    # RAM
    ram = psutil.virtual_memory()
    metrics["ram"] = {
        "total_gb": round(ram.total / (1024 ** 3), 2),
        "used_gb": round(ram.used / (1024 ** 3), 2),
        "available_gb": round(ram.available / (1024 ** 3), 2),
        "usage_percent": ram.percent,
    }
    if ram.percent > alert_ram_threshold:
        alerts.append({"severity": "warning", "message": f"RAM usage is high: {ram.percent}%"})
        status = "warning"

    # Disk
    disk = psutil.disk_usage("/")
    metrics["disk"] = {
        "total_gb": round(disk.total / (1024 ** 3), 2),
        "used_gb": round(disk.used / (1024 ** 3), 2),
        "free_gb": round(disk.free / (1024 ** 3), 2),
        "usage_percent": disk.percent,
    }
    if disk.percent > alert_disk_threshold:
        alerts.append({"severity": "critical", "message": f"Disk usage is critical: {disk.percent}%"})
        status = "critical"

    # GPU
    gpu_info = get_gpu_info()
    if gpu_info:
        metrics["gpu"] = gpu_info

    summary = f"CPU: {cpu_usage}%, RAM: {ram.percent}%, Disk: {disk.percent}%"
    logger.info(f"Health check completed: {summary}")

    return {
        "status": status,
        "timestamp": timestamp,
        "metrics": metrics,
        "alerts": alerts,
        "summary": summary,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = main()
    print(f"Health Status: {result['status']}")
    print(f"Summary: {result['summary']}")
    if result["alerts"]:
        print("\nAlerts:")
        for alert in result["alerts"]:
            print(f"  [{alert['severity']}] {alert['message']}")
