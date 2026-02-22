"""
Fallback chain for API resilience.
Tries providers in order; if one fails, falls back to next.
If one succeeds but has empty fields, next providers complement.
"""
import logging
from dataclasses import dataclass, field
from typing import Callable, Any

logger = logging.getLogger(__name__)


@dataclass
class FallbackResult:
    success: bool
    data: dict = field(default_factory=dict)
    source: str = ""
    complemented_from: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class FallbackChain:
    """Execute providers in order with fallback + field complementation."""

    def __init__(self, providers: list[tuple[str, Callable]]):
        """
        providers: list of (name, async_callable) tuples.
        Each callable should return a dict on success or raise on failure.
        """
        self.providers = providers

    async def execute(self) -> FallbackResult:
        result = FallbackResult(success=False)

        for name, fn in self.providers:
            try:
                data = await fn()
                if not data or not isinstance(data, dict):
                    result.errors.append(f"{name}: empty response")
                    continue

                if not result.success:
                    # First successful provider
                    result.success = True
                    result.data = data
                    result.source = name
                else:
                    # Complement empty fields from this provider
                    complemented = False
                    for key, value in data.items():
                        if value and not result.data.get(key):
                            result.data[key] = value
                            complemented = True
                    if complemented:
                        result.complemented_from.append(name)

                # Check if all fields are filled — stop early
                if result.success and all(v for v in result.data.values()):
                    break

            except Exception as e:
                logger.warning(f"FallbackChain: {name} failed: {e}")
                result.errors.append(f"{name}: {str(e)}")
                continue

        return result
