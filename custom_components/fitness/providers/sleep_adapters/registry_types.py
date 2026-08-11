"""Types shared by provider-specific sleep adapters and their registry."""
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SleepAdapterSpec:
    name: str
    domains: tuple[str, ...]
    fields: dict[str, tuple[str, ...]]
