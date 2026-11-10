import os
import sys
import json
import time

BASE = os.path.dirname(os.path.abspath(__file__))
OPTIONS_FILE = os.path.join(BASE, "snooze_options.json")
SNOOZES_FILE = os.path.join(BASE, "snoozes.json")

try:
    token = sys.argv[1]
    minutes = int(sys.argv[2])

    if minutes not in [5, 10, 15]:
        raise ValueError("Invalid snooze time")

    with open(OPTIONS_FILE, "r") as f:
        options = json.load(f)

    message = options.pop(token)

    snoozes = []
    if os.path.exists(SNOOZES_FILE):
        with open(SNOOZES_FILE, "r") as f:
            snoozes = json.load(f)

    snoozes.append({
        "text": message,
        "due": time.time() + minutes * 60
    })

    with open(SNOOZES_FILE, "w") as f:
        json.dump(snoozes, f, ensure_ascii=False, indent=4)

    with open(OPTIONS_FILE, "w") as f:
        json.dump(options, f, ensure_ascii=False, indent=4)

    os.system("termux-toast 'JARVIS: Snooze set!'")

except Exception as e:
    os.system("termux-toast 'JARVIS Snooze Error'")
    print("Snooze Error:", e)
