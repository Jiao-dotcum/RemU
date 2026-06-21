import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from watcharb.models import ArbitrageOpportunity


# ── shared formatters ──────────────────────────────────────────────────────────

def build_subject(opportunities: list[ArbitrageOpportunity]) -> str:
    return f"Watch arbitrage alert: {len(opportunities)} opportunity(ies) found"


def build_plaintext(opportunities: list[ArbitrageOpportunity]) -> str:
    lines = []
    for opp in opportunities:
        lines.append(
            f"{opp.brand} {opp.model} ({opp.reference})\n"
            f"  Buy:  ${opp.cheap.price:,.2f} from {opp.cheap.seller} via {opp.cheap.source}\n"
            f"        {opp.cheap.url}\n"
            f"  Sell: ${opp.expensive.price:,.2f} from {opp.expensive.seller} via {opp.expensive.source}\n"
            f"        {opp.expensive.url}\n"
            f"  Spread: ${opp.diff_abs:,.2f} ({opp.diff_pct:.1f}%) across {opp.listing_count} listings\n"
        )
    return "\n".join(lines)


def build_html(opportunities: list[ArbitrageOpportunity]) -> str:
    rows = "".join(
        f"<tr>"
        f"<td>{opp.brand} {opp.model}<br><small>{opp.reference}</small></td>"
        f"<td>${opp.cheap.price:,.2f}<br><small>{opp.cheap.seller} ({opp.cheap.source})</small><br>"
        f"<a href='{opp.cheap.url}'>listing</a></td>"
        f"<td>${opp.expensive.price:,.2f}<br><small>{opp.expensive.seller} ({opp.expensive.source})</small><br>"
        f"<a href='{opp.expensive.url}'>listing</a></td>"
        f"<td>${opp.diff_abs:,.2f}<br>({opp.diff_pct:.1f}%)</td>"
        f"</tr>"
        for opp in opportunities
    )
    return (
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<tr><th>Watch</th><th>Cheapest</th><th>Most expensive</th><th>Spread</th></tr>"
        f"{rows}</table>"
    )


# ── ntfy (zero-setup push notifications) ─────────────────────────────────────

class NtfyAlerter:
    """Sends push notifications via ntfy.sh — no account required.

    Set `alerts.ntfy_topic` in config.yaml to a private random string.
    Subscribe to https://ntfy.sh/<topic> in the free ntfy app (iOS/Android).
    Nothing else to configure.
    """

    def __init__(self, topic: str, server: str = "https://ntfy.sh"):
        self.topic = topic
        self.server = server.rstrip("/")

    def send(self, opportunities: list[ArbitrageOpportunity]) -> None:
        if not opportunities:
            return
        title = build_subject(opportunities)
        body = build_plaintext(opportunities)
        try:
            r = requests.post(
                f"{self.server}/{self.topic}",
                data=body.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": "high",
                    "Tags": "watch,money_with_wings",
                },
                timeout=10,
            )
            r.raise_for_status()
            print(f"[ntfy] alert sent to {self.server}/{self.topic}")
        except Exception as exc:
            print(f"[ntfy] failed to send alert: {exc}")


# ── Telegram ──────────────────────────────────────────────────────────────────

class TelegramAlerter:
    """Sends a message via a Telegram bot.

    Requires two env vars:
      TELEGRAM_BOT_TOKEN  — from @BotFather (/newbot)
      TELEGRAM_CHAT_ID    — your personal chat ID (send /start to the bot,
                            then visit https://api.telegram.org/bot<TOKEN>/getUpdates)
    """

    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    def send(self, opportunities: list[ArbitrageOpportunity]) -> None:
        if not opportunities:
            return
        missing = [k for k, v in [("TELEGRAM_BOT_TOKEN", self.token), ("TELEGRAM_CHAT_ID", self.chat_id)] if not v]
        if missing:
            print(f"[telegram] not sending, missing env vars: {', '.join(missing)}")
            return
        text = f"*{build_subject(opportunities)}*\n\n{build_plaintext(opportunities)}"
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
            r.raise_for_status()
            print(f"[telegram] alert sent to chat {self.chat_id}")
        except Exception as exc:
            print(f"[telegram] failed to send alert: {exc}")


# ── Email (optional) ──────────────────────────────────────────────────────────

class EmailAlerter:
    """Sends alerts via SMTP. Reads connection details from environment
    variables: SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO.
    For Gmail use an App Password, not your regular password.
    """

    def __init__(self):
        self.host = os.environ.get("SMTP_HOST")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.user = os.environ.get("SMTP_USER")
        self.password = os.environ.get("SMTP_PASS")
        self.to_addr = os.environ.get("ALERT_EMAIL_TO")

    def send(self, opportunities: list[ArbitrageOpportunity]) -> None:
        if not opportunities:
            return
        missing = [n for n, v in [("SMTP_HOST", self.host), ("SMTP_USER", self.user),
                                   ("SMTP_PASS", self.password), ("ALERT_EMAIL_TO", self.to_addr)] if not v]
        if missing:
            print(f"[email] not sending, missing env vars: {', '.join(missing)}")
            return
        msg = MIMEMultipart("alternative")
        msg["Subject"] = build_subject(opportunities)
        msg["From"] = self.user
        msg["To"] = self.to_addr
        msg.attach(MIMEText(build_plaintext(opportunities), "plain"))
        msg.attach(MIMEText(build_html(opportunities), "html"))
        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls()
            server.login(self.user, self.password)
            server.sendmail(self.user, [self.to_addr], msg.as_string())
        print(f"[email] sent alert to {self.to_addr}")


# ── factory ───────────────────────────────────────────────────────────────────

def build_alerter(config: dict):
    """Return the right alerter based on config['alerts']['channel'].
    Supported: ntfy (default), telegram, email, none.
    """
    alerts_cfg = config.get("alerts", {})
    channel = alerts_cfg.get("channel", "ntfy").lower()

    if channel == "ntfy":
        topic = alerts_cfg.get("ntfy_topic") or os.environ.get("NTFY_TOPIC", "")
        if not topic:
            raise ValueError("alerts.ntfy_topic is required when channel=ntfy")
        server = alerts_cfg.get("ntfy_server", "https://ntfy.sh")
        return NtfyAlerter(topic=topic, server=server)

    if channel == "telegram":
        return TelegramAlerter()

    if channel == "email":
        return EmailAlerter()

    if channel == "none":
        return None

    raise ValueError(f"Unknown alert channel: {channel!r}. Choose ntfy, telegram, email, or none.")
