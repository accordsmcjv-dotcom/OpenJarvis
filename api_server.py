from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import datetime
import json
import os
import shutil
import math
import ast
import asyncio
import time
import threading
import tempfile
import httpx
from contextlib import contextmanager
import uuid
import re
import urllib.parse
from tools_engine import execute_tool, get_available_tools

HOST = "127.0.0.1"
PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
MEMORY_CATEGORIES_FILE = os.path.join(BASE_DIR, "memory_categories.json")
HISTORY_FILE = os.path.join(BASE_DIR, "chat_history.json")
JARVIS_FILE = os.path.join(BASE_DIR, "jarvis.py")

APPROVALS_FILE = os.path.join(BASE_DIR, "pending_approvals.json")
APPROVAL_LOCK = threading.Lock()
MODELS_CACHE_FILE = os.path.join(BASE_DIR, "models_cache.json")
NOTES_FILE = os.path.join(BASE_DIR, "notes.json")
TOOL_CREDENTIALS_FILE = os.path.join(BASE_DIR, "tool_credentials.json")

def load_tool_credentials():
    data = load_json(TOOL_CREDENTIALS_FILE, {})
    return data if isinstance(data, dict) else {}

def save_tool_credentials(data):
    temp = TOOL_CREDENTIALS_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(temp, 0o600)
    os.replace(temp, TOOL_CREDENTIALS_FILE)
    os.chmod(TOOL_CREDENTIALS_FILE, 0o600)

def tavily_web_search(query, max_results=5):
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("Search प्रश्न 1 ते 500 अक्षरांचा असावा.")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 10:
        raise ValueError("निकालांची संख्या 1 ते 10 असावी.")
    credentials = load_tool_credentials().get("web_search", {})
    key = credentials.get("TAVILY_API_KEY") if isinstance(credentials, dict) else None
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Settings मध्ये Tavily API Key सेव्ह करा.")
    response = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": key.strip(), "query": query.strip(),
              "search_depth": "basic", "max_results": max_results,
              "include_answer": True},
        timeout=30
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("results", []):
        if isinstance(item, dict):
            results.append({
                "title": str(item.get("title", ""))[:300],
                "url": str(item.get("url", ""))[:1000],
                "content": str(item.get("content", ""))[:2000]
            })
    return {"query": query.strip(),
            "answer": str(data.get("answer", ""))[:3000],
            "results": results}


def load_approvals():
    data = load_json(APPROVALS_FILE, [])
    return data if isinstance(data, list) else []


def save_approvals(data):
    save_json(APPROVALS_FILE, data)


def set_approval_status(action_id, status, execution_result=None):
    """Update one approval against the latest queue without overwriting concurrent additions."""
    with APPROVAL_LOCK:
        approvals = load_approvals()
        action = next((item for item in approvals if item.get("id") == action_id), None)
        if action is None:
            return False
        action["status"] = status
        if execution_result is not None:
            action["execution_result"] = execution_result
        save_approvals(approvals)
        return True


def create_tool_approval(tool_name, arguments):
    import datetime
    import uuid
    allowed = {
        "save_memory_item", "update_memory_item", "forget_memory_item",
        "add_note", "delete_note"
    }
    if tool_name not in allowed or not isinstance(arguments, dict):
        raise ValueError("या कृतीसाठी मंजुरी तयार करता येत नाही.")
    now = datetime.datetime.now(datetime.timezone.utc)
    action = {
        "id": str(uuid.uuid4()),
        "action_type": "tool_execution",
        "description": "SHIVAM कृती मंजुरी: " + tool_name,
        "payload": {"tool_name": tool_name, "arguments": arguments},
        "permission_key": "assistant.mutate_data",
        "tier": "high",
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": (now + datetime.timedelta(minutes=5)).isoformat()
    }
    with APPROVAL_LOCK:
        approvals = load_approvals()
        approvals.append(action)
        save_approvals(approvals)
    return action

def create_approval(app_name):
    import datetime
    import uuid
    allowed_apps = {"chrome", "youtube", "gmail", "whatsapp", "camera", "settings", "phone", "maps", "calendar", "contacts", "messages", "clock", "files"}
    if not isinstance(app_name, str) or app_name.strip().lower() not in allowed_apps:
        raise ValueError("हे App परवानगी यादीत नाही.")
    app_name = app_name.strip().lower()

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

    with APPROVAL_LOCK:
        approvals = load_approvals()
        approvals.append(action)
        save_approvals(approvals)
    return action

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def correct_marathi(text):
    """सामान्य मराठी शब्दप्रयोग आणि व्याकरण सुरक्षितपणे सुधारा."""
    if not isinstance(text, str) or not text:
        return text

    text = text.replace("मी शिवम आहे, तुम्हाला AI मदत करायची.", "मी शिवम आहे. मी तुम्हाला AI च्या मदतीने सहाय्य करतो.")

    corrections = {
        "मी तुमचे प्रश्न सोप्या मराठीत उत्तरांसह सोडवतो": "मी तुमच्या प्रश्नांची उत्तरे सोप्या मराठीत देतो",
        "उत्तर देणाराहो": "उत्तर देईन",
        "उत्तर देशोय": "उत्तर देत आहे",
        "इतर भाषा मध्ये": "इतर भाषांमध्ये",
        "तुम्ही कसा समजले?": "तुम्हाला हे समजले का?",
        "आजचा नवीन शिकवणारी गोष्ट": "आजची नवीन शिकवणारी गोष्ट",
        "प्रकाशाची गती कसे जाणवते": "प्रकाशाचा वेग किती आहे?",
        "मला समजला नाही": "मला समजले नाही",
        "मी मदत करू शकतो तुम्हाला": "मी तुम्हाला मदत करू शकतो",
        "तुम्हाला AI मदत करायची": "तुम्हाला AI द्वारे मदत करायची",
        "मी शिवम आहे, तुम्हाला AI मदत करायची": "मी शिवम आहे. मी तुम्हाला AI च्या मदतीने सहाय्य करतो",
        "तुम्ही काय म्हणतो": "तुम्ही काय म्हणता",
        "कृपया करून": "कृपया",
        "माझे नाव आहे शिवम": "माझे नाव शिवम आहे",

        "मला मदत पाहिजे आहे": "मला मदत हवी आहे",
        "मी प्रयत्न करत आहे": "मी प्रयत्न करीत आहे",
        "तुम्ही मला सांगू शकता": "तुम्ही मला सांगू शकाल का?",
        "हे मला माहिती नाही आहे": "हे मला माहीत नाही",
        "माझ्याकडून चूक झाली आहे": "माझी चूक झाली आहे",
        "तुम्हाला काय पाहिजे आहे": "तुम्हाला काय हवे आहे",

    }

    corrections.update({
        "क्या आप मेरी मदद कर सकते हैं": "तुम्ही मला मदत करू शकता का?",
        "मुझे समझ में नहीं आया": "मला समजले नाही",
        "आप कैसे हैं": "तुम्ही कसे आहात",
        "बहुत अच्छा": "खूप छान",
        "धन्यवाद आपका": "तुमचे आभार",
        "कोई बात नहीं": "काही हरकत नाही",
        "मुझे लगता है": "मला वाटते",
        "अभी के लिए": "सध्यापुरते",
        "इसके अलावा": "याशिवाय",
        "कृपया बताइए": "कृपया सांगा",
    })

    corrections.update({
        "मी तुम्हाला मदत करेल": "मी तुम्हाला मदत करीन",
        "तुम्ही कसा आहात?": "तुम्ही कसे आहात?",
        "तुम्ही कुठे जातो?": "तुम्ही कुठे जाता?",
        "तुम्हाला कसे वाटतो?": "तुम्हाला कसे वाटते?",
        "मला हे समजत नाहीये": "मला हे समजत नाही",
        "मी तुमचे आभारी आहे": "मी तुमचा आभारी आहे",
        "तुमचे स्वागत आहे": "तुमचे मनापासून स्वागत आहे",
    })

    corrections.update({
        "How are you?": "तुम्ही कसे आहात?",
        "I am fine": "मी ठीक आहे",
        "Thank you": "धन्यवाद",
        "Good morning": "शुभ सकाळ",
        "Please help me": "कृपया मला मदत करा",
        "I don't understand": "मला समजत नाही",
        "What is your name?": "तुमचे नाव काय आहे?",
        "Where are you going?": "तुम्ही कुठे जात आहात?",
    })

    for wrong, right in corrections.items():
        text = text.replace(wrong, right)

    text = re.sub(r"[ \\t]{2,}", " ", text)
    return text
@contextmanager
def openrouter_stream(client, headers, payload):
    body = dict(payload)

    def send_with_retry(url, req_headers, req_body, provider):
        for attempt in range(3):
            try:
                response = client.send(
                    client.build_request(
                        "POST", url,
                        headers=req_headers,
                        json=req_body
                    ),
                    stream=True
                )
            except httpx.TimeoutException as exc:
                record_recovery_diagnostic(f"{provider}_TIMEOUT_RETRY_{attempt + 1}", exc)
                print(f"[SHIVAM {provider} TIMEOUT RETRY] {attempt + 1}/3: {exc}")
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
                continue
            except httpx.TransportError as exc:
                record_recovery_diagnostic(f"{provider}_TRANSPORT_RETRY_{attempt + 1}", exc)
                print(f"[SHIVAM {provider} RETRY] {attempt + 1}/3: {exc}")
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
                continue

            if (response.status_code in (408, 429) or 500 <= response.status_code <= 599) and attempt < 2:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    retry_delay = min(max(float(retry_after), 0), 30) if retry_after else attempt + 1
                except (TypeError, ValueError):
                    retry_delay = attempt + 1
                record_recovery_diagnostic(f"{provider}_HTTP_{response.status_code}_RETRY_{attempt + 1}", RuntimeError("Provider HTTP retry"))
                print(f"[SHIVAM {provider} RETRY] HTTP {response.status_code}, wait {retry_delay}s, {attempt + 1}/3")
                response.close()
                time.sleep(retry_delay)
                continue
            return response

        raise RuntimeError(provider + " request failed")

    response = None
    try:
        response = send_with_retry(OPENROUTER_URL, headers, body, "OPENROUTER")

        if response.status_code in (402, 404) and body.get("model") != "openrouter/free":
            response.close()
            body["model"] = "openrouter/free"
            body["max_tokens"] = 8192
            body["reasoning"] = {"effort": "low"}
            if body.get("messages") and body["messages"][0].get("role") == "system":
                body["messages"][0]["content"] += "\nसध्या प्रत्यक्ष वापरलेला मॉडेल पर्याय OpenRouter Free Model आहे. त्याला OpenRouter Auto म्हणू नकोस."
            print("[SHIVAM] OpenRouter Free Model वापरत आहे.")
            response = send_with_retry(OPENROUTER_URL, headers, body, "OPENROUTER FREE")

    except httpx.TimeoutException as exc:
        print("[SHIVAM] OpenRouter timeout:", repr(exc))
        if not os.getenv("GROQ_API_KEY"):
            raise
        response = None
    except httpx.TransportError as exc:
        print("[SHIVAM] OpenRouter network failure:", repr(exc))
        if not os.getenv("GROQ_API_KEY"):
            raise
        response = None

    if response is None or (
        (response.status_code in (404, 408, 429) or 500 <= response.status_code <= 599)
        and os.getenv("GROQ_API_KEY")
    ):
        if response is not None:
            print("[SHIVAM] OpenRouter अनुपलब्ध. Groq पर्यायी सेवा वापरत आहे.")
            response.close()

        groq_body = dict(body)
        groq_body["model"] = "openai/gpt-oss-20b"
        groq_body["max_tokens"] = 2048
        groq_body["reasoning_effort"] = "low"
        groq_body.pop("reasoning", None)
        groq_headers = {
            "Authorization": "Bearer " + os.getenv("GROQ_API_KEY"),
            "Content-Type": "application/json"
        }
        try:
            response = send_with_retry(
                "https://api.groq.com/openai/v1/chat/completions",
                groq_headers, groq_body, "GROQ"
            )
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise RuntimeError("OpenRouter आणि Groq दोन्ही सेवा उपलब्ध नाहीत: " + str(exc)) from exc
        if response.status_code != 200:
            error_text = response.read().decode("utf-8", errors="replace")
            response.close()
            raise RuntimeError("Groq API error " + str(response.status_code) + ": " + error_text[:1000])
        response.extensions["jarvis_model"] = "Groq: openai/gpt-oss-20b"

    if not response.extensions.get("jarvis_model"):
        response.extensions["jarvis_model"] = body.get("model", "")

    try:
        yield response
    finally:
        response.close()




def friendly_provider_error(status_code, error_text="", provider="AI"):
    messages = {
        401: "AI सेवा वापरण्यासाठी API Key योग्य नाही. API Key तपासा.",
        403: "AI सेवेकडून प्रवेश नाकारला गेला. API परवानग्या तपासा.",
        402: "AI सेवेचा उपलब्ध वापर किंवा क्रेडिट संपला आहे.",
        404: "निवडलेले AI मॉडेल सध्या उपलब्ध नाही.",
        408: "AI सेवेकडून उत्तर मिळण्यास वेळ लागला. पुन्हा प्रयत्न करा.",
        429: "AI सेवेची वापर मर्यादा पूर्ण झाली आहे. थोड्या वेळाने पुन्हा प्रयत्न करा.",
        500: "AI सेवेमध्ये अंतर्गत अडचण आहे. पुन्हा प्रयत्न करा.",
        502: "AI सेवा सध्या योग्य प्रतिसाद देत नाही.",
        503: "AI सेवा तात्पुरती अनुपलब्ध आहे.",
        504: "AI सेवेकडून उत्तर मिळण्यास खूप वेळ लागला."
    }
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        code = 0
    return messages.get(
        code,
        "AI कडून उत्तर मिळवताना अडचण आली. कृपया पुन्हा प्रयत्न करा."
    )


def safe_stream_lines(response, stage):
    completed = False
    interrupted = False
    try:
        try:
            for line in response.iter_lines():
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                if line.startswith("data:") and line[5:].strip() == "[DONE]":
                    if completed:
                        continue
                    completed = True
                yield line
        except httpx.TimeoutException as exc:
            interrupted = True
            print(f"[SHIVAM STREAM TIMEOUT] {stage}: {exc!r}")
            warning = {
                "choices": [{
                    "delta": {
                        "content": "\\n[उत्तर मिळण्यास वेळ लागला आणि प्रवाह थांबला. उपलब्ध उत्तर येथे दिले आहे.]"
                    }
                }]
            }
            yield "data: " + json.dumps(warning, ensure_ascii=False)
        except (httpx.TransportError, OSError, TimeoutError) as exc:
            interrupted = True
            print(f"[SHIVAM STREAM INTERRUPTED] {stage}: {exc!r}")
            warning = {
                "choices": [{
                    "delta": {
                        "content": "\\n[उत्तराचा प्रवाह मध्येच खंडित झाला. उपलब्ध उत्तर येथे दिले आहे.]"
                    }
                }]
            }
            yield "data: " + json.dumps(warning, ensure_ascii=False)

        if not completed and not interrupted:
            print(f"[SHIVAM STREAM INCOMPLETE] {stage}: DONE event missing")
            warning = {
                "choices": [{
                    "delta": {
                        "content": "\\n[उत्तराचा प्रवाह पूर्ण होण्यापूर्वी थांबला. उपलब्ध उत्तर येथे दिले आहे.]"
                    }
                }]
            }
            yield "data: " + json.dumps(warning, ensure_ascii=False)
    finally:
        try:
            response.close()
        except Exception as exc:
            print(f"[SHIVAM STREAM CLOSE] {stage}: {exc!r}")



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


def is_sensitive_memory(key, value):
    text = str(key) + " " + str(value)
    if str(key).strip().isdigit():
        return True
    return bool(re.search(
        r"password|passcode|api.?key|secret|token|otp|पासवर्ड|गुप्त.?कळ|"
        r"(?:jarvis|shivam)[-_ ]?\d{3,}",
        text, re.I
    ))



def _read_notes():
    notes = load_json(NOTES_FILE, [])
    if not isinstance(notes, list) or not all(isinstance(item, dict) for item in notes):
        raise ValueError("notes.json मधील माहिती योग्य स्वरूपात नाही.")
    return notes


def _write_notes(notes):
    temp_path = NOTES_FILE + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(notes, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.chmod(temp_path, 0o600)
    os.replace(temp_path, NOTES_FILE)
    os.chmod(NOTES_FILE, 0o600)


def add_note(text, title=""):
    import uuid
    text = str(text).strip()
    title = str(title).strip()
    if not text or len(text) > 10000:
        return {"success": False, "error": "नोंदीचा मजकूर 1 ते 10000 अक्षरांचा असावा."}
    if len(title) > 200:
        return {"success": False, "error": "नोंदीचे शीर्षक 200 अक्षरांपेक्षा मोठे नसावे."}
    notes = _read_notes()
    note = {
        "id": str(uuid.uuid4()),
        "title": title,
        "text": text,
        "created_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    }
    notes.append(note)
    _write_notes(notes)
    return {"success": True, "note": note}


def list_notes():
    notes = _read_notes()
    return {"success": True, "count": len(notes), "notes": notes}


def search_notes(query):
    query = str(query).strip().casefold()
    if not query:
        return {"success": False, "error": "शोधण्यासाठी शब्द द्या."}
    matches = [
        note for note in _read_notes()
        if query in str(note.get("title", "")).casefold()
        or query in str(note.get("text", "")).casefold()
    ]
    return {"success": True, "count": len(matches), "notes": matches}


def delete_note(note_id):
    note_id = str(note_id).strip()
    notes = _read_notes()
    remaining = [note for note in notes if str(note.get("id", "")) != note_id]
    if len(remaining) == len(notes):
        return {"success": False, "error": "या ID ची नोंद सापडली नाही."}
    _write_notes(remaining)
    return {"success": True, "message": "नोंद हटवली आहे."}


def verify_tool_result(result):
    """Tool निकालातील यश, अपयश आणि मंजुरीची प्रतीक्षा वेगळी ओळखा."""
    if not isinstance(result, dict):
        return {"success": result is not None, "status": "success" if result is not None else "error"}
    payload = result.get("result", result)
    if isinstance(payload, dict):
        if payload.get("pending_approval") is True:
            return {"success": False, "status": "pending_approval"}
        if payload.get("success") is False or payload.get("error") or result.get("error"):
            return {"success": False, "status": "error"}
    elif result.get("error"):
        return {"success": False, "status": "error"}
    return {"success": True, "status": "success"}


def retry_read_operation(operation, stage):
    """फक्त सुरक्षित read-only कामात exception आल्यास एकदाच पुनर्प्रयत्न."""
    try:
        return operation()
    except Exception as first_error:
        record_recovery_diagnostic(str(stage) + "_RETRY_1", first_error)
        try:
            time.sleep(0.2)
            return operation()
        except Exception as retry_error:
            record_recovery_diagnostic(str(stage) + "_RETRY_2", retry_error)
            raise


def validate_tool_arguments(tool_name, arguments, tool_specs):
    if not isinstance(arguments, dict):
        return "Tool Arguments अवैध आहेत."
    spec = next((x.get("function", {}) for x in tool_specs
                 if x.get("function", {}).get("name") == tool_name), None)
    if not spec:
        return "हे Tool उपलब्ध किंवा अनुमत नाही."
    schema = spec.get("parameters", {})
    props = schema.get("properties", {})
    if schema.get("additionalProperties") is False and set(arguments) - set(props):
        return "अनोळखी Tool Arguments आहेत."
    for key in schema.get("required", []):
        if key not in arguments:
            return "आवश्यक Tool माहिती अपूर्ण आहे."
    for key, value in arguments.items():
        rule = props.get(key, {})
        kind = rule.get("type")
        valid = (
            kind is None
            or (kind == "string" and isinstance(value, str))
            or (kind == "integer" and isinstance(value, int) and not isinstance(value, bool))
            or (kind == "number" and isinstance(value, (int, float)) and not isinstance(value, bool))
            or (kind == "boolean" and isinstance(value, bool))
            or (kind == "object" and isinstance(value, dict))
            or (kind == "array" and isinstance(value, list))
        )
        if not valid:
            return "Tool मधील " + key + " चा प्रकार चुकीचा आहे."
        if "enum" in rule and value not in rule["enum"]:
            return "Tool मधील " + key + " साठी मूल्य अनुमत नाही."
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in rule and value < rule["minimum"]:
                return key + " किमान मर्यादेपेक्षा कमी आहे."
            if "maximum" in rule and value > rule["maximum"]:
                return key + " कमाल मर्यादेपेक्षा जास्त आहे."
    return None


def classify_user_intent(text):
    """वापरकर्त्याच्या संदेशाचा प्राथमिक हेतू ओळखा."""
    value = str(text or "").casefold()

    rules = (
        ("memory", ("आठव", "मागे सांगितले", "माझी माहिती", "विसर", "जतन कर", "memory", "remember", "previous conversation")),
        ("calculation", ("किती बेरीज", "गुणाकार", "भागाकार", "हिशोब", "calculate", "calculator", "solve", " + ", " × ", " ÷ ")),
        ("web_search", ("इंटरनेटवर शोध", "वेब सर्च", "ताजी माहिती", "बातम्या", "शोधून सांग", "search online", "web search", "latest news", "research", "सरकारी योजना", "शासकीय योजना", "योजनेची पात्रता", "योजनेचा अर्ज", "government scheme", "government schemes", "scheme eligibility", "सरकारची योजना", "महाराष्ट्र योजना")),
        ("weather", ("हवामान", "पाऊस", "तापमान", "थंडी", "weather", "forecast")),
        ("time", ("आत्ताची वेळ", "आजची तारीख", "आज कोणता वार", "current time", "today's date")),
        ("device_action", ("उघड", "सुरू कर", "चालू कर", "बंद कर", "लॉन्च", "open app", "close app", "launch")),
    )

    for intent, keywords in rules:
        if any(word in value for word in keywords):
            return intent
    return "general"


def intent_guidance(intent):
    guidance = {
        "memory": "हा Memory संदर्भातील प्रश्न आहे. आवश्यक असल्यास संबंधित Memory किंवा संभाषण शोधूनच उत्तर दे.",
        "calculation": "हा गणिताचा प्रश्न असू शकतो. शक्य असल्यास smart_calculate Tool वापरून अचूक गणना कर.",
        "weather": "हा हवामानाचा प्रश्न आहे. get_weather Tool वापर आणि उपलब्ध माहितीपुरतेच उत्तर दे.",
        "time": "वेळ, तारीख किंवा वार विचारले असल्यास get_current_time Tool वापर.",
        "device_action": "ही Android कृतीची विनंती असू शकते. आवश्यक Tool वापर; आवश्यक मंजुरीशिवाय कृती करू नकोस.",
        "general": "प्रश्नाचा संदर्भ समजून योग्य Tool आवश्यक असल्यास वापर. माहिती नसेल तर अंदाज लावू नकोस."
    }
    return guidance.get(intent, guidance["general"])


def build_system_prompt():
    prompt = load_prompt()
    prompt = prompt.replace(
        "तुझे नाव JARVIS आहे.",
        "तुझे नाव SHIVAM (शिवम) आहे.",
        1
    )
    prompt = prompt.replace(
        "स्वतःला Flint किंवा Recursive म्हणू नकोस.",
        "स्वतःला JARVIS, Flint किंवा Recursive म्हणू नकोस.",
        1
    )
    prompt += (
        "प्रत्येक उत्तर पाठवण्यापूर्वी मनातल्या मनात मराठी व्याकरण आणि वाक्यरचना तपास. "
        "अर्थहीन, चुकीचे किंवा अर्धवट शब्दप्रयोग वापरू नकोस. "
        "हिंदी आणि मराठी शब्दांची अनावश्यक सरमिसळ करू नकोस. "
        "वाक्य नैसर्गिक, पूर्ण आणि स्पष्ट मराठीत पुन्हा मांड. "
"मी उत्तर देईन, मी उत्तर देत आहे, मला समजले, मी मदत करू शकतो असे योग्य शब्दप्रयोग वापर. "
"लिंग, वचन, काळ, विभक्ती आणि क्रियापद यांचे व्याकरण जुळव. "
"हिंदी ढंगाची वाक्यरचना टाळ आणि संभाषणातील मराठी भाषा नैसर्गिक ठेव. "
"अतिशय अवघड किंवा कृत्रिम शब्दांऐवजी सर्वसामान्यांना समजणारे मराठी शब्द वापर. "
        "उदाहरणार्थ, 'हा वेळतून' असे चुकीचे वाक्य न वापरता 'मी नेहमी सोप्या मराठीत उत्तर देतो' असे लिही. "
        "मागील संभाषणाचा उपलब्ध संदर्भ वापर. "
        "वापरकर्त्याने सध्याची वेळ, तारीख किंवा वार विचारल्यास "
        "get_current_time Tool नक्की वापर. "
        "Tool मधून मिळालेल्या अचूक माहितीनुसारच उत्तर दे. "
        "Android App उघडण्यापूर्वी वापरकर्त्याची स्पष्ट मंजुरी आवश्यक आहे. "
        "मंजुरी मिळेपर्यंत App उघडू नकोस. "
        "जतन केलेली माहिती शोधण्यासाठी search_memory Tool वापर. " +
        "वापरकर्ता आधीच्या संभाषणाचा, निर्णयाचा, पसंतीचा किंवा प्रोजेक्टच्या प्रगतीचा संदर्भ देत असल्यास उत्तर देण्यापूर्वी संबंधित Memory शोध. " +
        "शोधताना प्रश्नातील मुख्य शब्द, प्रोजेक्टचे नाव आणि संबंधित Category वापर. " +
        "सापडलेल्या माहितीचा सध्याच्या प्रश्नाशी संबंध तपासूनच उत्तरात वापर. " +
        "असंबंधित Memory उत्तरात आणू नकोस. " +
        "Memory मध्ये माहिती सापडली नाही तर अंदाजाने जुनी माहिती तयार करू नकोस; स्पष्टपणे सांग. " +
        "वापरकर्त्याने स्पष्टपणे सांगितलेली दीर्घकाळ उपयोगी माहिती ओळखून योग्य Category मध्ये जतन कर. " +
        "भाषा, उत्तर देण्याची पद्धत आणि कायमच्या आवडी preference मध्ये जतन कर. " +
        "प्रोजेक्टचे नाव, उद्दिष्टे, तांत्रिक निर्णय आणि प्रगती project मध्ये जतन कर. " +
        "पुढील संभाषणात उपयोगी ठरणारे स्पष्ट वैयक्तिक संदर्भ personal_context मध्ये जतन कर. " +
        "तात्पुरते प्रश्न, एकदाच केलेल्या विनंत्या किंवा AI चे स्वतःचे अंदाज Memory मध्ये जतन करू नकोस. " +
        "जतन करण्यापूर्वी search_memory वापरून आधीची माहिती तपास. " +
        "माहिती आधीपासून असल्यास नवीन Duplicate तयार करू नकोस. " +
        "नवीन माहिती जतन करण्यासाठी save_memory_item Tool वापर. "
        "नवीन माहिती जतन करण्यापूर्वी Memory मधील Key तपास आणि समान माहिती पुन्हा जतन करू नकोस. "
        "आधीची माहिती बदलण्याची स्पष्ट विनंती असल्यास update_memory_item Tool वापर. "
        "जतन केलेली माहिती विसरण्याची स्पष्ट विनंती असल्यास forget_memory_item Tool वापर. "
        "Update किंवा Forget करण्यापूर्वी संबंधित अचूक Memory Key शोध. "
        "Key निश्चित नसेल तर स्पष्टीकरण विचार. "
        "पासवर्ड, API Keys, OTP किंवा संवेदनशील माहिती जतन करू नकोस. "
        "Memory Tool यशस्वी झाल्याशिवाय माहिती जतन, अपडेट किंवा हटवली असे सांगू नकोस. "
        "तथ्यात्मक प्रश्नांची उत्तरे देताना उपलब्ध पुरावा आणि खात्री यांचा विचार कर. "
        "माहिती खात्रीशीर नसेल तर अनिश्चितता स्पष्ट सांग; अंदाजाला तथ्य म्हणून मांडू नकोस. "
        "गणिती उत्तरासाठी उपलब्ध Calculator Tool वापर आणि त्याचा निकाल बदलू नकोस. "
        "वेळ, हवामान, डिव्हाइस आणि Memory बाबत प्रत्यक्ष Tool निकालालाच प्राधान्य दे. "
        "महत्त्वाचे तथ्य सांगण्यापूर्वी उपलब्ध पुरावे तपास. "
        "ताजी किंवा बदलणारी माहिती असल्यास Web Search किंवा योग्य Tool वापर. "
        "सरकारी योजना, पात्रता, लाभ, कागदपत्रे, अर्ज प्रक्रिया, अंतिम तारीख किंवा अर्जस्थिती विचारल्यास Web Search Tool वापरून केंद्र किंवा संबंधित राज्य सरकारच्या अधिकृत वेबसाइटना प्राधान्य दे. " +
        "महाराष्ट्रातील योजनांसाठी महाराष्ट्र शासनाचे अधिकृत पोर्टल आणि केंद्राच्या योजनांसाठी संबंधित मंत्रालयाचे अधिकृत पोर्टल तपास. " +
        "योजनेचे नाव, पात्रता, लाभाची रक्कम, तारीख किंवा कागदपत्रे अधिकृत स्रोताने पुष्टी न केल्यास निश्चित म्हणून सांगू नकोस. " +
        "अधिकृत स्रोत उपलब्ध नसल्यास ते स्पष्ट सांग आणि अर्जापूर्वी अधिकृत विभागाकडून खात्री करण्यास सांग. " +
        "Search किंवा Tool वापरला नसेल तर तपासल्याचा दावा करू नकोस. "
        "स्रोतांमध्ये विरोधाभास असल्यास तो स्पष्ट सांग. "
        "पुरावा अपुरा असल्यास संभाव्य उत्तर आणि खात्रीशीर तथ्य यांत फरक ठेव. "
        "नावे, तारखा, आकडे, आवृत्त्या आणि तांत्रिक तपशील स्वतःहून तयार करू नकोस. "
        "Tool कडून मिळालेला निकाल बदलू नकोस किंवा त्यात नसलेली माहिती जोडू नकोस. "
        "Memory मधील जुनी माहिती सध्याची आहे असे पडताळणीशिवाय सांगू नकोस. "
        "उत्तर देण्यासाठी आवश्यक माहिती उपलब्ध नसेल तर स्पष्टपणे सांग किंवा एक नेमका प्रश्न विचार. "
        "Tool अपयशी ठरल्यास कृती पूर्ण झाली असे सांगू नकोस. "
        "वापरकर्त्याने दिलेली माहिती आणि तुझा निष्कर्ष यांत फरक स्पष्ट ठेव. "
        "उत्तर प्रश्नापुरते नेमके, सुसंगत आणि अनावश्यक पुनरावृत्तीविरहित ठेव. "
    )

    memory = load_json(MEMORY_FILE, {})
    categories = load_json(MEMORY_CATEGORIES_FILE, {})
    allowed_categories = ("preference", "project", "personal_context", "general")

    if isinstance(memory, dict) and memory:
        if not isinstance(categories, dict):
            categories = {}

        grouped = {category: [] for category in allowed_categories}
        for key, value in memory.items():
            if not isinstance(value, str) or is_sensitive_memory(key, value):
                continue

            category = categories.get(key, "general")
            if category not in allowed_categories:
                category = "general"

            grouped[category].append("- " + str(key) + ": " + value)

        labels = {
            "preference": "वापरकर्त्याच्या पसंती",
            "project": "प्रोजेक्ट माहिती",
            "personal_context": "वैयक्तिक संदर्भ",
            "general": "इतर माहिती"
        }

        sections = []
        for category in allowed_categories:
            if grouped[category]:
                sections.append(
                    labels[category] + ":\\n" + "\\n".join(grouped[category][-20:])
                )

        if sections:
            prompt += "\\nलक्षात ठेवलेली माहिती (Category नुसार):\\n"
            prompt += "\\n".join(sections)[:3000]

    return prompt






def infer_memory_category(key, value):
    """माहितीच्या आशयानुसार प्राथमिक Memory Category निवडा."""
    text = (str(key) + " " + str(value)).casefold()

    preference_words = (
        "पसंती", "आवड", "सूचना", "कार्यपद्धती", "नेहमी",
        "कायम", "preference", "prefer", "always", "style"
    )
    project_words = (
        "प्रोजेक्ट", "प्रकल्प", "कोड", "अॅप", "ॲप",
        "project", "github", "termux", "api", "development"
    )
    personal_words = (
        "माझे नाव", "माझं नाव", "माझे काम", "माझा व्यवसाय",
        "my name", "my job", "my business", "family"
    )

    if any(word in text for word in preference_words):
        return "preference"
    if any(word in text for word in project_words):
        return "project"
    if any(word in text for word in personal_words):
        return "personal_context"
    return "general"


def memory_integrity_check():
    """Memory आणि Category फाइलमधील सुसंगतता तपासा; नोंदी बदलू नका."""
    memory = load_json(MEMORY_FILE, {})
    categories = load_json(MEMORY_CATEGORIES_FILE, {})
    if not isinstance(memory, dict):
        return {"error": "Memory फाइलमध्ये वैध Dictionary नाही."}
    if not isinstance(categories, dict):
        return {"error": "Category फाइलमध्ये वैध Dictionary नाही."}

    allowed = ("preference", "project", "personal_context", "general")
    missing = sum(1 for key in memory if key not in categories)
    invalid = sum(1 for key in memory if categories.get(key, "general") not in allowed)
    orphan = sum(1 for key in categories if key not in memory)
    sensitive = sum(
        1 for key, value in memory.items()
        if isinstance(value, str) and is_sensitive_memory(key, value)
    )

    return {
        "total_memory": len(memory),
        "total_categories": len(categories),
        "missing_categories": missing,
        "invalid_categories": invalid,
        "orphan_categories": orphan,
        "sensitive_entries_excluded_from_search": sensitive,
        "integrity": "needs_attention" if (missing or invalid or orphan) else "ok",
        "note": "हा तपासणी अहवाल आहे. कोणतीही Memory नोंद बदललेली नाही."
    }






def memory_dashboard():
    """Memory ची Category नुसार आकडेवारी आणि आरोग्य दाखवा."""
    memory = load_json(MEMORY_FILE, {})
    categories = load_json(MEMORY_CATEGORIES_FILE, {})
    if not isinstance(memory, dict):
        return {"error": "Memory फाइल अवैध आहे."}
    if not isinstance(categories, dict):
        categories = {}
    counts = {"preference": 0, "project": 0, "personal_context": 0, "general": 0}
    sensitive = 0
    for key, value in memory.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if is_sensitive_memory(key, value):
            sensitive += 1
            continue
        category = categories.get(key) or infer_memory_category(key, value)
        if category not in counts:
            category = "general"
        counts[category] += 1
    return {
        "total_safe_memories": sum(counts.values()),
        "category_counts": counts,
        "sensitive_entries_excluded": sensitive,
        "backup_count": list_memory_backups().get("count", 0)
    }


def detect_memory_conflicts():
    """समान अर्थाच्या Key मधील संभाव्य विरोधाभास शोधा; बदल करू नका."""
    memory = load_json(MEMORY_FILE, {})
    if not isinstance(memory, dict):
        return {"error": "Memory फाइल अवैध आहे."}
    entries = []
    for key, value in memory.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if is_sensitive_memory(key, value):
            continue
        words = set(re.findall(r"[a-zA-Z0-9अ-ह]+", key.lower()))
        if words:
            entries.append((key, value, words))
    conflicts = []
    for i, (key1, value1, words1) in enumerate(entries):
        for key2, value2, words2 in entries[i + 1:]:
            overlap = len(words1 & words2) / max(1, min(len(words1), len(words2)))
            if overlap >= 0.6 and value1.strip().casefold() != value2.strip().casefold():
                conflicts.append({
                    "key_1": key1, "value_1": value1,
                    "key_2": key2, "value_2": value2,
                    "reason": "समान Key शब्द; मूल्य वेगवेगळे. कृपया पडताळा."
                })
                if len(conflicts) >= 30:
                    break
        if len(conflicts) >= 30:
            break
    return {"possible_conflicts": len(conflicts), "items": conflicts,
            "note": "ही संभाव्य जुळणी आहे; आपोआप कोणतीही Memory बदललेली नाही."}


def recall_conversation_context(query="", limit=8):
    """जुन्या संभाषणातून सर्वाधिक संबंधित संदर्भ शोधा."""
    if not isinstance(query, str) or not query.strip():
        return {"error": "शोधण्यासाठी प्रश्न किंवा शब्द आवश्यक आहेत."}

    try:
        limit = max(1, min(int(limit), 12))
    except (TypeError, ValueError):
        limit = 8

    history = load_history()
    normalized_query = " ".join(query.casefold().split())
    stop_words = {
        "आहे", "आहेत", "होते", "होता", "होती", "मला", "माझे",
        "माझा", "माझी", "तुझे", "तुमचे", "काय", "कसे", "कशी",
        "आणि", "किंवा", "कर", "करा", "the", "is", "are", "was",
        "what", "when", "where", "how", "did", "you", "me"
    }
    terms = [
        term for term in re.findall(r"[^\W_]+", normalized_query, re.UNICODE)
        if len(term) > 1 and term not in stop_words
    ]

    if not terms:
        return {"query": query, "matches": [], "count": 0}

    matches = []
    for position, item in enumerate(history):
        content = item.get("content", "")
        if not isinstance(content, str):
            continue

        lowered = " ".join(content.casefold().split())
        score = sum(min(lowered.count(term), 3) for term in set(terms))

        if normalized_query in lowered:
            score += 5

        if score:
            matches.append({
                "role": item.get("role", ""),
                "content": content[:700],
                "match_score": score,
                "_position": position
            })

    matches.sort(
        key=lambda item: (item["match_score"], item["_position"]),
        reverse=True
    )

    results = [
        {key: value for key, value in item.items() if key != "_position"}
        for item in matches[:limit]
    ]
    return {"query": query, "matches": results, "count": len(results)}

def preview_memory_backup(filename):
    """Backup पुनर्संचयित करण्यापूर्वी सुरक्षितपणे तपासा; फाइल बदलू नका."""
    if not isinstance(filename, str) or os.path.basename(filename) != filename:
        return {"error": "Backup फाइलचे नाव अवैध आहे."}
    if not filename.endswith(".json") or not filename.startswith(("memory_", "memory_categories_")):
        return {"error": "ही अनुमत Memory Backup फाइल नाही."}
    path = os.path.join(BASE_DIR, "MEMORY_BACKUPS", filename)
    if not os.path.isfile(path):
        return {"error": "Backup फाइल सापडली नाही."}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"error": "Backup मधील JSON Dictionary नाही."}
        return {
            "valid": True,
            "filename": filename,
            "entries": len(data),
            "size_bytes": os.path.getsize(path),
            "restore_status": "preview_only",
            "message": "Backup वैध आहे. मूळ Memory मध्ये कोणताही बदल केलेला नाही."
        }
    except Exception as exc:
        return {"valid": False, "error": type(exc).__name__}


def list_memory_backups():
    """स्थानिक Memory Backups ची यादी आणि JSON वैधता तपासा."""
    folder = os.path.join(BASE_DIR, "MEMORY_BACKUPS")
    if not os.path.isdir(folder):
        return {"count": 0, "backups": [], "message": "अजून Backup उपलब्ध नाही."}

    backups = []
    for filename in sorted(os.listdir(folder), reverse=True):
        if not filename.endswith(".json"):
            continue
        if not filename.startswith(("memory_", "memory_categories_")):
            continue

        path = os.path.join(folder, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
            valid = True
        except Exception:
            valid = False

        stat = os.stat(path)
        backups.append({
            "file": filename,
            "valid_json": valid,
            "size_bytes": stat.st_size,
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        })

    return {"count": len(backups), "backups": backups[:20]}


def backup_memory_state():
    """Memory बदलण्यापूर्वी पडताळलेला बॅकअप; जुने बॅकअप कधीही आपोआप हटवू नका."""
    stage = "backup_start"
    folder = os.path.join(BASE_DIR, "MEMORY_BACKUPS")
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    created = []

    for name in ("memory.json", "memory_categories.json"):
        source = os.path.join(BASE_DIR, name)
        if not os.path.isfile(source):
            print("[SHIVAM MEMORY]", stage, name, "not_present")
            continue

        stage = "backup_" + name
        with open(source, "r", encoding="utf-8") as src:
            original = json.load(src)
        if not isinstance(original, dict):
            raise ValueError(name + " मध्ये JSON Dictionary अपेक्षित आहे.")

        target_name = name.replace(".json", "_" + stamp + ".json")
        target = os.path.join(folder, target_name)
        shutil.copy2(source, target)
        with open(target, "r", encoding="utf-8") as check:
            copied = json.load(check)
        if copied != original:
            raise IOError("Backup पडताळणी अयशस्वी: " + target_name)
        created.append(target_name)
        print("[SHIVAM MEMORY]", stage, "verified", target_name)

    return created


def _write_memory_json_atomic(path, data):
    """त्याच फोल्डरमध्ये temp लिहा, fsync व JSON पडताळणी करूनच replace करा."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=BASE_DIR,
            prefix=".memory-safe-", suffix=".tmp", delete=False
        ) as temp:
            temp_path = temp.name
            json.dump(data, temp, ensure_ascii=False, indent=4)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())

        with open(temp_path, "r", encoding="utf-8") as check:
            verified = json.load(check)
        if verified != data:
            raise IOError("तात्पुरत्या JSON फाइलची पडताळणी अयशस्वी.")

        os.replace(temp_path, path)
        temp_path = None
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def save_memory_item(key, value, category="general"):
    stage = "validate"
    try:
        if not isinstance(key, str) or not isinstance(value, str):
            return {"success": False, "error": "Memory माहिती अवैध आहे.", "stage": stage}

        key = key.strip()[:80]
        value = " ".join(value.strip().split())[:500]

        if not key or not value:
            return {"success": False, "error": "Memory Key आणि Value आवश्यक आहेत.", "stage": stage}
        allowed_categories = ("preference", "project", "personal_context", "general")
        if category in (None, "", "auto"):
            category = infer_memory_category(key, value)
        if category not in allowed_categories:
            return {"success": False, "error": "Memory Category अवैध आहे.", "stage": stage}
        if is_sensitive_memory(key, value):
            return {"success": False, "error": "संवेदनशील माहिती सुरक्षिततेसाठी Memory मध्ये जतन केली जाणार नाही.", "stage": stage}

        stage = "read_existing_memory"
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as source:
                memory = json.load(source)
            if not isinstance(memory, dict):
                raise ValueError("memory.json मध्ये JSON Dictionary अपेक्षित आहे; मूळ फाइल बदललेली नाही.")
        else:
            memory = {}

        normalized_value = " ".join(
            re.sub(r"[^\w\s]", " ", value.casefold()).split()
        )
        for existing_key, existing_value in memory.items():
            if not isinstance(existing_value, str):
                continue
            existing_normalized = " ".join(
                re.sub(r"[^\w\s]", " ", existing_value.casefold()).split()
            )
            if existing_normalized == normalized_value:
                if existing_key == key:
                    return {"success": True, "result": "हीच Memory आधीपासून जतन आहे. Duplicate तयार केली नाही."}
                return {
                    "success": True,
                    "result": "ही माहिती आधीपासून '" + str(existing_key) +
                              "' या Key खाली जतन आहे. Duplicate तयार केली नाही."
                }

        if key in memory:
            return {
                "success": False,
                "error": "ही Key आधीपासून अस्तित्वात आहे. जुनी माहिती बदलण्यासाठी update_memory_item वापरा.",
                "stage": "duplicate_key"
            }

        stage = "read_existing_categories"
        if os.path.exists(MEMORY_CATEGORIES_FILE):
            with open(MEMORY_CATEGORIES_FILE, "r", encoding="utf-8") as source:
                categories = json.load(source)
            if not isinstance(categories, dict):
                raise ValueError("memory_categories.json मध्ये JSON Dictionary अपेक्षित आहे; मूळ फाइल बदललेली नाही.")
        else:
            categories = {}

        stage = "backup"
        backups = backup_memory_state()

        updated_memory = dict(memory)
        updated_memory[key] = value
        updated_categories = dict(categories)
        updated_categories[key] = category

        stage = "write_memory"
        _write_memory_json_atomic(MEMORY_FILE, updated_memory)
        print("[SHIVAM MEMORY]", stage, "success", "entries", len(updated_memory))

        try:
            stage = "write_categories"
            _write_memory_json_atomic(MEMORY_CATEGORIES_FILE, updated_categories)
            print("[SHIVAM MEMORY]", stage, "success", "entries", len(updated_categories))
        except Exception:
            stage = "rollback_memory"
            _write_memory_json_atomic(MEMORY_FILE, memory)
            print("[SHIVAM MEMORY]", stage, "success")
            raise

        print("[SHIVAM MEMORY]", "complete", "key_saved", "category", category)
        return {
            "success": True,
            "result": "नवीन Memory सुरक्षितपणे जतन झाली. Category: " + category,
            "stage": "complete",
            "backups": backups
        }

    except Exception as exc:
        print("[SHIVAM MEMORY ERROR]", stage, type(exc).__name__, str(exc)[:300])
        try:
            record_recovery_diagnostic("save_memory_item:" + stage, exc)
        except Exception as diagnostic_error:
            print("[SHIVAM MEMORY DIAGNOSTIC ERROR]", type(diagnostic_error).__name__)
        return {
            "success": False,
            "error": "Memory जतन करता आली नाही.",
            "stage": stage,
            "reason": type(exc).__name__ + ": " + str(exc)[:200],
            "original_data_preserved": True
        }

def auto_save_explicit_preference(user_text):
    if not isinstance(user_text, str):
        return None
    match = re.search(
        r"(?:ही|हे)\s+(?:माझी|माझे|माझा)\s+कायम(?:ची|स्वरूपी)\s+(कार्यपद्धती|पसंती|सूचना)\s+आहे",
        user_text
    )
    if not match:
        return None
    value = user_text[:match.start()].strip(" \t\n\"'“”‘’.,।")
    if not value or len(value) > 500:
        return None
    if re.search(r"password|api.?key|otp|पासवर्ड|गुप्त.?कळ", value, re.I):
        return None
    key = {
        "कार्यपद्धती": "कामाची-पद्धत",
        "पसंती": "कायमची-पसंती",
        "सूचना": "कायमची-सूचना"
    }[match.group(1)]
    result = save_memory_item(key, value, "preference")
    print("[SHIVAM AUTO MEMORY]", result)
    return result


def update_memory_item(key, value):
    if not isinstance(key, str) or not isinstance(value, str):
        return {"error": "Memory माहिती अवैध आहे."}

    key = key.strip()[:80]
    value = " ".join(value.strip().split())[:500]

    if not key or not value:
        return {"error": "Memory Key आणि Value आवश्यक आहेत."}

    if is_sensitive_memory(key, value):
        return {"error": "संवेदनशील माहिती सुरक्षिततेसाठी Memory मध्ये अपडेट केली जाणार नाही."}

    memory = load_json(MEMORY_FILE, {})
    if not isinstance(memory, dict) or key not in memory:
        return {"error": "ही Memory Key सापडली नाही."}

    normalized_value = " ".join(
        __import__("re").sub(r"[^\\w\\s]", " ", value.casefold()).split()
    )
    for other_key, other_value in memory.items():
        if other_key == key or not isinstance(other_value, str):
            continue
        existing = " ".join(
            __import__("re").sub(r"[^\\w\\s]", " ", other_value.casefold()).split()
        )
        if existing == normalized_value:
            return {"error": "ही माहिती दुसऱ्या '" + str(other_key) + "' Key खाली आधीपासून आहे."}

    if memory[key] == value:
        return {"result": "माहिती आधीपासून तशीच आहे. बदल केला नाही."}

    backup_memory_state()
    memory[key] = value
    save_json(MEMORY_FILE, memory)
    return {"result": "Memory यशस्वीपणे अपडेट झाली."}


def forget_memory_item(key):
    if not isinstance(key, str) or not key.strip():
        return {"error": "अचूक Memory Key आवश्यक आहे."}

    key = key.strip()
    memory = load_json(MEMORY_FILE, {})

    if not isinstance(memory, dict) or key not in memory:
        return {"error": "ही Memory Key सापडली नाही."}

    backup_memory_state()
    del memory[key]
    save_json(MEMORY_FILE, memory)
    categories = load_json(MEMORY_CATEGORIES_FILE, {})
    if isinstance(categories, dict) and key in categories:
        del categories[key]
        save_json(MEMORY_CATEGORIES_FILE, categories)
    return {"result": "निवडलेली Memory हटवली आहे."}



def memory_maintenance():
    """फक्त अवैध नोंदी आणि अनाथ Category नोंदी साफ करा."""
    memory = load_json(MEMORY_FILE, {})
    categories = load_json(MEMORY_CATEGORIES_FILE, {})

    if not isinstance(memory, dict):
        memory = {}
    if not isinstance(categories, dict):
        categories = {}

    clean_memory = {
        key: value for key, value in memory.items()
        if isinstance(key, str) and key.strip()
        and isinstance(value, str) and value.strip()
    }
    clean_categories = {
        key: value for key, value in categories.items()
        if key in clean_memory
    }

    removed = len(memory) - len(clean_memory)
    removed_categories = len(categories) - len(clean_categories)

    if removed:
        save_json(MEMORY_FILE, clean_memory)
    if removed_categories:
        save_json(MEMORY_CATEGORIES_FILE, clean_categories)

    return {
        "removed_invalid": removed,
        "removed_orphan_categories": removed_categories
    }


def smart_calculate(expression):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 200:
        raise ValueError("गणिती उदाहरण अवैध आहे.")
    digit_map = str.maketrans("०१२३४५६७८९", "0123456789")
    expression = expression.translate(digit_map)
    expression = expression.replace("^", "**").replace("×", "*").replace("÷", "/").replace(",", "")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp):
            a, b = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(b) > 100:
                raise ValueError("घातांक खूप मोठा आहे.")
            operations = {
                ast.Add: lambda: a + b, ast.Sub: lambda: a - b,
                ast.Mult: lambda: a * b, ast.Div: lambda: a / b,
                ast.FloorDiv: lambda: a // b, ast.Mod: lambda: a % b,
                ast.Pow: lambda: a ** b
            }
            operation = operations.get(type(node.op))
            if operation is None:
                raise ValueError("अवैध गणिती क्रिया.")
            return operation()
        if isinstance(node, ast.UnaryOp):
            value = evaluate(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
        raise ValueError("हे गणित समजले नाही.")

    result = evaluate(ast.parse(expression, mode="eval"))
    if type(result) not in (int, float) or not math.isfinite(result) or abs(result) > 1e100:
        raise ValueError("उत्तर मर्यादेबाहेर आहे.")
    return result



def smart_unit_convert(value, from_unit, to_unit):
    """सामान्य एककांचे सुरक्षित रूपांतर."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("रूपांतरासाठी वैध संख्या आवश्यक आहे.")
    if abs(value) > 1e100:
        raise ValueError("दिलेली संख्या खूप मोठी आहे.")

    aliases = {
        "km": ("length", 1000.0), "kilometer": ("length", 1000.0), "kilometers": ("length", 1000.0), "किमी": ("length", 1000.0),
        "m": ("length", 1.0), "meter": ("length", 1.0), "meters": ("length", 1.0), "मीटर": ("length", 1.0),
        "cm": ("length", 0.01), "centimeter": ("length", 0.01), "सेंमी": ("length", 0.01),
        "mm": ("length", 0.001), "millimeter": ("length", 0.001),
        "mi": ("length", 1609.344), "mile": ("length", 1609.344), "miles": ("length", 1609.344),
        "ft": ("length", 0.3048), "feet": ("length", 0.3048), "foot": ("length", 0.3048),
        "in": ("length", 0.0254), "inch": ("length", 0.0254), "inches": ("length", 0.0254),
        "kg": ("mass", 1.0), "kilogram": ("mass", 1.0), "किलो": ("mass", 1.0),
        "g": ("mass", 0.001), "gram": ("mass", 0.001), "grams": ("mass", 0.001), "ग्रॅम": ("mass", 0.001),
        "mg": ("mass", 0.000001), "milligram": ("mass", 0.000001),
        "lb": ("mass", 0.45359237), "lbs": ("mass", 0.45359237), "pound": ("mass", 0.45359237),
        "l": ("volume", 1.0), "liter": ("volume", 1.0), "litre": ("volume", 1.0), "लिटर": ("volume", 1.0),
        "ml": ("volume", 0.001), "milliliter": ("volume", 0.001), "millilitre": ("volume", 0.001), "मिली": ("volume", 0.001),
        "s": ("time", 1.0), "sec": ("time", 1.0), "second": ("time", 1.0), "seconds": ("time", 1.0),
        "min": ("time", 60.0), "minute": ("time", 60.0), "minutes": ("time", 60.0),
        "h": ("time", 3600.0), "hr": ("time", 3600.0), "hour": ("time", 3600.0), "hours": ("time", 3600.0),
        "day": ("time", 86400.0), "days": ("time", 86400.0),
        "c": ("temperature", None), "°c": ("temperature", None), "celsius": ("temperature", None), "सेल्सिअस": ("temperature", None),
        "f": ("temperature", None), "°f": ("temperature", None), "fahrenheit": ("temperature", None),
    }

    source = str(from_unit).strip().casefold()
    target = str(to_unit).strip().casefold()
    if source not in aliases or target not in aliases:
        raise ValueError("एकक ओळखता आले नाही. km, m, cm, kg, g, l, ml, c, f अशी एकके वापरा.")
    source_type, source_factor = aliases[source]
    target_type, target_factor = aliases[target]
    if source_type != target_type:
        raise ValueError("वेगवेगळ्या प्रकारच्या एककांचे रूपांतर करता येत नाही.")

    result = float(value)
    if source_type == "temperature":
        if source in ("c", "°c", "celsius", "सेल्सिअस"):
            result = result * 9 / 5 + 32 if target in ("f", "°f", "fahrenheit") else result
        else:
            result = (result - 32) * 5 / 9 if target in ("c", "°c", "celsius", "सेल्सिअस") else result
    else:
        result = result * source_factor / target_factor

    if not math.isfinite(result) or abs(result) > 1e100:
        raise ValueError("रूपांतराचे उत्तर मर्यादेबाहेर आहे.")
    return {"value": value, "from_unit": from_unit, "to_unit": to_unit, "converted_value": round(result, 10)}

def search_memory(query="", category="", limit=10):
    allowed_categories = ("preference", "project", "personal_context", "general")
    importance = {
        "preference": 4,
        "project": 3,
        "personal_context": 2,
        "general": 1
    }

    if not isinstance(query, str) or not isinstance(category, str):
        return {"error": "शोध माहिती अवैध आहे."}

    query = query.strip()[:100].casefold()
    category = category.strip()

    if category and category not in allowed_categories:
        return {"error": "Memory Category अवैध आहे."}
    if not query and not category:
        return {"error": "शोधण्यासाठी Query किंवा Category आवश्यक आहे."}

    try:
        limit = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        limit = 10

    cleanup = memory_maintenance()
    memory = load_json(MEMORY_FILE, {})
    categories = load_json(MEMORY_CATEGORIES_FILE, {})

    if not isinstance(memory, dict):
        memory = {}
    if not isinstance(categories, dict):
        categories = {}

    matches = []
    for key, value in memory.items():
        if not isinstance(value, str) or is_sensitive_memory(key, value):
            continue

        item_category = categories.get(key, "general")
        if item_category not in allowed_categories:
            item_category = "general"

        if category and item_category != category:
            continue
        if query and query not in (str(key) + " " + value).casefold():
            continue

        matches.append({
            "key": str(key),
            "value": value,
            "category": item_category,
            "importance": importance[item_category]
        })

    matches.sort(key=lambda item: item["importance"], reverse=True)

    return {
        "count": min(len(matches), limit),
        "matches": matches[:limit],
        "cleanup": cleanup
    }


def normalize_history(history):
    if not isinstance(history, list):
        return []

    valid = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue

        message = {"role": role, "content": content}
        if valid and valid[-1] == message:
            continue
        valid.append(message)

    return valid[-20:]


def load_history():
    return normalize_history(load_json(HISTORY_FILE, []))


def save_history(history):
    valid = normalize_history(history)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=BASE_DIR,
            prefix=".chat_history_",
            suffix=".tmp",
            delete=False
        ) as temp:
            temp_path = temp.name
            json.dump(valid, temp, ensure_ascii=False, indent=2)
            temp.flush()
            os.fsync(temp.fileno())

        os.replace(temp_path, HISTORY_FILE)
    except Exception as exc:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        print("[SHIVAM HISTORY] Save error:", str(exc))




def build_context_summary(history):
    """जुन्या संभाषणातील महत्त्वाचे निर्णय आणि संदर्भ जतन करा."""
    history = normalize_history(history)
    older = history[:-6]
    if not older:
        return ""

    important_terms = (
        "महत्त्वाचे", "लक्षात ठेव", "यापुढे", "नेहमी", "नको",
        "हवे", "ठरवले", "समस्या", "पूर्ण झाले", "बाकी",
        "api", "model", "error", "backup", "termux",
        "openjarvis", "shivam", "jarvis"
    )

    candidates = []
    for index, item in enumerate(older):
        content = " ".join(item["content"].split())
        if not content:
            continue

        lowered = content.casefold()
        score = 3 if item["role"] == "user" else 1
        score += sum(2 for term in important_terms if term in lowered)
        score += min(sum(ch.isdigit() for ch in content) // 4, 2)

        candidates.append({
            "index": index,
            "role": item["role"],
            "content": content,
            "score": score
        })

    selected = []
    total = 0
    for item in sorted(candidates, key=lambda x: (x["score"], x["index"]), reverse=True):
        label = "वापरकर्ता" if item["role"] == "user" else "SHIVAM"
        part = label + ": " + item["content"][:500]
        if total + len(part) > 3000:
            continue
        selected.append((item["index"], part))
        total += len(part)

    selected.sort(key=lambda x: x[0])
    if not selected:
        return ""

    return "महत्त्वाचे जुने संभाषण (कालक्रमानुसार):\n" + "\n".join(
        part for _, part in selected
    )

def record_recovery_diagnostic(stage, exc):
    try:
        path = os.path.join(BASE_DIR, "recovery_diagnostics.jsonl")
        if os.path.exists(path) and os.path.getsize(path) >= 1024 * 1024:
            backup = path + ".1"
            if os.path.exists(backup):
                os.remove(backup)
            os.replace(path, backup)
        entry = {
            "time": time.time(),
            "stage": str(stage)[:60],
            "error_type": type(exc).__name__
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as log_error:
        print("[SHIVAM DIAGNOSTICS] Log error:", type(log_error).__name__)


def protect_conversation_context(history, max_messages=20, max_chars=24000):
    history = normalize_history(history)
    selected = []
    total = 0

    for message in reversed(history):
        size = len(message.get("content", ""))
        if selected and (len(selected) >= max_messages or total + size > max_chars):
            break
        selected.append(message)
        total += size

    selected.reverse()
    return selected


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



GENERATED_DOCUMENTS_DIR = os.path.join(BASE_DIR, "generated_documents")

def create_document_file(arguments):
    """Create a local DOCX or XLSX using only Python's standard library."""
    import uuid
    import zipfile
    import csv
    import io
    from xml.sax.saxutils import escape

    def xml_safe(value):
        # XML 1.0 forbids most C0 control characters; strip them before escaping.
        return "".join(ch for ch in str(value) if ch in "\t\n\r" or 0x20 <= ord(ch) <= 0xD7FF or 0xE000 <= ord(ch) <= 0xFFFD or 0x10000 <= ord(ch) <= 0x10FFFF)

    fmt = arguments.get("format")
    title = arguments.get("title", "")
    filename = arguments.get("filename", "")
    content = arguments.get("content", "")
    headers = arguments.get("headers", [])
    rows = arguments.get("rows", [])
    if fmt not in ("word", "excel"):
        raise ValueError("फाइलचा प्रकार Word किंवा Excel असावा.")
    if not isinstance(title, str) or not title.strip() or len(title) > 180:
        raise ValueError("फाइलचे शीर्षक आवश्यक आहे.")
    title = title.strip()
    if not isinstance(filename, str):
        raise ValueError("फाइलचे नाव अवैध आहे.")
    filename = filename.strip()
    if not isinstance(content, str) or len(content) > 100000:
        raise ValueError("फाइलमधील मजकूर अवैध किंवा खूप मोठा आहे.")
    if not isinstance(headers, list) or len(headers) > 80 or any(not isinstance(x, str) for x in headers):
        raise ValueError("Excel शीर्षके अवैध आहेत.")
    if not isinstance(rows, list) or len(rows) > 5000:
        raise ValueError("Excel मधील ओळींची संख्या अवैध आहे.")
    for row in rows:
        if not isinstance(row, list) or len(row) > 80 or any(not isinstance(v, (str, int, float)) or isinstance(v, bool) for v in row):
            raise ValueError("Excel मधील डेटा अवैध आहे.")
    if fmt == "excel" and not headers and not rows:
        csv_text = content.lstrip("\ufeff")
        if csv_text.strip():
            first_line = csv_text.splitlines()[0]
            delimiter = "\t" if "\t" in first_line else ","
            parsed_rows = [
                row for row in csv.reader(io.StringIO(csv_text), delimiter=delimiter)
                if any(cell.strip() for cell in row)
            ]
            if parsed_rows:
                headers = [cell.strip() for cell in parsed_rows[0]]
                rows = [[cell.strip() for cell in row] for row in parsed_rows[1:]]
        else:
            headers, rows = ["माहिती"], [[title]]
    if len(headers) > 80 or any(not isinstance(x, str) for x in headers):
        raise ValueError("Excel शीर्षके अवैध आहेत किंवा खूप जास्त आहेत.")
    if len(rows) > 5000:
        raise ValueError("Excel मध्ये जास्तीत जास्त 5000 ओळी असू शकतात.")
    for row in rows:
        if not isinstance(row, list) or len(row) > 80:
            raise ValueError("Excel मधील ओळींची रचना अवैध आहे.")
        for value in row:
            if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                raise ValueError("Excel मधील डेटा अवैध आहे.")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Excel मधील संख्या मर्यादेबाहेर आहे.")
    if fmt == "word" and not content.strip():
        raise ValueError("Word फाइलसाठी मजकूर आवश्यक आहे.")

    safe_name = re.sub(r"[^\w .()-]", "", filename, flags=re.UNICODE).strip(" .")[:100]
    if not safe_name:
        safe_name = re.sub(r"[^\w-]", "_", title, flags=re.UNICODE)[:70] or "SHIVAM_Document"
    extension = ".docx" if fmt == "word" else ".xlsx"
    if safe_name.lower().endswith((".docx", ".xlsx")):
        safe_name = safe_name.rsplit(".", 1)[0]
    download_name = safe_name + extension
    os.makedirs(GENERATED_DOCUMENTS_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    path = os.path.join(GENERATED_DOCUMENTS_DIR, file_id + extension)

    if fmt == "word":
        paragraphs = []
        for line in content.splitlines():
            line = line.rstrip()
            style = ""
            if line.startswith("# "):
                line, style = line[2:], '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            elif line.startswith("## "):
                line, style = line[3:], '<w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
            text_xml = escape(xml_safe(line)).replace("\t", "    ")
            paragraphs.append('<w:p>' + style + '<w:r><w:t xml:space="preserve">' + text_xml + '</w:t></w:r></w:p>')
        title_xml = '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t xml:space="preserve">' + escape(xml_safe(title)) + '</w:t></w:r></w:p>'
        document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            + title_xml + "".join(paragraphs) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
            '</w:body></w:document>')
        styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
            '<w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/><w:sz w:val="22"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
            '<w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
            '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>'
            '<w:pPr><w:keepNext/><w:spacing w:before="180" w:after="80"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
            '</w:styles>')
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
            archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
            archive.writestr("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
            archive.writestr("word/document.xml", document)
            archive.writestr("word/styles.xml", styles)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        def col_letter(number):
            result = ""
            while number:
                number, remainder = divmod(number - 1, 26)
                result = chr(65 + remainder) + result
            return result
        def cell_xml(value, reference):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return '<c r="' + reference + '" t="n"><v>' + str(value) + '</v></c>'
            return '<c r="' + reference + '" t="inlineStr"><is><t xml:space="preserve">' + escape(xml_safe(value)) + '</t></is></c>'
        sheet_rows = ['<row r="1">' + cell_xml(title, "A1") + '</row>']
        if headers:
            sheet_rows.append('<row r="3">' + "".join(cell_xml(value, col_letter(i + 1) + "3") for i, value in enumerate(headers)) + '</row>')
            for row_index, row in enumerate(rows, 4):
                values = list(row[:80])
                if len(values) < len(headers):
                    values.extend([""] * (len(headers) - len(values)))
                sheet_rows.append('<row r="' + str(row_index) + '">' + "".join(cell_xml(value, col_letter(i + 1) + str(row_index)) for i, value in enumerate(values)) + '</row>')
        else:
            for row_index, row in enumerate(rows, 3):
                sheet_rows.append('<row r="' + str(row_index) + '">' + "".join(cell_xml(value, col_letter(i + 1) + str(row_index)) for i, value in enumerate(row)) + '</row>')
        sheet = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(sheet_rows) + '</sheetData></worksheet>'
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
            archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="माहिती" sheetId="1" r:id="rId1"/></sheets></workbook>')
            archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            archive.writestr("xl/worksheets/sheet1.xml", sheet)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    with open(os.path.join(GENERATED_DOCUMENTS_DIR, file_id + ".json"), "w", encoding="utf-8") as metadata_file:
        json.dump({"filename": download_name, "format": fmt}, metadata_file, ensure_ascii=False)
    return {"success": True, "file_id": file_id, "filename": download_name,
            "format": fmt, "download_url": "/v1/documents/download/" + file_id,
            "message": "फाइल तयार झाली आहे."}


class JarvisAPI(BaseHTTPRequestHandler):

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_json(200, {"status": "ok"})

    def do_GET(self):
        route = self.path.split("?", 1)[0]
        document_match = re.fullmatch(r"/v1/documents/download/([a-f0-9-]{36})", route)
        if document_match:
            file_id = document_match.group(1)
            file_path = next((os.path.join(GENERATED_DOCUMENTS_DIR, file_id + ext) for ext in (".docx", ".xlsx") if os.path.isfile(os.path.join(GENERATED_DOCUMENTS_DIR, file_id + ext))), None)
            if not file_path:
                self.send_json(404, {"error": "फाइल सापडली नाही किंवा हटवली आहे."})
                return
            extension = os.path.splitext(file_path)[1]
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if extension == ".docx" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(os.path.getsize(file_path)))
            metadata_path = os.path.join(GENERATED_DOCUMENTS_DIR, file_id + ".json")
            try:
                with open(metadata_path, "r", encoding="utf-8") as metadata_file:
                    original_name = json.load(metadata_file).get("filename", file_id + extension)
            except Exception:
                original_name = file_id + extension
            fallback_name = re.sub(r"[^A-Za-z0-9._-]", "_", original_name)
            encoded_name = urllib.parse.quote(original_name)
            self.send_header("Content-Disposition", 'attachment; filename="' + fallback_name + '"; filename*=UTF-8\'\'' + encoded_name)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(file_path, "rb") as document_file:
                shutil.copyfileobj(document_file, self.wfile)
            return
        if route == "/v1/info":
            self.send_json(200, {
                "model": os.getenv("JARVIS_MODEL", "openrouter/auto"),
                "agent": "SHIVAM",
                "engine": "OpenRouter"
            })
            return
        if route == "/v1/notes":
            notes = load_json(NOTES_FILE, [])
            if not isinstance(notes, list):
                notes = []
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("q", [""])[0].strip().casefold()
            if query:
                notes = [n for n in notes if isinstance(n, dict) and query in (str(n.get("title", "")) + " " + str(n.get("content", ""))).casefold()]
            notes.sort(key=lambda n: str(n.get("updated_at", "")), reverse=True)
            self.send_json(200, {"notes": notes})
            return
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
                "name": "SHIVAM",
                "message": "SHIVAM API Server चालू आहे."
            })
        elif self.path == "/v1/models":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                self.send_json(401, {"error": "OpenRouter API key not configured"})
                return
            try:
                response = httpx.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=30
                )
                response.raise_for_status()
                catalog = response.json().get("data", [])
                models = [{
                    "id": "openrouter/auto",
                    "object": "model",
                    "created": 0,
                    "owned_by": "openrouter",
                    "name": "OpenRouter Auto"
                }]
                for model in catalog:
                    if not isinstance(model, dict) or not model.get("id"):
                        continue
                    models.append({
                        "id": model["id"],
                        "object": "model",
                        "created": model.get("created", 0),
                        "owned_by": model.get("id", "openrouter").split("/")[0],
                        "name": model.get("name", model["id"])
                    })
                result = {"object": "list", "data": models}
                if len(models) > 1:
                    save_json(MODELS_CACHE_FILE, result)
                self.send_json(200, result)
            except Exception as exc:
                cached = load_json(MODELS_CACHE_FILE, None)
                if isinstance(cached, dict) and isinstance(cached.get("data"), list) and cached["data"]:
                    print("[SHIVAM] शेवटची जतन केलेली Model List वापरत आहे.")
                    self.send_json(200, cached)
                else:
                    self.send_json(502, {
                        "error": "Model Catalog आणि Cache दोन्ही उपलब्ध नाहीत",
                        "details": str(exc)[:250]
                    })
        elif route == "/v1/tools/web_search/credentials/status":
            credentials = load_tool_credentials().get("web_search", {})
            self.send_json(200, {
                "TAVILY_API_KEY": isinstance(credentials, dict) and bool(credentials.get("TAVILY_API_KEY"))
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
            # Expiry updates and queue reads must not race with approval creation/completion.
            with APPROVAL_LOCK:
                approvals = load_approvals()
                pending = []
                changed = False

                for action in approvals:
                    if action.get("status") == "processing":
                        try:
                            started = datetime.datetime.fromisoformat(
                                action.get("processing_at", "").replace("Z", "+00:00")
                            )
                            stale = now - started > datetime.timedelta(minutes=2)
                        except Exception:
                            stale = True
                        if stale:
                            action["status"] = "interrupted"
                            action["execution_result"] = {
                                "error": "Server व्यत्ययामुळे मंजुरीची कृती थांबली असू शकते. पुन्हा करण्यापूर्वी Memory किंवा Notes तपासा."
                            }
                            changed = True
                        continue
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
        if self.path == "/v1/tools/web_search/credentials":
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0 or length > 5000:
                    self.send_json(400, {"error": "Credential request आकार अवैध आहे"})
                    return
                data = json.loads(self.rfile.read(length))
                key = data.get("TAVILY_API_KEY") if isinstance(data, dict) and set(data) == {"TAVILY_API_KEY"} else None
                if not isinstance(key, str) or not key.strip() or len(key.strip()) > 500:
                    self.send_json(400, {"error": "Tavily API Key अवैध आहे"})
                    return
                credentials = load_tool_credentials()
                if not isinstance(credentials.get("web_search"), dict):
                    credentials["web_search"] = {}
                credentials["web_search"]["TAVILY_API_KEY"] = key.strip()
                save_tool_credentials(credentials)
                self.send_json(200, {"success": True})
            except Exception:
                self.send_json(400, {"error": "Tavily Credential सेव्ह करता आली नाही"})
            return

        if self.path == "/v1/notes":
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0 or length > 25000:
                    self.send_json(400, {"error": "नोंदीचा आकार अवैध आहे"})
                    return
                data = json.loads(self.rfile.read(length))
                title, content = data.get("title", ""), data.get("content", "")
                if not isinstance(title, str) or not isinstance(content, str) or not title.strip() or not content.strip():
                    self.send_json(400, {"error": "शीर्षक आणि मजकूर आवश्यक आहे"})
                    return
                if len(title) > 200 or len(content) > 20000:
                    self.send_json(400, {"error": "नोंद खूप मोठी आहे"})
                    return
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                note = {"id": str(uuid.uuid4()), "title": title.strip(), "content": content.strip(), "created_at": now, "updated_at": now}
                notes = load_json(NOTES_FILE, [])
                if not isinstance(notes, list):
                    notes = []
                notes.append(note)
                save_json(NOTES_FILE, notes)
                self.send_json(201, {"note": note})
            except Exception as exc:
                self.send_json(400, {"error": "नोंद जतन करता आली नाही: " + str(exc)[:180]})
            return
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
            # Atomically claim the approval so duplicate requests cannot execute it twice.
            with APPROVAL_LOCK:
                approvals = load_approvals()
                action = next((a for a in approvals if a.get("id") == action_id), None)
                if not action or action.get("status") != "pending":
                    self.send_json(404, {"error": "Pending approval not found or already used"})
                    return
                action["status"] = "processing"
                action["processing_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                save_approvals(approvals)

            try:
                expires = datetime.datetime.fromisoformat(
                    action["expires_at"].replace("Z", "+00:00")
                )
                if expires <= datetime.datetime.now(datetime.timezone.utc):
                    action["status"] = "expired"
                    set_approval_status(action_id, action.get("status"), action.get("execution_result"))
                    self.send_json(410, {"error": "Approval ची मुदत संपली"})
                    return
            except Exception:
                action["status"] = "expired"
                set_approval_status(action_id, action.get("status"), action.get("execution_result"))
                self.send_json(410, {"error": "Invalid approval expiry"})
                return

            if decision == "deny":
                action["status"] = "denied"
                set_approval_status(action_id, action.get("status"), action.get("execution_result"))
                self.send_json(200, {"success": True, "status": "denied"})
                return

            payload = action.get("payload", {})
            if action.get("action_type") == "tool_execution":
                allowed_mutations = {"save_memory_item", "update_memory_item", "forget_memory_item", "add_note", "delete_note"}
                tool_name = payload.get("tool_name") if isinstance(payload, dict) else None
                arguments = payload.get("arguments") if isinstance(payload, dict) else None
                if tool_name not in allowed_mutations or not isinstance(arguments, dict):
                    action["status"] = "failed"
                    action["execution_result"] = {"error": "Invalid tool approval payload"}
                    set_approval_status(action_id, action.get("status"), action.get("execution_result"))
                    self.send_json(400, {"error": "Invalid tool approval payload"})
                    return
                try:
                    if tool_name == "save_memory_item":
                        result = save_memory_item(arguments["key"], arguments["value"], arguments.get("category", "auto"))
                    elif tool_name == "update_memory_item":
                        result = update_memory_item(arguments["key"], arguments["value"])
                    elif tool_name == "forget_memory_item":
                        result = forget_memory_item(arguments["key"])
                    elif tool_name == "add_note":
                        result = add_note(arguments["text"], arguments.get("title", ""))
                    else:
                        result = delete_note(arguments["note_id"])
                    succeeded = (
                        isinstance(result, dict)
                        and result.get("success") is not False
                        and not result.get("error")
                        and ("success" in result or "result" in result)
                    )
                    action["status"] = "approved" if succeeded else "failed"
                    action["execution_result"] = result
                    set_approval_status(action_id, action.get("status"), action.get("execution_result"))
                    self.send_json(200, {"success": succeeded, "status": action["status"], "result": result})
                except Exception:
                    action["status"] = "failed"
                    action["execution_result"] = {"error": "मंजूर केलेली कृती पूर्ण करता आली नाही."}
                    set_approval_status(action_id, action.get("status"), action.get("execution_result"))
                    self.send_json(500, {"error": "Approved action failed"})
                return

            allowed_apps = {"chrome", "youtube", "gmail", "whatsapp", "camera", "settings", "phone", "maps", "calendar", "contacts", "messages", "clock", "files"}
            if (
                not isinstance(payload, dict)
                or set(payload) != {"app_name"}
                or not isinstance(payload.get("app_name"), str)
                or payload["app_name"].strip().lower() not in allowed_apps
            ):
                action["status"] = "failed"
                action["execution_result"] = {"error": "Invalid approval payload"}
                set_approval_status(action_id, action.get("status"), action.get("execution_result"))
                self.send_json(400, {"error": "Invalid approval payload"})
                return

            payload["app_name"] = payload["app_name"].strip().lower()
            result = execute_tool("open_android_app", payload)
            execution = result.get("result") if isinstance(result, dict) else None
            succeeded = isinstance(execution, dict) and execution.get("success") is True
            action["status"] = "approved" if succeeded else "failed"
            action["execution_result"] = result
            set_approval_status(action_id, action.get("status"), action.get("execution_result"))
            self.send_json(200, {
                "success": succeeded,
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
                if tool_name == "web_search":
                    result = tavily_web_search(
                        arguments.get("query", ""),
                        arguments.get("max_results", 5)
                    )
                elif tool_name == "get_weather":
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
                    if tool_name == "add_note":
                        result = add_note(arguments["text"], arguments.get("title", ""))
                    elif tool_name == "list_notes":
                        result = list_notes()
                    elif tool_name == "search_notes":
                        result = search_notes(arguments["query"])
                    elif tool_name == "delete_note":
                        result = delete_note(arguments["note_id"])
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

            incoming = []
            vision_message = None
            for item in request.get("messages", []):
                if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
                    continue
                raw_content = item.get("content")
                if isinstance(raw_content, str):
                    incoming.append({"role": item["role"], "content": raw_content})
                elif item.get("role") == "user" and isinstance(raw_content, list):
                    text_parts = []
                    valid_parts = []
                    for part in raw_content:
                        if not isinstance(part, dict):
                            continue
                        if part.get("type") == "text" and isinstance(part.get("text"), str):
                            text_parts.append(part["text"])
                            valid_parts.append(part)
                        elif part.get("type") == "image_url" and isinstance(part.get("image_url"), dict):
                            image_url = part["image_url"].get("url")
                            if isinstance(image_url, str) and image_url.startswith("data:image/"):
                                valid_parts.append(part)
                    if text_parts and any(part.get("type") == "image_url" for part in valid_parts):
                        incoming.append({"role": "user", "content": "\n".join(text_parts)})
                        vision_message = {"role": "user", "content": valid_parts}

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

            save_history(conversation)
            auto_save_explicit_preference(conversation[-1]["content"])
            conversation = protect_conversation_context(conversation)
            messages = [{"role": "system", "content": build_system_prompt()}]
            detected_intent = classify_user_intent(conversation[-1]["content"])
            messages.insert(1, {
                "role": "system",
                "content": "ओळखलेला प्राथमिक हेतू: " + detected_intent + ". " + intent_guidance(detected_intent)
            })
            context_summary = build_context_summary(conversation)
            if context_summary:
                messages.append({
                    "role": "system",
                    "content": "मागील संभाषणाचा संक्षिप्त संदर्भ:\n" + context_summary
                })
            messages.extend(conversation)
            if vision_message and messages and messages[-1].get("role") == "user":
                messages[-1] = vision_message
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
                "\\n\\nमराठी उत्तर गुणवत्ता नियम: वापरकर्त्याने मराठीत विचारल्यास "
                "नैसर्गिक, शुद्ध आणि सहज समजणाऱ्या मराठीत उत्तर दे. "
                "हिंदी शब्दरचना आणि अनावश्यक इंग्रजी टाळ. "
                "व्याकरण, काळ, लिंग, वचन आणि आदरार्थी संबोधन योग्य ठेव. "
                "तांत्रिक संज्ञा आवश्यक असल्यास त्यांचा मराठी अर्थ स्पष्ट कर. "
                "प्रश्नाचा अर्थ न बदलता थेट उत्तर दे. "
                "खात्री नसल्यास स्पष्ट सांग; तथ्ये बनवू नकोस. "
                "उत्तर संक्षिप्त पण पूर्ण ठेव."
            )
            messages[0]["content"] += (
                "\n\nनिवडलेले AI मॉडेल: " + selected_model + ". "
                "वापरकर्त्याने मॉडेलबद्दल विचारल्यास ही माहिती सांग. "
                "OpenRouter Auto असल्यास प्रत्यक्ष मॉडेलची खात्रीशीर माहिती उपलब्ध नाही असे सांग."
            )


            messages[0]["content"] += (
                "\\n\\nअचूकता आणि स्वायत्त कार्यप्रवाह नियम: आवश्यक तेव्हा उपलब्ध Tool वापर. "
                "अनेक टप्प्यांचे काम असल्यास आधी मनात क्रमवार योजना तयार कर आणि प्रत्येक टप्प्याची अवलंबित्वे ओळख. "
                "स्वतंत्र, सुरक्षित आणि केवळ माहिती-वाचणारी कामे एकाच Tool टप्प्यात एकत्र कर; उपलब्ध असल्यास जास्तीत जास्त 5 योग्य Tool Calls वापर. "
                "एखाद्या पुढील टप्प्यासाठी आधीच्या Tool चा निकाल आवश्यक असल्यास तो निकाल मिळाल्यानंतरच पुढील कृती ठरव; अंदाजाने Arguments तयार करू नकोस. "
                "वापरकर्त्याने Excel किंवा Word फाइल मागितल्यास create_document_file Tool वापरून प्रत्यक्ष डाउनलोड करता येणारी फाइल तयार कर. माहिती अपुरी असल्यास आधी एकच आवश्यक प्रश्न विचार; माहिती स्वतःहून बनवू नकोस. "
                "प्रत्येक Tool चा प्रत्यक्ष निकाल तपासूनच पुढे जा आणि अपयश आल्यास कारण स्पष्ट कर. "
                "App उघडणे, बाह्य संदेश पाठवणे, प्रकाशित करणे, Memory किंवा Notes जतन/अपडेट/हटवणे, खरेदी करणे किंवा सेटिंग बदलणे यांसारख्या बदल करणाऱ्या कृतींसाठी आवश्यक स्पष्ट मंजुरीशिवाय कृती करू नकोस. "
                "Tool चा निकाल मिळेपर्यंत कृती यशस्वी झाल्याचा दावा करू नकोस. "
                "Tool Error किंवा अपूर्ण माहिती स्पष्ट सांग. "
                "बनावट आकडे, Memory किंवा न केलेली कृती खरी म्हणून सांगू नकोस. "
                "उत्तर सोप्या, शुद्ध आणि नैसर्गिक मराठीत दे."
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
                                    "enum": ["chrome", "youtube", "gmail", "whatsapp", "camera", "settings", "phone", "maps", "calendar", "contacts", "messages", "clock", "files"]
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
                        "name": "web_search",
                        "description": "इंटरनेटवरील ताजी माहिती, बातम्या आणि संशोधन शोधा.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "max_results": {"type": "integer", "minimum": 1, "maximum": 10}
                            },
                            "required": ["query"],
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
                        "name": "smart_calculate",
                        "description": "बेरीज, वजाबाकी, गुणाकार, भागाकार, टक्केवारी, वर्गमूळ आणि इतर गणिती उदाहरणे अचूक सोडवा. गणिती प्रश्न आल्यास हे Tool वापरा.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "expression": {"type": "string", "description": "गणिती उदाहरण; उदा. २५०*१८/१००"}
                            },
                            "required": ["expression"],
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "smart_unit_convert",
                        "description": "लांबी, वजन, द्रव, वेळ आणि तापमान यांचे एकक रूपांतर करा. उदा. 5 km to m किंवा 100 c to f.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "value": {"type": "number", "description": "रूपांतर करायचे संख्यात्मक मूल्य"},
                                "from_unit": {"type": "string", "description": "मूळ एकक"},
                                "to_unit": {"type": "string", "description": "लक्ष्य एकक"}
                            },
                            "required": ["value", "from_unit", "to_unit"],
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
                        "name": "search_memory",
                        "description": "जतन केलेली Memory Query किंवा Category नुसार शोधा. Update किंवा Forget करण्यापूर्वी अचूक Key शोधण्यासाठी वापरा.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Key किंवा माहितीतील शब्द"},
                                "category": {"type": "string", "enum": ["preference", "project", "personal_context", "general"], "description": "Memory Category"},
                                "limit": {"type": "integer", "description": "जास्तीत जास्त 10 नोंदी"}
                            },
                            "required": [],
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "save_memory_item",
                        "description": "वापरकर्त्याने स्पष्टपणे सांगितलेली दीर्घकाळ उपयोगी पसंती किंवा प्रोजेक्टची माहिती जतन करा. पासवर्ड, API keys, OTP किंवा संवेदनशील माहिती जतन करू नका.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "माहितीचा विषय"},
                                "value": {"type": "string", "description": "जतन करायची माहिती"},
                                "category": {"type": "string", "enum": ["auto", "preference", "project", "personal_context", "general"], "description": "auto दिल्यास माहितीच्या स्वरूपानुसार Category निवडली जाईल"}
                            },
                            "required": ["key", "value"],
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "update_memory_item",
                        "description": "आधीपासून जतन केलेली Memory वापरकर्त्याच्या स्पष्ट विनंतीनुसार अपडेट करा.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "अपडेट करायच्या Memory ची अचूक Key"},
                                "value": {"type": "string", "description": "नवीन माहिती"}
                            },
                            "required": ["key", "value"],
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "forget_memory_item",
                        "description": "वापरकर्त्याने स्पष्टपणे सांगितलेली विशिष्ट Memory अचूक Key वापरून हटवा.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "हटवायच्या Memory ची अचूक Key"}
                            },
                            "required": ["key"],
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "memory_dashboard",
                        "description": "SHIVAM Memory ची Category नुसार आकडेवारी आणि सुरक्षित नोंदींची संख्या दाखवा.",
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "detect_memory_conflicts",
                        "description": "समान Key असलेल्या संभाव्य विरोधी Memory नोंदी शोधा. कोणतीही नोंद बदलू नका.",
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "recall_conversation_context",
                        "description": "जुन्या संभाषणातून दिलेल्या प्रश्नाशी संबंधित संदर्भ शोधा.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "limit": {"type": "integer", "minimum": 1, "maximum": 12}
                            },
                            "required": ["query"],
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "preview_memory_backup",
                        "description": "Memory Backup पुनर्संचयित करण्यापूर्वी त्याची वैधता तपासा. ही फक्त Preview सुविधा आहे; Restore करत नाही.",
                        "parameters": {
                            "type": "object",
                            "properties": {"filename": {"type": "string"}},
                            "required": ["filename"],
                            "additionalProperties": False
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "memory_integrity_check",
                        "description": "SHIVAM Memory आणि Category फाइलची सुसंगतता तपासा. कोणतीही नोंद बदलू नका.",
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
                        "name": "list_memory_backups",
                        "description": "उपलब्ध Memory Backup ची यादी, तारीख, आकार आणि JSON वैधता तपासा. कोणतीही फाइल बदलू नका.",
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
                        "name": "add_note",
                        "description": "नवीन वैयक्तिक नोंद जतन करा.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "description": "नोंदीचा मजकूर"},
                                "title": {"type": "string", "description": "नोंदीचे शीर्षक"}
                            },
                            "required": ["text"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "list_notes",
                        "description": "जतन केलेल्या सर्व नोंदी दाखवा.",
                        "parameters": {"type": "object", "properties": {}}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "search_notes",
                        "description": "जतन केलेल्या नोंदींमध्ये शब्द शोधा.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "शोधायचा शब्द किंवा मजकूर"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "delete_note",
                        "description": "नोंदीच्या अचूक ID द्वारे ती नोंद हटवा.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "note_id": {"type": "string", "description": "नोंदीचा ID"}
                            },
                            "required": ["note_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "create_document_file",
                        "description": "वापरकर्त्याने Excel किंवा Word फाइल मागितल्यास दिलेल्या माहितीनुसार नीट मांडलेली फाइल तयार करा. Excel साठी headers आणि rows द्या; Word साठी content मध्ये संपूर्ण मजकूर, विभाग आणि यादी newline ने द्या. माहिती अपुरी असल्यास आधी आवश्यक प्रश्न विचारा; माहिती बनवू नका. फाइल तयार झाल्यावर download_url वापरकर्त्याला द्या.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "format": {"type": "string", "enum": ["word", "excel"]},
                                "filename": {"type": "string"},
                                "title": {"type": "string"},
                                "content": {"type": "string"},
                                "headers": {"type": "array", "items": {"type": "string"}},
                                "rows": {"type": "array", "items": {"type": "array", "items": {"type": ["string", "number"]}}}
                            },
                            "required": ["format", "filename", "title", "content"],
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

            allowed_tool_names = {item["function"]["name"] for item in tool_specs}

            payload = {
                "model": model_id,
                "messages": messages,
                "stream": True,
                "temperature": request.get("temperature", 0.7),
                "tools": tool_specs,
                "tool_choice": "auto",
                "max_tokens": 8192,
                "reasoning": {"effort": "low"}
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
                            "error": friendly_provider_error(
                                upstream.status_code, error_text,
                                upstream.extensions.get("jarvis_model", "AI")
                            )
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
                    last_chunk = None

                    for line in safe_stream_lines(upstream, 'MAIN'):
                        if not line.startswith("data:"):
                            continue

                        data = line[5:].strip()
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            last_chunk = chunk
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

                                executed_tool_ids = set()
                                for call in delta.get("tool_calls", []):
                                    tool_call_id = getattr(call, 'id', None)
                                    if tool_call_id:
                                        if tool_call_id in executed_tool_ids:
                                            print('[SHIVAM] Duplicate Tool Action रोखली.')
                                            continue
                                        executed_tool_ids.add(tool_call_id)
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
                        except Exception as stream_error:
                            print("[SHIVAM STREAM PARSE ERROR]", repr(stream_error))
                            print("[SHIVAM STREAM DATA]", data[:1500])

                        try:
                            outgoing = json.loads(data)
                            outgoing_choices = outgoing.get('choices', [])
                            for outgoing_choice in outgoing_choices:
                                outgoing_delta = outgoing_choice.get('delta', {})
                                if isinstance(outgoing_delta, dict):
                                    outgoing_delta.pop('content', None)
                                    outgoing_delta.pop('reasoning', None)
                                    outgoing_delta.pop('reasoning_details', None)
                                outgoing.pop('reasoning', None)
                                outgoing.pop('reasoning_details', None)
                            has_payload = (not outgoing_choices) or any(
                                bool(c.get('delta')) or c.get('finish_reason') is not None
                                for c in outgoing_choices
                            )
                            if has_payload:
                                self.wfile.write(('data: ' + json.dumps(outgoing, ensure_ascii=False) + '\n\n').encode('utf-8'))
                                self.wfile.flush()
                        except Exception:
                            self.wfile.write(('data: ' + data + '\n\n').encode('utf-8'))
                            self.wfile.flush()

                    answer = correct_marathi(answer)
                    if answer:
                        corrected_chunk = {'choices': [{'delta': {'content': answer}}]}
                        self.wfile.write(('data: ' + json.dumps(corrected_chunk, ensure_ascii=False) + '\n\n').encode('utf-8'))
                        self.wfile.flush()

                    calls = [
                        pending_calls[index]
                        for index in sorted(pending_calls)
                    ][:5]

                    print("[SHIVAM] निवडलेले मॉडेल:", model_id)
                    print("[SHIVAM] मिळालेले Tool Calls:", json.dumps(calls, ensure_ascii=False))
                    if not answer and not calls:
                        print("[SHIVAM EMPTY RESPONSE DETAILS]", json.dumps(last_chunk, ensure_ascii=False)[:3000])

                    final_answer_start = len(answer)

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
                            argument_error = None
                            if arguments is not None:
                                if tool_name not in allowed_tool_names:
                                    argument_error = "हे Tool उपलब्ध किंवा अनुमत नाही."
                                else:
                                    argument_error = validate_tool_arguments(tool_name, arguments, tool_specs)

                            try:
                                if arguments is None or argument_error:
                                    result = {"error": argument_error or "Tool arguments अवैध आहेत."}
                                elif tool_name == "web_search":
                                    result = retry_read_operation(
                                        lambda: tavily_web_search(arguments["query"], arguments.get("max_results", 5)),
                                        "INITIAL_WEB_SEARCH"
                                    )
                                elif tool_name == "smart_calculate":
                                    result = {
                                        "expression": arguments["expression"],
                                        "answer": smart_calculate(arguments["expression"])
                                    }
                                elif tool_name == "smart_unit_convert":
                                    result = smart_unit_convert(
                                        arguments["value"], arguments["from_unit"], arguments["to_unit"]
                                    )
                                elif tool_name == "get_weather":
                                    result = retry_read_operation(
                                        lambda: get_badnera_weather(arguments),
                                        "INITIAL_WEATHER"
                                    )
                                elif tool_name == "open_android_app":
                                    app_name = arguments["app_name"].strip().lower()
                                    action = create_approval(app_name)
                                    result = {"result": {
                                        "pending_approval": True,
                                        "approval_id": action["id"],
                                        "message": app_name + " उघडण्यासाठी मंजुरी मागितली आहे. अजून App उघडलेले नाही."
                                    }}
                                elif tool_name == "search_memory":
                                    result = search_memory(arguments.get("query", ""), arguments.get("category", ""), arguments.get("limit", 10))
                                elif tool_name == "save_memory_item":
                                    action = create_tool_approval("save_memory_item", arguments)
                                    result = {"result": {"pending_approval": True, "approval_id": action["id"], "message": "ही कृती करण्यासाठी तुमची मंजुरी आवश्यक आहे. अजून कोणताही बदल केलेला नाही."}}

                                elif tool_name == "update_memory_item":
                                    action = create_tool_approval("update_memory_item", arguments)
                                    result = {"result": {"pending_approval": True, "approval_id": action["id"], "message": "ही कृती करण्यासाठी तुमची मंजुरी आवश्यक आहे. अजून कोणताही बदल केलेला नाही."}}

                                elif tool_name == "forget_memory_item":
                                    action = create_tool_approval("forget_memory_item", arguments)
                                    result = {"result": {"pending_approval": True, "approval_id": action["id"], "message": "ही कृती करण्यासाठी तुमची मंजुरी आवश्यक आहे. अजून कोणताही बदल केलेला नाही."}}

                                elif tool_name == "memory_dashboard":
                                    result = memory_dashboard()
                                elif tool_name == "detect_memory_conflicts":
                                    result = detect_memory_conflicts()
                                elif tool_name == "recall_conversation_context":
                                    result = recall_conversation_context(arguments["query"], arguments.get("limit", 8))
                                elif tool_name == "preview_memory_backup":
                                    result = preview_memory_backup(arguments["filename"])
                                elif tool_name == "memory_integrity_check":
                                    result = memory_integrity_check()
                                elif tool_name == "list_memory_backups":
                                    result = list_memory_backups()
                                elif tool_name == "add_note":
                                    action = create_tool_approval("add_note", arguments)
                                    result = {"result": {"pending_approval": True, "approval_id": action["id"], "message": "ही कृती करण्यासाठी तुमची मंजुरी आवश्यक आहे. अजून कोणताही बदल केलेला नाही."}}

                                elif tool_name == "list_notes":
                                    result = list_notes()
                                elif tool_name == "search_notes":
                                    result = search_notes(arguments["query"])
                                elif tool_name == "delete_note":
                                    action = create_tool_approval("delete_note", arguments)
                                    result = {"result": {"pending_approval": True, "approval_id": action["id"], "message": "ही कृती करण्यासाठी तुमची मंजुरी आवश्यक आहे. अजून कोणताही बदल केलेला नाही."}}
                                elif tool_name == "create_document_file":
                                    result = create_document_file(arguments)
                                elif tool_name in ("get_current_time", "get_system_info", "get_available_tools"):
                                    result = execute_tool(tool_name, arguments)
                                else:
                                    result = {"error": "हे Tool उपलब्ध किंवा अनुमत नाही."}
                                if not isinstance(result, dict):
                                    result = {"result": result}
                            except Exception as exc:
                                print("[SHIVAM TOOL ERROR]", tool_name, type(exc).__name__)
                                try:
                                    record_recovery_diagnostic("tool:" + str(tool_name), exc)
                                except Exception:
                                    pass
                                result = {"error": "Tool चालवताना त्रुटी आली. कृपया पुन्हा प्रयत्न करा."}

                            latency = int((__import__("time").time() - started) * 1000)
                            verification = verify_tool_result(result)
                            pending = verification["status"] == "pending_approval"

                            end_event = {
                                "tool": tool_name,
                                "success": verification["success"],
                                "status": verification["status"],
                                "result": result.get("result", result.get("answer", result.get("error", result))),
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
                            "max_tokens": 2048,
                            "tools": tool_specs,
                            "tool_choice": "auto"
                        }

                        followup_calls = {}
                        final_answer_start = len(answer)
                        try:
                            with openrouter_stream(client, headers, final_payload) as final_upstream:
    
                                if final_upstream.status_code != 200:
                                    error_text = final_upstream.read().decode("utf-8", "replace")
                                    print("[OPENROUTER FINAL ERROR]", final_upstream.status_code, error_text[:1000])
                                    fallback = friendly_provider_error(
                                        final_upstream.status_code, error_text,
                                        final_upstream.extensions.get("jarvis_model", "AI")
                                    )
                                    answer += fallback
                                    error_chunk = {
                                        "choices": [{
                                            "delta": {"content": fallback},
                                            "finish_reason": "stop"
                                        }]
                                    }
                                else:
                                    for line in safe_stream_lines(final_upstream, 'FINAL'):
                                        if not line.startswith("data:"):
                                            continue
    
                                        data = line[5:].strip()
                                        if data == "[DONE]":
                                            break
    
                                        try:
                                            chunk = json.loads(data)
                                            choices = chunk.get("choices", [])
                                            if choices:
                                                delta = choices[0].get("delta", {})
                                                content = delta.get("content")
                                                if isinstance(content, str):
                                                    answer += content
                                                for tool_delta in delta.get("tool_calls", []):
                                                    tool_index = tool_delta.get("index", 0)
                                                    item = followup_calls.setdefault(tool_index, {
                                                        "id": "", "type": "function",
                                                        "function": {"name": "", "arguments": ""}
                                                    })
                                                    if tool_delta.get("id"):
                                                        item["id"] = tool_delta["id"]
                                                    function_delta = tool_delta.get("function", {})
                                                    if function_delta.get("name"):
                                                        item["function"]["name"] += function_delta["name"]
                                                    if function_delta.get("arguments"):
                                                        item["function"]["arguments"] += function_delta["arguments"]
                                        except Exception as stream_error:
                                            record_recovery_diagnostic("FINAL_STREAM_PARSE", stream_error)
                                            print("[SHIVAM FINAL STREAM PARSE ERROR]", repr(stream_error))
                                            print("[SHIVAM FINAL STREAM DATA]", data[:1500])
    
                        except Exception as final_stream_error:
                            print("[SHIVAM FINAL STREAM ERROR]", type(final_stream_error).__name__)
                            record_recovery_diagnostic("FINAL_STREAM", final_stream_error)

                        # Bounded dependent follow-up: execute one additional round of
                        # read-only tools using the results from the previous round.
                        next_calls = [followup_calls[i] for i in sorted(followup_calls)][:5]
                        if next_calls:
                            messages.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": next_calls
                            })
                            readonly_tools = {
                                "web_search", "get_current_time", "smart_calculate",
                                "smart_unit_convert", "get_system_info", "get_weather",
                                "search_memory", "memory_dashboard", "detect_memory_conflicts",
                                "recall_conversation_context", "memory_integrity_check",
                                "list_memory_backups", "list_notes", "search_notes"
                            }
                            for follow_index, follow_call in enumerate(next_calls):
                                follow_args = {}
                                follow_name = follow_call.get("function", {}).get("name", "")
                                try:
                                    follow_args = json.loads(follow_call.get("function", {}).get("arguments") or "{}")
                                    if not isinstance(follow_args, dict):
                                        raise ValueError("Invalid tool arguments")
                                    validation_error = validate_tool_arguments(follow_name, follow_args, tool_specs)
                                    if follow_name not in readonly_tools or validation_error:
                                        follow_result = {"error": validation_error or "या पुढील टप्प्यात फक्त सुरक्षित माहिती-वाचणारी Tools अनुमत आहेत."}
                                    elif follow_name == "web_search":
                                        follow_result = retry_read_operation(
                                            lambda: tavily_web_search(follow_args["query"], follow_args.get("max_results", 5)),
                                            "FOLLOWUP_WEB_SEARCH"
                                        )
                                    elif follow_name == "get_current_time":
                                        follow_result = execute_tool(follow_name, follow_args)
                                    elif follow_name == "smart_calculate":
                                        follow_result = {"expression": follow_args["expression"], "answer": smart_calculate(follow_args["expression"])}
                                    elif follow_name == "smart_unit_convert":
                                        follow_result = smart_unit_convert(follow_args["value"], follow_args["from_unit"], follow_args["to_unit"])
                                    elif follow_name == "get_system_info":
                                        follow_result = execute_tool(follow_name, follow_args)
                                    elif follow_name == "get_weather":
                                        follow_result = retry_read_operation(
                                            lambda: get_badnera_weather(follow_args),
                                            "FOLLOWUP_WEATHER"
                                        )
                                    elif follow_name == "search_memory":
                                        follow_result = search_memory(follow_args.get("query", ""), follow_args.get("category", ""), follow_args.get("limit", 10))
                                    elif follow_name == "memory_dashboard":
                                        follow_result = memory_dashboard()
                                    elif follow_name == "detect_memory_conflicts":
                                        follow_result = detect_memory_conflicts()
                                    elif follow_name == "recall_conversation_context":
                                        follow_result = recall_conversation_context(follow_args["query"], follow_args.get("limit", 8))
                                    elif follow_name == "memory_integrity_check":
                                        follow_result = memory_integrity_check()
                                    elif follow_name == "list_memory_backups":
                                        follow_result = list_memory_backups()
                                    elif follow_name == "list_notes":
                                        follow_result = list_notes()
                                    elif follow_name == "search_notes":
                                        follow_result = search_notes(follow_args["query"])
                                    else:
                                        follow_result = {"error": "हे Tool उपलब्ध नाही."}
                                    if not isinstance(follow_result, dict):
                                        follow_result = {"result": follow_result}
                                except Exception as follow_error:
                                    print("[SHIVAM FOLLOW-UP TOOL ERROR]", follow_name, type(follow_error).__name__)
                                    record_recovery_diagnostic("FOLLOWUP_" + str(follow_name), follow_error)
                                    follow_result = {"error": "पुढील Tool टप्पा एक पुनर्प्रयत्न करूनही पूर्ण करता आला नाही."}

                                verification = verify_tool_result(follow_result)
                                self.wfile.write(("event: tool_call_start\ndata: " + json.dumps({
                                    "tool": follow_name, "arguments": follow_args
                                }, ensure_ascii=False) + "\n\n").encode("utf-8"))
                                self.wfile.flush()
                                self.wfile.write(("event: tool_call_end\ndata: " + json.dumps({
                                    "tool": follow_name,
                                    "success": verification["success"],
                                    "status": verification["status"],
                                    "result": follow_result
                                }, ensure_ascii=False) + "\n\n").encode("utf-8"))
                                self.wfile.flush()
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": follow_call.get("id") or ("follow_" + str(follow_index)),
                                    "content": json.dumps(follow_result, ensure_ascii=False)
                                })

                            # Ask the model to synthesize the dependent results; no further
                            # tool execution is allowed in this final synthesis call.
                            synthesis_payload = {
                                "model": model_id,
                                "messages": messages,
                                "stream": True,
                                "temperature": request.get("temperature", 0.7),
                                "max_tokens": 2048
                            }
                            try:
                                with openrouter_stream(client, headers, synthesis_payload) as synthesis_upstream:
                                    if synthesis_upstream.status_code == 200:
                                        for synthesis_line in safe_stream_lines(synthesis_upstream, "SYNTHESIS"):
                                            if not synthesis_line.startswith("data:"):
                                                continue
                                            synthesis_data = synthesis_line[5:].strip()
                                            if synthesis_data == "[DONE]":
                                                break
                                            try:
                                                synthesis_chunk = json.loads(synthesis_data)
                                                synthesis_choices = synthesis_chunk.get("choices", [])
                                                if synthesis_choices:
                                                    synthesis_text = synthesis_choices[0].get("delta", {}).get("content")
                                                    if isinstance(synthesis_text, str):
                                                        answer += synthesis_text
                                            except Exception:
                                                continue
                                    else:
                                        print("[SHIVAM SYNTHESIS ERROR]", synthesis_upstream.status_code)
                            except Exception as synthesis_error:
                                print("[SHIVAM SYNTHESIS FAILED]", type(synthesis_error).__name__)

                    final_part = correct_marathi(answer[final_answer_start:])
                    answer = answer[:final_answer_start] + final_part
                    if final_part:
                        corrected_chunk = {"choices": [{"delta": {"content": final_part}}]}
                        self.wfile.write(("data: " + json.dumps(corrected_chunk, ensure_ascii=False) + "\n\n").encode("utf-8"))
                        self.wfile.flush()

                    final_response_missing = bool(calls) and not answer[final_answer_start:].strip()
                    if not answer.strip() or final_response_missing:
                        fallback = "माफ करा, यावेळी पूर्ण उत्तर मिळाले नाही."
                        tool_result = locals().get("result")
                        if isinstance(tool_result, dict):
                            detail = tool_result.get("answer")
                            if not detail:
                                detail = tool_result.get("result")
                            if isinstance(detail, dict):
                                detail = detail.get("message")
                            if isinstance(detail, (str, int, float)) and not isinstance(detail, bool):
                                if str(detail).strip():
                                    fallback = str(detail)
                        fallback = correct_marathi(str(fallback))
                        if answer.strip():
                            answer = answer.rstrip() + "\n" + fallback
                        else:
                            answer = fallback
                        error_chunk = {
                            "choices": [{
                                "delta": {"content": answer},
                                "finish_reason": "stop"
                            }]
                        }
                        self.wfile.write(
                            ("data: " + json.dumps(error_chunk, ensure_ascii=False) + "\n\n").encode("utf-8")
                        )
                        self.wfile.flush()

                    if answer:
                        save_history(conversation + [
                            {"role": "assistant", "content": answer}
                        ])
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()



        except (BrokenPipeError, ConnectionResetError):
            print("[JARVIS API] Client disconnected")
        except Exception as e:
            print("[SHIVAM API] Error:", type(e).__name__)
            record_recovery_diagnostic("API_HANDLER", e)
            try:
                self.send_json(500, {"error": "SHIVAM API मध्ये अनपेक्षित अडचण आली. कृपया पुन्हा प्रयत्न करा."})
            except Exception:
                pass

    def do_PUT(self):
        match = re.fullmatch(r"/v1/notes/([0-9a-fA-F-]{36})", self.path.split("?", 1)[0])
        if not match:
            self.send_json(404, {"error": "नोंद सापडली नाही"})
            return
        try:
            note_id = str(uuid.UUID(match.group(1)))
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > 25000:
                self.send_json(400, {"error": "नोंदीचा आकार अवैध आहे"})
                return
            data = json.loads(self.rfile.read(length))
            title, content = data.get("title", ""), data.get("content", "")
            if not isinstance(title, str) or not isinstance(content, str) or not title.strip() or not content.strip():
                self.send_json(400, {"error": "शीर्षक आणि मजकूर आवश्यक आहे"})
                return
            if len(title) > 200 or len(content) > 20000:
                self.send_json(400, {"error": "नोंद खूप मोठी आहे"})
                return
            notes = load_json(NOTES_FILE, [])
            if not isinstance(notes, list):
                notes = []
            note = next((n for n in notes if isinstance(n, dict) and n.get("id") == note_id), None)
            if note is None:
                self.send_json(404, {"error": "नोंद सापडली नाही"})
                return
            import datetime
            note.update({"title": title.strip(), "content": content.strip(), "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            save_json(NOTES_FILE, notes)
            self.send_json(200, {"note": note})
        except Exception as exc:
            self.send_json(400, {"error": "नोंद बदलता आली नाही: " + str(exc)[:180]})

    def do_DELETE(self):
        route = self.path.split("?", 1)[0]
        if route == "/v1/tools/web_search/credentials/TAVILY_API_KEY":
            try:
                credentials = load_tool_credentials()
                web = credentials.get("web_search", {})
                if isinstance(web, dict):
                    web.pop("TAVILY_API_KEY", None)
                    if not web:
                        credentials.pop("web_search", None)
                save_tool_credentials(credentials)
                self.send_json(200, {"success": True})
            except Exception:
                self.send_json(500, {"error": "Credential हटवता आली नाही"})
            return
        match = re.fullmatch(r"/v1/notes/([0-9a-fA-F-]{36})", self.path.split("?", 1)[0])
        if not match:
            self.send_json(404, {"error": "नोंद सापडली नाही"})
            return
        try:
            note_id = str(uuid.UUID(match.group(1)))
            notes = load_json(NOTES_FILE, [])
            if not isinstance(notes, list):
                notes = []
            remaining = [n for n in notes if not isinstance(n, dict) or n.get("id") != note_id]
            if len(remaining) == len(notes):
                self.send_json(404, {"error": "नोंद सापडली नाही"})
                return
            save_json(NOTES_FILE, remaining)
            self.send_json(200, {"success": True, "deleted_id": note_id})
        except Exception as exc:
            self.send_json(400, {"error": "नोंद हटवता आली नाही: " + str(exc)[:180]})

    def log_message(self, format, *args):
        print("[JARVIS API]", format % args)



# SHIVAM GROUP 1: Advanced Marathi Response Quality
_original_build_system_prompt = build_system_prompt

def _shivam_marathi_quality_wrapper():
    prompt = _original_build_system_prompt()
    extra_rules = """
अतिरिक्त भाषा आणि उत्तर गुणवत्ता नियम:
1. वापरकर्त्याने मराठीत विचारल्यास नैसर्गिक, शुद्ध आणि व्याकरणदृष्ट्या योग्य मराठीत उत्तर दे.
2. मराठी उत्तरात विनाकारण हिंदी शब्द, हिंदी वाक्यरचना किंवा हिंदी-मराठी मिश्र भाषा वापरू नको.
3. शक्यतो मराठी देवनागरी लिपी वापर; तांत्रिक संज्ञा आवश्यक असल्यास प्रचलित इंग्रजी शब्द वापर.
4. वापरकर्त्याने दुसऱ्या भाषेत विचारल्यास त्याच भाषेत उत्तर दे.
5. उत्तर देण्यापूर्वी वाक्यरचना, शब्दांचा अर्थ आणि व्याकरण मनात तपास.
6. उत्तर स्पष्ट, थेट आणि आवश्यक तेवढेच सविस्तर ठेव; एकच मुद्दा पुन्हा पुन्हा सांगू नको.
7. माहिती माहीत नसल्यास अंदाजाने तथ्य सांगू नको; अनिश्चितता स्पष्ट कर.
8. प्रत्यक्ष कृती पूर्ण झाली नसेल तर ती पूर्ण झाल्याचा दावा करू नको.
"""
    if extra_rules not in prompt:
        prompt += "\n" + extra_rules
    return prompt

build_system_prompt = _shivam_marathi_quality_wrapper

if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), JarvisAPI)
    print(f"SHIVAM API Server: http://{HOST}:{PORT}")
    print("Health Check: http://127.0.0.1:8000/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSHIVAM API Server बंद झाला.")
        server.server_close()
