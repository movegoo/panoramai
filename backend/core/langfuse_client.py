"""
Langfuse tracing for LLM calls.
Graceful degradation: if keys are not configured, all calls are no-ops.
"""
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_langfuse = None
_initialized = False


def _get_langfuse():
    """Lazy singleton — returns Langfuse instance or None."""
    global _langfuse, _initialized
    if _initialized:
        return _langfuse
    _initialized = True
    try:
        from core.config import settings
        if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
            logger.info("Langfuse: keys not configured, tracing disabled")
            return None
        from langfuse import Langfuse
        _langfuse = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("Langfuse: tracing enabled")
    except Exception as e:
        logger.warning(f"Langfuse init failed (non-fatal): {e}")
        _langfuse = None
    return _langfuse


def trace_generation(
    *,
    name: str,
    model: str,
    input: Any,
    output: Any,
    usage: Optional[dict] = None,
    metadata: Optional[dict] = None,
):
    """Log a single LLM generation to Langfuse.

    Args:
        name: identifier for the call site (e.g. "creative_analyzer")
        model: model id (e.g. "claude-haiku-4-5-20251001")
        input: the prompt / messages sent
        output: the response text or object
        usage: {"input_tokens": ..., "output_tokens": ...} (normalized)
        metadata: extra context
    """
    try:
        lf = _get_langfuse()
        if lf is None:
            return
        trace = lf.trace(name=name, metadata=metadata or {})
        trace.generation(
            name=name,
            model=model,
            input=input,
            output=output,
            usage=usage or {},
            metadata=metadata or {},
        )
    except Exception as e:
        logger.debug(f"Langfuse trace error (non-fatal): {e}")


def flush():
    """Flush pending events. Call on shutdown."""
    lf = _get_langfuse()
    if lf:
        try:
            lf.flush()
        except Exception:
            pass
