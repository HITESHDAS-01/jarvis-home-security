import yaml
from pathlib import Path
from core.logger import get_logger

logger = get_logger("zone_manager")


class ZoneManager:
    def __init__(self, config_path="config/zones.yaml"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.zones = self.config.get("zones", {})
        self.rules = self.config.get("security_rules", [])

    def _load_config(self, config_path):
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Zone config not found: {config_path}, using defaults")
            return {"zones": {}, "security_rules": []}
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in zone config: {e}")
            return {"zones": {}, "security_rules": []}

    def get_zones_for_camera(self, camera_name):
        for zone_key, zone_data in self.zones.items():
            if zone_data.get("camera") == camera_name:
                return zone_data.get("areas", [])
        return []

    def get_zone(self, zone_name):
        return self.zones.get(zone_name)

    def add_zone(self, zone_name, camera_name, areas):
        self.zones[zone_name] = {
            "camera": camera_name,
            "areas": areas,
        }
        self._save_config()

    def update_zone(self, zone_name, areas):
        if zone_name in self.zones:
            self.zones[zone_name]["areas"] = areas
            self._save_config()

    def remove_zone(self, zone_name):
        if zone_name in self.zones:
            del self.zones[zone_name]
            self._save_config()

    def _save_config(self):
        config = {"zones": self.zones, "security_rules": self.rules}
        with open("config/zones.yaml", "w") as f:
            yaml.dump(config, f, default_flow_style=False)

    def get_rules(self):
        return self.rules

    def get_rules_for_time(self, hour):
        active_rules = []
        for rule in self.rules:
            time_range = rule.get("time_range", "24h")
            if time_range == "24h":
                active_rules.append(rule)
            elif time_range == "22:00-06:00":
                if hour >= 22 or hour < 6:
                    active_rules.append(rule)
        return active_rules

    def should_alert(self, event_type, zone_name=None, hour=None):
        if hour is None:
            from datetime import datetime
            hour = datetime.now().hour

        for rule in self.rules:
            if rule.get("trigger") == event_type:
                time_range = rule.get("time_range", "24h")
                if time_range == "24h":
                    return True, rule.get("severity", "medium")
                elif time_range == "22:00-06:00":
                    if hour >= 22 or hour < 6:
                        return True, rule.get("severity", "medium")
        return False, None
