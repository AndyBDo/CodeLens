import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

_config = {}


def load_config():
    global _config
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            _config = json.load(f)
    return _config


def save_config(config: dict):
    global _config
    _config = config
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_config() -> dict:
    return _config
