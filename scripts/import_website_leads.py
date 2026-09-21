"""Import every website lead the outreach agents found into a standalone leads file.

The outreach_worker narrated its prospects in each task's "## Agent Output" and (when it
remembered) appended a thin row to vault/outreach/crm.md. The CRM keeps 8 columns and only the
single contact the agent actually used; the task history holds strictly more — the other
channels it found, which run turned it up, how many times it resurfaced, the city/category it
was sourced from. This script reconstructs that fuller picture into its own file so the lead
list is readable on its own, without touching the CRM the pod writes to at runtime.

Four output shapes appear across the run history, parsed in descending fidelity:

  Table   — the agent pasted a full CRM table into its output (richest; contact + type + city)
              | Eko's Bar & Grill | Restaurant | Lowell, MA | @ekosbarandgrill | instagram | ...
  Status  — **Business Name**: Found email `x@y.com`. Sent email. Status: `email_sent`.
  Inline  — "Business Name": Sent an email to `x@y.com` and appended ... with status `email_sent`.
  Narrative — quoted/bulleted names under a "**City, ST - category:**" header or a
              'Searched for "cafes Fitchburg MA"' line; channel inferred from nearby wording.

Leads are merged by normalized business name across every run: contact channels union together,
the most advanced status wins, and first/last seen dates plus source task ids are retained.

Usage:
    python scripts/import_website_leads.py            # dry-run: parse + report, write nothing
    python scripts/import_website_leads.py --write    # write the markdown + csv lead files
"""
import argparse
import csv
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
TASK_DIRS = [ROOT / "workspace" / "tasks" / d for d in ("done", "failed", "todo")]
OUT_MD = ROOT / "workspace" / "outreach" / "website-leads.md"
OUT_CSV = ROOT / "workspace" / "outreach" / "website-leads.csv"

COLUMNS = ["Business", "Type", "City", "Email", "Instagram", "Phone",
           "Channel", "Status", "First Seen", "Last Seen", "Runs", "Source Tasks"]

# Most advanced outcome wins when the same business shows up across several runs.
STATUS_RANK = {
    "closed": 7, "replied": 6, "no_interest": 5, "followed_up": 4,
    "email_sent": 3, "dm_queued": 2, "call_queued": 1, "found": 0,
}
STATUS_ALIAS = {"emailed": "email_sent", "dm_sent": "dm_queued", "queued": "call_queued"}

_AGENT = re.compile(r"assigned_agent:\s*outreach_worker")
_POD = re.compile(r"pod:\s*local_outreach_pod")
_TASK_ID = re.compile(r"task_id:\s*(\S+)")
_CREATED = re.compile(r"created_at:\s*(\d{8})")

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_HANDLE = re.compile(r"@[A-Za-z0-9_.]{3,30}")
_PHONE = re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")
_STATUS_WORD = "email_sent|dm_queued|call_queued|followed_up|replied|closed|no_interest|emailed|dm_sent"

# --- lead-bearing line shapes -------------------------------------------------------------
_TABLE_ROW = re.compile(r"^\|(?P<cells>.+)\|\s*$")
_FMT_STATUS = re.compile(r"\*\*([^*\n]{2,70}?)\*\*[ \t]*:?[ \t]*([^\n]*?Status:\s*`?(" + _STATUS_WORD + r")`?)",
                         re.IGNORECASE)
_BOLD = re.compile(r"\*\*([^*\n]{3,70}?)\*\*")
_QUOTED = re.compile(r"[\"“]([^\"”\n]{3,70}?)[\"”]")
_BULLET_NAME_CITY = re.compile(r"(?m)^\s*[*\-•]\s*\**\s*([^*\n(]{3,70}?)\s*\**\s*\(([A-Za-z .'-]+,\s*[A-Z]{2})\)")

# --- city / category context --------------------------------------------------------------
# "**Chicopee, MA - cleaning services:**" / "**Haverhill, MA - Hair Salons:**"
_HDR_CITY_CAT = re.compile(r"\*\*\s*([A-Za-z .'-]+,\s*[A-Z]{2})\s*[-–—]\s*([^*:\n]+?)\s*:?\s*\*\*")
# "**Salem, MA (Hair Salons)**"
_HDR_CITY_PAREN = re.compile(r"\*\*\s*([A-Za-z .'-]+,\s*[A-Z]{2})\s*\(([^)]+)\)\s*\*\*")
# 'Searched for "nail salons Taunton MA"' / 'Searched for "restaurants" in Worcester, MA'
_SEARCH_QUOTED = re.compile(r"[\"“]([a-z][a-z /&'-]+?)\s+([A-Z][A-Za-z .'-]+?)\s+([A-Z]{2})[\"”]")
_SEARCH_IN = re.compile(r"[\"“]([a-z][a-z /&'-]+)[\"”]\s+in\s+([A-Z][A-Za-z .'-]+?,\s*[A-Z]{2})")
_CITY_INLINE = re.compile(r"\(([A-Za-z .'-]+,\s*[A-Z]{2})\)")

_CAT_HINTS = [
    ("nail", "Nail Salon"), ("barber", "Barbershop"), ("hair", "Hair Salon"), ("salon", "Salon"),
    ("spa", "Spa"), ("auto", "Auto"), ("tire", "Auto Repair"), ("detail", "Auto Detailing"),
    ("plumb", "Plumber"), ("electric", "Electrician"), ("hvac", "HVAC"), ("heating", "HVAC"),
    ("roof", "Roofer"), ("paint", "Painter"), ("landscap", "Landscaping"), ("lawn", "Lawn Care"),
    ("greenhouse", "Florist"), ("florist", "Florist"), ("flower", "Florist"),
    ("clean", "Cleaning"), ("sanitiz", "Cleaning"), ("cafe", "Cafe"), ("coffee", "Cafe"),
    ("baker", "Bakery"), ("daycare", "Daycare"), ("tutor", "Tutoring"), ("fitness", "Fitness"),
    ("yoga", "Yoga"), ("tattoo", "Tattoo"), ("massage", "Massage"), ("photo", "Photographer"),
    ("dry clean", "Dry Cleaner"), ("car wash", "Car Wash"), ("food truck", "Food Truck"), ("laundr", "Laundromat"), ("tailor", "Tailor"),
    ("moving", "Moving"), ("groom", "Pet Grooming"), ("pet", "Pet Services"),
    ("restaurant", "Restaurant"), ("pizza", "Restaurant"), ("grill", "Restaurant"),
    ("deli", "Deli"), ("contractor", "Contractor"), ("construction", "Contractor"),
    ("notary", "Notary"), ("halal", "Restaurant"),
]

# Bold/quoted spans that are section labels, tool names or agent chatter — never businesses.
_NOISE_EXACT = {
    "website", "websites", "interested", "status", "email", "emails", "instagram", "note",
    "notes", "failure", "metric", "metrics", "pattern", "crm", "crm update", "crm updates",
    "crm load", "the system", "read_inbox", "find_prospects", "send_email", "send_dm",
    "log_outreach_lead", "summary", "summary of actions", "inbox check", "checked inbox",
    "prospect discovery", "no website verification", "contact info extraction", "follow-ups",
    "follow up", "next outreach run", "memory log", "logged to memory", "created next task",
    "prospects found", "emails sent", "dms sent", "bounces", "replies received", "observation",
    "city targeted", "category", "categories", "call queue additions", "high", "medium", "low",
    "true", "false", "none", "n/a", "starter", "pro", "premium", "easy simple sites",
    "identified prospects", "attempted contact & updated crm", "prospected and contacted",
    "call queue", "next steps", "outreach", "task", "tasks", "error", "errors", "warning",
    "contact", "contact lookup", "action", "stop", "unsubscribe", "learning and next steps",
    "auto shops", "automotive service", "auto repair", "hair salons", "nail salons",
    "prospect auto", "follow-up scheduling", "follow-up", "prospecting", "outreach summary",
    "prospect", "prospect research", "plumbers", "carpet cleaners", "results", "next run",
    "next run task", "task creation", "patterns observed", "instagram dms sent",
    "air conditioning & heating", "heating and air conditioning", "second batch of margs",
}
# A bold/quoted span containing one of these is a section label or agent bookkeeping.
_NOISE_SUBSTR = (
    "crm", "metric", "reasoning", "summary", "next task", "contact information",
    "prospects", "call queued", "email sent", "dm queued", "follow-up task",
    "agent output", "memory", "inbox", "lookup", "next steps", "sending", "verification",
    "scheduling", "scheduled", "dms sent", "next outreach", "batch of", "contact info",
)
# "1. Daycares in Boston, MA" / "Step 9: Schedule Follow-ups" — numbered plan headers.
_PLAN_HEADER = re.compile(r"^(?:\d+[.)]\s|step\s*\d+\b)", re.IGNORECASE)
# "Auto Repair Shops in Worcester, MA" — a category-in-city header, not a business.
_CATEGORY_IN_CITY = re.compile(r"\b(?:in|for)\s+[A-Z][A-Za-z .'-]+,\s*[A-Z]{2}$")
# A search query the agent ran, quoted in the output: "cafes Fitchburg MA" / "hair salons Quincy MA".
_SEARCH_QUERY_SHAPE = re.compile(r"^[a-z][a-z /&'-]*\s+[A-Z][A-Za-z .'-]*\s+[A-Z]{2}$")
# A name that opens with "City, ST" is a section header: "Woburn, MA: Dry Cleaners".
_CITY_LED = re.compile(r"^[A-Za-z .'-]+,\s*[A-Z]{2}\b")

# A bold/quoted span opening with one of these is narration, not a name.
_NOISE_PREFIX = (
    "checked", "searched", "search", "found", "prospected", "identified", "created", "logged",
    "sent", "queued", "added", "updated", "completed", "scheduled", "verified", "confirmed",
    "unable", "no ", "all ", "total", "i ", "this ", "the crm", "an ", "for ", "attempted",
)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _clean_name(raw: str) -> str:
    n = raw.strip().strip("*`").strip()
    n = n.strip("\"“”'").strip()
    n = n.strip(" .,:;-–—").strip()
    n = re.sub(r"\s+", " ", n)
    # drop a trailing "(City, ST)" the name was quoted with
    n = _CITY_INLINE.sub("", n).strip(" .,:;-").strip()
    return n


def _is_business(name: str) -> bool:
    n = _clean_name(name)
    if len(n) < 3 or len(n) > 70:
        return False
    low = n.lower()
    if low in _NOISE_EXACT or _norm(n) in {_norm(x) for x in _NOISE_EXACT}:
        return False
    if low.startswith(_NOISE_PREFIX):
        return False
    if any(word in low for word in _NOISE_SUBSTR):
        return False
    if _SEARCH_QUERY_SHAPE.match(n) or _CITY_LED.match(n):
        return False
    if _PLAN_HEADER.match(n) or _CATEGORY_IN_CITY.search(n):
        return False
    if n.startswith(("http", "`", "@", "#")) or "@" in n:
        return False
    # bare city/state, or a "City, ST - category" header
    if re.fullmatch(r"[A-Za-z .'-]+,\s*[A-Z]{2}", n) or re.search(r",\s*[A-Z]{2}\s*[-–—]", n):
        return False
    if not re.search(r"[A-Za-z]", n) or not re.search(r"[A-Z]", n):
        return False
    # a full sentence is narration, not a business name
    if len(n.split()) > 9 or n.endswith((".", "!", "?")) and len(n.split()) > 5:
        return False
    return True


def _category_for(name: str, context_cat: str) -> str:
    if context_cat:
        return context_cat
    low = name.lower()
    for hint, cat in _CAT_HINTS:
        if hint in low:
            return cat
    return ""


def _titlecase_cat(raw: str) -> str:
    cat = re.sub(r"\s+", " ", raw.strip().strip(":-–— ")).strip()
    if not cat or len(cat) > 40:
        return ""
    low = cat.lower()
    for hint, mapped in _CAT_HINTS:
        if hint in low:
            return mapped
    return cat.title()


def _status_from(line: str) -> str:
    low = line.lower()
    m = re.search(r"status:?\s*`?(" + _STATUS_WORD + r")`?", low)
    if m:
        return STATUS_ALIAS.get(m.group(1), m.group(1))
    if re.search(r"\b(closed|signed|paid|won the deal)\b", low):
        return "closed"
    if re.search(r"\b(no[_ ]interest|not interested|unsubscribe|remove me)\b", low):
        return "no_interest"
    if re.search(r"\b(replied|responded|reply received)\b", low):
        return "replied"
    if re.search(r"\bfollow(ed)?[- ]up\b", low):
        return "followed_up"
    if re.search(r"(sent|send|sending)\s+(an?\s+)?(personalized\s+)?e-?mail|emailed|email was sent|status.{0,12}email", low):
        return "email_sent"
    if re.search(r"(instagram|ig)\s*dm|dm\s*(was\s*)?(sent|queued)|queued an instagram", low):
        return "dm_queued"
    if re.search(r"call[_ ]queue|queued for a call|added to the call|phone[- ]only|only found (a )?phone", low):
        return "call_queued"
    return "found"


def _contacts_from(text: str) -> tuple[str, str, str]:
    email = _EMAIL.search(text)
    # strip emails before hunting handles so "x@gmail.com" can't yield "@gmail"
    without_email = _EMAIL.sub(" ", text)
    handle = _HANDLE.search(without_email)
    phone = _PHONE.search(without_email)
    return (email.group(0) if email else "",
            handle.group(0).rstrip("._") if handle else "",
            phone.group(0) if phone else "")


def _channel_for(status: str, email: str, handle: str, phone: str) -> str:
    """The channel to work this lead on — the contact actually on file decides it, since the
    agent's status sometimes names a channel whose contact never made it into the output."""
    if status == "email_sent" and email:
        return "email"
    if status == "dm_queued" and handle:
        return "instagram"
    if status == "call_queued" and phone:
        return "phone"
    if email:
        return "email"
    if handle:
        return "instagram"
    if phone:
        return "phone"
    return {"email_sent": "email", "dm_queued": "instagram", "call_queued": "phone"}.get(status, "")


class Leads:
    """Accumulates one merged record per business across every run it appears in."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def augment(self, key: str, *, email="", handle="", phone="", status="found") -> None:
        """Attach contacts found on a continuation line to the lead named just above it."""
        row = self.rows.get(key)
        if row is None:
            return
        for field, value in (("email", email), ("instagram", handle), ("phone", phone)):
            if value and not row[field]:
                row[field] = value
        if STATUS_RANK.get(status, 0) > STATUS_RANK.get(row["status"], 0):
            row["status"] = status

    def add(self, name, *, city="", category="", email="", handle="", phone="",
            status="found", task_id="", run_date="", source_rank=0) -> str:
        """Merge one sighting into the lead list. Returns the merged key, or "" if rejected."""
        if not _is_business(name):
            return ""
        name = _clean_name(name)
        key = _norm(name)
        row = self.rows.get(key)
        if row is None:
            row = self.rows[key] = {
                "business": name, "type": "", "city": "", "email": "", "instagram": "",
                "phone": "", "status": "found", "first_seen": "", "last_seen": "",
                "tasks": [], "rank": -1,
            }
        # a higher-fidelity source (a pasted CRM table) may correct the display name
        if source_rank > row["rank"]:
            row["business"], row["rank"] = name, source_rank
        for field, value in (("type", _category_for(name, category)), ("city", city),
                             ("email", email), ("instagram", handle), ("phone", phone)):
            if value and not row[field]:
                row[field] = value
        if STATUS_RANK.get(status, 0) > STATUS_RANK.get(row["status"], 0):
            row["status"] = status
        if run_date:
            if not row["first_seen"] or run_date < row["first_seen"]:
                row["first_seen"] = run_date
            if not row["last_seen"] or run_date > row["last_seen"]:
                row["last_seen"] = run_date
        if task_id and task_id not in row["tasks"]:
            row["tasks"].append(task_id)
        return key


def _parse_table_rows(body: str, leads: Leads, task_id: str, run_date: str) -> int:
    """A CRM table pasted straight into the output — the highest-fidelity shape."""
    hits = 0
    for line in body.splitlines():
        m = _TABLE_ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group("cells").split("|")]
        if len(cells) < 6 or set("".join(cells)) <= {"-", ":", " "}:
            continue
        if not re.fullmatch(_STATUS_WORD, cells[5], re.IGNORECASE):
            continue
        business, ctype, city, contact = cells[0], cells[1], cells[2], cells[3]
        email, handle, phone = _contacts_from(contact)
        status = STATUS_ALIAS.get(cells[5].lower(), cells[5].lower())
        row_date = cells[6] if len(cells) > 6 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[6]) else run_date
        if leads.add(business, city=city, category=_titlecase_cat(ctype), email=email,
                     handle=handle, phone=phone, status=status, task_id=task_id,
                     run_date=row_date, source_rank=3):
            hits += 1
    return hits


def _parse_status_lines(body: str, leads: Leads, city_map: dict, task_id: str, run_date: str) -> int:
    """**Business**: ... Status: `email_sent`."""
    hits = 0
    for m in _FMT_STATUS.finditer(body):
        name, detail, status = m.group(1), m.group(2), m.group(3).lower()
        email, handle, phone = _contacts_from(detail)
        if leads.add(name, city=city_map.get(_norm(_clean_name(name)), ""), email=email,
                     handle=handle, phone=phone, status=STATUS_ALIAS.get(status, status),
                     task_id=task_id, run_date=run_date, source_rank=2):
            hits += 1
    return hits


def _parse_lines(body: str, leads: Leads, city_map: dict, task_id: str, run_date: str) -> int:
    """Inline prose and narrative bullets, carrying city/category down from the last header."""
    hits = 0
    city = category = last_key = ""
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        # -- context headers: set the city/category following lines inherit
        header = _HDR_CITY_CAT.search(line) or _HDR_CITY_PAREN.search(line)
        if header:
            city, category = header.group(1).strip(), _titlecase_cat(header.group(2))
        elif len(_SEARCH_QUOTED.findall(line)) + len(_SEARCH_IN.findall(line)) > 1:
            city = category = ""  # ambiguous: several queries on one line
        else:
            m = _SEARCH_IN.search(line)
            if m:
                category, city = _titlecase_cat(m.group(1)), m.group(2).strip()
            else:
                m = _SEARCH_QUOTED.search(line)
                if m:
                    category = _titlecase_cat(m.group(1))
                    city = f"{m.group(2).strip()}, {m.group(3)}"
        # a header line carries no lead of its own
        if header and not (_QUOTED.search(line.replace(header.group(0), "")) or _EMAIL.search(line)):
            continue

        email, handle, phone = _contacts_from(line)
        status = _status_from(line)
        line_city = city
        inline_city = _CITY_INLINE.search(line)
        if inline_city:
            line_city = inline_city.group(1).strip()

        candidates = []
        bullet = _BULLET_NAME_CITY.match(line)
        if bullet:
            candidates.append((bullet.group(1), bullet.group(2).strip()))
        candidates += [(q, "") for q in _QUOTED.findall(line)]
        candidates += [(b, "") for b in _BOLD.findall(line)]

        # Keep only real businesses, deduped — a rejected span (the search query the agent ran,
        # a section label) must not make a genuinely single-lead line look ambiguous.
        names, seen_on_line = [], set()
        for name, name_city in candidates:
            key = _norm(_clean_name(name))
            if key in seen_on_line or not _is_business(name):
                continue
            seen_on_line.add(key)
            names.append((name, name_city, key))

        if not names:
            # an indented continuation line ("*  **Contact Lookup**: found `@handle`") carries
            # contact details for the lead named on the line above
            if last_key and (email or handle or phone) and line[:1].isspace():
                leads.augment(last_key, email=email, handle=handle, phone=phone, status=status)
            elif last_key and status != "found" and line[:1].isspace():
                leads.augment(last_key, status=status)
            continue

        solo = len(names) == 1
        for name, name_city, key in names:
            use_city = name_city or city_map.get(key, "") or line_city
            merged = leads.add(name, city=use_city, category=category,
                               email=email if solo else "", handle=handle if solo else "",
                               phone=phone if solo else "",
                               status=status if solo else ("found" if status in ("email_sent", "dm_queued") else status),
                               task_id=task_id, run_date=run_date, source_rank=1)
            if merged:
                hits += 1
                last_key = merged if solo else ""
    return hits


def parse_task(text: str, leads: Leads) -> int:
    if not (_AGENT.search(text) or _POD.search(text)):
        return 0
    idx = text.find("## Agent Output")
    if idx == -1:
        return 0
    body = text[idx + len("## Agent Output"):]
    if len(body.strip()) < 40:
        return 0

    tid = _TASK_ID.search(text)
    task_id = tid.group(1).strip() if tid else ""
    created = _CREATED.search(text)
    run_date = (f"{created.group(1)[:4]}-{created.group(1)[4:6]}-{created.group(1)[6:8]}"
                if created else "")

    # "Business Name (City, ST)" bullets name the city for lines that mention the business later
    city_map = {}
    for m in _BULLET_NAME_CITY.finditer(body):
        name = _clean_name(m.group(1))
        if _is_business(name):
            city_map[_norm(name)] = m.group(2).strip()

    hits = _parse_table_rows(body, leads, task_id, run_date)
    hits += _parse_status_lines(body, leads, city_map, task_id, run_date)
    hits += _parse_lines(body, leads, city_map, task_id, run_date)
    return hits


def collect() -> tuple[Leads, dict]:
    leads = Leads()
    stats = {"files": 0, "outreach": 0, "with_output": 0, "with_leads": 0}
    files = sorted((p for d in TASK_DIRS if d.exists() for p in d.glob("*.md")),
                   key=lambda p: p.name)  # chronological: AUTO-<timestamp> sorts by run
    for path in files:
        stats["files"] += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not (_AGENT.search(text) or _POD.search(text)):
            continue
        stats["outreach"] += 1
        if "## Agent Output" in text and len(text.split("## Agent Output", 1)[1].strip()) >= 40:
            stats["with_output"] += 1
        if parse_task(text, leads):
            stats["with_leads"] += 1
    return leads, stats


def _record(row: dict) -> dict:
    channel = _channel_for(row["status"], row["email"], row["instagram"], row["phone"])
    return {
        "Business": row["business"],
        "Type": row["type"],
        "City": row["city"],
        "Email": row["email"],
        "Instagram": row["instagram"],
        "Phone": row["phone"],
        "Channel": channel,
        "Status": row["status"],
        "First Seen": row["first_seen"],
        "Last Seen": row["last_seen"],
        "Runs": str(len(row["tasks"])),
        "Source Tasks": ", ".join(row["tasks"][:3]) + ("…" if len(row["tasks"]) > 3 else ""),
    }


def _summary(records: list[dict], stats: dict) -> list[str]:
    by_status = Counter(r["Status"] for r in records)
    by_city = Counter(r["City"] for r in records if r["City"])
    by_type = Counter(r["Type"] for r in records if r["Type"])
    reachable = sum(1 for r in records if r["Email"] or r["Instagram"] or r["Phone"])
    lines = [
        f"- **{len(records)} leads** recovered from {stats['with_leads']} lead-bearing runs "
        f"({stats['outreach']} outreach task files scanned, {stats['with_output']} with agent output)",
        f"- **Reachable now:** {reachable} have a contact on file — "
        f"{sum(1 for r in records if r['Email'])} email, "
        f"{sum(1 for r in records if r['Instagram'])} Instagram, "
        f"{sum(1 for r in records if r['Phone'])} phone",
        "- **By status:** " + ", ".join(f"{s} {n}" for s, n in by_status.most_common()),
        "- **Top cities:** " + ", ".join(f"{c} ({n})" for c, n in by_city.most_common(8)),
        "- **Top categories:** " + ", ".join(f"{t} ({n})" for t, n in by_type.most_common(8)),
    ]
    return lines


def render_markdown(records: list[dict], stats: dict) -> str:
    out = [
        "# Easy Simple Sites — Website Leads",
        "",
        f"Imported from agent task history on {date.today()} by `scripts/import_website_leads.py`.",
        "Source: `workspace/tasks/{done,failed,todo}` — every prospect the outreach pod found,",
        "merged across runs. Regenerate with `python scripts/import_website_leads.py --write`.",
        "",
        "This file is a read-only view of history. The pod's live CRM is `vault/outreach/crm.md`.",
        "",
        "## Summary",
        "",
        *_summary(records, stats),
        "",
        "## Leads",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "|".join("---" for _ in COLUMNS) + "|",
    ]
    for r in records:
        out.append("| " + " | ".join((r[c] or "—").replace("|", "/") for c in COLUMNS) + " |")
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the lead files (default: dry run)")
    args = ap.parse_args()

    leads, stats = collect()
    records = [_record(r) for r in leads.rows.values()]
    # reachable leads first, then most-recently-seen — the order you would work the list in
    records.sort(key=lambda r: (not (r["Email"] or r["Instagram"] or r["Phone"]),
                                -STATUS_RANK.get(r["Status"], 0), r["City"], r["Business"]))

    for line in _summary(records, stats):
        print(line.replace("**", ""))

    if not args.write:
        print(f"\nDry run — nothing written. Re-run with --write to create {OUT_MD.name} "
              f"and {OUT_CSV.name}.")
        return

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(render_markdown(records, stats), encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    print(f"\nWrote {len(records)} leads -> {OUT_MD.relative_to(ROOT)}, {OUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
