<<<<<<< HEAD
# Escalation POC

A local-only FastAPI demonstration of a technical support escalation workflow.
All Zendesk, Claude, Google Chat, and vehicle records are fictional or mocked.
No real API calls are made.

## Start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m uvicorn app.main:app --reload --host 127.0.0.1
```

In a second shell (with the environment active):

```bash
python -m pytest -q
python -m ruff check .
```

See http://127.0.0.1:8000/docs for the interactive API documentation.

## Warning

Endpoints have no authentication and store state in process memory. Never expose
this demo on a public network or connect it to production systems.
=======
# escalation-poc
Python-based technical support escalation management system that automates workflows between Zendesk, Google Chat, Claude AI, and internal vehicle databases. Streamlines ticket escalation, AI-assisted diagnostics, manager collaboration, and resolution tracking through event-driven automation.
>>>>>>> 8c6366f0734965dddb1442cf2eba223fb11607c7
