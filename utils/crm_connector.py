"""
CRM Connector module – simulates pushing a completed onboarding record to Zap's CRM.

In production this would call an internal REST API (e.g. Salesforce, HubSpot, or a
custom Zap CRM endpoint).  Here we log every action and write a timestamped JSON
file to outputs/ so the full audit trail is preserved locally.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.ai_processor import OnboardingResult

logger = logging.getLogger(__name__)

CRM_OUTPUT_DIR = Path("outputs")

# Simulated CRM endpoint (would be a real URL in production)
_MOCK_CRM_ENDPOINT = "https://crm.zapgroup.co.il/api/v1/customers"


def post_to_crm(result: "OnboardingResult") -> dict:
    """
    Simulate an API call to Zap's CRM system.

    Actions performed:
      1. Build a CRM-ready payload from the OnboardingResult.
      2. Log the (simulated) API call.
      3. Persist the payload as outputs/sent_to_crm_<timestamp>.json.
      4. Return the CRM record dict so callers can confirm what was sent.

    Args:
        result: Validated OnboardingResult from ai_processor.

    Returns:
        The CRM record dict that was "sent".
    """
    info = result.business_info

    crm_record = {
        "crm_meta": {
            "submitted_at": datetime.now().isoformat(),
            "endpoint": _MOCK_CRM_ENDPOINT,
            "status": "mock_success",
            "record_type": "new_customer_onboarding",
        },
        "customer": {
            "business_name": info.business_name,
            "phone": info.phone,
            "email": info.email,
            "service_categories": info.service_categories,
            "brands": info.brands,
            "service_area": info.service_area,
            "operates_in_krayot": info.operates_in_krayot,
            "additional_notes": info.additional_notes,
        },
        "onboarding_package": {
            "customer_card": result.customer_card,
            "onboarding_script": result.onboarding_script,
        },
    }

    # ── Simulate the API call ────────────────────────────────────────────────
    logger.info(
        "[CRM] → POST %s  |  customer: '%s'  |  phone: %s",
        _MOCK_CRM_ENDPOINT,
        info.business_name,
        info.phone,
    )
    logger.info("[CRM] Payload size: %d bytes", len(json.dumps(crm_record, ensure_ascii=False)))

    # ── Persist locally ──────────────────────────────────────────────────────
    CRM_OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = CRM_OUTPUT_DIR / f"sent_to_crm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(crm_record, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("[CRM] Record documented → %s", out_path)
    return crm_record
