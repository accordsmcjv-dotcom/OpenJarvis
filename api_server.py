from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import math
import ast
import asyncio
import time
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
MEMORY_CATEGORIES_FILE = os.path.join(BASE_DIR, "memory_categories.json")
HISTORY_FILE = os.path.join(BASE_DIR, "chat_history.json")
JARVIS_FILE = os.path.join(BASE_DIR, "jarvis.py")

APPROVALS_FILE = os.path.join(BASE_DIR, "pending_approvals.json")
MODELS_CACHE_FILE = os.path.join(BASE_DIR, "models_cache.json")


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
    r@contextmanager
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
                print(f"[SHIVAM {provider} TIMEOUT RETRY] {attempt + 1}/3: {exc}")
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
                continue
            except httpx.TransportError as exc:
                print(f"[SHIVAM {provider} RETRY] {attempt + 1}/3: {exc}")
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
                continue

            if response.status_code in (500, 502, 503, 504) and attempt < 2:
                print(f"[SHIVAM {provider} RETRY] HTTP {response.status_code}, {attempt + 1}/3")
                response.close()
                time.sleep(attempt + 1)
                continue
            return response

        raise RuntimeError(provider + " request failed")

    response = None
    try:
        response = send_with_retry(OPENROUTER_URL, headers, body, "OPENROUTER")

        if response.status_code == 402 and body.get("model") != "openrouter/free":
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
        response.status_code in (429, 500, 502, 503, 504)
        and os.getenv("GROQ_API_KEY")
    ):
        if response is not None:
            print("[SHIVAM] OpenRouter अनुपलब्ध. Groq पर्यायी सेवा वापरत आहे.")
            response.close()

        groq_body = dict(body)
        groq_body["model"] = "openai/gpt-oss-20b"
        groq_body["max_tokens"] = 512
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

nse.close()


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


def save_memory_item(key, value, category="general"):
    if not isinstance(key, str) or not isinstance(value, str):
        return {"error": "Memory माहिती अवैध आहे."}

    key = key.strip()[:80]
    value = " ".join(value.strip().split())[:500]

    if not key or not value:
        return {"error": "Memory Key आणि Value आवश्यक आहेत."}
    allowed_categories = ("preference", "project", "personal_context", "general")
    if category not in allowed_categories:
        return {"error": "Memory Category अवैध आहे."}
    if is_sensitive_memory(key, value):
        return {"error": "संवेदनशील माहिती सुरक्षिततेसाठी Memory मध्ये जतन केली जाणार नाही."}

    memory = load_json(MEMORY_FILE, {})
    if not isinstance(memory, dict):
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
                return {"result": "हीच Memory आधीपासून जतन आहे. Duplicate तयार केली नाही."}
            return {
                "result": "ही माहिती आधीपासून '" + str(existing_key) +
                          "' या Key खाली जतन आहे. Duplicate तयार केली नाही."
            }

    if key in memory:
        return {
            "error": "ही Key आधीपासून अस्तित्वात आहे. जुनी माहिती बदलण्यासाठी update_memory_item वापरा."
        }

    memory[key] = value
    save_json(MEMORY_FILE, memory)

    categories = load_json(MEMORY_CATEGORIES_FILE, {})
    if not isinstance(categories, dict):
        categories = {}
    categories[key] = category
    save_json(MEMORY_CATEGORIES_FILE, categories)

    return {"result": "नवीन Memory सुरक्षितपणे जतन झाली. Category: " + category}

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


def load_history():
    data = load_json(HISTORY_FILE, [])
    if not isinstance(data, list):
        return []

    return [
        m for m in data
        if isinstance(m, dict)
        and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
    ][-20:]


def save_history(history):
    if not isinstance(history, list):
        return
    valid = [
        m for m in history
        if isinstance(m, dict)
        and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
    ]
    save_json(HISTORY_FILE, valid[-20:])


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

            auto_save_explicit_preference(conversation[-1]["content"])
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
                                "category": {"type": "string", "enum": ["preference", "project", "personal_context", "general"], "description": "माहितीची Category"}
                            },
                            "required": ["key", "value", "category"],
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
                    ][:3]

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
                            if arguments is None:
                                result = {"error": "Tool arguments अवैध आहेत."}
                            elif tool_name == "smart_calculate":
                                try:
                                    result = {"expression": arguments.get("expression", ""), "answer": smart_calculate(arguments.get("expression", ""))}
                                except Exception as exc:
                                    result = {"error": str(exc)}
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
                            elif tool_name == "search_memory":
                                result = search_memory(
                                    arguments.get("query", ""),
                                    arguments.get("category", ""),
                                    arguments.get("limit", 10)
                                )
                            elif tool_name == "save_memory_item":
                                result = save_memory_item(
                                    arguments.get("key"),
                                    arguments.get("value"),
                                    arguments.get("category", "general")
                                )
                            elif tool_name == "update_memory_item":
                                result = update_memory_item(
                                    arguments.get("key"),
                                    arguments.get("value")
                                )
                            elif tool_name == "forget_memory_item":
                                result = forget_memory_item(
                                    arguments.get("key")
                                )
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
                            "max_tokens": 2048
                        }

                        final_answer_start = len(answer)
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
                                            content = choices[0].get("delta", {}).get("content")
                                            if isinstance(content, str):
                                                answer += content
                                    except Exception as stream_error:
                                        print("[SHIVAM FINAL STREAM PARSE ERROR]", repr(stream_error))
                                        print("[SHIVAM FINAL STREAM DATA]", data[:1500])


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
                            if isinstance(detail, str) and detail.strip():
                                fallback = detail
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
    print(f"SHIVAM API Server: http://{HOST}:{PORT}")
    print("Health Check: http://127.0.0.1:8000/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSHIVAM API Server बंद झाला.")
        server.server_close()
