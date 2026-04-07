"""
AI processing module – the intelligence layer of the Zap onboarding pipeline.

Flow:
  scraped text  →  LLM (Anthropic Claude or OpenAI GPT)
                →  JSON extraction
                →  Pydantic validation
                →  OnboardingResult  (structured data + Hebrew outputs)

Pydantic enforces a strict schema so downstream CRM integrations always receive
clean, typed data – never raw, unpredictable LLM strings.
"""

import json
import logging
import os
from typing import List, Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

load_dotenv()
logger = logging.getLogger(__name__)

# Cities that count as "Krayot" for the service-area business rule
KRAYOT_KEYWORDS = {"קריית", "קריות", "הקריות", "krayot", "kraiot"}


# ---------------------------------------------------------------------------
# Pydantic models – single source of truth for data shape
# ---------------------------------------------------------------------------

class BusinessInfo(BaseModel):
    """Core structured data extracted from the customer's digital footprint."""

    business_name: str = Field(description="Full business name (as it appears on the site)")
    phone: str = Field(description="Primary phone – Israeli format: 05X-XXXXXXX or 0X-XXXXXXX")
    email: Optional[str] = Field(None, description="Business email, or null if not found")
    service_categories: List[Literal["תיקון", "התקנה", "תחזוקה"]] = Field(
        description="Service categories offered – only those explicitly mentioned"
    )
    brands: List[str] = Field(
        description="AC brands mentioned (e.g. אלקטרה, תדיראן, LG, Samsung)"
    )
    service_area: List[str] = Field(
        description="Cities / regions where the business operates"
    )
    operates_in_krayot: bool = Field(
        description="True if any Krayot city appears in service_area"
    )
    additional_notes: Optional[str] = Field(
        None,
        description="USPs, certifications, years of experience, or other notable details"
    )

    @field_validator("phone")
    @classmethod
    def standardize_phone(cls, v: str) -> str:
        """Normalize Israeli phone numbers to XX-XXXXXXX format."""
        digits = "".join(filter(str.isdigit, v))

        # Strip country code +972 → 0
        if digits.startswith("972") and len(digits) >= 12:
            digits = "0" + digits[3:]

        # Format: 052-8834567 (mobile) or 04-8523410 (landline)
        if len(digits) == 10:
            return f"{digits[:3]}-{digits[3:]}"
        if len(digits) == 9:
            return f"{digits[:2]}-{digits[2:]}"

        logger.warning("Could not normalize phone '%s' – returning as-is.", v)
        return v


class OnboardingResult(BaseModel):
    """Complete onboarding package delivered to the Zap producer."""

    business_info: BusinessInfo
    customer_card: str = Field(
        description="Structured Hebrew כרטיס לקוח for the Zap internal producer"
    )
    onboarding_script: str = Field(
        description="Personalized Hebrew script for the first onboarding call"
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def process_business_data(
    content: str,
    sources: Optional[List[str]] = None,
    provider: str = "openai",
) -> OnboardingResult:
    """
    Run aggregated scraped text through an LLM and return a validated OnboardingResult.

    Args:
        content:  Plain text from utils.scraper.scrape_site() – may contain
                  content merged from multiple URLs (business site + Daf Zahav, etc.)
        sources:  List of source labels (URLs / 'sample:…') for prompt context.
        provider: 'anthropic' (default) or 'openai'

    Returns:
        OnboardingResult – always fully validated by Pydantic before returning.
    """
    logger.info("Starting AI extraction with provider: %s", provider)

    prompt = _build_prompt(content, sources or [])

    if provider == "anthropic":
        raw = _call_anthropic(prompt)
    elif provider == "openai":
        raw = _call_openai(prompt)
    else:
        raise ValueError(f"Unknown provider '{provider}'. Choose 'anthropic' or 'openai'.")

    return _parse_and_validate(raw)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(content: str, sources: List[str]) -> str:
    sources_note = (
        f"The content below was aggregated from {len(sources)} digital source(s): "
        + ", ".join(sources)
        if sources
        else "The content below was loaded from a sample fixture."
    )

    return f"""You are a senior data analyst at Zap Group, Israel's leading digital marketplace.

CONTEXT: A new customer has just signed up on Zap. They are an air-conditioner technician
who purchased a 5-page website and a minisite on Daf Zahav, operating in the KRAYOT area
(קריות) in northern Israel. Your job is to analyze ALL of their scraped digital assets and
produce two things:
  1. Structured business data (for the CRM).
  2. Hebrew-language outputs for the Zap producer who will call the customer.

{sources_note}

SCRAPED CONTENT (ALL SOURCES MERGED):
---
{content}
---

Return ONLY a valid JSON object – no markdown fences, no extra text – matching this schema exactly:

{{
  "business_info": {{
    "business_name": "<string: full business name>",
    "phone": "<string: primary phone in Israeli format 05X-XXXXXXX>",
    "email": "<string or null>",
    "service_categories": ["<only values from: תיקון, התקנה, תחזוקה>"],
    "brands": ["<list of AC brand names found in the content>"],
    "service_area": ["<list of city/region names in Hebrew>"],
    "operates_in_krayot": <boolean: true if Krayot cities appear in service_area>,
    "additional_notes": "<string or null: certifications, years of experience, USPs>"
  }},
  "customer_card": "<HEBREW כרטיס לקוח – see format instructions below>",
  "onboarding_script": "<HEBREW onboarding call script – see format instructions below>"
}}

--- FORMAT: customer_card ---
A well-structured Hebrew summary for an internal Zap producer. Use clear sections:
  • שם העסק, איש קשר, טלפון, אימייל
  • קטגוריות שירות
  • מותגים
  • אזורי שירות | פעיל בקריות: כן/לא
  • נקודות בולטות (ניסיון, רישיון, USPs)
  • המלצה לסוג חבילה ב-זאפ

--- FORMAT: onboarding_script ---
A warm, professional, consultative Hebrew script for the FIRST phone call.
  • Opening: introduce the Zap representative by first name.
  • Research hook: mention AT LEAST 2 specific facts found in the content
    (e.g. brands they work with, specific cities, years of experience, certifications).
    This proves Zap did its homework and builds instant trust.
  • Value pitch: briefly explain how Zap's platform helps AC technicians in the Krayot area
    get more qualified leads.
  • Soft close: propose a short onboarding call or demo – no pressure.
  • Tone: friendly (not corporate), confident, and in fluent spoken Hebrew (not formal writing style).

STRICT RULES:
1. customer_card and onboarding_script MUST be in high-quality, natural Hebrew.
2. Do NOT invent data that is not in the content. Use null for missing fields.
3. operates_in_krayot: true only if קריות / קריית appears in service_area.
4. Return pure JSON only.
"""


# ---------------------------------------------------------------------------
# LLM callers
# ---------------------------------------------------------------------------

def _call_anthropic(prompt: str) -> str:
    """Send a pre-built prompt to Claude and return the raw text response."""
    try:
        import anthropic
    except ImportError as exc:
        raise ImportError(
            "The 'anthropic' package is not installed. Run: pip3 install anthropic"
        ) from exc

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file."
        )

    client = anthropic.Anthropic(api_key=api_key)
    logger.info("Calling Claude API (claude-sonnet-4-6)…")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    logger.debug("Claude response (first 300 chars): %s…", response_text[:300])
    return response_text


def _call_openai(prompt: str) -> str:
    """Send a pre-built prompt to GPT-4o and return the raw text response."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "The 'openai' package is not installed. Run: pip3 install openai"
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Add it to your .env file."
        )

    client = OpenAI(api_key=api_key)
    logger.info("Calling OpenAI API (gpt-4o)…")

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior data analyst at Zap Group Israel. "
                    "Always respond with valid JSON only, no markdown, no extra text."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    response_text = response.choices[0].message.content
    logger.debug("GPT-4o response (first 300 chars): %s…", response_text[:300])
    return response_text


# ---------------------------------------------------------------------------
# Response parsing & validation
# ---------------------------------------------------------------------------

def _parse_and_validate(raw: str) -> OnboardingResult:
    """
    Parse the LLM's raw text into a validated OnboardingResult.

    Handles:
      - Markdown code-fence wrappers (```json … ```)
      - Leading/trailing whitespace
      - Invalid JSON → raises ValueError with context
      - Pydantic validation errors → raises ValueError with context
      - Independently re-verifies operates_in_krayot as a business-rule safety net
    """
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Drop first line (```json or ```) and last line (```)
        cleaned = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned non-JSON output. First 600 chars:\n%s", raw[:600])
        raise ValueError(f"LLM response is not valid JSON: {exc}") from exc

    # ---- Business-rule safety net: verify Krayot independently ----
    service_area: list = data.get("business_info", {}).get("service_area", [])
    data.setdefault("business_info", {})["operates_in_krayot"] = _check_krayot(service_area)

    try:
        result = OnboardingResult(**data)
    except Exception as exc:
        logger.error(
            "Pydantic validation failed.\nData:\n%s",
            json.dumps(data, ensure_ascii=False, indent=2),
        )
        raise ValueError(f"Data validation error: {exc}") from exc

    logger.info(
        "Extraction complete → %s | Krayot: %s",
        result.business_info.business_name,
        "✓" if result.business_info.operates_in_krayot else "✗",
    )
    return result


def _check_krayot(service_areas: List[str]) -> bool:
    """Return True if any Krayot-related keyword appears in the service area list."""
    for area in service_areas:
        normalized = area.strip().lower()
        if any(kw in normalized for kw in KRAYOT_KEYWORDS):
            return True
    return False
