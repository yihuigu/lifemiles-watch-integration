"""Constants for the LifeMiles Watch integration."""
from datetime import timedelta

DOMAIN = "lifemiles_watch"
DEFAULT_PORT = 8099
SCAN_INTERVAL = timedelta(minutes=5)
REQUEST_TIMEOUT = 15

CONF_API_TOKEN = "api_token"

# Attributes of the main sensor, in the shape the lifemiles-watch-card dashboard card reads.
ATTRIBUTES = ("last_run", "next_run", "config", "runs", "current", "history")

# A starting list for the airport pickers; any other 3-letter code can be typed in.
AIRPORTS = {
    "SYD": "Sydney", "MEL": "Melbourne", "BNE": "Brisbane", "PER": "Perth", "ADL": "Adelaide",
    "CBR": "Canberra", "OOL": "Gold Coast", "AKL": "Auckland",
    "HND": "Tokyo Haneda", "NRT": "Tokyo Narita", "KIX": "Osaka Kansai", "NGO": "Nagoya",
    "FUK": "Fukuoka", "CTS": "Sapporo", "ICN": "Seoul Incheon", "GMP": "Seoul Gimpo",
    "HKG": "Hong Kong", "TPE": "Taipei", "PVG": "Shanghai Pudong", "SHA": "Shanghai Hongqiao",
    "HGH": "Hangzhou", "PEK": "Beijing Capital", "PKX": "Beijing Daxing", "CAN": "Guangzhou",
    "SZX": "Shenzhen", "CTU": "Chengdu", "SIN": "Singapore", "BKK": "Bangkok", "KUL": "Kuala Lumpur",
    "MNL": "Manila", "SGN": "Ho Chi Minh City", "DEL": "Delhi", "BOM": "Mumbai",
    "DXB": "Dubai", "SFO": "San Francisco", "LAX": "Los Angeles", "VIE": "Vienna",
    "FRA": "Frankfurt", "ZRH": "Zurich", "LHR": "London Heathrow",
}
