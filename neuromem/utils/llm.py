"""Unified LLM chat-completion helper for NeuroMem.

Dispatches to OpenAI or Ollama based on the model name prefix, mirroring the
provider routing already used in `neuromem/utils/embeddings.py`. Lets every
LLM caller in the SDK use one signature regardless of provider, so flipping
a model name in `neuromem.yaml` is enough to switch providers — no per-call
``provider="..."`` plumbing required.

Routing rules:
- Model name starts with ``ollama/`` (e.g. ``ollama/qwen2.5-coder:7b``)
  → strip prefix and call local Ollama at ``OLLAMA_BASE_URL`` / default host.
- Bare names that match a known local model family (qwen, llama, mistral,
  gemma, phi, gpt-oss) also route to Ollama. This matches how
  ``utils/embeddings.py`` allowlists ``nomic-embed-text`` etc.
- Anything else → OpenAI Chat Completions (``OPENAI_API_KEY`` required).
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from neuromem.utils.logging import get_logger

logger = get_logger(__name__)


_OLLAMA_FAMILIES = (
    "qwen",
    "llama",
    "mistral",
    "gemma",
    "phi",
    "gpt-oss",
    "deepseek",
    "codellama",
    "tinyllama",
)


def is_ollama_model(model: str) -> bool:
    """Return True when the model name should route to a local Ollama server."""
    if not model:
        return False
    if model.startswith("ollama/"):
        return True
    clean = model.split(":", 1)[0].lower()
    return any(clean.startswith(family) for family in _OLLAMA_FAMILIES)


def _strip_ollama_prefix(model: str) -> str:
    return model[len("ollama/") :] if model.startswith("ollama/") else model


def chat_completion(
    model: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    ollama_base_url: Optional[str] = None,
) -> str:
    """Run a single chat completion and return the assistant's text content.

    Args:
        model: Model name. ``ollama/<name>`` or a known local family routes to
            Ollama; everything else routes to OpenAI.
        messages: OpenAI-style chat messages (``[{"role": ..., "content": ...}]``).
        temperature: Sampling temperature (default 0.3).
        max_tokens: Optional output cap. Forwarded as ``max_tokens`` (OpenAI)
            or ``num_predict`` (Ollama).
        ollama_base_url: Override the Ollama host. Falls back to
            ``OLLAMA_BASE_URL`` env var, then ``http://localhost:11434``.

    Returns:
        The assistant message content as a stripped string.

    Raises:
        Whatever the underlying provider raises. Callers are expected to
        wrap this in their existing try/except — the dispatcher does not
        swallow errors so they remain visible at the caller's log site.
    """
    if is_ollama_model(model):
        import ollama

        host = ollama_base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        client = ollama.Client(host=host)
        options: Dict[str, object] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        response = client.chat(
            model=_strip_ollama_prefix(model),
            messages=messages,
            options=options,
        )
        return response["message"]["content"].strip()

    import openai

    client = openai.OpenAI()
    kwargs: Dict[str, object] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()
