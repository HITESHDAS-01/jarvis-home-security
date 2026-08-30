import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from core.logger import get_logger

logger = get_logger("storage")


class EventStorage:
    def __init__(self, db_path="data/events.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=-64000")
                conn.execute("PRAGMA temp_store=MEMORY")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        camera_name TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        severity TEXT DEFAULT 'medium',
                        timestamp TEXT NOT NULL,
                        zone TEXT,
                        description TEXT,
                        snapshot_path TEXT,
                        clip_path TEXT,
                        detection_data TEXT,
                        summary TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS camera_health (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        camera_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        message TEXT,
                        timestamp TEXT NOT NULL
                    )
                """)

                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_name)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")

            logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def vacuum(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("VACUUM")
            logger.info("Database vacuumed")
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")

    def cleanup_old_events(self, days=30):
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
                deleted = cursor.rowcount
            logger.info(f"Cleaned up {deleted} events older than {days} days")
            return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup events: {e}")
            return 0

    def get_database_stats(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM events")
                event_count = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM camera_health")
                health_count = cursor.fetchone()[0]

                cursor = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM events")
                row = cursor.fetchone()
                oldest = row[0] if row[0] else None
                newest = row[1] if row[1] else None

            return {
                "event_count": event_count,
                "health_count": health_count,
                "oldest_event": oldest,
                "newest_event": newest,
            }
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}

    def create_event(self, camera_name, event_type, severity="medium", zone=None,
                     description=None, snapshot_path=None, clip_path=None,
                     detection_data=None, summary=None):
        try:
            timestamp = datetime.now().isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO events (camera_name, event_type, severity, timestamp,
                                       zone, description, snapshot_path, clip_path,
                                       detection_data, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (camera_name, event_type, severity, timestamp, zone,
                      description, snapshot_path, clip_path,
                      json.dumps(detection_data) if detection_data else None,
                      summary))

                event_id = cursor.lastrowid
                logger.debug(f"Created event {event_id}: {event_type} at {camera_name}")
                return event_id
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return None

    def get_events(self, camera_name=None, event_type=None, start_time=None,
                   end_time=None, limit=50):
        try:
            query = "SELECT * FROM events WHERE 1=1"
            params = []

            if camera_name:
                query += " AND camera_name = ?"
                params.append(camera_name)

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []

    def get_recent_events(self, hours=2, limit=20):
        start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        return self.get_events(start_time=start_time, limit=limit)

    def get_event_by_id(self, event_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get event by ID: {e}")
            return None

    def search_events(self, query, limit=20):
        try:
            search_term = f"%{query}%"
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM events
                    WHERE description LIKE ? OR zone LIKE ? OR summary LIKE ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (search_term, search_term, search_term, limit))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to search events: {e}")
            return []

    def get_event_stats(self, hours=24):
        try:
            start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT camera_name, event_type, COUNT(*) as count
                    FROM events
                    WHERE timestamp >= ?
                    GROUP BY camera_name, event_type
                """, (start_time,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get event stats: {e}")
            return []

    def log_camera_health(self, camera_name, status, message=None):
        try:
            timestamp = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO camera_health (camera_name, status, message, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (camera_name, status, message, timestamp))
        except Exception as e:
            logger.error(f"Failed to log camera health: {e}")

    def update_event_summary(self, event_id, summary):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE events SET summary = ? WHERE id = ?", (summary, event_id))
        except Exception as e:
            logger.error(f"Failed to update event summary: {e}")
