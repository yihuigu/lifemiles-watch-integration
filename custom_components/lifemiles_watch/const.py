"""Constants for the LifeMiles Watch integration."""
from datetime import timedelta

DOMAIN = "lifemiles_watch"
DEFAULT_PORT = 8099
SCAN_INTERVAL = timedelta(minutes=5)
REQUEST_TIMEOUT = 15

# Attributes of the main sensor, in the shape the lifemiles-watch-card dashboard card reads.
ATTRIBUTES = ("last_run", "next_run", "config", "runs", "current", "history")
