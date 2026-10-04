#!/usr/bin/env python
"""Brutal inspection of the whole stack, chain: local-vllm -> groq -> openai.

    python scripts/inspect_stack_vllm.py

Exits non-zero if anything failed, or if any fault injection could not prove it landed.
All logic lives in `_inspect_common.py`; this file only names the engine, so the two
entrypoints cannot drift apart.
"""

from __future__ import annotations

import sys

from _inspect_common import exclusive_run, main

if __name__ == "__main__":
    with exclusive_run("inspect-vllm"):
        sys.exit(main("vllm"))
