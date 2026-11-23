import json
import os
import secrets
import time
import urllib.request

from flask import request

# Fission's Python environment calls main(). Secrets are mounted as files by `fission fn create --secret app-env`.
SECRET_DIR = "/secrets/default/app-env"
STARTED = time.time()
calls = 0  # per pod. 1 means this pod was just started for this request: a cold start


def secret(name:str) -> str:
    with open(os.path.join(SECRET_DIR, name)) as f:
        return f.read().strip().strip("\"'")  # .env values may carry quotes


def main():
    global calls
    calls += 1
    began = time.time()

    expected = secret("API_KEY")
    sent = request.headers.get("X-API-Key", "")
    if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
        return json.dumps({"error": "Missing or wrong API key"}), 401

    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "there"))[:60]
    role = str(body.get("role", "new joiner"))[:40]

    payload = {
        "model": secret("GROQ_FREE_MODEL") if os.path.exists(os.path.join(SECRET_DIR, "GROQ_FREE_MODEL")) else "openai/gpt-oss-20b",
        "messages": [
            {"role": "system", "content": "You write a short, warm welcome note (max 60 words) for a new joiner's first day. No emojis."},
            {"role": "user", "content": f"Name: {name}. Role: {role}."},
        ],
        "temperature": 0,
        "max_tokens": 400,
        "reasoning_effort": "low",
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {secret('GROQ_API_KEY')}", "Content-Type": "application/json", "User-Agent": "onboarding-buddy-fission"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            note = json.load(resp)["choices"][0]["message"]["content"].strip()
    except Exception as e:  # shortcut: one plain fallback note if Groq is down; add retries if this becomes important
        note = f"Welcome to the team, {name}! We're glad you're here. Your buddy will help you get started."
        return json.dumps({"note": note, "source": "fallback", "error": str(e)[:200]})

    return json.dumps({
        "note": note,
        "source": "groq",
        "pod_call_number": calls,                      # 1 = cold start for this pod
        "pod_age_seconds": round(time.time() - STARTED, 2),
        "handler_seconds": round(time.time() - began, 2),
    })
