"""Load and validate intent overlay YAMLs.

Catches typos and schema errors before they reach the LLM prompts.
Returns typed OverlayConfig dataclasses with fields matching the YAML schema.
Validation fails loudly if a required field is missing or a card_slot is malformed.

See docs/article-spec.md Section 6.6 for overlay schema.
See docs/article-spec.md Section 10.5.1 for canonical callout keys.
See docs/article-spec.md Section 6.6.3 for overlay variable vocabulary.
See docs/v2-module-architecture.md "lib/overlay_loader.py" for API contract.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

OVERLAYS_DIR = Path(__file__).resolve().parent.parent / "overlays"

# Spec Section 10.5.1 — canonical archetype-neutral callout keys
CANONICAL_CALLOUT_KEYS = frozenset({
    "numerical_proof",
    "reality_check",
    "procedural_guidance",
    "deal_preservation",
    "qualification_gate",
    "authority_note",
    "situational_example",
    "clarification_section",
})

# Spec Section 6.6.3 — overlay variable vocabulary
VALID_OVERLAY_VARIABLES = frozenset({
    "Topic", "Term", "Year",
    "Option A", "Option B",
    "Winner", "Second", "Niche", "Niche Use Case",
})

VALID_INTENTS = frozenset({"definition", "process", "decision", "cost", "comparison"})
VALID_BLUF = frozenset({"include", "omit", "conditional"})
VALID_BODY = frozenset({"tables_dominant", "bullets_dominant", "mixed"})

_VARIABLE_RE = re.compile(r"\{([^}]+)\}")


class OverlayValidationError(Exception):
    """Raised when an overlay YAML fails validation."""


@dataclass(frozen=True)
class CardSlot:
    role: str
    h3_pattern: str
    bullet_label_hints: list[str]


@dataclass(frozen=True)
class OverlayConfig:
    intent: str
    display_name: str
    spec_reference: str
    bluf_default: Literal["include", "omit", "conditional"]
    body_default: Literal["tables_dominant", "bullets_dominant", "mixed"]
    card_slots: list[CardSlot]
    callout_preferences: dict[str, list[str]]
    default_atf_faq_patterns: list[str]
    question_h2_floor_when_paa_sparse: int
    question_h2_floor_when_paa_rich: int


def _validate_variables(text: str, field_name: str, intent: str) -> None:
    """Check that all {variables} in text are from the valid vocabulary."""
    for match in _VARIABLE_RE.finditer(text):
        var_name = match.group(1)
        if var_name not in VALID_OVERLAY_VARIABLES:
            raise OverlayValidationError(
                f"[{intent}] Unknown variable '{{{var_name}}}' in {field_name}. "
                f"Valid variables: {sorted(VALID_OVERLAY_VARIABLES)}"
            )


def _validate_overlay(raw: dict, intent: str) -> OverlayConfig:
    """Validate raw YAML dict and return typed OverlayConfig."""
    errors = []

    # (a) All required top-level fields
    required_fields = {
        "intent", "display_name", "spec_reference", "bluf_default",
        "body_default", "card_slots", "callout_preferences",
        "default_atf_faq_patterns", "question_h2_floor_when_paa_sparse",
        "question_h2_floor_when_paa_rich",
    }
    missing = required_fields - set(raw.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")

    if errors:
        raise OverlayValidationError(f"[{intent}] " + "; ".join(errors))

    # Intent matches filename
    if raw["intent"] != intent:
        errors.append(f"intent field '{raw['intent']}' does not match filename '{intent}'")

    # bluf_default and body_default values
    if raw["bluf_default"] not in VALID_BLUF:
        errors.append(f"bluf_default '{raw['bluf_default']}' not in {sorted(VALID_BLUF)}")
    if raw["body_default"] not in VALID_BODY:
        errors.append(f"body_default '{raw['body_default']}' not in {sorted(VALID_BODY)}")

    # (b) Exactly 4 card_slots
    card_slots_raw = raw.get("card_slots", [])
    if len(card_slots_raw) != 4:
        errors.append(f"Expected 4 card_slots, got {len(card_slots_raw)}")

    # Validate each card slot
    card_slots = []
    for i, slot in enumerate(card_slots_raw):
        if not isinstance(slot, dict):
            errors.append(f"card_slots[{i}] is not a dict")
            continue
        slot_missing = {"role", "h3_pattern", "bullet_label_hints"} - set(slot.keys())
        if slot_missing:
            errors.append(f"card_slots[{i}] missing fields: {sorted(slot_missing)}")
            continue

        # (c) Each card_slot has exactly 4 bullet_label_hints
        hints = slot.get("bullet_label_hints", [])
        if len(hints) != 4:
            errors.append(f"card_slots[{i}] ({slot.get('role', '?')}): expected 4 bullet_label_hints, got {len(hints)}")

        # (f) Variable validation on h3_pattern
        _validate_variables(slot["h3_pattern"], f"card_slots[{i}].h3_pattern", intent)

        card_slots.append(CardSlot(
            role=slot["role"],
            h3_pattern=slot["h3_pattern"],
            bullet_label_hints=list(hints),
        ))

    # (d) Exactly 3 default_atf_faq_patterns
    faq_patterns = raw.get("default_atf_faq_patterns", [])
    if len(faq_patterns) != 3:
        errors.append(f"Expected 3 default_atf_faq_patterns, got {len(faq_patterns)}")

    # (f) Variable validation on FAQ patterns
    for i, pattern in enumerate(faq_patterns):
        _validate_variables(pattern, f"default_atf_faq_patterns[{i}]", intent)

    # (e) callout_preferences values reference ONLY canonical keys
    callout_prefs = raw.get("callout_preferences", {})
    if not isinstance(callout_prefs, dict):
        errors.append("callout_preferences must be a dict")
    else:
        for section_role, callout_keys in callout_prefs.items():
            if not isinstance(callout_keys, list):
                errors.append(f"callout_preferences['{section_role}'] must be a list")
                continue
            for key in callout_keys:
                if key not in CANONICAL_CALLOUT_KEYS:
                    errors.append(
                        f"callout_preferences['{section_role}'] contains unknown "
                        f"callout key '{key}'. Valid keys: {sorted(CANONICAL_CALLOUT_KEYS)}"
                    )

    if errors:
        raise OverlayValidationError(f"[{intent}] " + "; ".join(errors))

    return OverlayConfig(
        intent=raw["intent"],
        display_name=raw["display_name"],
        spec_reference=raw["spec_reference"],
        bluf_default=raw["bluf_default"],
        body_default=raw["body_default"],
        card_slots=card_slots,
        callout_preferences=dict(callout_prefs),
        default_atf_faq_patterns=list(faq_patterns),
        question_h2_floor_when_paa_sparse=int(raw["question_h2_floor_when_paa_sparse"]),
        question_h2_floor_when_paa_rich=int(raw["question_h2_floor_when_paa_rich"]),
    )


def load_overlay(intent: str) -> OverlayConfig:
    """Load and validate an intent overlay YAML.

    Args:
        intent: One of 'definition', 'process', 'decision', 'cost', 'comparison'.

    Returns:
        Validated OverlayConfig dataclass.

    Raises:
        OverlayValidationError: On any schema or content validation failure.
        FileNotFoundError: If the overlay YAML doesn't exist.
    """
    if intent not in VALID_INTENTS:
        raise OverlayValidationError(f"Unknown intent '{intent}'. Valid: {sorted(VALID_INTENTS)}")

    yaml_path = OVERLAYS_DIR / f"{intent}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Overlay not found: {yaml_path}")

    with open(yaml_path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise OverlayValidationError(f"[{intent}] YAML root must be a mapping, got {type(raw).__name__}")

    return _validate_overlay(raw, intent)


def list_overlays() -> list[str]:
    """List available overlay intent names.

    Returns:
        Sorted list of intent strings (e.g., ['comparison', 'cost', ...]).
    """
    if not OVERLAYS_DIR.exists():
        return []
    return sorted(
        p.stem for p in OVERLAYS_DIR.glob("*.yaml")
        if p.stem in VALID_INTENTS
    )
