# HealthCheck — Web-Based Symptom Assessment Chatbot

A final year project: a web-based chatbot for basic symptom self-assessment
and preliminary, non-diagnostic health advice.

## How it works

1. The user describes symptoms in free text (or taps a quick-reply button).
2. The backend extracts recognised symptoms from the text using a synonym
   dictionary (`data/symptom_synonyms.json`).
3. On every turn, the message is also checked against a list of emergency
   "red-flag" phrases (`data/red_flags.json`) — e.g. chest pain, difficulty
   breathing, stroke signs. If any are found, the bot immediately stops the
   normal flow and tells the user to seek emergency care.
4. If no emergency flags are found, the bot asks a couple of follow-up
   questions (any other symptoms? how severe? how long?).
5. The collected symptoms are scored against a knowledge base of common
   conditions (`data/conditions.json`) using a weighted rule-based matching
   algorithm (see `matcher.py`).
6. The top matches, a plain-language urgency recommendation (self-care /
   routine / urgent / emergency), and a safety disclaimer are returned to
   the user.

This is a decision-support / triage aid only — it is explicitly **not** a
diagnostic tool and does not replace a qualified medical professional.

## Project structure

```
health-chatbot/
├── app.py                     # Flask app: routes (stateless — see below)
├── conversation.py            # Conversation state machine (dialogue flow)
├── matcher.py                 # Symptom extraction + condition scoring engine
├── data/
│   ├── symptom_synonyms.json  # Maps free-text phrases -> canonical symptoms
│   ├── red_flags.json         # Emergency keyword list + escalation messages
│   └── conditions.json        # Knowledge base: conditions, weighted symptoms, advice
├── templates/
│   └── index.html             # Chat UI page
├── public/
│   ├── css/style.css          # Styling
│   └── js/app.js              # Frontend chat logic (calls the API)
└── requirements.txt
```

Static assets live in `public/` rather than the more typical Flask `static/`
folder — this is a deliberate accommodation for Vercel (see the deployment
section below), and `app.py` is configured so it works identically whether
you're running locally or deployed.

## How conversation state works (important)

The server is **stateless** — it does not store anything about a conversation
in memory. Instead, every `/api/chat` response includes a `state` object
(the current step in the conversation, symptoms collected so far, etc.), and
the browser sends that same `state` back on the next request.

This is a deliberate design choice for compatibility with serverless hosting
platforms like Vercel, where each request can be handled by a completely
different, freshly-started function instance — a server-side in-memory
dictionary keyed by session ID would not reliably survive between two
messages in that environment. Carrying state in the client sidesteps this
entirely.

## Requirements

- Python 3.9+
- Flask (`pip install flask`)

## Running locally

```bash
cd health-chatbot
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Deploying to Vercel

As of mid-2026, Vercel deploys Flask apps with **zero configuration** — no
`vercel.json` needed for a basic deployment like this one. Vercel detects a
`Flask` instance named `app` in `app.py` automatically.

1. Push this project to a GitHub repository (Vercel deploys from a repo).
   **Make sure `app.py` sits at the repository root** (or at whatever path
   you set as the project's Root Directory in Vercel) — not nested inside an
   extra folder, which is the most common cause of a 404 after deploying.
2. Go to [vercel.com](https://vercel.com), sign in, and click **Add New → Project**.
3. Import your repository.
4. Leave the build settings as detected — don't add a custom build/install
   command. If your repo has the project files inside a subfolder, set
   **Root Directory** (under Project Settings → Build and Deployment) to that
   subfolder's name.
5. Click **Deploy**. You'll get a live URL like `https://your-project.vercel.app`.

**Important:** static files are served from `public/` on Vercel (its CDN
serves anything under `public/**` directly), **not** Flask's usual `static/`
folder — this project is already set up for that (see Project structure
above), so no changes needed on your end, but if you ever add new CSS/JS/
image files, put them under `public/` rather than a `static/` folder.

If you still see a 404 after deploying, the two things to check first are:
(1) is `app.py` actually at the configured project root (not nested), and
(2) does `app.py` define a variable literally named `app` at module level
(it does, by default, in this project).

## Extending the knowledge base

To add a new condition, add an entry to `data/conditions.json`:

```json
{
  "id": "example_condition",
  "name": "Example Condition",
  "urgency": "routine",
  "symptoms": { "fever": 2, "cough": 3 },
  "advice": "General advice text shown to the user."
}
```

Symptom keys must match (or be added to) `data/symptom_synonyms.json`, so the
extractor can recognise them from free-text input. `urgency` must be one of:
`self_care`, `routine`, `urgent`, `emergency`.

To recognise a new way of describing a symptom, add the phrase to the
relevant array in `data/symptom_synonyms.json` — no code changes needed.

## Known limitations (worth mentioning in your report)

- Symptom extraction is keyword/synonym-based rather than full NLP — it
  won't understand negation ("no fever") or complex phrasing.
- Conversation state is carried by the client rather than persisted in a
  database, so if a user closes the tab mid-conversation, that in-progress
  assessment is lost (this is a reasonable trade-off for a single-session
  triage tool, but worth noting as a design decision in your report).
- The knowledge base covers only a limited set of common, non-emergency
  conditions, as scoped in the project proposal.

## Suggested things to test / evaluate for your Chapter 4

- Accuracy of symptom-to-condition matching against a small labelled test
  set of sample conversations.
- Whether red-flag detection reliably catches emergency phrasing.
- Usability testing with a handful of representative users (clarity of
  questions, trust in the advice given, time to complete an assessment).
