import os
import json
import httpx
import subprocess
import datetime
import urllib.parse
import re
import threading
import time
import ast
import math


def search_files(filename, search_path=None):
    if search_path is None:
        search_path = os.path.expanduser("~")

    results = []
    try:
        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                if filename.lower() in name.lower():
                    results.append(os.path.join(root, name))
                    if len(results) >= 30:
                        return results
    except Exception:
        pass

    return results


def smart_calculate(expression):
    digit_map = str.maketrans("०१२३४५६७८९", "0123456789")
    expression = expression.translate(digit_map)
    expression = expression.replace("^", "**")
    expression = expression.replace("×", "*").replace("÷", "/")
    expression = expression.replace(",", "")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp):
            a = evaluate(node.left)
            b = evaluate(node.right)
            operations = {
                ast.Add: lambda: a + b,
                ast.Sub: lambda: a - b,
                ast.Mult: lambda: a * b,
                ast.Div: lambda: a / b,
                ast.FloorDiv: lambda: a // b,
                ast.Mod: lambda: a % b,
                ast.Pow: lambda: a ** b
            }
            operation = operations.get(type(node.op))
            if operation is None:
                raise ValueError("अवैध गणित")
            return operation()
        if isinstance(node, ast.UnaryOp):
            value = evaluate(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
        raise ValueError("हे गणित समजले नाही")

    tree = ast.parse(expression, mode="eval")
    result = evaluate(tree)

    if not isinstance(result, (int, float)) or not math.isfinite(result):
        raise ValueError("उत्तर काढता आले नाही")

    return result

key = os.getenv("OPENROUTER_API_KEY")

if not key:
    print("API Key set nahi. Pahile key set kara.")
    raise SystemExit

url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

messages = [
    {
        "role": "system",
        "content": "तुझे नाव SHIVAM (शिवम) आहे. तू माझा वैयक्तिक AI सहाय्यक आहेस. स्वतःला JARVIS, Flint किंवा Recursive म्हणू नकोस. नेहमी सोप्या, शुद्ध, नैसर्गिक आणि व्याकरणदृष्ट्या योग्य मराठीत उत्तर दे. प्रत्येक उत्तर पाठवण्यापूर्वी वाक्यरचना, शब्दांची निवड, लिंग, वचन आणि काळ तपास. चुकीचे, अर्धवट किंवा अर्थहीन शब्दप्रयोग करू नकोस. हिंदी-मराठीची अनावश्यक सरमिसळ टाळ. स्वतःविषयी बोलताना योग्य क्रियापदे वापर. तांत्रिक संज्ञा आवश्यक असेल तेव्हाच इंग्रजी वापर. उत्तर स्पष्ट, पूर्ण आणि संभाषणाला साजेसे ठेव."
    }
]


MEMORY_FILE = "memory.json"

def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# PERSISTENT CHAT HISTORY
CHAT_HISTORY_FILE = "chat_history.json"

def load_chat_history():
    try:
        with open(CHAT_HISTORY_FILE, "r") as f:
            history = json.load(f)
        return [m for m in history if m.get("role") in ["user", "assistant"]][-20:]
    except Exception:
        return []

def save_chat_history(history):
    with open(CHAT_HISTORY_FILE, "w") as f:
        json.dump(history[-20:], f, ensure_ascii=False, indent=4)


def load_reminders():
    try:
        with open("reminders.json", "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_reminders(data):
    with open("reminders.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def send_snooze_notification(message, options_file):
    token = str(time.time_ns())

    try:
        with open(options_file, "r") as f:
            options = json.load(f)
    except Exception:
        options = {}

    options[token] = message
    with open(options_file, "w") as f:
        json.dump(options, f, ensure_ascii=False, indent=4)

    base = os.path.dirname(os.path.abspath(__file__))
    python_path = "/data/data/com.termux/files/usr/bin/python"
    script_path = os.path.join(base, "snooze.py")
    action = f'PATH=/data/data/com.termux/files/usr/bin:$PATH; export PATH; "{python_path}" "{script_path}"'

    subprocess.run([
        "termux-notification",
        "--title", "JARVIS Reminder",
        "--content", message,
        "--button1", "5 मिनिटे",
        "--button1-action", f"{action} {token} 5",
        "--button2", "10 मिनिटे",
        "--button2-action", f"{action} {token} 10",
        "--button3", "15 मिनिटे",
        "--button3-action", f"{action} {token} 15"
    ])


def reminder_worker():
    base = os.path.dirname(os.path.abspath(__file__))
    options_file = os.path.join(base, "snooze_options.json")
    snoozes_file = os.path.join(base, "snoozes.json")

    while True:
        try:
            reminders = load_reminders()
            now = datetime.datetime.now().timestamp()
            pending = []
            reminders_changed = False

            for item in reminders:
                if item.get("due", 0) <= now:
                    message = item.get("text", "तुमचा रिमाइंडर")
                    send_snooze_notification(message, options_file)

                    subprocess.run([
                        "termux-tts-speak", "-l", "mr-IN",
                        "आठवण: " + message
                    ])

                    reminders_changed = True
                    repeat = item.get("repeat")

                    if repeat in ["daily", "weekly"]:
                        due = datetime.datetime.fromtimestamp(item["due"])
                        current = datetime.datetime.now()
                        days = 1 if repeat == "daily" else 7

                        while due.timestamp() <= current.timestamp():
                            due += datetime.timedelta(days=days)

                        item["due"] = due.timestamp()
                        pending.append(item)
                else:
                    pending.append(item)

            if reminders_changed:
                save_reminders(pending)

            try:
                with open(snoozes_file, "r") as f:
                    snoozes = json.load(f)
            except Exception:
                snoozes = []

            snooze_pending = []

            for item in snoozes:
                if item.get("due", 0) <= now:
                    message = item.get("text", "तुमचा रिमाइंडर")
                    send_snooze_notification(message, options_file)

                    subprocess.run([
                        "termux-tts-speak", "-l", "mr-IN",
                        "पुन्हा आठवण: " + message
                    ])
                else:
                    snooze_pending.append(item)

            if len(snooze_pending) != len(snoozes):
                with open(snoozes_file, "w") as f:
                    json.dump(snooze_pending, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print("Reminder Error:", e)

        time.sleep(5)


threading.Thread(target=reminder_worker, daemon=True).start()

messages.extend(load_chat_history())

while True:
    choice = input("\nबोलण्यासाठी Enter दाबा किंवा प्रश्न टाइप करा: ").strip()

    if choice.lower() in ["exit", "quit"]:
        print("JARVIS बंद होत आहे.")
        break

    try:
        if choice:
            question = choice
        else:
            question = ""
            for attempt in range(3):
                print("JARVIS ऐकत आहे... प्रयत्न", attempt + 1, "/ 3")
                try:
                    question = subprocess.check_output(
                        ["termux-speech-to-text"],
                        text=True,
                        timeout=15
                    ).strip()
                except Exception:
                    question = ""

                if question:
                    break

                print("आवाज समजला नाही. पुन्हा बोला.")
                subprocess.run(["termux-tts-speak", "कृपया पुन्हा बोला"])

        if not question:
            print("JARVIS: तीन प्रयत्न झाले. पुन्हा Enter दाबा.")
            continue

        print("तुम्ही:", question)
        q = question.lower().strip()
        q = q.replace("-", " ")
        q = " ".join(q.split())

        # VOICE COMMAND NORMALIZATION
        voice_aliases = {
            "what is the time": "time",
            "tell me the time": "time",
            "current time": "time",
            "what is today's date": "date",
            "tell me the date": "date",
            "open up chrome": "open chrome",
            "start chrome": "open chrome",
            "open up youtube": "open youtube",
            "start youtube": "open youtube",
            "open up whatsapp": "open whatsapp",
            "start whatsapp": "open whatsapp",
            "internet chalu kar": "open chrome",
            "internet ughad": "open chrome",
            "ब्राउजर सुरू कर": "open chrome",
            "इंटरनेट चालू कर": "open chrome",
            "video baghaycha aahe": "open youtube",
            "video dakhav": "open youtube",
            "व्हिडिओ बघायचा आहे": "open youtube",
            "email baghaycha aahe": "open gmail",
            "email ughad": "open gmail",
            "ईमेल बघायचा आहे": "open gmail",
            "क्रोम सुरू करा": "open chrome",
            "क्रोम चालू करा": "open chrome",
            "ब्राउझर सुरू करा": "open chrome",
            "chrome suru kara": "open chrome",
            "chrome chalu kara": "open chrome",
            "browser ughad": "open chrome",
            "यूट्यूब सुरू करा": "open youtube",
            "यूट्यूब चालू करा": "open youtube",
            "व्हिडिओ दाखवा": "open youtube",
            "youtube suru kar": "open youtube",
            "youtube chalu kara": "open youtube",
            "video baghaycha ahe": "open youtube",
            "व्हॉट्सॲप सुरू करा": "open whatsapp",
            "व्हॉट्सॲप चालू करा": "open whatsapp",
            "whatsapp suru kar": "open whatsapp",
            "whatsapp chalu kara": "open whatsapp",
            "जीमेल सुरू करा": "open gmail",
            "जीमेल चालू करा": "open gmail",
            "gmail suru kar": "open gmail",
            "gmail chalu kara": "open gmail"
        }

        q = voice_aliases.get(q, q)

        # ROMAN MARATHI CALCULATOR WORDS
        roman_math_words = {
            "vargarmul": "वर्गमूळ",
            "vargamul": "वर्गमूळ",
            "vargmul": "वर्गमूळ",
            "vargmool": "वर्गमूळ",
            "sqrt": "वर्गमूळ",
            "ghat": "घात",
            "power": "घात",
            "varg": "वर्ग",
            "jama": "बेरीज",
            "jamaa": "बेरीज",
            "vaja": "वजाबाकी",
            "gunakar": "गुणाकार",
            "gunile": "गुणिले",
            "bhagakar": "भागाकार",
            "bhagile": "भागिले",
            "takke": "टक्के",
            "takkewari": "टक्केवारी"
        }
        for roman, marathi in roman_math_words.items():
            q = q.replace(roman, marathi)

        # SMART CALCULATOR COMMAND
        calc_words = ["calculate", "calculator", "कॅल्क्युलेट", "किती होतात", "किती होईल", "बेरीज", "वजाबाकी", "गुणाकार", "भागाकार", "टक्के", "टक्केवारी", "वर्गमूळ", "square root", "percentage", "वर्ग", "घात"]

        if any(word in q for word in calc_words):
            expression = q
            digit_map = str.maketrans("०१२३४५६७८९", "0123456789")
            expression = expression.translate(digit_map)

            try:
                import re
                result = None

                # SQUARE ROOT
                if "वर्गमूळ" in expression or "square root" in expression:
                    numbers = re.findall(r"\d+(?:\.\d+)?", expression)
                    if numbers:
                        result = math.sqrt(float(numbers[-1]))

                # PERCENTAGE
                elif "%" in expression or "टक्के" in expression or "टक्केवारी" in expression or "percentage" in expression:
                    numbers = re.findall(r"\d+(?:\.\d+)?", expression)
                    if len(numbers) >= 2:
                        result = float(numbers[0]) / 100 * float(numbers[1])
                    else:
                        raise ValueError("टक्केवारी समजली नाही")

                # SQUARE
                elif "वर्ग" in expression or "square" in expression:
                    numbers = re.findall(r"\d+(?:\.\d+)?", expression)
                    if numbers:
                        result = float(numbers[0]) ** 2

                # POWER
                elif "घात" in expression or "power" in expression:
                    numbers = re.findall(r"\d+(?:\.\d+)?", expression)
                    if len(numbers) >= 2:
                        result = float(numbers[0]) ** float(numbers[1])
                    else:
                        raise ValueError("घात समजला नाही")

                else:
                    replacements = {
                        "कॅल्क्युलेटर": "", "कॅल्क्युलेट": "",
                        "calculate": "", "calculator": "",
                        "किती होतात": "", "किती होईल": "",
                        "बेरीज": "+", "जमा": "+",
                        "वजाबाकी": "-", "वजा": "-",
                        "गुणाकार": "*", "गुणिले": "*",
                        "भागाकार": "/", "भागिले": "/",
                        "of": "*", "चे": "*", "चा": "*"
                    }
                    for word, symbol in replacements.items():
                        expression = expression.replace(word, symbol)

                    result = smart_calculate(expression.strip())

                if not math.isfinite(result):
                    raise ValueError("अवैध उत्तर")

                answer = "उत्तर आहे " + str(result)

            except Exception:
                answer = "माफ करा, हे गणित समजले नाही. पुन्हा विचारा."

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if any(x in q for x in ["time", "वेळ", "किती वाजले"]):
            now = datetime.datetime.now()
            answer = "आत्ता वेळ आहे " + now.strftime("%I वाजून %M मिनिटे.")
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if q.strip() in ["date", "तारीख", "आज कोणता दिवस", "आजची तारीख", "today date"]:
            today = datetime.datetime.now()
            answer = "आजची तारीख " + today.strftime("%d-%m-%Y") + " आहे."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue




        # FILE SEARCH ASSISTANT
        if q.startswith(("search file ", "find file ", "फाइल शोध ")):
            filename = q
            for prefix in ["search file ", "find file ", "फाइल शोध "]:
                if filename.startswith(prefix):
                    filename = filename[len(prefix):].strip()
                    break
            print("DEBUG filename:", repr(filename))
            print("DEBUG search path:", os.path.dirname(os.path.abspath(__file__)))
            results = search_files(filename, os.path.dirname(os.path.abspath(__file__)))
            print("DEBUG results:", results)

            if results:
                answer = "फाइल सापडल्या: " + str(len(results)) + "\n" + "\n".join(results)
            else:
                answer = "माफ करा, फाइल सापडली नाही."

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", "फाइल शोध पूर्ण झाला."])
            continue

        # SMART NOTES - SAVE NOTE
        if any(x in q for x in ["नोट सेव्ह कर", "नोट सेव करा", "save note", "add note", "नोट लिहून ठेव"]):
            note_text = question
            for phrase in ["नोट सेव्ह कर", "नोट सेव करा", "save note", "add note", "नोट लिहून ठेव"]:
                note_text = re.sub(re.escape(phrase), "", note_text, flags=re.IGNORECASE).strip()

            if note_text:
                try:
                    with open("notes.json", "r") as f:
                        notes = json.load(f)
                except Exception:
                    notes = []

                if not isinstance(notes, list):
                    notes = []

                notes.append({
                    "text": note_text,
                    "date": datetime.datetime.now().strftime("%d-%m-%Y %I:%M %p")
                })

                with open("notes.json", "w") as f:
                    json.dump(notes, f, ensure_ascii=False, indent=4)

                answer = "तुमची नोट सेव्ह केली आहे."
            else:
                answer = "कृपया नोटचा मजकूर सांगा."

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # TOMORROW RAIN PROBABILITY
        if any(x in q for x in ["पाऊस पडेल का", "पाऊस येईल का", "पाऊस होईल का"]) and "उद्या" in q:
            try:
                rain_url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": 20.8648,
                    "longitude": 77.73521,
                    "daily": "precipitation_probability_max",
                    "timezone": "Asia/Kolkata",
                    "forecast_days": 2
                }
                data = httpx.get(rain_url, params=params, timeout=20)
                data.raise_for_status()
                daily = data.json()["daily"]
                rain = daily["precipitation_probability_max"][1]
                answer = "उद्या बदनेरा येथे पावसाची शक्यता " + str(rain) + " टक्के आहे."
                print("JARVIS:", answer)
                subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            except Exception as e:
                print("पावसाची शक्यता मिळवताना त्रुटी:", e)
            continue

        # TODAY RAIN PROBABILITY
        if any(x in q for x in ["पाऊस पडेल का", "पाऊस येईल का", "पाऊस होईल का"]) and not any(x in q for x in ["उद्या", "उद्याचा", "उद्याचे"]):
            try:
                rain_url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": 20.8648,
                    "longitude": 77.73521,
                    "daily": "precipitation_probability_max",
                    "timezone": "Asia/Kolkata",
                    "forecast_days": 1
                }
                data = httpx.get(rain_url, params=params, timeout=20)
                data.raise_for_status()
                daily = data.json()["daily"]
                rain = daily["precipitation_probability_max"][0]
                answer = "आज बदनेरा येथे पावसाची शक्यता " + str(rain) + " टक्के आहे."
                print("JARVIS:", answer)
                subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            except Exception as e:
                print("आजच्या पावसाची शक्यता मिळवताना त्रुटी:", e)
            continue

        # BADNERA 7 DAY FORECAST
        tomorrow_only = any(x in q for x in ["उद्याचा", "उद्याचे", "उद्या"]) and not any(x in q for x in ["7 days", "सात दिवस", "आठवड्याचा"])
        if any(x in q for x in ["forecast", "उद्याचा", "उद्याचे", "उद्या", "7 days", "सात दिवस", "हवामान अंदाज", "आठवड्याचा", "थंडी", "गारवा", "किमान तापमान"]) and not q.startswith(("काम जोडा ", "add task ")):
            try:
                forecast_url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": 20.8648,
                    "longitude": 77.73521,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "Asia/Kolkata",
                    "forecast_days": 7
                }

                data = httpx.get(forecast_url, params=params, timeout=20)
                data.raise_for_status()
                daily = data.json()["daily"]

                days = ["सोमवार", "मंगळवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]

                cold_only = any(x in q for x in ["थंडी", "गारवा", "किमान तापमान"])
                today_only = cold_only and "आज" in q
                if cold_only:
                    answer = "आज बदनेरा येथे " if today_only else "उद्या बदनेरा येथे "
                    forecast_days = [0] if today_only else [1]
                else:
                    answer = "बदनेरा येथील उद्याचा हवामान अंदाज. " if tomorrow_only else "बदनेरा येथील पुढील सात दिवसांचा हवामान अंदाज. "
                    forecast_days = [1] if tomorrow_only else range(len(daily["time"]))
                for i in forecast_days:
                    day = daily["time"][i]
                    date = datetime.date.fromisoformat(day)
                    day_name = days[date.weekday()]
                    maximum = daily["temperature_2m_max"][i]
                    minimum = daily["temperature_2m_min"][i]
                    rain = daily["precipitation_probability_max"][i]

                    if cold_only:
                        answer += "किमान तापमान " + str(minimum) + " अंश आणि कमाल तापमान " + str(maximum) + " अंश राहील."
                    else:
                        answer += (
                            day_name + " " + date.strftime("%d-%m") + ". "
                            + "किमान तापमान " + str(minimum) + " अंश. "
                            + "कमाल तापमान " + str(maximum) + " अंश. "
                            + "पावसाची शक्यता " + str(rain) + " टक्के. "
                        )

                print("JARVIS:", answer)
                subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])

            except Exception as e:
                print("हवामान अंदाज मिळवताना त्रुटी:", e)
            continue

        # BADNERA WEATHER FEATURE
        if any(x in q for x in ["weather", " हवामान", "हवामान", "temperature", "तापमान", "पाऊस", "rain"]):
            try:
                weather_url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": 20.8648,
                    "longitude": 77.73521,
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
                    "daily": "precipitation_probability_max",
                    "timezone": "Asia/Kolkata",
                    "forecast_days": 1
                }

                data = httpx.get(weather_url, params=params, timeout=20).json()
                current = data["current"]
                rain = data["daily"]["precipitation_probability_max"][0]

                conditions = {
                    0: "आकाश निरभ्र आहे",
                    1: "मुख्यतः निरभ्र आहे",
                    2: "अंशतः ढगाळ आहे",
                    3: "ढगाळ आहे",
                    45: "धुके आहे",
                    48: "धुके आहे",
                    51: "हलका रिमझिम पाऊस आहे",
                    61: "हलका पाऊस आहे",
                    63: "मध्यम पाऊस आहे",
                    65: "जोरदार पाऊस आहे",
                    80: "पावसाच्या सरी येऊ शकतात",
                    81: "पावसाच्या सरी येऊ शकतात",
                    82: "जोरदार पावसाच्या सरी येऊ शकतात",
                    95: "मेघगर्जनेसह पाऊस होऊ शकतो"
                }

                condition = conditions.get(current["weather_code"], "हवामान बदलते आहे")
                answer = (
                    "बदनेरा येथील सध्याचे हवामान. "
                    + condition + ". "
                    + "तापमान " + str(current["temperature_2m"]) + " अंश सेल्सिअस. "
                    + "जाणवणारे तापमान " + str(current["apparent_temperature"]) + " अंश. "
                    + "आर्द्रता " + str(current["relative_humidity_2m"]) + " टक्के. "
                    + "वाऱ्याचा वेग " + str(current["wind_speed_10m"]) + " किलोमीटर प्रति तास. "
                    + "आज पावसाची शक्यता " + str(rain) + " टक्के."
                )

                print("JARVIS:", answer)
                subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            except Exception as e:
                print("हवामान मिळवताना त्रुटी:", e)
            continue


        # WHATSAPP MESSAGE FEATURE
        if any(x in q for x in ["send whatsapp", "whatsapp message", "whatsapp msg", "send message", "मेसेज पाठव", "मेसेज पाठवा", "व्हॉट्सॲप मेसेज", "व्हाट्सएप मेसेज"]):
            print("JARVIS: Contact चे नाव सांगा.")
            subprocess.run(["termux-tts-speak", "Contact चे नाव सांगा"])
            contact_name = subprocess.check_output(["termux-speech-to-text"], text=True).strip()

            if not contact_name:
                contact_name = input("Contact चे नाव टाइप करा: ").strip()

            contacts = json.loads(subprocess.check_output(["termux-contact-list"], text=True))
            matches = [c for c in contacts if contact_name.lower() in c.get("name", "").lower()]

            if len(matches) == 1:
                phone = "".join(c for c in matches[0].get("number", "") if c.isdigit())
                print("JARVIS: Contact सापडला. " + matches[0].get("name", ""))
            elif len(matches) > 1:
                print("एकापेक्षा जास्त Contacts सापडले:")
                for i, c in enumerate(matches, 1):
                    print(str(i) + ". " + c.get("name", ""))
                choice = input("योग्य Contact क्रमांक निवडा: ").strip()
                if not choice.isdigit() or int(choice) < 1 or int(choice) > len(matches):
                    print("चुकीची निवड.")
                    continue
                phone = "".join(c for c in matches[int(choice)-1].get("number", "") if c.isdigit())
            else:
                print("Contact सापडला नाही. नंबर टाइप करा.")
                phone = input("मोबाईल नंबर: ").strip()
                phone = "".join(c for c in phone if c.isdigit())

            if len(phone) == 10:
                phone = "91" + phone

            if len(phone) < 11 or len(phone) > 15:
                print("चुकीचा नंबर. पुन्हा प्रयत्न करा.")
                continue

            print("JARVIS: आता तुमचा मेसेज बोला.")
            subprocess.run(["termux-tts-speak", "आता तुमचा मेसेज बोला"])
            message = subprocess.check_output(["termux-speech-to-text"], text=True).strip()

            if not message:
                print("आवाजातून मेसेज समजला नाही. कृपया मेसेज टाइप करा.")
                message = input("तुमचा मेसेज: ").strip()

            if not message:
                print("मेसेज रिकामा आहे.")
                continue

            print("JARVIS: हा मेसेज पाठवू का? हो किंवा नाही सांगा.")
            subprocess.run(["termux-tts-speak", "हा मेसेज पाठवू का? हो किंवा नाही सांगा."])
            try:
                confirmation = subprocess.check_output(["termux-speech-to-text"], text=True).strip().lower()
            except Exception:
                confirmation = ""

            if not confirmation:
                confirmation = input("हो / नाही: ").strip().lower()

            if confirmation not in ["हो", "होय", "हां", "हा", "yes", "y", "ho", "haan", "ha", "हो पाठव", "पाठव"]:
                print("JARVIS: मेसेज रद्द केला.")
                subprocess.run(["termux-tts-speak", "मेसेज रद्द केला"])
                continue

            encoded_message = urllib.parse.quote(message)
            whatsapp_url = "https://wa.me/" + phone + "?text=" + encoded_message

            print("WhatsApp मध्ये मेसेज उघडत आहे. तपासून Send दाबा.")
            subprocess.run(["am", "start", "-a", "android.intent.action.VIEW", "-d", whatsapp_url])
            continue

        # SMS MESSAGE FEATURE
        if q == "sms" or any(x in q for x in ["send sms", "sms message", "sms पाठव", "एसएमएस पाठव"]):
            print("JARVIS: कोणाला SMS पाठवायचा आहे?")
            subprocess.run(["termux-tts-speak", "कोणाला SMS पाठवायचा आहे?"])

            try:
                name = subprocess.check_output(["termux-speech-to-text"], text=True).strip()
            except Exception:
                name = ""

            if not name:
                name = input("Contact चे नाव: ").strip()

            contacts = json.loads(subprocess.check_output(["termux-contact-list"], text=True))
            matches = [c for c in contacts if name.lower() in c.get("name", "").lower()]

            if len(matches) == 0:
                print("Contact सापडला नाही.")
                continue
            elif len(matches) > 1:
                for i, c in enumerate(matches, 1):
                    print(str(i) + ". " + c.get("name", ""))
                choice = input("Contact क्रमांक निवडा: ").strip()
                if not choice.isdigit() or not 1 <= int(choice) <= len(matches):
                    print("चुकीची निवड.")
                    continue
                contact = matches[int(choice)-1]
            else:
                contact = matches[0]

            phone = "".join(c for c in contact.get("number", "") if c.isdigit())
            if len(phone) == 10:
                phone = "91" + phone

            if len(phone) < 11 or len(phone) > 15:
                print("चुकीचा फोन नंबर.")
                continue

            print("JARVIS: SMS काय पाठवायचा आहे?")
            subprocess.run(["termux-tts-speak", "SMS काय पाठवायचा आहे?"])

            try:
                message = subprocess.check_output(["termux-speech-to-text"], text=True).strip()
            except Exception:
                message = ""

            if not message:
                message = input("तुमचा SMS: ").strip()

            if not message:
                print("SMS रिकामा आहे.")
                continue

            question = contact.get("name", "या Contact") + " यांना SMS पाठवू का? हो किंवा नाही सांगा."
            print("JARVIS:", question)
            subprocess.run(["termux-tts-speak", question])

            try:
                confirmation = subprocess.check_output(["termux-speech-to-text"], text=True).strip().lower()
            except Exception:
                confirmation = ""

            if not confirmation:
                confirmation = input("हो / नाही: ").strip().lower()

            if confirmation not in ["हो", "होय", "yes", "y", "ho", "haan", "ha"]:
                print("JARVIS: SMS रद्द केला.")
                subprocess.run(["termux-tts-speak", "SMS रद्द केला"])
                continue

            print("JARVIS: SMS पाठवत आहे.")
            result = subprocess.run(["termux-sms-send", "-n", phone, message])

            if result.returncode == 0:
                print("JARVIS: SMS command पूर्ण झाली.")
            else:
                print("SMS पाठवता आला नाही. Termux:API SMS permission तपासा.")
            continue

        # CONTACT VOICE CALL FEATURE
        if q == "call" or any(x in q for x in ["call ", "make a call", "phone call", "कॉल", "फोन लावा", "फोन करा"]):
            print("JARVIS: कोणाला कॉल करायचा आहे?")
            subprocess.run(["termux-tts-speak", "कोणाला कॉल करायचा आहे?"])
            name = subprocess.check_output(["termux-speech-to-text"], text=True).strip()

            if not name:
                name = input("Contact चे नाव: ").strip()

            contacts = json.loads(subprocess.check_output(["termux-contact-list"], text=True))
            matches = [c for c in contacts if name.lower() in c.get("name", "").lower()]

            if len(matches) == 0:
                print("Contact सापडला नाही.")
                continue
            elif len(matches) > 1:
                for i, c in enumerate(matches, 1):
                    print(str(i) + ". " + c.get("name", ""))
                choice = input("Contact क्रमांक निवडा: ").strip()
                if not choice.isdigit() or not 1 <= int(choice) <= len(matches):
                    print("चुकीची निवड.")
                    continue
                contact = matches[int(choice)-1]
            else:
                contact = matches[0]

            phone = "".join(c for c in contact.get("number", "") if c.isdigit())
            if len(phone) == 10:
                phone = "91" + phone
            if len(phone) < 11 or len(phone) > 15:
                print("चुकीचा फोन नंबर.")
                continue

            contact_label = contact.get("name", "या Contact")
            question = contact_label + " यांना कॉल करू का? हो किंवा नाही सांगा."
            print("JARVIS:", question)
            subprocess.run(["termux-tts-speak", question])

            try:
                confirmation = subprocess.check_output(
                    ["termux-speech-to-text"], text=True
                ).strip().lower()
            except Exception:
                confirmation = ""

            if not confirmation:
                confirmation = input("हो / नाही: ").strip().lower()

            if confirmation not in ["हो", "होय", "yes", "y", "ho", "haan", "ha"]:
                print("JARVIS: कॉल रद्द केला.")
                subprocess.run(["termux-tts-speak", "कॉल रद्द केला"])
                continue

            print("JARVIS: कॉल लावत आहे.")
            subprocess.run(["termux-tts-speak", "कॉल लावत आहे"])
            result = subprocess.run(["termux-telephony-call", phone])
            if result.returncode != 0:
                print("कॉल करता आला नाही. Termux:API permission तपासा.")
            continue

        apps = {
            "chrome": ("com.android.chrome/com.google.android.apps.chrome.Main", ["open chrome", "chrome open", "chrome उघड", "क्रोम उघड", "chrome chalu kar", "chrome open kar", "क्रोम चालू कर", "क्रोम सुरू कर", "क्रोम खोलो", "क्रोम चालू करो", "क्रोम सुरू करा", "ब्राउजर उघड", "इंटरनेट उघड", "इंटरनेट दाखव", "chrome दाखव", "क्रोम दाखव", "मला chrome दाखव", "मला इंटरनेट दाखव", "ब्राउजर दाखव", "ब्राउझर उघड", "chrome dakhav", "क्रोम दिखाओ", "इंटरनेट सुरू कर"]),
            "youtube": ("com.google.android.youtube/.HomeActivity", ["open youtube", "youtube open", "youtube उघड", "यूट्यूब उघड", "youtube chalu kar", "youtube open kar", "यूट्यूब चालू कर", "यूट्यूब सुरू कर", "यूट्यूब खोलो", "यूट्यूब चालू करो", "यूट्यूब सुरू करा", "व्हिडिओ उघड", "youtube दाखव", "यूट्यूब दाखव", "युट्युब दाखव", "मला youtube दाखव", "मला यूट्यूब दाखव", "youtube dakhav", "यूट्यूब दिखाओ", "youtube पाहिजे", "youtube dikhao", "youtube dekho", "youtube", "युट्युब", "यूट्यूब"]),
            "gmail": ("com.google.android.gm/.ConversationListActivityGmail", ["open gmail", "gmail open", "gmail उघड", "जीमेल उघड", "gmail chalu kar", "gmail open kar", "जीमेल चालू कर", "जीमेल खोलो", "जीमेल चालू करो", "जीमेल सुरू करा", "ईमेल उघड", "gmail दाखव", "जीमेल दाखव", "मला gmail दाखव", "मला ईमेल दाखव", "gmail dakhav", "जीमेल दिखाओ", "ईमेल दाखव"]),
            "whatsapp": ("com.whatsapp/.Main", ["open whatsapp", "whatsapp open", "whatsapp उघड", "व्हॉट्सॲप उघड", "whatsapp chalu kar", "whatsapp open kar", "व्हॉट्सॲप चालू कर", "व्हाट्सएप खोलो", "व्हाट्सएप चालू करो", "व्हॉट्सॲप सुरू करा", "मेसेज ॲप उघड", "whatsapp दाखव", "व्हॉट्सॲप दाखव", "मला whatsapp दाखव", "मला व्हॉट्सॲप दाखव", "whatsapp dakhav", "व्हाट्सएप दिखाओ", "मेसेज ॲप दाखव"]),
            "camera": ("com.android.camera/.Camera", ["open camera", "camera open", "camera उघड", "कॅमेरा उघड", "camera chalu kar", "camera open kar", "कॅमेरा चालू कर", "कैमरा खोलो", "कैमरा चालू करो", "कॅमेरा सुरू करा", "फोटो काढ", "camera दाखव", "कॅमेरा दाखव", "मला कॅमेरा दाखव", "camera dakhav", "कैमरा दिखाओ", "फोटो काढण्यासाठी कॅमेरा उघड"]),
            "settings": ("com.android.settings/.Settings", ["open settings", "open setting", "settings open", "setting open", "settings उघड", "सेटिंग उघड", "सेटिंग्स खोलो", "सेटिंग खोल", "मोबाईल सेटिंग उघड", "फोन सेटिंग उघड", "सेटिंग चालू करो", "सेटिंग सुरू करा", "मोबाईल सेटिंग उघडा", "settings open kar", "settings chalu kar", "सेटिंग्स चालू कर", "settings दाखव", "सेटिंग दाखव", "मला settings दाखव", "फोनची सेटिंग उघड", "मोबाईलची सेटिंग उघड", "settings dakhav", "सेटिंग दिखाओ"]),
            "phone": ("com.google.android.dialer/.extensions.GoogleDialtactsActivity", ["open phone", "phone open", "phone उघड", "फोन उघड", "phone open kar", "phone chalu kar", "फोन चालू कर", "फोन खोलो", "फोन चालू करो", "फोन सुरू करा", "डायलर उघड", "phone दाखव", "फोन दाखव", "मला फोन दाखव", "dialer दाखव", "डायलर दाखव", "phone dakhav", "फोन दिखाओ"])
        }

        if any(x in q for x in ["torch on", "flashlight on", "टॉर्च चालू", "टॉर्च सुरू", "टॉर्च लावा"]):
            subprocess.run(["termux-torch", "on"])
            answer = "मोबाइलचा टॉर्च सुरू केला."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if any(x in q for x in ["torch off", "flashlight off", "टॉर्च बंद", "टॉर्च बंद करा"]):
            subprocess.run(["termux-torch", "off"])
            answer = "मोबाइलचा टॉर्च बंद केला."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if any(x in q for x in ["wifi", "wi fi", "वायफाय", "वाईफाय", "वाय फाय", "वाई फाय"]):
            if any(x in q for x in ["on", "chalu", " चालू", "चालू", "सुरू", "लावा"]):
                subprocess.run(["termux-wifi-enable", "true"])
                answer = "Wi-Fi सुरू करण्याची कमांड दिली."
                print("JARVIS:", answer)
                subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
                continue

            if any(x in q for x in ["off", "बंद"]):
                subprocess.run(["termux-wifi-enable", "false"])
                answer = "Wi-Fi बंद करण्याची कमांड दिली."
                print("JARVIS:", answer)
                subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
                continue

        if any(x in q for x in ["bluetooth", "ब्लूटूथ"]):
            subprocess.run(["am", "start", "-a", "android.settings.BLUETOOTH_SETTINGS"])
            answer = "Bluetooth Settings उघडत आहे."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if any(x in q for x in ["awaaz", "आवाज", "volume up", "increase volume", "awaaz badhao", "awaz badhao", "awaaz badha", "आवाज वाढवा", "व्हॉल्यूम वाढवा"]):
            data = json.loads(subprocess.check_output(["termux-volume"], text=True))
            music = next(x for x in data if x["stream"] == "music")
            level = min(music["volume"] + 1, music["max_volume"])
            subprocess.run(["termux-volume", "music", str(level)])
            answer = "आवाज वाढवला."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if any(x in q for x in ["down", "kami", "कमी", "volume down", "decrease volume", "awaaz kam", "awaz kam", "awaaz ghat", "आवाज कमी करा", "व्हॉल्यूम कमी करा"]):
            data = json.loads(subprocess.check_output(["termux-volume"], text=True))
            music = next(x for x in data if x["stream"] == "music")
            level = max(music["volume"] - 1, 0)
            subprocess.run(["termux-volume", "music", str(level)])
            answer = "आवाज कमी केला."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        matched = False
        # SMART APP INTENT MATCHING
        clean_q = q
        for word in ["jarvis", "please", "kindly", "मला", "जरा"]:
            clean_q = clean_q.replace(word, " ")
        clean_q = " ".join(clean_q.split())

        # SMART CLOSE APP COMMANDS
        close_apps = {
            "chrome": ("com.android.chrome", ["chrome", "क्रोम", "browser", "ब्राउजर", "ब्राउझर"]),
            "youtube": ("com.google.android.youtube", ["youtube", "यूट्यूब", "युट्युब"]),
            "gmail": ("com.google.android.gm", ["gmail", "जीमेल", "ईमेल"]),
            "whatsapp": ("com.whatsapp", ["whatsapp", "व्हॉट्सॲप", "व्हाट्सएप"])
        }
        close_words = ["बंद कर", "बंद करा", "बंद कर दो", "बंद", "close", "बंद करायचे", "band", "band kar", "band kara", "close kar"]
        if any(x in clean_q for x in close_words):
            for app, (package, names) in close_apps.items():
                if any(x in clean_q for x in names):
                    result = subprocess.run(["/system/bin/input", "keyevent", "4"], capture_output=True, text=True)
                    if result.returncode == 0:
                        answer = app.capitalize() + " मागील स्क्रीनवर जात आहे."
                    else:
                        answer = "Back action करता आले नाही. Android permission तपासा."
                    print("JARVIS:", answer)
                    subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
                    matched = True
                    break

        if matched:
            continue

        for app, (activity, phrases) in apps.items():
            if any(x in clean_q for x in phrases):
                if app == "phone":
                    subprocess.run(["am", "start", "-a", "android.intent.action.DIAL", "-d", "tel:"])
                else:
                    subprocess.run(["am", "start", "-n", activity])
                answer = app.capitalize() + " उघडत आहे."
                print("JARVIS:", answer)
                subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
                matched = True
                break

        if matched:
            continue

        if False:
            subprocess.run([
                "am", "start", "-n",
                "com.android.chrome/com.google.android.apps.chrome.Main"
            ])
            answer = "Chrome उघडत आहे."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # MEMORY UPDATE COMMAND
        if q.startswith("update memory "):
            parts = question.strip()[len("update memory "):].split(" to ", 1)
            if len(parts) == 2:
                old, new = parts[0].strip(), parts[1].strip()
                memory = load_memory()
                found = False
                for k, v in memory.items():
                    if old.lower().replace("-", "").replace(" ", "") in v.lower().replace("-", "").replace(" ", ""):
                        memory[k] = new
                        found = True
                        break
                if found:
                    save_memory(memory)
                    answer = "Memory अपडेट केली."
                else:
                    answer = "जुनी माहिती सापडली नाही."
            else:
                answer = "उदाहरण: update memory Badnera to Amravati"

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # FORGET ONE MEMORY
        if q.startswith("forget ") or q.startswith("विसर "):
            term = question.split(" ", 1)[1].strip()
            memory = load_memory()
            matches = [k for k, v in memory.items() if term.lower() in v.lower()]

            if matches:
                for k in matches:
                    del memory[k]
                save_memory(memory)
                answer = "संबंधित माहिती विसरलो."
            else:
                answer = "ती माहिती Memory मध्ये सापडली नाही."

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # FORGET ALL MEMORY
        if q in ["forget all memory", "clear memory", "सगळी माहिती विसर", "सर्व आठवणी विसर"]:
            save_memory({})
            answer = "माझी सर्व Memory साफ केली."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # SMART MEMORY COMMANDS
        if q.startswith("remember ") or q.startswith("लक्षात ठेव "):
            if q.startswith("remember "):
                item = question[9:].strip()
            else:
                item = question[len("लक्षात ठेव "):].strip()

            if item:
                memory = load_memory()
                memory[str(len(memory) + 1)] = item
                save_memory(memory)
                answer = "ठीक आहे, मी हे लक्षात ठेवले."
            else:
                answer = "काय लक्षात ठेवायचे ते सांगा."

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if any(x in q for x in ["what do you remember", "show memory", "तुला काय आठवतं", "काय लक्षात आहे"]):
            memory = load_memory()
            if memory:
                answer = "मला हे आठवत आहे: " + ". ".join(memory.values())
            else:
                answer = "माझ्या Memory मध्ये अजून काही सेव्ह नाही."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # REPEAT LAST ANSWER
        if q in ["repeat last answer", "repeat", "मागचे उत्तर सांग", "पुन्हा सांग"]:
            previous = next(
                (m["content"] for m in reversed(messages)
                 if m.get("role") == "assistant"),
                None
            )
            answer = previous or "मागील उत्तर उपलब्ध नाही."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # CHAT HISTORY SUMMARY
        if q in ["what did we discuss", "show chat history", "आधी काय बोललो", "आपण काय बोललो"]:
            history = [
                m["role"] + ": " + m["content"]
                for m in messages[1:]
                if m.get("role") in ["user", "assistant"]
            ]
            answer = "आपले मागील संभाषण: " + " | ".join(history[-10:]) if history else "मागील संभाषण उपलब्ध नाही."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # CLEAR CHAT HISTORY WITH CONFIRMATION
        if q in ["clear chat history", "clear history", "chat history delete", "चॅट हिस्ट्री साफ कर"]:
            confirm = input("Chat History साफ करायची आहे का? हो / नाही: ").strip().lower()
            if confirm in ["हो", "होय", "yes", "y", "ho"]:
                messages[:] = messages[:1]
                save_chat_history([])
                answer = "Chat History साफ केली."
            else:
                answer = "Chat History सुरक्षित ठेवली आहे."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue


        # SMART REMINDER COMMANDS
        # REMINDER DELETE MANAGEMENT
        if q.startswith("रिमाइंडर हटवा ") or q.startswith("delete reminder "):
            try:
                number = int(q.split()[-1])
                reminders = load_reminders()
                if 1 <= number <= len(reminders):
                    removed = reminders.pop(number - 1)
                    save_reminders(reminders)
                    answer = "रिमाइंडर हटवला: " + removed.get("text", "")
                else:
                    answer = "त्या क्रमांकाचा रिमाइंडर सापडला नाही."
            except Exception:
                answer = "कृपया क्रमांक सांगा. उदाहरण: रिमाइंडर हटवा 1"
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if q.startswith("रिमाइंडर एडिट ") or q.startswith("edit reminder "):
            try:
                number = int(q.split()[-1])
                reminders = load_reminders()

                if 1 <= number <= len(reminders):
                    item = reminders[number - 1]
                    print("सध्याचा रिमाइंडर:", item.get("text", ""))

                    new_text = input("नवीन मजकूर (बदल नको असल्यास रिकामे ठेवा): ").strip()
                    new_date = input("नवीन तारीख (YYYY-MM-DD, बदल नको असल्यास रिकामी): ").strip()
                    new_time = input("नवीन वेळ (HH:MM): ").strip()

                    match = re.fullmatch(r"(\d{1,2}):(\d{2})", new_time)

                    if match:
                        hour, minute = int(match.group(1)), int(match.group(2))

                        if hour <= 23 and minute <= 59:
                            old_due = datetime.datetime.fromtimestamp(item["due"])

                            if new_date:
                                selected_date = datetime.datetime.strptime(new_date, "%Y-%m-%d").date()
                            else:
                                selected_date = old_due.date()

                            due = datetime.datetime.combine(
                                selected_date,
                                datetime.time(hour, minute)
                            )

                            now = datetime.datetime.now()

                            if due > now:
                                if new_text:
                                    item["text"] = new_text

                                item["due"] = due.timestamp()

                                if item.get("repeat") == "weekly":
                                    item["weekday"] = due.weekday()

                                save_reminders(reminders)
                                answer = "रिमाइंडर अपडेट केला."
                            else:
                                answer = "भविष्यातील तारीख आणि वेळ द्या."
                        else:
                            answer = "वेळ चुकीची आहे."
                    else:
                        answer = "वेळ HH:MM स्वरूपात द्या."
                else:
                    answer = "त्या क्रमांकाचा रिमाइंडर सापडला नाही."

            except ValueError:
                answer = "तारीख YYYY-MM-DD स्वरूपात द्या. उदाहरण: 2026-11-15"
            except Exception:
                answer = "उदाहरण: रिमाइंडर एडिट 1"

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if q in ["सर्व रिमाइंडर हटवा", "सगळे रिमाइंडर हटवा", "delete all reminders"]:
            confirm = input("सर्व रिमाइंडर हटवायचे आहेत का? हो / नाही: ").strip().lower()
            if confirm in ["हो", "होय", "yes", "y", "ho"]:
                save_reminders([])
                answer = "सर्व रिमाइंडर हटवले."
            else:
                answer = "रिमाइंडर सुरक्षित ठेवले आहेत."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if q in ["रिमाइंडर यादी", "रिमाइंडर दाखव", "show reminders", "list reminders"]:
            reminders = load_reminders()
            if reminders:
                answer = "तुमचे रिमाइंडर: " + " | ".join(
                    str(i + 1) + ". " + item.get("text", "")
                    for i, item in enumerate(reminders)
                )
            else:
                answer = "तुमची रिमाइंडर यादी रिकामी आहे."
            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if "आठवण" in q or "remind" in q:
            now = datetime.datetime.now()
            due = None

            repeat = None
            weekday = None
            weekdays = {
                "सोमवारी": 0, "मंगळवारी": 1, "बुधवारी": 2,
                "गुरुवारी": 3, "शुक्रवारी": 4, "शनिवारी": 5,
                "रविवारी": 6
            }

            if any(x in q for x in ["रोज", "दररोज", "daily", "every day"]):
                repeat = "daily"
            else:
                for day_name, day_number in weekdays.items():
                    if day_name in q:
                        repeat = "weekly"
                        weekday = day_number
                        break

            minute_match = re.search(r"(\d+)\s*(?:मिनिटांनी|मिनिटात|minutes?|mins?)", q)
            hour_match = re.search(r"(\d+)\s*(?:तासांनी|तासात|hours?|hrs?)", q)

            if repeat:
                time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*वाजता", q)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        if ("संध्याकाळी" in q or "रात्री" in q) and hour < 12:
                            hour += 12
                        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        if repeat == "daily":
                            if due <= now:
                                due += datetime.timedelta(days=1)
                        else:
                            days_ahead = (weekday - now.weekday()) % 7
                            due += datetime.timedelta(days=days_ahead)
                            if due <= now:
                                due += datetime.timedelta(days=7)

            elif minute_match:
                due = now + datetime.timedelta(minutes=int(minute_match.group(1)))
            elif hour_match:
                due = now + datetime.timedelta(hours=int(hour_match.group(1)))
            elif "उद्या" in q or "tomorrow" in q:
                time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(?:वाजता)?", q)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        if ("संध्याकाळी" in q or "रात्री" in q) and hour < 12:
                            hour += 12
                        due = (now + datetime.timedelta(days=1)).replace(
                            hour=hour, minute=minute, second=0, microsecond=0
                        )

            if due:
                reminders = load_reminders()
                reminder = {
                    "text": question.strip(),
                    "due": due.timestamp()
                }
                if repeat:
                    reminder["repeat"] = repeat
                reminders.append(reminder)
                save_reminders(reminders)
                answer = "तुमचा रिमाइंडर सेव्ह केला."
            else:
                answer = "वेळ समजली नाही. उदाहरण: 10 मिनिटांनी पाणी पिण्याची आठवण करून दे."

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # TASK MANAGER
        if q.startswith("काम जोडा ") or q.startswith("add task "):
            if q.startswith("काम जोडा "):
                task_text = question.strip()[len("काम जोडा "):].strip()
            else:
                task_text = question.strip()[len("add task "):].strip()

            try:
                with open("tasks.json", "r") as f:
                    tasks = json.load(f)
                if not isinstance(tasks, list):
                    tasks = []
            except Exception:
                tasks = []

            if task_text:
                tasks.append({"task": task_text, "done": False})
                with open("tasks.json", "w") as f:
                    json.dump(tasks, f, ensure_ascii=False, indent=4)
                answer = "काम यादीत सेव्ह केले."
            else:
                answer = "कृपया कामाचे नाव सांगा."

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if q in ["कामांची यादी", "कामे दाखव", "show tasks", "list tasks"]:
            try:
                with open("tasks.json", "r") as f:
                    tasks = json.load(f)
                if not isinstance(tasks, list):
                    tasks = []
            except Exception:
                tasks = []

            if tasks:
                lines = [
                    str(i + 1) + ". " + ("पूर्ण: " if t.get("done") else "बाकी: ") + t.get("task", "")
                    for i, t in enumerate(tasks)
                ]
                answer = "तुमची कामे: " + " | ".join(lines)
            else:
                answer = "तुमच्या कामांची यादी रिकामी आहे."

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if q.startswith("काम पूर्ण ") or q.startswith("complete task "):
            try:
                number = int(q.split()[-1])
                with open("tasks.json", "r") as f:
                    tasks = json.load(f)
                if 1 <= number <= len(tasks):
                    tasks[number - 1]["done"] = True
                    with open("tasks.json", "w") as f:
                        json.dump(tasks, f, ensure_ascii=False, indent=4)
                    answer = "काम पूर्ण म्हणून नोंदवले."
                else:
                    answer = "त्या क्रमांकाचे काम सापडले नाही."
            except Exception:
                answer = "कृपया कामाचा क्रमांक सांगा. उदाहरण: काम पूर्ण 1"

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        if q in ["कामे साफ करा", "clear tasks", "delete all tasks"]:
            confirm = input("सर्व कामे हटवायची आहेत का? हो / नाही: ").strip().lower()
            if confirm in ["हो", "होय", "yes", "y", "ho"]:
                with open("tasks.json", "w") as f:
                    json.dump([], f, ensure_ascii=False, indent=4)
                answer = "सर्व कामे हटवली."
            else:
                answer = "कामे सुरक्षित ठेवली आहेत."

            print("JARVIS:", answer)
            subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])
            continue

        # SMART PERSONAL ASSISTANT MEMORY
        memory = load_memory()
        base_prompt = (
            "तुझे नाव SHIVAM (शिवम) आहे. तू माझा वैयक्तिक AI सहाय्यक आहेस. "
            "स्वतःला Flint किंवा Recursive म्हणू नकोस. नेहमी सोप्या मराठीत उत्तर दे. "
            "मागील संभाषणाचा संदर्भ लक्षात घे. "
            "वापरकर्ता 'त्याबद्दल सांग', 'अजून सांग', 'ते पुन्हा सांग' "
            "असे म्हणाल्यास मागील संभाषणाशी त्याचा संबंध जोड. "
            "मागील उत्तर पुन्हा सांगण्यास सांगितल्यास ते पुन्हा सांग. "
            "आधीच्या संभाषणाबद्दल विचारल्यास उपलब्ध Chat History वापरून उत्तर दे. "
            "संदर्भ स्पष्ट नसेल तर एक छोटा प्रश्न विचार. "
            "वापरकर्त्याच्या प्रश्नाचा अर्थ आणि हेतू आधी समजून घे. "
            "नेहमी प्रश्नाला थेट, स्पष्ट आणि नैसर्गिक उत्तर दे. "
            "सोप्या आणि बोलण्यासारख्या मराठीत संवाद साध. "
            "माहिती माहीत नसेल किंवा खात्री नसेल तर तसे स्पष्ट सांग; अंदाजाने तथ्य सांगू नकोस. "
            "एकाच गोष्टीची अनावश्यक पुनरावृत्ती करू नकोस. "
            "वापरकर्त्याने विषय बदलल्यास नवीन विषयानुसार उत्तर दे. "
            "आधीच्या संभाषणाचा संदर्भ उपयोगी असेल तेव्हाच वापर. "
            "वापरकर्ता 'मला काहीतरी नवीन शिकव', 'आज काहीतरी शिकव' किंवा 'नवीन गोष्ट सांग' म्हणाल्यास विषय विचारू नकोस. "
            "स्वतःहून एक रंजक आणि उपयुक्त गोष्ट निवडून सोप्या मराठीत शिकव. "
            "शक्य असल्यास छोटे उदाहरण दे आणि शेवटी एक छोटा प्रश्न विचारून समजले का ते तपास. "
            "शिकवताना विज्ञान, तंत्रज्ञान, इतिहास किंवा सामान्य ज्ञानातील खरी आणि उपयुक्त माहिती निवड. "
            "खोटी, काल्पनिक किंवा खात्री नसलेली गोष्ट खरी असल्यासारखी सांगू नकोस. "
            "वेळ, तारीख, आकडे किंवा वैज्ञानिक तथ्य खात्रीशिवाय बनवू नकोस. "
            "माहितीची खात्री नसेल तर तसे स्पष्ट सांग. "
            "उत्तर देण्यापूर्वी त्यातील तथ्ये सुसंगत आहेत का ते तपास."
            "उत्तर नेहमी नैसर्गिक, व्याकरणदृष्ट्या योग्य आणि स्पष्ट मराठीत दे. "
            "शक्यतो देवनागरी लिपीचा वापर कर. "
            "हिंदी, चिनी किंवा इतर भाषांतील अनावश्यक शब्द किंवा अक्षरे मिसळू नकोस. "
            "इंग्रजी शब्द फक्त तांत्रिक संज्ञेसाठी आवश्यक असल्यास वापर आणि त्याचा मराठी अर्थ स्पष्ट कर. "
            "शब्दलेखन, वाक्यरचना आणि लिंग-वचन यांची काळजी घे. "
            "उत्तरात विचित्र चिन्हे, अनावश्यक परकीय अक्षरे किंवा अर्थहीन शब्द लिहू नकोस. "
            "आवाजात वाचण्यासाठी उत्तरे सोपी, लहान आणि स्पष्ट वाक्यांत लिही. "
            "प्रत्येक उत्तर देण्यापूर्वी मराठी व्याकरण आणि शब्दरचना तपासून सुधार. "
            "नाम, सर्वनाम आणि क्रियापद यांचे लिंग, वचन आणि काळ यांचा योग्य मेळ ठेव. "
            "स्वतःविषयी बोलताना नैसर्गिक आणि योग्य मराठी क्रियापदे वापर. "
            "उदाहरणार्थ, मी उत्तर देईन, मी मराठीत उत्तर देत आहे, माझे नाव शिवम आहे अशी वाक्ये वापर. "
            "उत्तर देणाराहो, उत्तर देशोय यांसारखे चुकीचे शब्दप्रयोग कधीही वापरू नकोस. "
            "वापरकर्त्याला नेहमी आदराने 'तुम्ही' किंवा 'तुम्हाला' असे संबोध. "
            "उदाहरणार्थ, 'तुम्ही कसा समजले?' असे न लिहिता 'तुम्हाला हे समजले का?' असे लिही. "
            "उदाहरणार्थ, 'आजचा नवीन शिकवणारी गोष्ट' असे न लिहिता 'आजची नवीन शिकवणारी गोष्ट' असे लिही. "
            "उदाहरणार्थ, 'प्रकाशाची गती कसे जाणवते' असे न लिहिता 'प्रकाशाचा वेग किती आहे?' असे लिही. "
            "अपूर्ण, विसंगत किंवा चुकीची वाक्ये उत्तरात देऊ नकोस. "
            "अंतिम उत्तर देण्यापूर्वी संपूर्ण मजकूर पुन्हा वाचून तपास. "
            "उत्तरात देवनागरी मराठी, आवश्यक इंग्रजी तांत्रिक संज्ञा आणि सामान्य विरामचिन्हे यांचाच वापर कर. "
            "चिनी, जपानी, कोरियन किंवा इतर अनावश्यक परकीय लिपीतील अक्षरे अजिबात वापरू नकोस. "
            "एखादा शब्द चुकीचा किंवा अनोळखी दिसत असल्यास त्याऐवजी सोपा आणि योग्य मराठी शब्द वापर. "
            "विज्ञानविषयक उत्तरात कारण आणि परिणाम यांची गल्लत करू नकोस. "
            "प्रकाशाच्या रंगांबद्दल सांगताना रंगांमुळे प्रकाशाचा वेग सर्वत्र वेगळा असतो असे म्हणू नकोस. "
            "आकाश निळे दिसण्याचे कारण रेले प्रकीर्णन आहे; निळ्या प्रकाशाचे प्रकीर्णन लाल प्रकाशापेक्षा अधिक होते. "
            "वैज्ञानिक माहितीची खात्री नसेल तर अंदाजाने उत्तर देण्याऐवजी तसे स्पष्ट सांग. "
            "उत्तरात चुकीचे उदाहरण किंवा बनावट वैज्ञानिक संज्ञा वापरू नकोस. "
            "प्रत्येक गुंतागुंतीच्या प्रश्नावर उत्तर देण्यापूर्वी टप्प्याटप्प्याने विचार कर. "
            "मोठ्या कामाचे छोटे आणि कृतीयोग्य टप्पे तयार कर. "
            "समस्या आल्यास तिचे संभाव्य कारण शोध आणि सुरक्षित उपाय सुचव. "
            "उपलब्ध साधने आणि क्षमतांचा योग्य वापर करून काम पूर्ण करण्याचा प्रयत्न कर. "
            "एखादी कृती करण्यासाठी परवानगी आवश्यक असल्यास आधी वापरकर्त्याची संमती घे. "
            "काम पूर्ण झाले नसताना पूर्ण झाल्याचा दावा करू नकोस. "
            "आवश्यक माहिती अपुरी असल्यास योग्य प्रश्न विचार. "
            "महत्त्वाच्या कामांसाठी परिणाम तपास आणि चूक झाल्यास ती स्पष्ट सांग. "
            "वापरकर्त्याचे उद्दिष्ट समजून घेऊन पुढील उपयुक्त पाऊल सुचव. "
            "नेहमी सुरक्षितता, गोपनीयता आणि वापरकर्त्याचे नियंत्रण यांना प्राधान्य दे. "
        )

        messages[0]["content"] = base_prompt

        if memory:
            memory_context = "\\n".join(
                "- " + str(value) for value in memory.values()
            )
            messages[0]["content"] += (
                "\\n\\nवापरकर्त्याबद्दल लक्षात ठेवलेली माहिती:"
                "\\n" + memory_context +
                "\\nही माहिती उत्तर देताना संदर्भ म्हणून वापर."
            )

        messages.append({"role": "user", "content": question})

        response = httpx.post(
            url,
            headers=headers,
            json={"model": "openrouter/free", "messages": [messages[0]] + messages[1:][-20:]},
            timeout=90
        )
        response.raise_for_status()

        answer = response.json()["choices"][0]["message"]["content"]

        # AI ANSWER QUALITY CHECK - TEACHING QUESTIONS
        teach_words = ["शिकव", "नवीन गोष्ट सांग", "काहीतरी शिकव", "teach me"]

        if any(word in question.lower() for word in teach_words):
            review_prompt = (
                "तू उत्कृष्ट मराठी भाषा संपादक आणि तथ्य तपासक आहेस. "
                "प्रत्येक वाक्याचे मराठी व्याकरण, शब्दलेखन, लिंग, वचन आणि क्रियापद तपास. "
                "चुकीचे किंवा अर्धवट मराठी शब्द पूर्णपणे दुरुस्त कर. "
                "उदाहरणार्थ, 'अन्नला' ऐवजी 'अन्नाला', 'छोट्या आंतासाठी' ऐवजी 'लहान आतड्यात' लिही. "
                "अप्राकृतिक भाषांतर टाळून रोजच्या वापरातील सहज मराठी वापर. "
                "ऐतिहासिक, वैज्ञानिक आणि सामान्य ज्ञानातील तथ्ये काळजीपूर्वक तपास. "
                "ऐतिहासिक व्यक्तींची जन्मतारीख, आई-वडिलांची नावे, नातेसंबंध आणि ठिकाणे चुकीची असल्यास दुरुस्त कर. "
                "उदाहरणार्थ, छत्रपती शिवाजी महाराजांच्या आईचे नाव जिजाबाई होते. "
                "पहिल्या उत्तरातील चुकीची माहिती कायम ठेवू नकोस. "
                "तथ्यांची खात्री नसेल तर अंदाजाने दुरुस्ती करू नकोस; अनिश्चितता स्पष्ट ठेव. "
                "वैज्ञानिक तथ्ये आणि कारण-परिणाम तपासूनच दुरुस्त कर. "
                "चुकीची माहिती किंवा बनावट उदाहरणे ठेवू नकोस. "
                "देवनागरी लिपी वापर. चिनी, जपानी किंवा इतर अनावश्यक परकीय अक्षरे वापरू नकोस. "
                "आवश्यक वैज्ञानिक संज्ञा मराठीत समजावून सांग. "
                "उत्तर मूळ प्रश्नाशी संबंधित, थोडक्यात आणि स्पष्ट ठेव. "
                "शेवटी स्वतःचे उत्तर पुन्हा वाचून सर्व भाषिक चुका दुरुस्त कर. "
                "खात्री नसलेली माहिती बनवू नकोस. "
                "फक्त एकच सुधारलेले अंतिम उत्तर दे. "
                "प्रश्न, उत्तर किंवा अंतिम उत्तर अशी शीर्षके देऊ नकोस. "
                "स्वतःहून कोणताही नवीन प्रश्न विचारू नकोस. "
                "मूळ प्रश्नाचा विषय आणि उद्देश बदलू नकोस. "
                "पहिल्या उत्तरातील योग्य माहिती कायम ठेव. "
                "चुकीची माहिती दुरुस्त कर; नवीन तथ्ये किंवा उदाहरणे स्वतःहून जोडू नकोस. "
                "उत्तरात अनावश्यक पुनरावृत्ती, प्रस्तावना किंवा शेवटचा प्रश्न ठेवू नकोस. "
                "तपासणीचे स्पष्टीकरण देऊ नकोस."
            )

            review_messages = [
                {"role": "system", "content": review_prompt},
                {
                    "role": "user",
                    "content": (
                        "मूळ प्रश्न: " + question +
                        "\nपहिले उत्तर:\n" + answer +
                        "\nया उत्तरातील चुका दुरुस्त करून अंतिम उत्तर दे."
                    )
                }
            ]

            try:
                review_response = httpx.post(
                    url,
                    headers=headers,
                    json={
                        "model": "openrouter/free",
                        "messages": review_messages
                    },
                    timeout=90
                )
                review_response.raise_for_status()
                reviewed_answer = review_response.json()["choices"][0]["message"]["content"]

                if reviewed_answer and reviewed_answer.strip():
                    answer = reviewed_answer.strip()

            except Exception as review_error:
                print("AI Review unavailable. Using original answer.")

        print("\nJARVIS:", answer)

        messages.append({"role": "assistant", "content": answer})
        save_chat_history(messages[1:])
        subprocess.run(["termux-tts-speak", "-l", "mr-IN", answer])

    except Exception as e:
        print("Error:", e)
        if messages[-1]["role"] == "user":
            messages.pop()
