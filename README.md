# Zap Group – AI Onboarding Automation

An AI-First prototype that transforms a new customer's raw web presence into structured CRM data
and a personalized Hebrew onboarding package — automatically, in seconds.

---

## What this project does (in plain English)

When a new business signs up (example: an AC technician in the Krayot area), this tool:

- Scrapes one or more digital sources (business site, Daf Zahav minisite, etc.)
- Uses an LLM (Claude or GPT-4o) to extract CRM-ready structured JSON
- Generates Hebrew:
  - a customer card (כרטיס לקוח)
  - a first-call onboarding script (תסריט שיחה)
- Documents the record in a mock CRM (writes a payload file)
- Sends a mock notification to the customer (writes a WhatsApp/Email text file)

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY or OPENAI_API_KEY

# 3. Run against a live URL
python main.py https://some-ac-technician.co.il

# 4. Run against multiple sources (website + Daf Zahav minisite)
python main.py https://some-ac-technician.co.il https://www.d.co.il/some-business

# 5. Or run against the bundled sample (no internet needed for scraping)
python main.py --use-sample

# 6. Use Anthropic instead of OpenAI (OpenAI is the default)
python main.py --use-sample --provider anthropic

# 7. JSON-only output (for automations / ingestion)
python main.py https://example.co.il --output json
```

Outputs are displayed in the terminal and written under `outputs/`.
Logs are saved under `logs/` (timestamped).

---

## Project Structure

```
├── main.py                  # CLI entry point
├── utils/
│   ├── scraper.py           # BeautifulSoup HTML parser + URL fallback logic
│   └── ai_processor.py      # Pydantic models + LLM extraction + Hebrew generation
│   ├── crm_connector.py      # Mock CRM "POST" + local audit file
│   └── notifier.py           # Mock WhatsApp/Email notification + local audit file
├── samples/
│   └── sample_site.html     # Realistic Hebrew AC technician site (יוסי מזגנים מהקריות)
├── requirements.txt
└── .env.example
```

---

## How it works (pipeline)

`main.py` runs a 5-step pipeline:

1. Scrape (`utils/scraper.py`)
   - Fetch each URL with `requests` + `BeautifulSoup`
   - Skip failed URLs with a warning (non-fatal)
   - If all fail (or `--use-sample`): load `samples/sample_site.html`
   - Aggregate all sources into one merged text document
2. AI extract + generate (`utils/ai_processor.py`)
   - Build a strict JSON-only prompt
   - Call GPT-4o (`openai`, default) or Claude (`anthropic`)
   - Validate the response with Pydantic v2
   - Independently enforce the Krayot rule for `operates_in_krayot`
3. Output
   - Print the customer card + onboarding script + a structured data summary
   - Save `outputs/onboarding_<timestamp>.json`
4. Mock CRM
   - Build a CRM payload and write `outputs/sent_to_crm_<timestamp>.json`
5. Mock notification
   - Build WhatsApp + Email text and write `outputs/notification_<timestamp>.txt`

---

## Outputs

After a successful run you’ll typically see:

- `outputs/onboarding_<timestamp>.json` – validated `OnboardingResult`
- `outputs/sent_to_crm_<timestamp>.json` – mock CRM payload (audit trail)
- `outputs/notification_<timestamp>.txt` – mock WhatsApp + Email (audit trail)
- `logs/onboarding_<timestamp>.log` – timestamped logs

---

## Troubleshooting

- `ANTHROPIC_API_KEY is not set` / `OPENAI_API_KEY is not set`
  - Create `.env` from `.env.example` and set the key for the provider you use.
- Scraping fails for some URLs
  - The scraper skips failed URLs and continues.
  - If all URLs fail, it falls back to `samples/sample_site.html` so the demo still works.
- Validation error
  - Pydantic will reject malformed or out-of-schema LLM output. The log prints the failing field and the data that was returned.

## Why an AI-First Approach Reduces Time-to-Live

Traditional onboarding at a marketplace like Zap requires a producer to:

1. Call the new customer.
2. Ask basic questions (What do you do? Which cities? Which brands?).
3. Manually type that data into the CRM.
4. Write a follow-up summary.

Each step introduces **latency and human error**. The new customer's account sits inactive
while producers manage their queue.

This automation collapses steps 1–4 into a **single command that completes in under 30 seconds**:

| Stage | Traditional | AI-First |
|---|---|---|
| Data collection | 10–20 min phone call | Automated scrape |
| CRM entry | Manual, error-prone | Validated JSON |
| First-call prep | Ad-hoc, generic | Personalized script |
| **Total Time-to-Live** | **Hours–Days** | **Minutes** |

When the Zap producer finally calls the customer, they already know their brands, service area,
years of experience, and certifications. The customer's first impression of Zap is of a
**company that did its homework** — not a company reading from a generic script.

---

## Why Pydantic for Data Integrity

LLMs are probabilistic. On any given run, the model might return a phone number formatted
differently, omit a field, or invent a service category. Feeding inconsistent data directly
into a CRM causes downstream failures.

**Pydantic acts as a contract** between the LLM and the rest of the system:

- **Type enforcement**: `service_categories` is a `List[Literal["תיקון","התקנה","תחזוקה"]]`.
  Any value outside this enum is rejected at parse time — not silently ignored.
- **Field-level transforms**: The `@field_validator("phone")` method normalizes every phone
  number to `05X-XXXXXXX` format regardless of how the LLM returned it.
- **Explicit nullability**: Optional fields are typed `Optional[str] = None`.
  Downstream code never has to guess whether a missing email is `""`, `"N/A"`, or `null`.
- **Automatic error context**: A `ValidationError` names the exact field and rule that failed,
  making debugging fast.

The result: **every `OnboardingResult` that passes Pydantic validation is guaranteed to be
CRM-ready** — same shape, same types, every time.

---

## How This Improves Customer Experience (חווית לקוח)

The most important customer interaction is the **first one**. Research consistently shows that
a personalized, informed first call builds trust and increases conversion rates.

### The Problem with Generic Scripts

A generic opening — *"שלום, אני מחברת זאפ, אנחנו מציעים פרסום דיגיטלי..."* — signals to
the customer that they are just a number in a queue. They've heard it before. They're on guard.

### The AI-Powered Difference

This automation gives the Zap producer a script that opens with **specific facts pulled from
the customer's own website**:

> *"שלום יוסי, אני [שם] מזאפ. ראיתי שאתה עובד עם אלקטרה ותדיראן, ושיש לך ניסיון של 15 שנה
> עם רישיון קבלן. הכל בסדר עם הביקוש מהקריות בתקופה האחרונה?"*

This opening achieves three things simultaneously:
1. **Proves preparation** — the producer isn't reading a cold script.
2. **Establishes credibility** — Zap is portrayed as a professional partner, not a vendor.
3. **Invites dialogue** — asking about the Krayot area (the customer's home turf) gets them
   talking about their business, which is the fastest path to a productive sales conversation.

### The Flywheel Effect

Every customer whose onboarding is handled this way becomes a higher-quality account:
- Faster setup → shorter time from payment to first lead.
- More accurate CRM data → better targeting and category matching on Zap's platform.
- Warmer first interaction → higher producer NPS and lower early churn.

**The automation doesn't replace the human call — it makes every human call count.**

---

## Architecture Diagram

```
         ┌─────────────────┐
         │   main.py (CLI) │
         └────────┬────────┘
                  │
        ┌─────────▼──────────┐
        │  utils/scraper.py  │
        │  ┌──────────────┐  │
        │  │  URLs (1..n) │  │  → requests + BeautifulSoup
        │  └──────┬───────┘  │
        │         │ (all fail?) 
        │  ┌──────▼───────┐  │
        │  │ sample HTML  │  │  → samples/sample_site.html
        │  └──────────────┘  │
        └─────────┬──────────┘
                  │ plain text
        ┌─────────▼────────────────┐
        │  utils/ai_processor.py   │
        │                          │
        │  prompt → LLM (Claude /  │
        │           GPT-4o)        │
        │       ↓                  │
        │  JSON → Pydantic models  │
        │       ↓                  │
        │  OnboardingResult        │
        └─────────┬────────────────┘
                  │
        ┌─────────▼───────────────┐
        │ Console + outputs/*.json │
        └─────────┬───────────────┘
                  │
        ┌─────────▼───────────────┐
        │ utils/crm_connector.py   │ → outputs/sent_to_crm_*.json
        └─────────┬───────────────┘
                  │
        ┌─────────▼───────────────┐
        │ utils/notifier.py        │ → outputs/notification_*.txt
        └─────────────────────────┘
```

---

## Sample Output

Running `python main.py --use-sample` produces:

**כרטיס לקוח** – a structured Hebrew summary with business name, contact details, service
categories, brands, service area, and a recommended Zap package tier.

**תסריט שיחת אונבורדינג** – a complete, named Hebrew call script referencing the customer's
specific brands, certifications, and the Krayot area.

**JSON file** – a machine-readable `OnboardingResult` ready for CRM ingestion via API.
