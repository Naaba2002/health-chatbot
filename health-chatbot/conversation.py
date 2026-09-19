"""
conversation.py
----------------
A small finite-state machine that drives the chatbot's multi-turn dialogue:

  GREETING -> COLLECTING_SYMPTOMS -> ASK_MORE_SYMPTOMS -> ASK_SEVERITY
  -> ASK_DURATION -> RESULT -> (restart)

Each call to `handle_message` takes the current session state (a plain dict,
easy to keep in memory or serialize) and the user's latest message, and
returns the bot's reply, any quick-reply button suggestions, and the updated
session state.
"""

from matcher import (
    extract_red_flags,
    extract_symptoms,
    score_conditions,
    compute_final_urgency,
    URGENCY_LABELS,
)

DISCLAIMER = (
    "Please remember: I'm not a doctor and this isn't a medical diagnosis. "
    "I can only offer general, preliminary guidance based on the symptoms you describe."
)

EMERGENCY_FOOTER = (
    "If you are in immediate danger or your condition is worsening, please call your "
    "local emergency number or go to the nearest emergency room right away."
)


def new_session():
    return {
        "state": "GREETING",
        "symptoms": [],
        "severity": None,
        "duration": None,
    }


def _greeting_reply():
    text = (
        "Hello! I'm a health check assistant. I can help you think through common, "
        "non-emergency symptoms and suggest what to do next.\n\n" + DISCLAIMER + "\n\n"
        "If you ever feel this is a medical emergency, please stop and contact emergency "
        "services or go to the nearest hospital immediately.\n\n"
        "What symptom(s) are you experiencing today? Describe them in your own words "
        "(e.g. \"I have a fever and headache\")."
    )
    return text


def handle_message(session: dict, user_text: str):
    state = session.get("state", "GREETING")
    quick_replies = []
    ended = False

    # Red flags are checked on every turn, regardless of conversation state.
    red_flags = extract_red_flags(user_text) if user_text else []
    if red_flags:
        messages = "\n".join(f"⚠ {msg}" for _, msg in red_flags)
        reply = (
            "Based on what you've described, this may be a medical emergency.\n\n"
            f"{messages}\n\n" + EMERGENCY_FOOTER + "\n\n"
            "This chatbot cannot help further with an emergency — please seek "
            "immediate care. You can type \"restart\" if you'd like to check a "
            "different, non-emergency symptom afterward."
        )
        session["state"] = "GREETING"
        session["symptoms"] = []
        session["severity"] = None
        session["duration"] = None
        return {
            "reply": reply,
            "quick_replies": [],
            "session": session,
            "ended": True,
            "urgency": "emergency",
        }

    if user_text and user_text.strip().lower() in ("restart", "start over", "start again"):
        session = new_session()
        return {
            "reply": _greeting_reply(),
            "quick_replies": [],
            "session": session,
            "ended": False,
            "urgency": None,
        }

    if state == "GREETING":
        found = extract_symptoms(user_text)
        session["symptoms"] = list(set(session["symptoms"]) | found)

        if not found:
            reply = (
                "I didn't quite catch a specific symptom in that. Could you describe "
                "what you're feeling? For example: fever, cough, headache, stomach pain, "
                "vomiting, diarrhea, rash, etc."
            )
            return {"reply": reply, "quick_replies": [], "session": session, "ended": False, "urgency": None}

        matched_list = ", ".join(s.replace("_", " ") for s in found)
        reply = (
            f"Thanks. I noted these symptoms: {matched_list}.\n\n"
            "Are you experiencing any other symptoms? If not, just say \"no\"."
        )
        session["state"] = "ASK_MORE_SYMPTOMS"
        quick_replies = ["No, that's all", "Yes, let me add more"]
        return {"reply": reply, "quick_replies": quick_replies, "session": session, "ended": False, "urgency": None}

    if state == "ASK_MORE_SYMPTOMS":
        lowered = user_text.strip().lower()
        if lowered.startswith("no"):
            session["state"] = "ASK_SEVERITY"
            reply = "Understood. How would you describe the severity of your symptoms overall?"
            quick_replies = ["Mild", "Moderate", "Severe"]
            return {"reply": reply, "quick_replies": quick_replies, "session": session, "ended": False, "urgency": None}
        else:
            found = extract_symptoms(user_text)
            session["symptoms"] = list(set(session["symptoms"]) | found)
            if found:
                matched_list = ", ".join(s.replace("_", " ") for s in found)
                reply = f"Got it, added: {matched_list}. Anything else? Say \"no\" if that's everything."
            else:
                reply = (
                    "I didn't catch a specific symptom there — could you name it directly "
                    "(e.g. \"cough\", \"stomach pain\")? Or say \"no\" if that's everything."
                )
            quick_replies = ["No, that's all", "Yes, let me add more"]
            return {"reply": reply, "quick_replies": quick_replies, "session": session, "ended": False, "urgency": None}

    if state == "ASK_SEVERITY":
        lowered = user_text.strip().lower()
        if "sever" in lowered:
            session["severity"] = "severe"
        elif "moderate" in lowered:
            session["severity"] = "moderate"
        else:
            session["severity"] = "mild"

        session["state"] = "ASK_DURATION"
        reply = "How long have you had these symptoms?"
        quick_replies = ["Less than 24 hours", "1-3 days", "More than 3 days"]
        return {"reply": reply, "quick_replies": quick_replies, "session": session, "ended": False, "urgency": None}

    if state == "ASK_DURATION":
        lowered = user_text.strip().lower()
        if "more than" in lowered or "3 days" in lowered and "1-3" not in lowered:
            session["duration"] = "more_than_3_days"
        elif "1-3" in lowered or "1 to 3" in lowered:
            session["duration"] = "1_to_3_days"
        else:
            session["duration"] = "less_than_24_hours"

        session["state"] = "RESULT"
        return _build_result(session)

    if state == "RESULT":
        # Conversation had already concluded; nudge toward restarting.
        reply = (
            "That completes this check. If you'd like to assess a different or new "
            "set of symptoms, just say \"restart\"."
        )
        return {"reply": reply, "quick_replies": ["Restart"], "session": session, "ended": True, "urgency": None}

    # Fallback — should not normally be reached.
    session = new_session()
    return {"reply": _greeting_reply(), "quick_replies": [], "session": session, "ended": False, "urgency": None}


def _build_result(session: dict):
    symptoms = set(session.get("symptoms", []))
    ranked = score_conditions(symptoms)
    top = [r for r in ranked if r["score"] >= 30][:3]

    if not top:
        reply = (
            "Based on what you've described, I couldn't confidently match your symptoms "
            "to a specific condition in my knowledge base. This doesn't mean nothing is "
            "wrong — if your symptoms are troubling you or getting worse, please see a "
            "healthcare provider for a proper evaluation.\n\n" + DISCLAIMER + "\n\n"
            "Say \"restart\" to check a different set of symptoms."
        )
        return {"reply": reply, "quick_replies": ["Restart"], "session": session, "ended": True, "urgency": "routine"}

    urgency = compute_final_urgency(top, session.get("severity"), session.get("duration"))
    urgency_label = URGENCY_LABELS.get(urgency, urgency)

    lines = ["Based on your symptoms, here's what I found:\n"]
    for i, cond in enumerate(top, start=1):
        lines.append(f"{i}. {cond['name']} — {cond['score']}% symptom match")
        lines.append(f"   {cond['advice']}")

    lines.append(f"\nOverall recommendation: {urgency_label}")

    if urgency == "emergency":
        lines.append(EMERGENCY_FOOTER)
    elif urgency == "urgent":
        lines.append("Please try to see a healthcare provider as soon as you reasonably can.")

    lines.append("\n" + DISCLAIMER)
    lines.append("Say \"restart\" if you'd like to check a different set of symptoms.")

    reply = "\n".join(lines)
    return {
        "reply": reply,
        "quick_replies": ["Restart"],
        "session": session,
        "ended": True,
        "urgency": urgency,
        "results": top,
    }
