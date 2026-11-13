from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import ast
import asyncio
import tempfile
import httpx
from contextlib import contextmanager
import uuid
import re
from tools_engine import execute_tool, get_available_tools

HOST = "127.0.0.1"
PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
HISTORY_FILE = os.path.join(BASE_DIR, "chat_history.json")
JARVIS_FILE = os.path.join(BASE_DIR, "jarvis.py")

APPROVALS_FILE = os.path.join(BASE_DIR, "pending_approvals.json")


def load_approvals():
    data = load_json(APPROVALS_FILE, [])
    return data if isinstance(data, list) else []


def save_approvals(data):
    save_json(APPROVALS_FILE, data)


def create_approval(app_name):
    import datetime
    import uuid

    now = datetime.datetime.now(datetime.timezone.utc)
    action = {
        "id": str(uuid.uuid4()),
        "action_type": "open_android_app",
        "description": f"{app_name} App उघडण्याची परवानगी",
        "payload": {"app_name": app_name},
        "permission_key": "android.open_app",
        "tier": "medium",
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": (now + datetime.timedelta(minutes=5)).isoformat()
    }

    approvals = load_approvals()
    approvals.append(action)
    save_approvals(approvals)
    return action

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@contextmanager
def openrouter_stream(client, headers, payload):
    body = dict(payload)
    response = client.send(
        client.build_request("POST", OPENROUTER_URL, headers=headers, json=body),
        stream=True
    )

    if response.status_code == 402 and body.get("model") != "openrouter/free":
        error_text = response.read().decode("utf-8", "replace")
        response.close()
        body["model"] = "openrouter/free"
        body["max_tokens"] = 150
        if body.get("messages") and body["messages"][0].get("role") == "system":
            body["messages"][0]["content"] += "\nसध्या प्रत्यक्ष वापरलेला मॉडेल पर्याय OpenRouter Free Model आहे. त्याला OpenRouter Auto म्हणू नकोस."
        print("[JARVIS] Credits कमी आहेत. आता OpenRouter Free Model वापरत आहे.")
        response = client.send(
            client.build_request("POST", OPENROUTER_URL, headers=headers, json=body),
            stream=True
        )

    response.extensions["jarvis_model"] = body.get("model", "")
    try:
        yield response
    finally:
        response.close()


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(temp, path)


def load_prompt():
    tree = ast.parse(open(JARVIS_FILE, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "base_prompt"
                   for t in node.targets):
                return ast.literal_eval(node.value)
    raise RuntimeError("JARVIS base_prompt सापडला नाही")


def build_system_prompt():
    prompt = (
        "तुझे नाव SHIVAM (शिवम) आहे. स्वतःला JARVIS, Flint किंवा Recursive म्हणू नकोस. "
        "नेहमी सोप्या, शुद्ध आणि नैसर्गिक मराठीत उत्तर दे. "
        "प्रश्नाचा संदर्भ समजून थेट उत्तर दे. "
        "खात्री नसलेली माहिती बनवू नकोस. "
        "मागील संभाषणाचा उपलब्ध संदर्भ वापर. "
        "Tool वापरताना नियम पाळ. Android App उघडण्यापूर्वी "
        "वापरकर्त्याची स्पष्ट मंजुरी आवश्यक आहे. "
        "मंजुरी मिळेपर्यंत App उघडू नकोस."
    )
    memory = load_json(MEMORY_FILE, {})
    if isinstance(memory, dict) and memory:
        context = "\\n".join(
            "- " + str(v) for v in list(memory.values())[:10]
        )[:600]
        prompt += "\\nलक्षात ठेवलेली माहिती:\\n" + context
    return prompt


def load_history():
    data = load_json(HISTORY_FILE, [])
    if not isinstance(data, list):
        return []
    return [m for m in data
            if isinstance(m, dict)
            and m.get("role") in ("user", "assistant")][-20:]


def save_history(history):
    save_json(HISTORY_FILE, history[-20:])


def get_badnera_weather(arguments):
    """बदनेरा, अमरावतीचे प्रत्यक्ष हवामान Open-Meteo वरून मिळवा."""
    forecast_type = arguments.get("forecast_type", "current")
    allowed = {"current", "tomorrow", "7day", "rain_today", "rain_tomorrow"}
    if forecast_type not in allowed:
        return {"error": "हवामानाचा प्रकार अवैध आहे."}

    params = {
        "latitude": 20.8648,
        "longitude": 77.73521,
        "timezone": "Asia/Kolkata",
        "forecast_days": 7 if forecast_type == "7day" else (2 if forecast_type in ("tomorrow", "rain_tomorrow") else 1),
    }
    if forecast_type == "current":
        params["current"] = "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code"
        params["daily"] = "precipitation_probability_max"
    else:
        params["daily"] = "temperature_2m_max,temperature_2m_min,precipitation_probability_max"

    try:
        response = httpx.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        daily = data.get("daily", {})
        if forecast_type == "current":
            current = data["current"]
            conditions = {0: "आकाश निरभ्र आहे", 1: "मुख्यतः निरभ्र आहे", 2: "अंशतः ढगाळ आहे", 3: "ढगाळ आहे", 45: "धुके आहे", 48: "धुके आहे", 51: "हलका रिमझिम पाऊस आहे", 53: "रिमझिम पाऊस आहे", 55: "जोरदार रिमझिम पाऊस आहे", 61: "हलका पाऊस आहे", 63: "मध्यम पाऊस आहे", 65: "जोरदार पाऊस आहे", 80: "पावसाच्या सरी येऊ शकतात", 81: "पावसाच्या सरी येऊ शकतात", 82: "जोरदार सरी येऊ शकतात", 95: "मेघगर्जनेसह पाऊस होऊ शकतो"}
            code = current.get("weather_code")
            answer = ("बदनेरा येथील सध्याचे हवामान: " + conditions.get(code, "हवामान बदलते आहे") + ". "
                      + "तापमान " + str(current.get("temperature_2m")) + " अंश सेल्सिअस. "
                      + "जाणवणारे तापमान " + str(current.get("apparent_temperature")) + " अंश. "
                      + "आर्द्रता " + str(current.get("relative_humidity_2m")) + " टक्के. "
                      + "वाऱ्याचा वेग " + str(current.get("wind_speed_10m")) + " किलोमीटर प्रति तास. "
                      + "आज पावसाची शक्यता " + str((daily.get("precipitation_probability_max") or ["माहिती उपलब्ध नाही"])[0]) + " टक्के.")
        elif forecast_type in ("rain_today", "rain_tomorrow"):
            index = 1 if forecast_type == "rain_tomorrow" else 0
            values = daily.get("precipitation_probability_max", [])
            answer = ("उद्या" if index else "आज") + " बदनेरा येथे पावसाची शक्यता " + str(values[index] if len(values) > index else "माहिती उपलब्ध नाही") + " टक्के आहे."
        else:
            indices = [1] if forecast_type == "tomorrow" else range(len(daily.get("time", [])))
            answer = "बदनेरा येथील उद्याचा हवामान अंदाज: " if forecast_type == "tomorrow" else "बदनेरा येथील पुढील सात दिवसांचा हवामान अंदाज: "
            weekdays = ["सोमवार", "मंगळवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
            for i in indices:
                if i >= len(daily.get("time", [])):
                    continue
                date_text = daily["time"][i]
                from datetime import date
                day = date.fromisoformat(date_text)
                answer += (weekdays[day.weekday()] + " " + day.strftime("%d-%m") + ": किमान तापमान "
                           + str(daily["temperature_2m_min"][i]) + " अंश, कमाल तापमान "
                           + str(daily["temperature_2m_max"][i]) + " अंश, पावसाची शक्यता "
                           + str(daily["precipitation_probability_max"][i]) + " टक्के. ")
        return {"result": answer.strip(), "location": "बदनेरा, अमरावती", "source": "Open-Meteo", "forecast_type": forecast_type}
    except Exception as exc:
        return {"error": "बदनेरा येथील हवामान मिळवता आले नाही: " + str(exc)[:250]}


class JarvisAPI(BaseHTTPRequestHandler):

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_json(200, {"status": "ok"})

    def do_GET(self):
        if self.path == "/v1/speech/tts/health":
            self.send_json(200, {
                "available": True,
                "backend": "edge-tts",
                "voice_id": "mr-IN-ManoharNeural",
                "voices": ["mr-IN-ManoharNeural", "mr-IN-ManoharNeural"],
                "speed": 1.0
            })
        elif self.path == "/health":
            self.send_json(200, {
                "status": "online",
                "name": "JARVIS",
                "message": "JARVIS API Server चालू आहे."
            })
        elif self.path == "/v1/models":
            if not os.getenv("OPENROUTER_API_KEY"):
                self.send_json(401, {"error": "OpenRouter API key not configured"})
                return
            models = [
                "openrouter/auto",
                "anthropic/claude-sonnet-4.6",
                "deepseek/deepseek-r1"
            ]
            self.send_json(200, {
                "object": "list",
                "data": [
                    {
                        "id": model,
                        "object": "model",
                        "created": 0,
                        "owned_by": "openrouter"
                    }
                    for model in models
                ]
            })
        elif self.path == "/v1/tools":
            self.send_json(200, {
                "tools": get_available_tools()
            })
        elif self.path == "/v1/cloud/status":
            self.send_json(200, {
                "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY"))
            })
        elif self.path == "/v1/approvals/pending":
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            approvals = load_approvals()
            pending = []
            changed = False

            for action in approvals:
                if action.get("status") != "pending":
                    continue
                try:
                    expires = datetime.datetime.fromisoformat(
                        action["expires_at"].replace("Z", "+00:00")
                    )
                    if expires <= now:
                        action["status"] = "expired"
                        changed = True
                        continue
                except Exception:
                    action["status"] = "expired"
                    changed = True
                    continue
                pending.append(action)

            if changed:
                save_approvals(approvals)

            self.send_json(200, {"actions": pending})
        else:
            self.send_json(404, {"error": "API endpoint not found"})

    def do_POST(self):
        if self.path == "/v1/speech/synthesize":
            temp_path = None
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0 or length > 20000:
                    self.send_json(400, {"detail": "अवैध मजकूर आकार"})
                    return

                request = json.loads(self.rfile.read(length))
                text = request.get("text", "")
                voice = request.get("voice_id") or "mr-IN-ManoharNeural"
                speed = float(request.get("speed") or 1.0)

                if not isinstance(text, str) or not text.strip():
                    self.send_json(400, {"detail": "मजकूर आवश्यक आहे"})
                    return
                if len(text) > 5000:
                    self.send_json(400, {"detail": "मजकूर खूप मोठा आहे"})
                    return
                if voice not in ("mr-IN-ManoharNeural", "mr-IN-ManoharNeural"):
                    self.send_json(400, {"detail": "अवैध Marathi voice"})
                    return

                speed = max(0.5, min(speed, 2.0))
                rate = f"{round((speed - 1) * 100):+d}%"

                import edge_tts
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    temp_path = f.name

                async def generate_audio():
                    communicate = edge_tts.Communicate(
                        text.strip(), voice, rate=rate
                    )
                    await communicate.save(temp_path)

                asyncio.run(generate_audio())

                with open(temp_path, "rb") as f:
                    audio_data = f.read()

                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(audio_data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(audio_data)

            except Exception as e:
                self.send_json(502, {"detail": "Marathi TTS त्रुटी: " + str(e)[:300]})
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
            return

        if self.path.startswith("/v1/approvals/"):
            import datetime
            import re

            match = re.fullmatch(
                r"/v1/approvals/([a-f0-9-]+)/(approve|deny)",
                self.path
            )
            if not match:
                self.send_json(404, {"error": "Invalid approval endpoint"})
                return

            action_id, decision = match.groups()
            approvals = load_approvals()
            action = next(
                (a for a in approvals if a.get("id") == action_id),
                None
            )

            if not action or action.get("status") != "pending":
                self.send_json(404, {"error": "Pending approval सापडली नाही"})
                return

            try:
                expires = datetime.datetime.fromisoformat(
                    action["expires_at"].replace("Z", "+00:00")
                )
                if expires <= datetime.datetime.now(datetime.timezone.utc):
                    action["status"] = "expired"
                    save_approvals(approvals)
                    self.send_json(410, {"error": "Approval ची मुदत संपली"})
                    return
            except Exception:
                action["status"] = "expired"
                save_approvals(approvals)
                self.send_json(410, {"error": "Invalid approval expiry"})
                return

            if decision == "deny":
                action["status"] = "denied"
                save_approvals(approvals)
                self.send_json(200, {"success": True, "status": "denied"})
                return

            payload = action.get("payload", {})
            if not isinstance(payload, dict) or set(payload) != {"app_name"}:
                self.send_json(400, {"error": "Invalid approval payload"})
                return

            result = execute_tool("open_android_app", payload)
            action["status"] = "approved" if "result" in result else "failed"
            action["execution_result"] = result
            save_approvals(approvals)
            self.send_json(200, {
                "success": "result" in result,
                "status": action["status"],
                "result": result
            })
            return

        if self.path == "/v1/tools/execute":
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0 or length > 10000:
                    self.send_json(400, {"error": "Invalid request size"})
                    return

                request = json.loads(self.rfile.read(length))
                tool_name = request.get("name")

                if not isinstance(tool_name, str):
                    self.send_json(400, {"error": "Tool name आवश्यक आहे"})
                    return

                arguments = request.get("arguments", {})
                if not isinstance(arguments, dict):
                    self.send_json(400, {"error": "Invalid tool arguments"})
                    return
                if tool_name == "get_weather":
                    result = get_badnera_weather(arguments)
                elif tool_name == "open_android_app":
                    app_name = arguments.get("app_name")
                    if not isinstance(app_name, str):
                        self.send_json(400, {"error": "App नाव अवैध आहे"})
                        return
                    action = create_approval(app_name)
                    result = {
                        "pending_approval": True,
                        "approval_id": action["id"],
                        "message": "App उघडण्यासाठी मंजुरी मागितली आहे."
                    }
                else:
                    result = execute_tool(tool_name, arguments)

                self.send_json(200, result)
            except Exception:
                self.send_json(400, {"error": "Invalid tool request"})
            return

        if self.path != "/v1/chat/completions":
            self.send_json(404, {"error": "API endpoint not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > 2_000_000:
                self.send_json(400, {"error": "Invalid request size"})
                return

            request = json.loads(self.rfile.read(length))
            api_key = os.getenv("OPENROUTER_API_KEY")

            if not api_key:
                self.send_json(500, {"error": "OPENROUTER_API_KEY सेट केलेली नाही"})
                return

            incoming = [
                {"role": m["role"], "content": m["content"]}
                for m in request.get("messages", [])
                if isinstance(m, dict)
                and m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)
            ]

            if len(incoming) == 1 and incoming[0]["role"] == "user":
                history = load_history()
                if not history or history[-1] != incoming[0]:
                    history.append(incoming[0])
                conversation = history[-20:]
            elif incoming:
                conversation = incoming[-20:]
            else:
                conversation = load_history()[-20:]

            if not conversation or conversation[-1]["role"] != "user":
                self.send_json(400, {"error": "User message आवश्यक आहे"})
                return

            messages = [{"role": "system", "content": build_system_prompt()}]
            messages.extend(conversation)

            model_id = request.get("model") or os.getenv("JARVIS_MODEL", "openrouter/auto")
            model_id = {"anthropic/claude-sonnet-4": "anthropic/claude-sonnet-4.6", "openrouter/anthropic/claude-sonnet-4": "anthropic/claude-sonnet-4.6", "openrouter/anthropic/claude-sonnet-4.6": "anthropic/claude-sonnet-4.6", "openrouter/deepseek/deepseek-r1": "deepseek/deepseek-r1"}.get(model_id, model_id)

            model_labels = {
                "anthropic/claude-sonnet-4.6": "Claude Sonnet 4.6 via OpenRouter",
                "deepseek/deepseek-r1": "DeepSeek R1 via OpenRouter",
                "openrouter/free": "OpenRouter Free Model",
                "openrouter/auto": "OpenRouter Auto",
            }
            selected_model = model_labels.get(model_id, model_id)
            messages[0]["content"] += (
                "\n\nनिवडलेले AI मॉडेल: " + selected_model + ". "
                "वापरकर्त्याने मॉडेलबद्दल विचारल्यास ही माहिती सांग. "
                "OpenRouter Auto असल्यास प्रत्यक्ष मॉडेलची खात्रीशीर माहिती उपलब्ध नाही असे सांग."
            )


            tool_specs = [
                {
                    "type": "function",
                    "function": {
                        "name": "open_android_app",
                        "description": "Android App उघडण्यासाठी वापरकर्त्याची मंजुरी मागा. मंजुरी मिळेपर्यंत App उघडू नका.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "app_name": {
                                    "type": "string",
                                    "enum": ["chrome", "youtube", "gmail", "whatsapp", "camera", "settings", "phone"]
                                }
                            },
                            "required": ["app_name"],
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_time",
                        "description": "सध्याची तारीख आणि वेळ मिळवा.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_system_info",
                        "description": "Android डिव्हाइस आणि Python ची माहिती मिळवा.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "बदनेरा, अमरावतीचे प्रत्यक्ष हवामान, आज/उद्याची पावसाची शक्यता किंवा सात दिवसांचा अंदाज मिळवा. हवामानाविषयी प्रश्न आल्यास हे Tool वापरा; अंदाज स्वतः बनवू नका.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "forecast_type": {
                                    "type": "string",
                                    "enum": ["current", "tomorrow", "7day", "rain_today", "rain_tomorrow"]
                                }
                            },
                            "required": ["forecast_type"],
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_available_tools",
                        "description": "JARVIS ची उपलब्ध Tools यादी मिळवा.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    }
                }
            ]

            payload = {
                "model": model_id,
                "messages": messages,
                "stream": True,
                "temperature": request.get("temperature", 0.7),
                "tools": tool_specs,
                "tool_choice": "auto",
                "max_tokens": min(int(request.get("max_tokens", 150)), 150)
            }

            headers = {
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json"
            }

            with httpx.Client(timeout=90) as client:
                with openrouter_stream(client, headers, payload) as upstream:

                    if upstream.status_code != 200:
                        error_text = upstream.read().decode("utf-8", "replace")
                        print("[OPENROUTER ERROR]", upstream.status_code, error_text[:1000])
                        self.send_json(502, {
                            "error": "OpenRouter API error",
                            "details": error_text[:1000]
                        })
                        return

                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    model_info = {
                        "selected_model": payload.get("model", ""),
                        "actual_model": upstream.extensions.get("jarvis_model", "")
                    }
                    self.wfile.write(
                        ("event: inference_start\ndata: " +
                         json.dumps(model_info) + "\n\n").encode("utf-8")
                    )
                    self.wfile.flush()

                    answer = ""
                    pending_calls = {}

                    for line in upstream.iter_lines():
                        if not line.startswith("data:"):
                            continue

                        data = line[5:].strip()
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            if chunk.get("model"):
                                provider_model = chunk["model"]
                                upstream.extensions["jarvis_provider_model"] = provider_model
                                self.wfile.write(
                                    ("event: inference_model\ndata: " +
                                     json.dumps({"actual_model": provider_model}) + "\n\n").encode("utf-8")
                                )
                                self.wfile.flush()
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")

                                if isinstance(content, str):
                                    answer += content

                                for call in delta.get("tool_calls", []):
                                    index = call.get("index", 0)
                                    item = pending_calls.setdefault(index, {
                                        "id": "",
                                        "type": "function",
                                        "function": {
                                            "name": "",
                                            "arguments": ""
                                        }
                                    })

                                    if call.get("id"):
                                        item["id"] = call["id"]

                                    function = call.get("function", {})
                                    if function.get("name"):
                                        item["function"]["name"] += function["name"]
                                    if function.get("arguments"):
                                        item["function"]["arguments"] += function["arguments"]
                        except Exception:
                            pass

                        self.wfile.write(
                            ("data: " + data + "\n\n").encode("utf-8")
                        )
                        self.wfile.flush()

                    calls = [
                        pending_calls[index]
                        for index in sorted(pending_calls)
                    ][:3]

                    if calls:
                        messages.append({
                            "role": "assistant",
                            "content": answer or None,
                            "tool_calls": calls
                        })

                        for index, call in enumerate(calls):
                            function = call.get("function", {})
                            tool_name = function.get("name", "")

                            try:
                                arguments = json.loads(
                                    function.get("arguments") or "{}"
                                )
                                if not isinstance(arguments, dict):
                                    raise ValueError("Invalid tool arguments")
                            except Exception:
                                arguments = None

                            start_event = {
                                "tool": tool_name,
                                "arguments": arguments or {}
                            }
                            self.wfile.write(
                                ("event: tool_call_start\ndata: " +
                                 json.dumps(start_event, ensure_ascii=False) +
                                 "\n\n").encode("utf-8")
                            )
                            self.wfile.flush()

                            started = __import__("time").time()
                            if arguments is None:
                                result = {"error": "Tool arguments अवैध आहेत."}
                            elif tool_name == "get_weather":
                                result = get_badnera_weather(arguments)
                            elif tool_name == "open_android_app":
                                app_name = arguments.get("app_name")
                                if not isinstance(app_name, str):
                                    result = {"error": "App नाव अवैध आहे."}
                                else:
                                    action = create_approval(app_name)
                                    result = {
                                        "result": {
                                            "pending_approval": True,
                                            "approval_id": action["id"],
                                            "message": (
                                                app_name + " उघडण्यासाठी मंजुरी मागितली आहे. "
                                                "अजून App उघडलेले नाही. Approval Bell मधून मंजुरी द्या."
                                            )
                                        }
                                    }
                            else:
                                result = execute_tool(tool_name, arguments)

                            latency = int(
                                (__import__("time").time() - started) * 1000
                            )
                            success = ("result" in result and "error" not in result and not (isinstance(result.get("result"), dict) and result["result"].get("pending_approval", False)))

                            end_event = {
                                "tool": tool_name,
                                "success": success,
                                "result": result.get("result", result.get("error")),
                                "latency": latency
                            }
                            self.wfile.write(
                                ("event: tool_call_end\ndata: " +
                                 json.dumps(end_event, ensure_ascii=False) +
                                 "\n\n").encode("utf-8")
                            )
                            self.wfile.flush()

                            messages.append({
                                "role": "tool",
                                "tool_call_id": call.get("id") or ("call_" + str(index)),
                                "content": json.dumps(result, ensure_ascii=False)
                            })

                        final_payload = {
                            "model": model_id,
                            "messages": messages,
                            "stream": True,
                            "temperature": request.get("temperature", 0.7),
                            "max_tokens": min(int(request.get("max_tokens", 150)), 150)
                        }

                        with openrouter_stream(client, headers, final_payload) as final_upstream:

                            if final_upstream.status_code != 200:
                                error_text = final_upstream.read().decode("utf-8", "replace")
                                print("[OPENROUTER FINAL ERROR]", final_upstream.status_code, error_text[:1000])
                                fallback = (
                                    result.get("result", {}).get("message", "Tool प्रक्रिया पूर्ण झाली.")
                                    if isinstance(result, dict) and isinstance(result.get("result"), dict)
                                    else "Tool प्रक्रिया पूर्ण झाली."
                                )
                                answer += fallback
                                error_chunk = {
                                    "choices": [{
                                        "delta": {"content": fallback},
                                        "finish_reason": "stop"
                                    }]
                                }
                                self.wfile.write(
                                    ("data: " + json.dumps(error_chunk, ensure_ascii=False) + "\n\n").encode("utf-8")
                                )
                            else:
                                for line in final_upstream.iter_lines():
                                    if not line.startswith("data:"):
                                        continue

                                    data = line[5:].strip()
                                    if data == "[DONE]":
                                        break

                                    try:
                                        chunk = json.loads(data)
                                        choices = chunk.get("choices", [])
                                        if choices:
                                            content = choices[0].get("delta", {}).get("content")
                                            if isinstance(content, str):
                                                answer += content
                                    except Exception:
                                        pass

                                    self.wfile.write(
                                        ("data: " + data + "\n\n").encode("utf-8")
                                    )
                                    self.wfile.flush()

                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()

                    if answer:
                        save_history(conversation + [
                            {"role": "assistant", "content": answer}
                        ])


        except (BrokenPipeError, ConnectionResetError):
            print("[JARVIS API] Client disconnected")
        except Exception as e:
            print("[JARVIS API] Error:", str(e))
            try:
                self.send_json(500, {"error": "JARVIS API error"})
            except Exception:
                pass

    def log_message(self, format, *args):
        print("[JARVIS API]", format % args)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), JarvisAPI)
    print(f"JARVIS API Server: http://{HOST}:{PORT}")
    print("Health Check: http://127.0.0.1:8000/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nJARVIS API Server बंद झाला.")
        server.server_close()
