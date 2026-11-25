import html
import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
from typing import Dict, List, Optional, Tuple
from backend.finance import format_inr

CATEGORY_BAR_COLORS = {
    "Food": "#3D9A9B",
    "Accommodation": "#8E7CC3",
    "Transport": "#5B88B8",
    "Activities": "#E07A6B",
    "Shopping": "#E6A15C",
    "Utilities": "#6F9E82",
    "Miscellaneous": "#B9788B",
}


def _get_smtp_config() -> Optional[Dict[str, str]]:
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_password = (
        os.environ.get("SMTP_PASSWORD", "").strip()
        or os.environ.get("SMTP_PASS", "").strip()
    )
    smtp_port_raw = os.environ.get("SMTP_PORT", "587").strip() or "587"
    if not smtp_host and smtp_user.lower().endswith("@gmail.com"):
        smtp_host = "smtp.gmail.com"
    if smtp_host and smtp_user and smtp_password:
        return {
            "host": smtp_host,
            "port": smtp_port_raw,
            "user": smtp_user,
            "password": smtp_password,
        }
    return None


def get_email_provider_status() -> Dict:
    smtp_cfg = _get_smtp_config()
    resend_key = os.environ.get("RESEND_API_KEY", "").strip()
    raw_from = os.environ.get("EMAIL_FROM", "").strip()
    email_from = (
        raw_from
        or (smtp_cfg["user"] if smtp_cfg else "")
        or "TripLedger <noreply@tripledger.local>"
    )

    if smtp_cfg:
        return {
            "configured": True,
            "mode": "live",
            "provider": "smtp",
            "email_from": email_from,
            "message": f"SMTP relay configured ({smtp_cfg['host']}:{smtp_cfg['port']}) for live email delivery.",
        }
    if resend_key:
        return {
            "configured": True,
            "mode": "live",
            "provider": "resend",
            "email_from": email_from,
            "message": "Resend API credentials configured for live email delivery.",
        }
    return {
        "configured": False,
        "mode": "demo",
        "provider": "demo",
        "email_from": email_from,
        "message": "Email credentials are not configured. Running in Demo Mode with downloadable HTML summaries.",
    }


def _split_label(method: str) -> str:
    if method == "custom":
        return "Custom"
    if method == "percentage":
        return "Percentage"
    return "Equal"


def _format_signed_inr(paise: int) -> str:
    if paise > 0:
        return f"+{format_inr(paise)}"
    return format_inr(paise)


def render_member_summary_html(
    trip,
    member_balance: Dict,
    suggested_settlements: List[Dict],
    completed_settlements: List[Dict],
    member_map: Dict[int, str],
    total_trip_spend_paise: int,
    expense_count: int,
    category_breakdown: List[Dict],
    all_balances: Optional[List[Dict]] = None,
) -> Tuple[str, str]:
    """
    Build a comprehensive, crystal-clear, responsive HTML summary email for a single
    member matching the maroon (#641C32), burgundy (#873B52), blush (#F3E7EB),
    and warm white (#FAF9F7) palette.
    Returns (subject, html_body).
    """
    mid = member_balance["member_id"]
    m_name = html.escape(member_balance["member_name"])
    trip_name = html.escape(trip.name)
    destination = html.escape(trip.destination or trip.name)

    outgoing = [
        s for s in suggested_settlements if s["from_member_id"] == mid and s["amount_paise"] > 0
    ]
    incoming = [
        s for s in suggested_settlements if s["to_member_id"] == mid and s["amount_paise"] > 0
    ]
    completed_out = [
        s for s in completed_settlements if s["from_member_id"] == mid and s["amount_paise"] > 0
    ]
    completed_in = [
        s for s in completed_settlements if s["to_member_id"] == mid and s["amount_paise"] > 0
    ]

    total_owed_paise = sum(s["amount_paise"] for s in outgoing)
    total_receivable_paise = sum(s["amount_paise"] for s in incoming)
    total_paid_paise = member_balance["total_paid_paise"]
    total_share_paise = member_balance["total_share_paise"]
    expense_net_paise = member_balance.get(
        "expense_net_paise", total_paid_paise - total_share_paise
    )

    date_label = (
        html.escape(trip.start_date)
        if not trip.end_date or trip.end_date == trip.start_date
        else f"{html.escape(trip.start_date)} to {html.escape(trip.end_date)}"
    )
    subtitle_parts = [date_label, f"{len(member_map)} members", f"{expense_count} expenses"]
    if trip.destination and trip.destination.strip().lower() != trip.name.strip().lower():
        subtitle_parts.insert(0, destination)
    subtitle_html = " | ".join(subtitle_parts)

    if total_owed_paise > 0:
        subject = f"{trip.name} Expense Statement: You owe {format_inr(total_owed_paise)}"
        headline_status = (
            f"You owe a remaining balance of {format_inr(total_owed_paise)} to settle this trip."
        )
        position_label = "Remaining To Pay"
        position_value = format_inr(total_owed_paise)
        position_color = "#641C32"
    elif total_receivable_paise > 0:
        subject = f"{trip.name} Expense Statement: You receive {format_inr(total_receivable_paise)}"
        headline_status = (
            f"Others owe you a remaining balance of {format_inr(total_receivable_paise)} for this trip."
        )
        position_label = "Remaining To Receive"
        position_value = format_inr(total_receivable_paise)
        position_color = "#2F6F4E"
    else:
        subject = f"{trip.name} Expense Statement: Settled"
        headline_status = "Your trip balance is completely settled with zero remaining dues."
        position_label = "Remaining Balance"
        position_value = format_inr(0)
        position_color = "#2F6F4E"

    def render_transfer_rows(items: List[Dict], direction: str) -> str:
        if not items:
            empty_txt = (
                "No outgoing payments required."
                if direction == "out"
                else "No incoming payments expected."
            )
            return f"""
              <tr>
                <td colspan="2" style="padding:12px 16px;font-size:13px;color:#6E656B;border-top:1px solid #EFE9EB;">
                  {empty_txt}
                </td>
              </tr>
            """
        rows = []
        for item in items:
            counterparty_id = (
                item["to_member_id"] if direction == "out" else item["from_member_id"]
            )
            counterparty_name = html.escape(member_map.get(counterparty_id, "Trip Member"))
            label = (
                f"Pay {counterparty_name}"
                if direction == "out"
                else f"Receive from {counterparty_name}"
            )
            amt_str = format_inr(item["amount_paise"])
            amt_color = "#641C32" if direction == "out" else "#2F6F4E"
            rows.append(
                f"""
                <tr>
                  <td style="padding:12px 16px;font-size:14px;font-weight:500;color:#29252A;border-top:1px solid #EFE9EB;">
                    {label}
                  </td>
                  <td align="right" style="padding:12px 16px;font-size:14px;font-weight:700;color:{amt_color};font-family:'JetBrains Mono',Consolas,monospace;border-top:1px solid #EFE9EB;">
                    {amt_str}
                  </td>
                </tr>
                """
            )
        return "\n".join(rows)

    completed_section = ""
    if completed_out or completed_in:
        c_rows = []
        for item in completed_out:
            name = html.escape(member_map.get(item["to_member_id"], "Trip Member"))
            c_rows.append(
                f'<tr><td style="padding:10px 16px;font-size:13px;color:#29252A;border-top:1px solid #EFE9EB;">Paid to {name} (Recorded)</td>'
                f'<td align="right" style="padding:10px 16px;font-size:13px;font-family:Consolas,monospace;color:#2F6F4E;border-top:1px solid #EFE9EB;">{format_inr(item["amount_paise"])}</td></tr>'
            )
        for item in completed_in:
            name = html.escape(member_map.get(item["from_member_id"], "Trip Member"))
            c_rows.append(
                f'<tr><td style="padding:10px 16px;font-size:13px;color:#29252A;border-top:1px solid #EFE9EB;">Received from {name} (Recorded)</td>'
                f'<td align="right" style="padding:10px 16px;font-size:13px;font-family:Consolas,monospace;color:#2F6F4E;border-top:1px solid #EFE9EB;">{format_inr(item["amount_paise"])}</td></tr>'
            )
        completed_section = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;border:1px solid #E9E2E4;border-radius:10px;background-color:#FFFFFF;border-collapse:separate;">
          <tr>
            <td colspan="2" style="padding:11px 16px;background-color:#FAF9F7;font-size:11px;font-weight:700;color:#6E656B;text-transform:uppercase;letter-spacing:0.05em;">
              Already Recorded Payments
            </td>
          </tr>
          {''.join(c_rows)}
        </table>
        """

    # Itemized Expense Breakdown for full auditability
    sorted_expenses = sorted(
        list(getattr(trip, "expenses", []) or []),
        key=lambda e: (e.expense_date, e.id),
    )
    expense_rows_html = []
    for exp in sorted_expenses:
        paid_by_me = exp.amount_paise if exp.payer_id == mid else 0
        my_share_obj = next((sh for sh in exp.shares if sh.member_id == mid), None)
        my_share = my_share_obj.share_paise if my_share_obj else 0
        net_effect = paid_by_me - my_share
        payer_name = html.escape(
            member_map.get(exp.payer_id, exp.payer.name if exp.payer else "Member")
        )
        participant_count = len(exp.shares)
        meta_line = (
            f"{html.escape(exp.expense_date)} | {html.escape(exp.category)} | "
            f"Paid by {payer_name} | {_split_label(exp.split_method)} ({participant_count})"
        )
        if net_effect > 0:
            net_color = "#2F6F4E"
            net_text = _format_signed_inr(net_effect)
        elif net_effect < 0:
            net_color = "#641C32"
            net_text = _format_signed_inr(net_effect)
        else:
            net_color = "#6E656B"
            net_text = format_inr(0)

        share_text = format_inr(my_share) if my_share_obj else "Not included"
        share_color = "#29252A" if my_share_obj else "#8E8489"
        paid_text = format_inr(paid_by_me) if paid_by_me > 0 else "-"
        paid_color = "#29252A" if paid_by_me > 0 else "#8E8489"

        expense_rows_html.append(
            f"""
            <tr>
              <td style="padding:11px 12px;border-top:1px solid #EFE9EB;vertical-align:top;">
                <div style="font-size:13px;font-weight:600;color:#29252A;">{html.escape(exp.title)}</div>
                <div style="margin-top:2px;font-size:11px;color:#6E656B;">{meta_line}</div>
              </td>
              <td align="right" style="padding:11px 10px;border-top:1px solid #EFE9EB;font-size:12px;font-family:Consolas,monospace;color:#524A4E;white-space:nowrap;vertical-align:top;">
                {format_inr(exp.amount_paise)}
              </td>
              <td align="right" style="padding:11px 10px;border-top:1px solid #EFE9EB;font-size:12px;font-family:Consolas,monospace;color:{paid_color};white-space:nowrap;vertical-align:top;">
                {paid_text}
              </td>
              <td align="right" style="padding:11px 10px;border-top:1px solid #EFE9EB;font-size:12px;font-family:Consolas,monospace;color:{share_color};white-space:nowrap;vertical-align:top;">
                {share_text}
              </td>
              <td align="right" style="padding:11px 12px;border-top:1px solid #EFE9EB;font-size:12px;font-weight:700;font-family:Consolas,monospace;color:{net_color};white-space:nowrap;vertical-align:top;">
                {net_text}
              </td>
            </tr>
            """
        )

    if not expense_rows_html:
        expense_rows_html.append(
            """
            <tr>
              <td colspan="5" style="padding:14px 12px;font-size:13px;color:#6E656B;border-top:1px solid #EFE9EB;text-align:center;">
                No expenses were logged for this trip.
              </td>
            </tr>
            """
        )

    # Full Group Member Balances Overview
    group_balance_rows = []
    if all_balances:
        for bal in all_balances:
            is_self = bal["member_id"] == mid
            b_name = html.escape(bal["member_name"])
            tag = ' <span style="color:#641C32;font-weight:700;">(You)</span>' if is_self else ""
            rem = bal["remaining_net_paise"]
            rem_color = "#2F6F4E" if rem > 0 else "#641C32" if rem < 0 else "#6E656B"
            row_bg = "#FAF9F7" if is_self else "#FFFFFF"
            group_balance_rows.append(
                f"""
                <tr style="background-color:{row_bg};">
                  <td style="padding:9px 12px;font-size:12px;color:#29252A;border-top:1px solid #EFE9EB;">{b_name}{tag}</td>
                  <td align="right" style="padding:9px 10px;font-size:12px;font-family:Consolas,monospace;color:#524A4E;border-top:1px solid #EFE9EB;">{format_inr(bal['total_paid_paise'])}</td>
                  <td align="right" style="padding:9px 10px;font-size:12px;font-family:Consolas,monospace;color:#524A4E;border-top:1px solid #EFE9EB;">{format_inr(bal['total_share_paise'])}</td>
                  <td align="right" style="padding:9px 12px;font-size:12px;font-weight:700;font-family:Consolas,monospace;color:{rem_color};border-top:1px solid #EFE9EB;">{_format_signed_inr(rem)}</td>
                </tr>
                """
            )

    group_balances_section = ""
    if group_balance_rows:
        group_balances_section = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;border:1px solid #E9E2E4;border-radius:10px;background-color:#FFFFFF;border-collapse:separate;">
          <tr>
            <td colspan="4" style="padding:11px 12px;background-color:#FAF9F7;font-size:11px;font-weight:700;color:#873B52;text-transform:uppercase;letter-spacing:0.05em;">
              Group Member Balances Overview
            </td>
          </tr>
          <tr style="background-color:#FAF9F7;">
            <td style="padding:8px 12px;font-size:11px;font-weight:600;color:#6E656B;border-top:1px solid #EFE9EB;">Member</td>
            <td align="right" style="padding:8px 10px;font-size:11px;font-weight:600;color:#6E656B;border-top:1px solid #EFE9EB;">Paid</td>
            <td align="right" style="padding:8px 10px;font-size:11px;font-weight:600;color:#6E656B;border-top:1px solid #EFE9EB;">Share</td>
            <td align="right" style="padding:8px 12px;font-size:11px;font-weight:600;color:#6E656B;border-top:1px solid #EFE9EB;">Remaining</td>
          </tr>
          {''.join(group_balance_rows)}
        </table>
        """

    # Full Group Settlement Plan
    group_plan_section = ""
    if suggested_settlements:
        plan_rows = []
        for s in suggested_settlements:
            from_n = html.escape(member_map.get(s["from_member_id"], "Member"))
            to_n = html.escape(member_map.get(s["to_member_id"], "Member"))
            is_mine = s["from_member_id"] == mid or s["to_member_id"] == mid
            weight = "700" if is_mine else "500"
            bg = "#F3E7EB" if is_mine else "#FFFFFF"
            plan_rows.append(
                f"""
                <tr style="background-color:{bg};">
                  <td style="padding:9px 14px;font-size:12px;font-weight:{weight};color:#29252A;border-top:1px solid #EFE9EB;">
                    {from_n} pays {to_n}
                  </td>
                  <td align="right" style="padding:9px 14px;font-size:12px;font-weight:700;font-family:Consolas,monospace;color:#641C32;border-top:1px solid #EFE9EB;">
                    {format_inr(s['amount_paise'])}
                  </td>
                </tr>
                """
            )
        group_plan_section = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;border:1px solid #E9E2E4;border-radius:10px;background-color:#FFFFFF;border-collapse:separate;">
          <tr>
            <td colspan="2" style="padding:11px 14px;background-color:#FAF9F7;font-size:11px;font-weight:700;color:#873B52;text-transform:uppercase;letter-spacing:0.05em;">
              Complete Group Settlement Plan ({len(suggested_settlements)} optimized transfer(s))
            </td>
          </tr>
          {''.join(plan_rows)}
        </table>
        """

    # Visual Category Breakdown
    cat_rows = []
    for cat in category_breakdown:
        cat_name = html.escape(cat["category"])
        bar_color = CATEGORY_BAR_COLORS.get(cat["category"], "#873B52")
        pct_width = max(4, min(100, int(round(cat["percentage"]))))
        cat_rows.append(
            f"""
            <tr>
              <td style="padding:8px 0;border-bottom:1px solid #F3ECEE;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="font-size:13px;font-weight:500;color:#29252A;">{cat_name} <span style="font-size:11px;color:#6E656B;">({cat['count']} items)</span></td>
                    <td align="right" style="font-size:12px;font-family:Consolas,monospace;color:#29252A;">{format_inr(cat['amount_paise'])} ({cat['percentage']}%)</td>
                  </tr>
                  <tr>
                    <td colspan="2" style="padding-top:5px;">
                      <div style="width:100%;height:6px;background-color:#F3ECEE;border-radius:4px;overflow:hidden;">
                        <div style="width:{pct_width}%;height:6px;background-color:{bar_color};border-radius:4px;"></div>
                      </div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            """
        )

    net_pos_color = "#2F6F4E" if expense_net_paise > 0 else "#641C32" if expense_net_paise < 0 else "#29252A"

    html_body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html.escape(subject)}</title>
</head>
<body style="margin:0;padding:0;background-color:#FAF9F7;color:#29252A;font-family:'DM Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#FAF9F7;padding:28px 14px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:660px;background-color:#FFFFFF;border:1px solid #E9E2E4;border-radius:14px;overflow:hidden;">
          <tr>
            <td style="background-color:#641C32;padding:26px 28px;color:#FFFFFF;">
              <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#F3E7EB;margin-bottom:6px;">TripLedger Final Statement</div>
              <h1 style="margin:0;font-size:23px;font-weight:700;color:#FFFFFF;">{trip_name}</h1>
              <div style="margin-top:6px;font-size:13px;color:#F3E7EB;">{subtitle_html}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:26px 28px;">
              <p style="margin:0 0 6px 0;font-size:15px;font-weight:600;color:#29252A;">Hello {m_name},</p>
              <p style="margin:0 0 18px 0;font-size:14px;line-height:1.55;color:#524A4E;">
                {headline_status} Below is your personalized balance summary, settlement plan, and complete item-by-item expense breakdown.
              </p>

              <!-- 4-metric snapshot -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F3E7EB;border-radius:10px;border:1px solid #E4D0D7;">
                <tr>
                  <td width="25%" style="padding:12px 12px;vertical-align:top;">
                    <div style="font-size:11px;color:#873B52;margin-bottom:4px;">Total Paid</div>
                    <div style="font-size:15px;font-weight:700;color:#29252A;font-family:Consolas,monospace;">{format_inr(total_paid_paise)}</div>
                  </td>
                  <td width="25%" style="padding:12px 12px;border-left:1px solid #DFC8D0;vertical-align:top;">
                    <div style="font-size:11px;color:#873B52;margin-bottom:4px;">Your Share</div>
                    <div style="font-size:15px;font-weight:700;color:#29252A;font-family:Consolas,monospace;">{format_inr(total_share_paise)}</div>
                  </td>
                  <td width="25%" style="padding:12px 12px;border-left:1px solid #DFC8D0;vertical-align:top;">
                    <div style="font-size:11px;color:#873B52;margin-bottom:4px;">Expense Net</div>
                    <div style="font-size:15px;font-weight:700;color:{net_pos_color};font-family:Consolas,monospace;">{_format_signed_inr(expense_net_paise)}</div>
                  </td>
                  <td width="25%" style="padding:12px 12px;border-left:1px solid #DFC8D0;vertical-align:top;">
                    <div style="font-size:11px;color:#873B52;margin-bottom:4px;">{position_label}</div>
                    <div style="font-size:15px;font-weight:700;color:{position_color};font-family:Consolas,monospace;">{position_value}</div>
                  </td>
                </tr>
              </table>

              <!-- Action Required: Outgoing -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;border:1px solid #E9E2E4;border-radius:10px;background-color:#FFFFFF;border-collapse:separate;">
                <tr>
                  <td colspan="2" style="padding:11px 16px;background-color:#FAF9F7;font-size:11px;font-weight:700;color:#873B52;text-transform:uppercase;letter-spacing:0.05em;">
                    Payments You Must Make
                  </td>
                </tr>
                {render_transfer_rows(outgoing, "out")}
              </table>

              <!-- Action Required: Incoming -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px;border:1px solid #E9E2E4;border-radius:10px;background-color:#FFFFFF;border-collapse:separate;">
                <tr>
                  <td colspan="2" style="padding:11px 16px;background-color:#FAF9F7;font-size:11px;font-weight:700;color:#873B52;text-transform:uppercase;letter-spacing:0.05em;">
                    Payments Others Must Send You
                  </td>
                </tr>
                {render_transfer_rows(incoming, "in")}
              </table>

              {completed_section}

              <!-- Itemized Expense Ledger -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;border:1px solid #E9E2E4;border-radius:10px;background-color:#FFFFFF;border-collapse:separate;">
                <tr>
                  <td colspan="5" style="padding:11px 12px;background-color:#FAF9F7;font-size:11px;font-weight:700;color:#641C32;text-transform:uppercase;letter-spacing:0.05em;">
                    Itemized Trip Expense Breakdown ({expense_count} expenses)
                  </td>
                </tr>
                <tr style="background-color:#FAF9F7;">
                  <td style="padding:8px 12px;font-size:11px;font-weight:600;color:#6E656B;border-top:1px solid #EFE9EB;">Expense</td>
                  <td align="right" style="padding:8px 10px;font-size:11px;font-weight:600;color:#6E656B;border-top:1px solid #EFE9EB;">Total</td>
                  <td align="right" style="padding:8px 10px;font-size:11px;font-weight:600;color:#6E656B;border-top:1px solid #EFE9EB;">You Paid</td>
                  <td align="right" style="padding:8px 10px;font-size:11px;font-weight:600;color:#6E656B;border-top:1px solid #EFE9EB;">Your Share</td>
                  <td align="right" style="padding:8px 12px;font-size:11px;font-weight:600;color:#6E656B;border-top:1px solid #EFE9EB;">Net Effect</td>
                </tr>
                {''.join(expense_rows_html)}
                <tr style="background-color:#FAF9F7;">
                  <td style="padding:10px 12px;font-size:12px;font-weight:700;color:#29252A;border-top:1px solid #DFC8D0;">Total</td>
                  <td align="right" style="padding:10px 10px;font-size:12px;font-weight:700;font-family:Consolas,monospace;color:#29252A;border-top:1px solid #DFC8D0;">{format_inr(total_trip_spend_paise)}</td>
                  <td align="right" style="padding:10px 10px;font-size:12px;font-weight:700;font-family:Consolas,monospace;color:#29252A;border-top:1px solid #DFC8D0;">{format_inr(total_paid_paise)}</td>
                  <td align="right" style="padding:10px 10px;font-size:12px;font-weight:700;font-family:Consolas,monospace;color:#29252A;border-top:1px solid #DFC8D0;">{format_inr(total_share_paise)}</td>
                  <td align="right" style="padding:10px 12px;font-size:12px;font-weight:700;font-family:Consolas,monospace;color:{net_pos_color};border-top:1px solid #DFC8D0;">{_format_signed_inr(expense_net_paise)}</td>
                </tr>
              </table>

              {group_balances_section}
              {group_plan_section}

              <!-- Category Spending -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:22px;">
                <tr>
                  <td style="font-size:12px;font-weight:700;color:#641C32;text-transform:uppercase;letter-spacing:0.05em;padding-bottom:6px;">Spending By Category</td>
                </tr>
                {''.join(cat_rows) if cat_rows else '<tr><td style="font-size:12px;color:#6E656B;">No category breakdown available.</td></tr>'}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 28px;background-color:#FAF9F7;border-top:1px solid #E9E2E4;font-size:12px;color:#6E656B;">
              Generated by TripLedger | Consolidated net settlement calculation | {html.escape(trip.status.title())} Trip
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return subject, html_body


def _build_plain_text_fallback(subject: str, html_body: str) -> str:
    import re

    text = re.sub(r"<style[^>]*>.*?</style>", "", html_body, flags=re.S | re.I)
    text = re.sub(r"<(tr|p|div|h1|h2|h3|li)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<t[dh][^>]*>", "  ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return f"{subject}\n\n" + "\n".join(lines)


def send_email_message(to_email: str, subject: str, html_body: str) -> Dict:
    """
    Attempt real email delivery via SMTP (preferred when configured) or Resend.
    Returns dict with keys: status ('sent'|'demo'|'failed'), provider, error_message, sent_at.
    Never reports 'sent' unless the provider actually accepted the email.
    """
    provider_info = get_email_provider_status()
    if not provider_info["configured"]:
        return {
            "status": "demo",
            "provider": "demo",
            "error_message": "Email credentials unavailable. Preview and HTML download generated in Demo Mode.",
            "sent_at": None,
        }

    email_from = provider_info["email_from"]

    if provider_info["provider"] == "smtp":
        smtp_cfg = _get_smtp_config()
        assert smtp_cfg is not None
        smtp_host = smtp_cfg["host"]
        smtp_port = int(smtp_cfg["port"])
        smtp_user = smtp_cfg["user"]
        smtp_password = smtp_cfg["password"]

        _, bare_from = parseaddr(email_from)
        sender_addr = bare_from or smtp_user

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr(("TripLedger", sender_addr))
        msg["Reply-To"] = sender_addr
        msg["To"] = to_email
        plain_body = _build_plain_text_fallback(subject, html_body)
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        raw_msg = msg.as_string()
        ssl_context = ssl.create_default_context()

        def _deliver(password_to_try: str):
            if smtp_port == 465:
                with smtplib.SMTP_SSL(
                    smtp_host, smtp_port, timeout=15, context=ssl_context
                ) as server:
                    server.ehlo()
                    server.login(smtp_user, password_to_try)
                    server.sendmail(sender_addr, [to_email], raw_msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                    server.ehlo()
                    server.starttls(context=ssl_context)
                    server.ehlo()
                    server.login(smtp_user, password_to_try)
                    server.sendmail(sender_addr, [to_email], raw_msg)

        try:
            try:
                _deliver(smtp_password)
            except smtplib.SMTPAuthenticationError:
                compact_pw = smtp_password.replace(" ", "")
                if compact_pw != smtp_password and len(compact_pw) == 16:
                    _deliver(compact_pw)
                else:
                    raise
            return {
                "status": "sent",
                "provider": "smtp",
                "error_message": None,
                "sent_at": datetime.now(timezone.utc),
            }
        except Exception as exc:
            return {
                "status": "failed",
                "provider": "smtp",
                "error_message": str(exc)[:300],
                "sent_at": None,
            }

    # Resend fallback only when SMTP is not configured
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    payload = json.dumps(
        {
            "from": email_from,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                return {
                    "status": "sent",
                    "provider": "resend",
                    "error_message": None,
                    "sent_at": datetime.now(timezone.utc),
                }
            return {
                "status": "failed",
                "provider": "resend",
                "error_message": f"Resend returned HTTP {resp.status}",
                "sent_at": None,
            }
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        return {
            "status": "failed",
            "provider": "resend",
            "error_message": f"Resend HTTP {exc.code}: {err_body[:240]}",
            "sent_at": None,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "provider": "resend",
            "error_message": str(exc)[:240],
            "sent_at": None,
        }
