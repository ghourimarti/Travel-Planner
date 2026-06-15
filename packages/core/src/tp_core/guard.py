"""Prompt-injection guard (S12d, Decision 18): neutralize untrusted text before it
becomes prompt content.

Defense-in-depth, NOT the sole defense — the critic's grounding gate (S7) is the
enforcement boundary that rejects any place not in the allowed list. This sanitizer
shrinks the attack surface: it caps payload size, removes control characters, flattens
newlines (so injected text can't fake a new message), and masks instruction/role markers.
"""

from __future__ import annotations

import re

_MAX_LEN = 400  # bounds an injected payload; real cities/interests/POI names are short
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_REPLACEMENT = "[filtered]"

# Instruction-override / role / template markers an injection uses to escape "this is data".
_INJECTION_RE = re.compile(
    r"""(
        ignore\s+(all\s+|the\s+|any\s+)*previous\s+(instructions|prompts)
      | disregard\s+(the\s+|all\s+)*(above|previous|prior)
      | forget\s+(everything|all|the\s+above)
      | you\s+are\s+now\b
      | new\s+(instructions|system\s+prompt)\b
      | (system|assistant|developer)\s*:           # fake chat-role prefixes
      | <\|.*?\|>                                   # chat template tokens
      | ```                                          # code-fence escapes
    )""",
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


def sanitize_untrusted(text: str) -> str:
    """Return ``text`` made safe to embed as prompt *data* (never instructions)."""
    cleaned = _CONTROL_RE.sub(" ", text)
    cleaned = re.sub(r"\s*[\r\n]+\s*", " ", cleaned)  # flatten line breaks
    cleaned = _INJECTION_RE.sub(_REPLACEMENT, cleaned)
    cleaned = cleaned[:_MAX_LEN].strip()
    return cleaned
