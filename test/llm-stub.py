#!/usr/bin/env python3
"""Tiny OpenAI-compatible stub for testing Mira without a real LLM key.

Answers /v1/models and /v1/chat/completions. For forced tool calls
(tool_choice = {function: name}) it returns a valid submit_* call; for
json_mode summarisation it returns a {"files": [...]} summary for each file
named in the prompt. Requires "Authorization: Bearer $STUB_KEY". Binds IPv6
dual-stack so it works on Railway's private network.
"""
import json, os, re, socket, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEY = os.environ.get("STUB_KEY", "stub-key")
CALLS = {"n": 0}


def tool_args(name, body):
    if name == "submit_review":
        return {"comments": [], "key_issues": [], "summary": "Stub review: no issues found.",
                "metadata": {}}
    if name == "submit_walkthrough":
        return {"summary": "Stub walkthrough of this change.", "confidence_score": 4,
                "change_groups": [{"label": "Stub", "files": [{"path": "README.md", "change": "edited"}]}],
                "effort": 1, "sequence_diagram": None}
    if name == "submit_critique":
        return {"verdicts": []}
    if name == "submit_thread_reply":
        return {"intent": "answer", "reply": "Stub reply."}
    return {}


def summarize(body):
    text = "\n".join(m.get("content") or "" for m in body.get("messages", []) if isinstance(m.get("content"), str))
    paths = re.findall(r"^### (.+)$", text, flags=re.M)
    return json.dumps({"files": [{"path": p.strip(), "language": "text", "summary": f"Stub summary of {p.strip()}.",
                                  "symbols": [], "imports": [], "symbol_references": [], "external_refs": []}
                                 for p in paths]})


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        if self.headers.get("Authorization", "") != f"Bearer {KEY}":
            self._send(401, {"error": {"message": "bad key"}})
            return False
        return True

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/health", "/healthz"):
            return self._send(200, {"ok": True, "calls": CALLS["n"]})
        if self.path.endswith("/models"):
            if not self._auth():
                return
            return self._send(200, {"object": "list", "data": [{"id": "stub-model", "object": "model"}]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if not self._auth():
            return
        CALLS["n"] += 1
        tc = body.get("tool_choice")
        msg = {"role": "assistant", "content": None}
        finish = "stop"
        if isinstance(tc, dict) and tc.get("function", {}).get("name"):
            name = tc["function"]["name"]
            msg["tool_calls"] = [{"id": f"call_{CALLS['n']}", "type": "function",
                                  "function": {"name": name, "arguments": json.dumps(tool_args(name, body))}}]
            finish = "tool_calls"
        elif body.get("tools"):
            names = [t["function"]["name"] for t in body["tools"]]
            sub = next((x for x in names if x.startswith("submit_")), None)
            if sub:
                msg["tool_calls"] = [{"id": f"call_{CALLS['n']}", "type": "function",
                                      "function": {"name": sub, "arguments": json.dumps(tool_args(sub, body))}}]
                finish = "tool_calls"
            else:
                msg["content"] = "Done."
        elif (body.get("response_format") or {}).get("type") == "json_object":
            msg["content"] = summarize(body)
        else:
            msg["content"] = "Stub answer."
        print(f"stub call {CALLS['n']}: model={body.get('model')} tool_choice={json.dumps(tc)[:80]}", flush=True)
        self._send(200, {"id": f"chatcmpl-{CALLS['n']}", "object": "chat.completion", "created": int(time.time()),
                         "model": body.get("model"), "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                         "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})

    def log_message(self, *a):
        pass


class S(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"llm stub on :{port}", flush=True)
    S(("::", port), H).serve_forever()
