# Email Automation

Real-time Gmail email routing powered by a fine-tuned **DeBERTa-v3** transformer.

The system watches a Gmail inbox via the Gmail API `watch` + Google Cloud Pub/Sub
push notifications, classifies each incoming email into a department using an
LLM-based transformer model (~96% accuracy), and automatically forwards it to
the department's destination address. Processing is idempotent — every message
is handled **exactly once** — and forwarded emails are tagged so they can be
distinguished from real mail.

## Features

- **Real-time detection** — Gmail API `watch` (INBOX) + Pub/Sub streaming pull subscription
- **DeBERTa-v3 classification** — a fine-tuned `microsoft/deberta-v3-base` model
  routes emails to departments: `CRM`, `DELIVERY`, `FINANCE`, `HR`, `PURCHASE`,
  `RECYCLE`, `SALES`, `SPAM`, `STORE`, `SUPPORT`
- **Confidence gating** — predictions below the 0.70 confidence threshold are
  treated as `UNKNOWN` and sent to the default address
- **Automatic forwarding** — per-department destination addresses, original
  attachments included, subject tagged `[<Department> Department]`
- **Exactly-once processing** — processed message IDs + history IDs are persisted
  in `data/`, so nothing is ever forwarded twice (survives restarts/crashes)
- **Loop safety** — every forwarded message carries the `X-Email-Automation`
  header for identification; sent mail never re-enters the INBOX
- **Graceful shutdown** — `Ctrl+C` stops cleanly; `just stop` force-kills stale listeners

## Architecture

```
                         ┌─────────────────────────────┐
                         │          Gmail / GCP        │
                         │                             │
   New email arrives ──▶ │  Gmail API watch (INBOX)    │
                         │  pushes notification ──────▶│
                         └──────────────┬──────────────┘
                                        │ Pub/Sub topic
                                        ▼ (push/pull)
                    ┌───────────────────────────────────┐
                    │      gmail-listener (this repo)   │
                    │                                   │
                    │ 1. Pull notification (historyId)  │
                    │ 2. Dedup + fetch new messages     │
                    │ 3. Fetch full email (MIME parse)  │
                    │ 4. DeBERTa classify (subject+body)│
                    │ 5. Forward to department address  │
                    └───────────────────┬───────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
   ┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
   │   Gmail API        │   │  models/deberta/   │   │  data/ (state)     │
   │   messages.send    │   │  fine-tuned        │   │  history_id.txt    │
   │   (forward w/      │   │  DeBERTa checkpoint│   │  processed_messages│
   │   attachments)     │   │  + calibration     │   │  .txt              │
   └────────────────────┘   └────────────────────┘   └────────────────────┘
```

### Message lifecycle (workflow)

```
email arrives in INBOX
        │  Gmail API detects change (watch on INBOX)
        ▼
Pub/Sub notification published (contains new historyId)
        │
        ▼
listener pulls notification ──▶ historyId <= last? ──yes──▶ ignore (duplicate/old)
        │                              │no
        │                              ▼
        │                    first ever notification?
        │                              │
        │                     yes ─────┴──── no
        │                              ▼
        │                    save historyId   fetch messagesAdded since last historyId
        │                    (backfill,       │
        │                     nothing sent)   ▼
        │                              for each new message:
        │                              message in processed set? ──yes──▶ skip
        │                                            │no
        │                                            ▼
        │                              fetch + parse full email (headers,
        │                              body, attachments, X-Email-Automation)
        │                                            │
        │                                            ▼
        │                              DeBERTa classify(subject, body)
        │                                            │
        │                                            ▼
        │                              confidence < 0.70? ──▶ label = UNKNOWN
        │                                            ▼
        │                              resolve destination (per-department map
        │                              or DEFAULT_EMAIL)
        │                                            ▼
        │                              forward via Gmail API (subject tag,
        │                              X-Email-Automation header, attachments)
        │                                            ▼
        │                              save messageId to processed set
        ▼
save historyId  (only after all messages in this batch are handled)
```

## Project Structure

```
email_automation/
├── Justfile                      # Task runner recipes
├── pyproject.toml                # Package metadata, deps, ruff config, console scripts
├── .gitignore
├── config/                       # Secrets (git-ignored)
│   ├── credentials.json          # Gmail OAuth client (download from Google Cloud Console)
│   └── token.json                # Generated after first auth
├── data/                         # Runtime state (git-ignored)
│   ├── history_id.txt            # Last processed Gmail history ID
│   └── processed_messages.txt    # Message IDs already forwarded
├── models/
│   └── deberta/                  # Fine-tuned DeBERTa model (config.json,
│                                 # model.safetensors, tokenizer, calibration.json)
├── tests/
│   └── test_config.py            # Smoke tests: paths + config/data presence
└── src/
    └── gmail_access/
        ├── config.py             # Central path configuration
        ├── read_mail.py          # Gmail auth, message fetching, attachment download
        ├── watch_mail.py         # Starts the Gmail watch (push notification setup)
        ├── pubsub_listener.py    # Pub/Sub subscriber: classify + forward (entry point)
        └── classifier/
            ├── classifier.py     # DeBERTa loading + classification (confidence-gated)
            ├── forward_mail.py   # Builds and sends the forwarded email
            └── mail_config.py    # Department -> destination email mapping
```

## Prerequisites

1. **Gmail API enabled** and a Desktop OAuth client — download
   `credentials.json` from Google Cloud Console into `config/`
2. **Google Cloud Pub/Sub**:
   - A topic (e.g. `gmail-new-mail`), configured in `watch_mail.py`
   - A subscription (pull), configured in `pubsub_listener.py`
3. **Gmail API service account** with Pub/Sub *publish* permission
4. **Python 3.10+**, `torch`, `transformers`, and [just](https://github.com/casey/just)

> The fine-tuned DeBERTa checkpoint must be present at `models/deberta/`.
> It is produced by the sibling `email_classifier` project (training, evaluation,
> calibration) and copied here for inference.

## Setup

```powershell
# 1. Create and activate a virtual environment (recommended)
python -m venv .venv
.\.venv\Scripts\activate

# 2. Install the package (editable) + dependencies
pip install -e .

# 3. Drop config\credentials.json from the Google Cloud Console
#    (already at config\credentials.json if you followed the structure)

# 4. Start the Gmail watch (enables push notifications for the INBOX)
just watch
```

The first run opens a browser for Gmail OAuth authorization and writes
`config/token.json`.

## Running the Listener

```powershell
just listen          # installs (if needed) and runs the Pub/Sub listener
```

Or manually:

```powershell
cd src
python -m gmail_access.pubsub_listener
```

The listener stays running. Every new inbox email is classified and forwarded
once. On the first notification it records the current history ID without
processing anything (backlog behavior).

### Stopping

- Press `Ctrl+C` in the terminal (graceful, exits within ~6s)
- From any terminal: `just stop` force-kills any running listener process

## Testing

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests -q
```

## Configuration

All environment-specific settings live in a root **`.env`** file (git-ignored).
Copy the template and fill in your values:

```powershell
Copy-Item .env.example .env   # then edit .env
```

| Variable                   | Purpose                                              |
|----------------------------|------------------------------------------------------|
| `DEPARTMENT_<NAME>`        | Destination address per department (`HR`, `STORE`, …) — empty = fall back to `DEFAULT_EMAIL` |
| `DEFAULT_DEPARTMENT`       | Label used for unclassified mail (default `PERSONAL`) |
| `DEFAULT_EMAIL`            | Receives unclassified / unknown-department mail       |
| `GCP_PROJECT_ID`           | Google Cloud project ID (Pub/Sub)                     |
| `PUBSUB_TOPIC`             | Full topic path used by the Gmail watch               |
| `PUBSUB_SUBSCRIPTION_ID`   | Pull subscription the listener consumes               |

```ini
# .env (example)
DEPARTMENT_HR=hr@example.com
DEFAULT_EMAIL=you@example.com
GCP_PROJECT_ID=your-gcp-project-id
PUBSUB_TOPIC=projects/your-gcp-project-id/topics/gmail-new-mail
PUBSUB_SUBSCRIPTION_ID=your-subscription-id
```

`DEFAULT_EMAIL` receives emails whose predicted department is not configured
or whose confidence is below the threshold (classified as `UNKNOWN`).

### Classification model

`src/gmail_access/classifier/classifier.py` loads the DeBERTa checkpoint from
`models/deberta/` at import time (CPU inference, `MAX_LENGTH = 256`,
`CONFIDENCE_THRESHOLD = 0.70`). Label names come from the model's own
`config.json` (`id2label`) — nothing is hardcoded.

## Justfile Recipes

| Recipe      | Description                                   |
|-------------|-----------------------------------------------|
| `just install`    | `pip install -e .`                          |
| `just watch`      | Start Gmail watch (push notification setup) |
| `just listen`     | Run the Pub/Sub listener                    |
| `just stop`       | Force-kill any running listener             |
| `just lint`       | Ruff check                                  |
| `just fix`        | Ruff check --fix                            |
| `just fmt`        | Ruff format                                 |
| `just fmt-check`  | Ruff format --check                         |

## How It Works

1. `just watch` calls the Gmail API `watch` endpoint, registering the INBOX
   with the Pub/Sub topic (`watch_mail.py`)
2. New mail publishes a notification containing the current `historyId`
3. `pubsub_listener` pulls notifications and fetches `messageAdded` history
   since the last saved ID
4. Each message is fetched and parsed (`read_mail.py`): headers, plain-text or
   HTML body, attachments, and the `X-Email-Automation` header
5. Duplicate protection: message IDs already in `processed_messages.txt` are
   skipped, then classified by the DeBERTa model and forwarded with
   `X-Email-Automation` header + original attachments
6. The message ID and history ID are persisted so nothing is ever processed twice

## Troubleshooting

- **"No such file: credentials.json"** — make sure the OAuth client JSON is at
  `config/credentials.json`
- **Listener won't stop with Ctrl+C** — old code before the fix; run
  `just stop` once, then relaunch
- **No emails processed** — confirm `just watch` succeeded and the Pub/Sub
  subscription ID in `pubsub_listener.py` matches your subscription
- **Slow first startup** — the DeBERTa model (~700 MB) is loaded into memory
  when the listener starts
- **Everything goes to DEFAULT_EMAIL** — the model is confident it is not one
  of the configured departments (below 0.70 threshold), or the predicted
  department has no destination configured in `mail_config.py`

## Notes

- `config/`, `data/`, and `models/` are git-ignored — credentials and the
  700 MB checkpoint must never enter version control
- Model training, evaluation, and calibration live in the sibling
  `email_classifier` project; this project is the production consumer
