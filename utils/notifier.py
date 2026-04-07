"""
Notifier module – simulates sending the onboarding package to the customer.

In production this would dispatch via:
  • WhatsApp Business API (e.g. 360dialog / Twilio)
  • SMTP / SendGrid for email
  • Zap's internal notification service

Here we build the formatted Hebrew message, log the (simulated) dispatch,
and save a timestamped copy to outputs/ for audit purposes.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.ai_processor import OnboardingResult

logger = logging.getLogger(__name__)

NOTIFY_OUTPUT_DIR = Path("outputs")

# Simulated sender credentials (would be real in production)
_MOCK_WHATSAPP_SENDER = "Zap-Group-Bot (+972-3-0000000)"
_MOCK_EMAIL_SENDER = "onboarding@zapgroup.co.il"


def send_notification(result: "OnboardingResult") -> str:
    """
    Simulate sending the onboarding materials to the new customer.

    Generates two message formats:
      • WhatsApp – short, warm, mobile-friendly Hebrew message.
      • Email    – full structured Hebrew email with customer card + next steps.

    Both are logged and saved to outputs/notification_<timestamp>.txt.

    Args:
        result: Validated OnboardingResult from ai_processor.

    Returns:
        The full notification text that was "sent".
    """
    info = result.business_info
    recipient_phone = info.phone
    recipient_email = info.email or "לא נמצא"

    whatsapp_msg = _build_whatsapp_message(result)
    email_msg = _build_email_message(result)

    full_notification = "\n".join([
        "=" * 60,
        "📱  הודעת WhatsApp (מדומה)",
        f"   אל: {recipient_phone}  |  שולח: {_MOCK_WHATSAPP_SENDER}",
        "=" * 60,
        whatsapp_msg,
        "",
        "=" * 60,
        "📧  הודעת אימייל (מדומה)",
        f"   אל: {recipient_email}  |  משולח: {_MOCK_EMAIL_SENDER}",
        "=" * 60,
        email_msg,
    ])

    # ── Log the dispatch ─────────────────────────────────────────────────────
    logger.info(
        "[NOTIFIER] WhatsApp → %s  |  Email → %s  |  customer: '%s'",
        recipient_phone,
        recipient_email,
        info.business_name,
    )

    # ── Persist locally ──────────────────────────────────────────────────────
    NOTIFY_OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = (
        NOTIFY_OUTPUT_DIR
        / f"notification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    out_path.write_text(full_notification, encoding="utf-8")
    logger.info("[NOTIFIER] Notification saved → %s", out_path)

    return full_notification


# ---------------------------------------------------------------------------
# Private message builders
# ---------------------------------------------------------------------------

def _build_whatsapp_message(result: "OnboardingResult") -> str:
    """Short, mobile-friendly Hebrew WhatsApp message."""
    info = result.business_info
    brands_preview = "، ".join(info.brands[:3]) if info.brands else "מגוון מותגים"
    categories_str = " | ".join(info.service_categories)

    return f"""שלום {info.business_name}! 👋

אני מחברת *זאפ גרופ* – ברוכים הבאים למשפחה!

חשבון הלקוח שלך נפתח בהצלחה ✅
📋 פרטים שאספנו עבורך:
  • שירותים: {categories_str}
  • מותגים: {brands_preview} ועוד
  • אזורי שירות: {", ".join(info.service_area[:4])}

נציג שלנו יצור איתך קשר בקרוב לשיחת אונבורדינג קצרה ויעילה.

בינתיים, אם יש שאלות – אנחנו כאן!
*זאפ גרופ* | onboarding@zapgroup.co.il"""


def _build_email_message(result: "OnboardingResult") -> str:
    """Full structured Hebrew onboarding email."""
    info = result.business_info
    now_str = datetime.now().strftime("%d/%m/%Y")

    return f"""נושא: ברוכים הבאים לזאפ גרופ – סיכום פרטי החשבון שלך

שלום {info.business_name},

אנחנו שמחים לברך אותך על הצטרפותך לזאפ גרופ – הפלטפורמה המובילה בישראל לחיבור בין עסקים ולקוחות!

להלן סיכום פרטי החשבון שנפתח עבורך ב-{now_str}:

──────────────────────────────────────
פרטי עסק
──────────────────────────────────────
{result.customer_card}

──────────────────────────────────────
הצעדים הבאים
──────────────────────────────────────
1. נציג זאפ יצור איתך קשר תוך 24 שעות לשיחת אונבורדינג אישית.
2. בשיחה נסביר כיצד להפיק את המקסימום מהפלטפורמה שלנו.
3. עמוד העסק שלך יפורסם ויהיה חשוף ללקוחות בקריות ובסביבה.

──────────────────────────────────────

בברכה,
צוות האונבורדינג של זאפ גרופ
onboarding@zapgroup.co.il | 03-000-0000
"""
