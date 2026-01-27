#!/usr/bin/env python3
import os
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass



SHOP = os.getenv("SHOPIFY_SHOP") 
TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN")
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL_ID")

# Optional env
API_VER = os.getenv("SHOPIFY_API_VERSION", "2025-10")
STORE_HANDLE = os.getenv("SHOPIFY_ADMIN_STORE_HANDLE")  
LOCAL_TZ = ZoneInfo("America/Chicago")

if not all([SHOP, TOKEN, SLACK_TOKEN, SLACK_CHANNEL]):
    raise RuntimeError("Missing required env vars: SHOPIFY_SHOP, SHOPIFY_ADMIN_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID")



now_utc = datetime.now(timezone.utc)
lower = (now_utc - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
upper = (now_utc - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

search = (
    f"fulfillment_status:unfulfilled AND status:open "
    f"AND -financial_status:pending "
    f"AND created_at:>={lower} AND created_at:<{upper}"
)


GQL = """
query UnfulfilledWindow($q: String!, $first: Int = 50, $after: String) {
  orders(first: $first, after: $after, query: $q, sortKey: CREATED_AT, reverse: true) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        legacyResourceId
        name
        createdAt
        displayFulfillmentStatus
        displayFinancialStatus
      }
    }
  }
}
"""

def shopify_fetch_all():
    url = f"https://{SHOP}/admin/api/{API_VER}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    }
    after = None
    out = []
    while True:
        payload = {"query": GQL, "variables": {"q": search, "first": 100, "after": after}}
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise RuntimeError(f"Shopify GraphQL errors: {data['errors']}")

        orders = data["data"]["orders"]
        for edge in orders["edges"]:
            n = edge["node"]
            out.append({
                "name": n["name"],
                "createdAt": n["createdAt"],
                "fulfillment": n["displayFulfillmentStatus"],
                "financial": n["displayFinancialStatus"],
                "legacyId": str(n["legacyResourceId"]),
                "gid": n["id"],
            })

        if not orders["pageInfo"]["hasNextPage"]:
            break
        after = orders["pageInfo"]["endCursor"]
    return out

def fmt_dt_iso_to_ct(iso_ts: str) -> str:
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    return dt.strftime("%b %d, %Y %I:%M %p %Z")

def order_url(legacy_id: str) -> str:
    if STORE_HANDLE:
        return f"https://admin.shopify.com/store/{STORE_HANDLE}/orders/{legacy_id}"
    return f"https://{SHOP}/admin/orders/{legacy_id}"

def build_lines(rows):
    """Return header and list of bullet lines (strings)."""
    if not rows:
        return ":white_check_mark: No unfulfilled orders in the 30d→24h window.", []
    header = "*Unfulfilled orders > 24hrs (within last 30 days) — Please Review*"
    lines = []
    for r in rows:
        link = order_url(r["legacyId"])
        when = fmt_dt_iso_to_ct(r["createdAt"])
        lines.append(f"• <{link}|{r['name']}> — {when} — Financial: `{r['financial']}` — Fulfillment: `{r['fulfillment']}`")
    return header, lines


MAX_SECTION_CHARS = 2900 
SLEEP_BETWEEN_POSTS = 0.6 

def blocks_from_chunk(header_or_none, body_text):
    blocks = []
    if header_or_none:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": header_or_none}})
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body_text}})
    return blocks

def post_blocks(blocks, fallback_text="Unfulfilled orders"):
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {"channel": SLACK_CHANNEL, "text": fallback_text, "blocks": blocks}
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    resp = r.json()
    if not resp.get("ok"):
        raise RuntimeError(f"Slack error: {resp}")
    return resp

def post_with_chunking(header, lines):
    """
    Try single post; if Slack complains about size, or if body is too long,
    split lines into <=MAX_SECTION_CHARS chunks and post multiple messages.
    """
    if not lines:
        post_blocks(blocks_from_chunk(None, header), header)
        return 1

    body = "\n".join(lines)
    if len(body) <= MAX_SECTION_CHARS:
        try:
            post_blocks(blocks_from_chunk(header, body), header)
            return 1
        except RuntimeError as e:
            if "msg_too_long" not in str(e) and "invalid_blocks" not in str(e):
                raise

    parts = []
    cur, cur_len = [], 0
    for line in lines:
        add_len = len(line) + 1 
        if cur_len + add_len > MAX_SECTION_CHARS and cur:
            parts.append("\n".join(cur))
            cur, cur_len = [line], len(line) + 1
        else:
            cur.append(line)
            cur_len += add_len
    if cur:
        parts.append("\n".join(cur))

    count = 0
    for idx, part in enumerate(parts):
        hdr = header if idx == 0 else f"{header} (cont. {idx})"
        post_blocks(blocks_from_chunk(hdr, part), hdr)
        count += 1
        time.sleep(SLEEP_BETWEEN_POSTS)
    return count

def main():
    rows = shopify_fetch_all()
    header, lines = build_lines(rows)
    msgs = post_with_chunking(header, lines)
    print(f"Posted {msgs} Slack message(s) with {len(rows)} order(s).")
    return {"messages": msgs, "orders": len(rows)}


if __name__ == "__main__":
    main()
