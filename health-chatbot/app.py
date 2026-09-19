"""
app.py
------
Flask entry point for the Health Check Chatbot.

Routes:
  GET  /              -> serves the chat UI (templates/index.html)
  POST /api/chat        -> accepts {message, state} and returns the bot's reply + new state
  POST /api/reset       -> returns a fresh greeting + blank state

Design note (important for deployment):
This app is STATELESS on the server. The full conversation state (a small
JSON-serializable dict from conversation.py) is sent back to the browser on
every response, and the browser sends it back on the next request. The
server never stores anything about a session in memory.

This is a deliberate choice for compatibility with serverless hosting (e.g.
Vercel), where each request may be handled by a completely different,
freshly-started function instance. A server-side in-memory dictionary would
not reliably survive between two consecutive messages in that environment,
which could make the chatbot silently "forget" earlier symptoms mid
conversation. Carrying state in the client sidesteps that entirely, at the
cost of trusting the client to send back what it was given -- an acceptable
trade-off here since the state has no sensitive data and is not security-
critical.
"""

from flask import Flask, render_template, request, jsonify

from conversation import new_session, handle_message, _greeting_reply

# static_folder="public", static_url_path="" makes Flask serve files from
# public/ directly at the site root (e.g. public/css/style.css -> /css/style.css).
# This deliberately matches how Vercel's CDN serves the public/** directory in
# production (see README for details) -- so the exact same url_for() calls in
# index.html resolve correctly whether running locally or deployed.
app = Flask(__name__, static_folder="public", static_url_path="")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    incoming_state = data.get("state")

    # First contact: no state yet and no message -> just greet.
    if incoming_state is None and not message:
        return jsonify({
            "reply": _greeting_reply(),
            "quick_replies": [],
            "ended": False,
            "urgency": None,
            "state": new_session(),
        })

    state = incoming_state if isinstance(incoming_state, dict) else new_session()
    result = handle_message(state, message)

    return jsonify({
        "reply": result["reply"],
        "quick_replies": result["quick_replies"],
        "ended": result["ended"],
        "urgency": result.get("urgency"),
        "state": result["session"],
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    return jsonify({
        "reply": _greeting_reply(),
        "quick_replies": [],
        "ended": False,
        "urgency": None,
        "state": new_session(),
    })


if __name__ == "__main__":
    # debug=True is convenient for local development; turn off in production.
    app.run(host="0.0.0.0", port=5000, debug=True)
