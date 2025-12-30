# discord_alerts.py

import requests
from config import DISCORD_WEBHOOK

def send_discord(message):
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK, json=payload)
