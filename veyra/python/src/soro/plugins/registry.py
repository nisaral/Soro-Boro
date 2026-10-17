"""Veyra Plugin System: Plugin registration, metadata, and discovery interface.

Enables extending Veyra with custom tool adapters, policy packs, recovery strategies,
verification hooks, and observability exporters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from soro.policy.base import RoutePolicy
from soro.policy.deterministic import DeterministicRoutePolicy
from soro.policy.history_adaptive import AdaptiveHistoryRoutePolicy
from soro.policy.learning import BanditRoutePolicy
from soro.policy.reliability import ReliabilityAwareRoutePolicy
from soro.policy.selective import SelectiveResolutionPolicy


@dataclass
class PluginMetadata:
    name: str
    version: str = "0.1.0"
    compatibility: str = ">=0.2.0"
    capabilities: List[str] = field(default_factory=list)
    risk_level: str = "low"
    description: str = ""


class PolicyPluginRegistry:
    """Central registry for built-in and third-party Veyra plugins."""

    def __init__(self):
        self._factories: Dict[str, Callable[..., Any]] = {}
        self._metadata: Dict[str, PluginMetadata] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_plugin(
            "deterministic",
            lambda **kw: DeterministicRoutePolicy(),
            metadata=PluginMetadata(
                name="deterministic",
                version="0.2.0",
                compatibility=">=0.2.0",
                capabilities=["routing", "policy_pack"],
                risk_level="low",
                description="Deterministic hard-constraint route policy",
            ),
        )
        self.register_plugin(
            "tage",
            lambda **kw: AdaptiveHistoryRoutePolicy(),
            metadata=PluginMetadata(
                name="tage",
                version="0.2.0",
                compatibility=">=0.2.0",
                capabilities=["routing", "adaptive_history"],
                risk_level="low",
                description="TAgE history-adaptive branch-prediction routing policy",
            ),
        )
        self.register_plugin(
            "reliability",
            lambda **kw: ReliabilityAwareRoutePolicy(),
            metadata=PluginMetadata(
                name="reliability",
                version="0.2.0",
                compatibility=">=0.2.0",
                capabilities=["routing", "reliability_tracker"],
                risk_level="low",
                description="Reliability-aware tool resolution policy",
            ),
        )
        self.register_plugin(
            "selective",
            lambda **kw: SelectiveResolutionPolicy(),
            metadata=PluginMetadata(
                name="selective",
                version="0.2.0",
                compatibility=">=0.2.0",
                capabilities=["routing", "selective_resolution"],
                risk_level="low",
                description="Selective resolution fallback policy",
            ),
        )
        self.register_plugin(
            "bandit",
            lambda **kw: BanditRoutePolicy(**kw),
            metadata=PluginMetadata(
                name="bandit",
                version="0.2.0",
                compatibility=">=0.2.0",
                capabilities=["routing", "online_learning"],
                risk_level="medium",
                description="Contextual bandit route policy",
            ),
        )

    def register_plugin(
        self,
        name: str,
        factory: Callable[..., Any],
        metadata: Optional[PluginMetadata] = None,
    ) -> None:
        key = name.lower()
        self._factories[key] = factory
        self._metadata[key] = metadata or PluginMetadata(name=key)

    def register(self, name: str, factory: Callable[..., RoutePolicy]) -> None:
        """Backwards-compatible registration method."""
        self.register_plugin(name, factory)

    def get(self, name: str, **kwargs: Any) -> Any:
        key = name.lower()
        if key not in self._factories:
            raise KeyError(f"Unknown Veyra plugin '{name}'. Available: {list(self._factories.keys())}")
        return self._factories[key](**kwargs)

    def inspect(self, name: str) -> Dict[str, Any]:
        key = name.lower()
        if key not in self._metadata:
            raise KeyError(f"Plugin '{name}' not found.")
        meta = self._metadata[key]
        return {
            "name": meta.name,
            "version": meta.version,
            "compatibility": meta.compatibility,
            "capabilities": meta.capabilities,
            "risk_level": meta.risk_level,
            "description": meta.description,
        }

    def validate(self, name: str) -> Dict[str, Any]:
        key = name.lower()
        if key not in self._factories:
            return {"valid": False, "error": f"Plugin '{name}' is not registered."}
        try:
            inst = self.get(key)
            return {"valid": True, "instance_type": type(inst).__name__}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def list_plugins(self) -> List[str]:
        return sorted(self._factories.keys())


# Global default plugin registry
default_plugins = PolicyPluginRegistry()


def veyra_plugin(
    name: Optional[str] = None,
    version: str = "0.1.0",
    capabilities: Optional[List[str]] = None,
    risk_level: str = "low",
    description: str = "",
) -> Callable[[Type[Any]], Type[Any]]:
    """Decorator to register a custom class or factory as a Veyra plugin."""

    def decorator(cls_or_factory: Type[Any]) -> Type[Any]:
        plugin_name = name or cls_or_factory.__name__.lower()
        meta = PluginMetadata(
            name=plugin_name,
            version=version,
            capabilities=capabilities or [],
            risk_level=risk_level,
            description=description,
        )
        default_plugins.register_plugin(plugin_name, cls_or_factory, metadata=meta)
        return cls_or_factory

    return decorator
