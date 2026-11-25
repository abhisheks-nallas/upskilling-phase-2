import re

# Simple guardrails for the chat endpoint (Bedrock Guardrails is not available on this account, see ADR 001).
# shortcut: pattern lists catch the common attacks only, a determined attacker can rephrase. Upgrade to Bedrock Guardrails or a classifier when available.
MAX_MESSAGE_CHARS = 2000

INJECTION_PATTERNS = [
    r"ignore (all |any |the |your )?(previous|prior|above|earlier)? ?(instructions|rules|prompt)",
    r"disregard (all |any |the |your )?(previous|prior|above|earlier)? ?(instructions|rules|prompt)",
    r"(reveal|show|print|repeat|tell me) (me )?(your |the )?(system|hidden|initial) (prompt|instructions|message)",
    r"(translate|repeat|summari[sz]e|rewrite|paraphrase|encode).{0,60}(instructions|everything you were (told|given)|your (prompt|rules)|before this message)",
    r"(ignore|disregard|forget) (the )?(lines|text|messages?|everything) (above|before)",
    r"you are now (?!a new joiner)",
    r"\b(jailbreak|developer mode|dan mode)\b",
    r"pretend (that )?you (have no|are not|don't have) (rules|restrictions|limits)",
]
SECRET_PATTERNS = [
    r"gsk_[A-Za-z0-9]{20,}",                # Groq keys
    r"AKIA[0-9A-Z]{16}",                    # AWS access key ids
    r"(sk|pk)-lf-[A-Za-z0-9-]{20,}",        # Langfuse keys
    r"\b\d{3}-\d{2}-\d{4}\b",               # SSN-shaped numbers
]
REFUSAL = "Sorry, I can't help with that. I can answer questions about your first 30 days, access, and company policies."


def check_input(message:str) -> str | None:
    """Returns the reason the message is blocked, or None if it is fine."""
    if len(message) > MAX_MESSAGE_CHARS:
        return "message too long"
    text = message.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text):
            return "prompt injection"
    return None


def clean_output(text:str) -> str:
    """Hides anything that looks like a key or an ID number in the model's answer."""
    for pattern in SECRET_PATTERNS:
        text = re.sub(pattern, "[hidden]", text)
    return text
