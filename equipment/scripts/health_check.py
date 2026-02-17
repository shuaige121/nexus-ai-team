"""
Health Check Equipment
Monitors system health: CPU, RAM, Disk, GPU
"""

import psutil
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_gpu_info():
    """Get GPU information if available."""
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            return [{
                "id": gpu.id,
                "name": gpu.name,
                "load": round(gpu.load * 100, 2),
                "memory_used": round(gpu.memoryUsed, 2),
                "memory_total": round(gpu.memoryTotal, 2),
                "memory_percent": round((gpu.memoryUsed / gpu.memoryTotal) * 100, 2),
                "temperature": gpu.temperature
            } for gpu in gpus]
    except ImportError:
        logger.debug("GPUtil not available, skipping GPU check")
    except Exception as e:
        logger.warning(f"Failed to get GPU info: {e}")
    return None


def main(alert_cpu_threshold=80, alert_ram_threshold=80, alert_disk_threshold=90):
    """
    Check system health and return metrics.

    Args:
        alert_cpu_threshold: CPU usage % threshold for alerts
        alert_ram_threshold: RAM usage % threshold for alerts
        alert_disk_threshold: Disk usage % threshold for alerts

    Returns:
        Health check report
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "status": "healthy",
        "alerts": [],
        "metrics": {}
    }

    # CPU Check
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()

    report["metrics"]["cpu"] = {
        "usage_percent": round(cpu_percent, 2),
        "count": cpu_count,
        "frequency_mhz": round(cpu_freq.current, 2) if cpu_freq else None
    }

    if cpu_percent > alert_cpu_threshold:
        report["alerts"].append({
            "type": "cpu",
            "severity": "warning",
            "message": f"CPU usage is high: {cpu_percent}%"
        })
        report["status"] = "warning"

    # RAM Check
    ram = psutil.virtual_memory()
    report["metrics"]["ram"] = {
        "total_gb": round(ram.total / (1024**3), 2),
        "used_gb": round(ram.used / (1024**3), 2),
        "available_gb": round(ram.available / (1024**3), 2),
        "usage_percent": round(ram.percent, 2)
    }

    if ram.percent > alert_ram_threshold:
        report["alerts"].append({
            "type": "ram",
            "severity": "warning",
            "message": f"RAM usage is high: {ram.percent}%"
        })
        report["status"] = "warning"

    # Disk Check
    disk = psutil.disk_usage('/')
    report["metrics"]["disk"] = {
        "total_gb": round(disk.total / (1024**3), 2),
        "used_gb": round(disk.used / (1024**3), 2),
        "free_gb": round(disk.free / (1024**3), 2),
        "usage_percent": round(disk.percent, 2)
    }

    if disk.percent > alert_disk_threshold:
        report["alerts"].append({
            "type": "disk",
            "severity": "critical",
            "message": f"Disk usage is critical: {disk.percent}%"
        })
        report["status"] = "critical"

    # GPU Check (optional)
    gpu_info = get_gpu_info()
    if gpu_info:
        report["metrics"]["gpu"] = gpu_info

    # Summary
    report["summary"] = (
        f"CPU: {cpu_percent}%, RAM: {ram.percent}%, Disk: {disk.percent}%"
    )

    logger.info(f"Health check completed: {report['status']}")

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = main()
    print(f"Health Status: {result['status']}")
    print(f"Summary: {result['summary']}")
    if result['alerts']:
        print("\nAlerts:")
        for alert in result['alerts']:
            print(f"  [{alert['severity']}] {alert['message']}")
