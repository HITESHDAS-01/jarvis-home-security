import psutil
import os
import time
import threading
from pathlib import Path
from core.logger import get_logger

logger = get_logger("disk_monitor")


class DiskMonitor:
    def __init__(self, min_free_gb=5, check_interval=60):
        self.min_free_gb = min_free_gb
        self.check_interval = check_interval
        self._running = False
        self._thread = None
        self._callbacks = []

    def register_callback(self, callback):
        self._callbacks.append(callback)

    def _fire_callbacks(self, usage_percent, free_gb):
        for cb in self._callbacks:
            try:
                cb(usage_percent, free_gb)
            except Exception as e:
                logger.error(f"Disk monitor callback error: {e}")

    def get_disk_usage(self, path=None):
        if path is None:
            path = os.getcwd()

        try:
            usage = psutil.disk_usage(path)
            return {
                "total_gb": usage.total / (1024**3),
                "used_gb": usage.used / (1024**3),
                "free_gb": usage.free / (1024**3),
                "percent": usage.percent,
            }
        except Exception as e:
            logger.error(f"Failed to get disk usage: {e}")
            return None

    def check_disk(self):
        usage = self.get_disk_usage()
        if usage is None:
            return

        free_gb = usage["free_gb"]
        percent = usage["percent"]

        if free_gb < self.min_free_gb:
            logger.warning(f"Low disk space: {free_gb:.1f}GB free ({percent}% used)")
            self._fire_callbacks(percent, free_gb)
            return False

        logger.debug(f"Disk OK: {free_gb:.1f}GB free ({percent}% used)")
        return True

    def start(self):
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"Disk monitor started (min free: {self.min_free_gb}GB)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Disk monitor stopped")

    def _monitor_loop(self):
        while self._running:
            self.check_disk()
            time.sleep(self.check_interval)

    def get_storage_stats(self):
        data_dir = Path("data")
        stats = {"recordings": 0, "snapshots": 0, "database": 0, "total_files": 0}

        recordings_dir = data_dir / "recordings"
        if recordings_dir.exists():
            files = list(recordings_dir.rglob("*"))
            stats["recordings"] = sum(f.stat().st_size for f in files if f.is_file()) / (1024**2)
            stats["total_files"] += sum(1 for f in files if f.is_file())

        snapshots_dir = data_dir / "snapshots"
        if snapshots_dir.exists():
            files = list(snapshots_dir.rglob("*"))
            stats["snapshots"] = sum(f.stat().st_size for f in files if f.is_file()) / (1024**2)
            stats["total_files"] += sum(1 for f in files if f.is_file())

        db_file = data_dir / "events.db"
        if db_file.exists():
            stats["database"] = db_file.stat().st_size / (1024**2)

        stats["total_size_mb"] = stats["recordings"] + stats["snapshots"] + stats["database"]
        return stats
