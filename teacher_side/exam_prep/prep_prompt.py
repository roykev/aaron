"""Prompt builders for the student exam-prep generator.

The prompt TEXT lives in ``prep_prompt.yaml`` next to this file (asset_creation
style) so it can be edited without touching Python. This module just loads that
YAML and fills the ``str.format`` placeholders:
  * system_prompt -> {language} {course_data}
  * user_prompt   -> {n_quiz} {n_eval} {total} {t_basic} {t_adv_cov} {t_adv_diff}

Design choices baked into the prompt (see the YAML for the full text):
  * Output is STRICT, valid JSON only (no prose, no markdown fences).
  * Questions mirror the class schema: 4-option multiple-choice with a ``correct``
    1-based index string ("1".."4", or "1,3" when several are correct).
  * Two types: ``quiz`` (easier, practice) and ``evaluation`` (harder,
    integrative); every question carries a short ``explanation``.
  * A fixed difficulty distribution (the ``tiers`` block) across quiz + eval.
  * The math/code/escaping formatting rules match the platform's asset_creation
    ``quiz`` contract so content renders and loads into the DB correctly.
"""
from pathlib import Path

import yaml

_CFG = yaml.safe_load((Path(__file__).parent / "prep_prompt.yaml").read_text(encoding="utf-8"))

# Config surfaced for the runner / validator (one source of truth).
DEFAULTS = _CFG.get("defaults", {})
# Tier definitions: list of (name, target_fraction), order preserved.
TIERS = [(t["name"], float(t["weight"])) for t in _CFG["tiers"]]


def tier_targets(total):
    """Split ``total`` questions across the tier fractions (largest remainder)."""
    raw = [(name, total * pct) for name, pct in TIERS]
    floors = [(name, int(v)) for name, v in raw]
    used = sum(v for _, v in floors)
    remainder = total - used
    # hand out the leftover to the largest fractional parts
    order = sorted(range(len(raw)), key=lambda i: raw[i][1] - floors[i][1], reverse=True)
    counts = dict(floors)
    for i in order[:remainder]:
        counts[raw[i][0]] += 1
    return counts


def compose_system_prompt(language, course_data):
    """System prompt: role + the (already trimmed) course data + global rules."""
    return _CFG["system_prompt"].format(language=language, course_data=course_data)


def compose_user_prompt(language, n_quiz, n_eval):
    """User prompt: the task, the allocation contract, and the JSON schema."""
    total = n_quiz + n_eval
    targets = tier_targets(total)
    return _CFG["user_prompt"].format(
        language=language, n_quiz=n_quiz, n_eval=n_eval, total=total,
        t_basic=targets["basic_coverage"],
        t_adv_cov=targets["advanced_coverage"],
        t_adv_diff=targets["advanced_difficult"],
    )
