#!/usr/bin/env python3
"""
Zap Group – AI Onboarding Automation
CLI entry point.

Full pipeline:
  STEP 1 – Scrape all provided URLs (aggregated into one document)
  STEP 2 – AI extraction → validated OnboardingResult
  STEP 3 – Print outputs to console / save JSON
  STEP 4 – Push record to CRM (mock)
  STEP 5 – Send notification to customer (mock)

Usage examples:
  python3 main.py --use-sample
  python3 main.py https://yossi-ac.co.il
  python3 main.py https://yossi-ac.co.il https://www.d.co.il/yossi-mazganim
  python3 main.py https://yossi-ac.co.il --provider openai --output json
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from utils.scraper import scrape_site
from utils.ai_processor import OnboardingResult, process_business_data
from utils.crm_connector import post_to_crm
from utils.notifier import send_notification

# ---------------------------------------------------------------------------
# Logging – console + timestamped file
# ---------------------------------------------------------------------------

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f"onboarding_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("zap.main")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zap-onboarding",
        description="Zap Group – AI-powered customer onboarding automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use bundled sample (no internet / API key needed for scraping)
  python3 main.py --use-sample

  # Single live URL
  python3 main.py https://yossi-ac.co.il

  # Multiple sources: business site + Daf Zahav minisite
  python3 main.py https://yossi-ac.co.il https://www.d.co.il/yossi-mazganim

  # Use OpenAI instead of Anthropic
  python3 main.py --use-sample --provider openai

  # JSON output only (for CRM pipe)
  python3 main.py https://yossi-ac.co.il --output json
        """,
    )
    parser.add_argument(
        "urls",
        nargs="*",
        metavar="URL",
        help="One or more customer website URLs to scrape (business site, Daf Zahav, etc.)",
    )
    parser.add_argument(
        "--use-sample",
        action="store_true",
        help="Skip live scraping and use samples/sample_site.html directly",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai"],
        default="openai",
        help="LLM provider (default: openai)",
    )
    parser.add_argument(
        "--output",
        choices=["console", "json", "both"],
        default="both",
        help="Output format (default: both)",
    )
    return parser


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Default to sample if nothing was provided
    if not args.urls and not args.use_sample:
        logger.warning("No URL provided – falling back to sample site.")
        args.use_sample = True

    _print_banner()

    # ── STEP 1: Scrape ───────────────────────────────────────────────────────
    urls_to_scrape = [] if args.use_sample else args.urls
    source_count = len(urls_to_scrape) or 1  # 1 = sample
    logger.info("STEP 1 / 5 – Scraping %d source(s)…", source_count)
    try:
        content, sources = scrape_site(urls_to_scrape)
        logger.info("Content acquired from: %s", sources)
    except Exception as exc:
        logger.error("Scraping failed: %s", exc)
        sys.exit(1)

    # ── STEP 2: AI extraction ────────────────────────────────────────────────
    logger.info("STEP 2 / 5 – Extracting structured data with %s…", args.provider)
    try:
        result: OnboardingResult = process_business_data(
            content, sources=sources, provider=args.provider
        )
    except EnvironmentError as exc:
        logger.error("%s", exc)
        logger.error(
            "Add your API key to .env (see .env.example). "
            "Default provider is OpenAI (OPENAI_API_KEY)."
        )
        sys.exit(1)
    except Exception as exc:
        logger.error("AI processing failed: %s", exc)
        sys.exit(1)

    # ── STEP 3: Output ───────────────────────────────────────────────────────
    logger.info("STEP 3 / 5 – Generating outputs…")
    if args.output in ("console", "both"):
        _print_to_console(result)
    if args.output in ("json", "both"):
        out_path = _save_json(result)
        logger.info("JSON saved → %s", out_path)

    # ── STEP 4: CRM ──────────────────────────────────────────────────────────
    logger.info("STEP 4 / 5 – Pushing record to CRM…")
    try:
        post_to_crm(result)
    except Exception as exc:
        logger.warning("CRM push failed (non-fatal): %s", exc)

    # ── STEP 5: Notify ───────────────────────────────────────────────────────
    logger.info("STEP 5 / 5 – Sending customer notification…")
    try:
        notification = send_notification(result)
        if args.output in ("console", "both"):
            _print_notification(notification)
    except Exception as exc:
        logger.warning("Notification failed (non-fatal): %s", exc)

    logger.info("Onboarding automation completed successfully.")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    sep = "═" * 60
    print(f"\n{sep}")
    print("   ZAP GROUP – AI ONBOARDING AUTOMATION")
    print(sep)


def _print_to_console(result: OnboardingResult) -> None:
    thick = "═" * 60
    thin = "─" * 60

    print(f"\n{thick}")
    print("📋  כרטיס לקוח  |  ZAP GROUP")
    print(thick)
    print(result.customer_card)

    print(f"\n{thick}")
    print("📞  תסריט שיחת אונבורדינג")
    print(thick)
    print(result.onboarding_script)

    print(f"\n{thick}")
    print("🔍  נתונים מובנים (Structured CRM Data)")
    print(thick)
    info = result.business_info
    rows = [
        ("שם העסק",        info.business_name),
        ("טלפון",          info.phone),
        ("אימייל",         info.email or "לא נמצא"),
        ("קטגוריות שירות", " | ".join(info.service_categories) or "—"),
        ("מותגים",         ", ".join(info.brands) or "—"),
        ("אזורי שירות",    ", ".join(info.service_area) or "—"),
        ("פעיל בקריות",    "✅ כן" if info.operates_in_krayot else "❌ לא"),
        ("הערות נוספות",   info.additional_notes or "—"),
    ]
    for label, value in rows:
        print(f"  {label:<20} {value}")
    print(f"{thin}\n")


def _print_notification(notification: str) -> None:
    print(f"\n{'═' * 60}")
    print("✉️   הודעות ללקוח (מדומות)")
    print("═" * 60)
    print(notification)


def _save_json(result: OnboardingResult) -> Path:
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"onboarding_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
