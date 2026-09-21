"""Immutable, fail-closed configuration for the sealed Stage-G paper candidate."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, get_type_hints

from coinmaster.domain.wave_overlay import Candidate


class ConfigurationError(ValueError):
    """A configuration file is absent, malformed, or outside the sealed schema."""


@dataclass(frozen=True)
class LoadedCandidate:
    candidate: Candidate
    sha256: str
    path: Path


@dataclass(frozen=True)
class InstanceConfig:
    instance_id: str
    venue: str
    mode: str
    strategy_config: Path
    state_db: Path
    trader_id: str
    strategy_id: str
    order_id_tag: str
    path: Path


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"INVALID_CONFIGURATION:{path}") from error
    if not isinstance(value, dict):
        raise ConfigurationError("CONFIGURATION_MUST_BE_OBJECT")
    return value


def canonical_candidate_json(candidate: Candidate) -> str:
    """Canonical candidate content only; labels and filesystem names never affect it."""
    return json.dumps(asdict(candidate), sort_keys=True, separators=(",", ":"), allow_nan=False)


def candidate_content_hash(candidate: Candidate) -> str:
    return hashlib.sha256(canonical_candidate_json(candidate).encode("utf-8")).hexdigest()


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigurationError(f"INVALID_CANDIDATE_VALUE:{name}")
    return float(value)


def _candidate_from_mapping(value: dict[str, Any]) -> Candidate:
    names = {item.name for item in fields(Candidate)}
    if set(value) != names:
        missing, extra = sorted(names - set(value)), sorted(set(value) - names)
        raise ConfigurationError(f"CANDIDATE_FIELDS_MISMATCH:missing={missing}:extra={extra}")
    hints = get_type_hints(Candidate)
    normalized: dict[str, Any] = {}
    for item in fields(Candidate):
        raw, annotation = value[item.name], hints[item.name]
        if annotation is int:
            if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
                raise ConfigurationError(f"INVALID_CANDIDATE_VALUE:{item.name}")
            normalized[item.name] = raw
        elif annotation is float:
            normalized[item.name] = _finite_number(raw, item.name)
        elif annotation is bool:
            if not isinstance(raw, bool):
                raise ConfigurationError(f"INVALID_CANDIDATE_VALUE:{item.name}")
            normalized[item.name] = raw
        else:
            if not isinstance(raw, list) or len(raw) != 3:
                raise ConfigurationError(f"INVALID_CANDIDATE_VALUE:{item.name}")
            normalized[item.name] = tuple(_finite_number(part, item.name) for part in raw)
    candidate = Candidate(**normalized)
    if (candidate.wave_quantiles != tuple(sorted(candidate.wave_quantiles))
            or any(not 0 <= item <= 1 for item in candidate.wave_quantiles)
            or candidate.btc_tp_fractions_initial_qty != tuple(sorted(candidate.btc_tp_fractions_initial_qty))
            or any(not 0 <= item <= 1 for item in candidate.btc_tp_fractions_initial_qty)
            or sum(candidate.btc_tp_fractions_initial_qty) > 1
            or candidate.btc_notional_multiplier <= 0
            or candidate.max_parent_notional <= 0
            or candidate.sol_size_multipliers_h != tuple(sorted(candidate.sol_size_multipliers_h))
            or any(item <= 0 for item in candidate.sol_size_multipliers_h)
            or candidate.sol_entry_z != tuple(sorted(candidate.sol_entry_z))
            or len(set(candidate.sol_entry_z)) != len(candidate.sol_entry_z)
            or any(item <= 0 for item in candidate.sol_entry_z)
            or candidate.sol_exit_half_z < 0
            or candidate.sol_exit_all_z < 0
            or candidate.sol_exit_all_z > candidate.sol_exit_half_z
            or not 0 < candidate.btc_close_trail_fraction < 1):
        raise ConfigurationError("INVALID_CANDIDATE_CONSTRAINTS")
    return candidate


def load_candidate(path: Path) -> LoadedCandidate:
    document = _read_object(path)
    if set(document) != {"candidate"} or not isinstance(document.get("candidate"), dict):
        raise ConfigurationError("CANDIDATE_DOCUMENT_SCHEMA")
    candidate = _candidate_from_mapping(document["candidate"])
    return LoadedCandidate(candidate=candidate, sha256=candidate_content_hash(candidate), path=path.resolve())


def load_instance_config(path: Path) -> InstanceConfig:
    document = _read_object(path)
    names = {item.name for item in fields(InstanceConfig)} - {"path"}
    if set(document) != names:
        missing, extra = sorted(names - set(document)), sorted(set(document) - names)
        raise ConfigurationError(f"INSTANCE_FIELDS_MISMATCH:missing={missing}:extra={extra}")
    strings = {name: document[name] for name in names if name not in {"strategy_config", "state_db"}}
    if any(not isinstance(value, str) or not value.strip() for value in strings.values()):
        raise ConfigurationError("INVALID_INSTANCE_VALUE")
    if document["mode"] != "paper" or document["venue"] != "BYBIT":
        raise ConfigurationError("UNSUPPORTED_INSTANCE_MODE_OR_VENUE")
    base = path.resolve().parent
    for name in ("strategy_config", "state_db"):
        if not isinstance(document[name], str) or not document[name]:
            raise ConfigurationError(f"INVALID_INSTANCE_VALUE:{name}")
    return InstanceConfig(
        **strings,
        strategy_config=(base / document["strategy_config"]).resolve(),
        state_db=(base / document["state_db"]).resolve(),
        path=path.resolve(),
    )
