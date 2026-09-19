"""
matcher.py
----------
Core rule-based reasoning engine for the Health Check Chatbot.

Responsibilities:
1. Extract canonical symptoms and red-flag (emergency) indicators from free-text
   user input, using a synonym dictionary (a lightweight stand-in for full NLP).
2. Score each condition in the knowledge base against the symptoms collected
   during the conversation, and rank the most likely matches.
3. Determine an overall urgency level, factoring in reported severity/duration.

This module has no Flask dependency and can be unit-tested in isolation.
"""

import json
import os
import re

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

with open(os.path.join(DATA_DIR, "symptom_synonyms.json"), encoding="utf-8") as f:
    SYMPTOM_SYNONYMS = json.load(f)

with open(os.path.join(DATA_DIR, "red_flags.json"), encoding="utf-8") as f:
    RED_FLAGS = json.load(f)

with open(os.path.join(DATA_DIR, "conditions.json"), encoding="utf-8") as f:
    CONDITIONS = json.load(f)

# Urgency levels ranked from least to most urgent. Higher index = more urgent.
URGENCY_ORDER = ["self_care", "routine", "urgent", "emergency"]

URGENCY_LABELS = {
    "self_care": "Self-care",
    "routine": "Routine — see a doctor within a few days",
    "urgent": "Urgent — seek medical attention soon",
    "emergency": "EMERGENCY — seek immediate medical help",
}


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace/punctuation for simple keyword matching."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} "  # pad so substring matches don't merge words


def extract_red_flags(text: str):
    """Return a list of (flag_id, message) for any emergency keywords found in text."""
    norm = _normalize(text)
    found = []
    for flag_id, flag in RED_FLAGS.items():
        for kw in flag["keywords"]:
            if f" {kw} " in norm or norm.strip().startswith(kw) or kw in norm:
                found.append((flag_id, flag["message"]))
                break
    return found


def extract_symptoms(text: str):
    """Return a set of canonical symptom keys found in the free-text input."""
    norm = _normalize(text)
    found = set()
    for symptom_key, synonyms in SYMPTOM_SYNONYMS.items():
        for syn in synonyms:
            if syn in norm:
                found.add(symptom_key)
                break
    return found


def score_conditions(symptom_keys):
    """
    Score every condition in the knowledge base against the given set of
    canonical symptom keys. Score = (sum of weights matched) / (sum of all
    weights for that condition), expressed as a percentage.

    Returns a list of dicts sorted by descending score, each with:
        id, name, urgency, advice, score (0-100), matched_symptoms
    """
    results = []
    for cond in CONDITIONS:
        total_weight = sum(cond["symptoms"].values())
        matched = {s: w for s, w in cond["symptoms"].items() if s in symptom_keys}
        matched_weight = sum(matched.values())
        if matched_weight == 0:
            continue
        score = round((matched_weight / total_weight) * 100)
        results.append({
            "id": cond["id"],
            "name": cond["name"],
            "urgency": cond["urgency"],
            "advice": cond["advice"],
            "score": score,
            "matched_symptoms": list(matched.keys()),
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def bump_urgency(level: str, steps: int = 1, cap: str = "emergency") -> str:
    """Escalate an urgency level by `steps` positions, capped at `cap`."""
    idx = URGENCY_ORDER.index(level)
    cap_idx = URGENCY_ORDER.index(cap)
    idx = min(idx + steps, cap_idx)
    return URGENCY_ORDER[idx]


def compute_final_urgency(top_conditions, severity: str, duration: str) -> str:
    """
    Combine the urgency of the best-matched condition(s) with user-reported
    severity and duration to produce a final urgency level.

    Escalation from symptom-matching is deliberately capped at 'urgent':
    the 'emergency' label is reserved for explicit red-flag keyword
    detection (see extract_red_flags), so a routine symptom combination
    can never be auto-labelled an emergency just from severity/duration.
    """
    if not top_conditions:
        return "self_care"

    urgency = top_conditions[0]["urgency"]

    # Escalate if the user describes symptoms as severe.
    if severity == "severe":
        urgency = bump_urgency(urgency, 1, cap="urgent")

    # Escalate if symptoms have persisted a long time (fever-type illnesses
    # especially warrant review if they drag on).
    if duration == "more_than_3_days":
        urgency = bump_urgency(urgency, 1, cap="urgent")

    return urgency
