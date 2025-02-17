import json
import os
import logging

SETTINGS_FILE ="settings.json"

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        logging.error("Failed to save settings: %s", e)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error("Failed to load settings: %s", e)
    return {}

