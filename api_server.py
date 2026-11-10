from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import ast
import httpx
import uuid

HOST = "127.0.0.1"
PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
HISTORY_FILE = os.path.join(BASE_DIR, "chat_history.json")
JARVIS_FILE = os.path.join(BASE_DIR, "jarvis.py")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


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
    prompt = load_prompt()
    memory = load_json(MEMORY_FILE, {})
    if isinstance(memory, dict) and memory:
        context = "\n".join("- " + str(v) for v in memory.values())
        prompt += "\n\nवापरकर्त्याबद्दल लक्षात ठेवलेली माहिती:\n"
        prompt += context + "\nही माहिती उत्तर देताना संदर्भ म्हणून वापर."
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
        if self.path == "/health":
            self.send_json(200, {
                "status": "online",
                "name": "JARVIS",
                "message": "JARVIS API Server चालू आहे."
            })
        else:
            self.send_json(404, {"error": "API endpoint not found"})

    def do_POST(self):
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
                conversation = load_history()

            if not conversation or conversation[-1]["role"] != "user":
                self.send_json(400, {"error": "User message आवश्यक आहे"})
                return

            messages = [{"role": "system", "content": build_system_prompt()}]
            messages.extend(conversation)

            payload = {
                "model": os.getenv("JARVIS_MODEL", "openrouter/free"),
                "messages": messages,
                "stream": True,
                "temperature": request.get("temperature", 0.7)
            }

            if request.get("max_tokens"):
                payload["max_tokens"] = request["max_tokens"]

            headers = {
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json"
            }

            with httpx.Client(timeout=90) as client:
                with client.stream(
                    "POST", OPENROUTER_URL,
                    headers=headers, json=payload
                ) as upstream:

                    if upstream.status_code != 200:
                        error_text = upstream.read().decode("utf-8", "replace")
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

                    self.wfile.write(b"event: inference_start\ndata: {}\n\n")
                    self.wfile.flush()

                    answer = ""

                    for line in upstream.iter_lines():
                        if not line.startswith("data:"):
                            continue

                        data = line[5:].strip()

                        if data == "[DONE]":
                            self.wfile.write(b"data: [DONE]\n\n")
                            self.wfile.flush()
                            break

                        try:
                            chunk = json.loads(data)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                if isinstance(content, str):
                                    answer += content
                        except Exception:
                            pass

                        self.wfile.write(
                            ("data: " + data + "\n\n").encode("utf-8")
                        )
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
