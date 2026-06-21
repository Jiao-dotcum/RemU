import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from watcharb.models import ArbitrageOpportunity


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


class EmailAlerter:
    """Sends alerts via SMTP. Reads connection details from environment
    variables so credentials never end up in config files or git history:

      SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO

    For Gmail: use an App Password (https://myaccount.google.com/apppasswords),
    not your regular password, and set SMTP_HOST=smtp.gmail.com.
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
        missing = [
            name
            for name, val in [
                ("SMTP_HOST", self.host),
                ("SMTP_USER", self.user),
                ("SMTP_PASS", self.password),
                ("ALERT_EMAIL_TO", self.to_addr),
            ]
            if not val
        ]
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
