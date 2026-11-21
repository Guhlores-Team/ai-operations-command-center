"""Source website-outreach candidates from the City of Boston Certified Business Directory.

The directory is public open data (PDDL) and is the cleanest lead source found so far: every
row is a currently certified business with a named contact, a published email and a website
field. A blank website field plus a published email is the starting signal — it is NOT proof
the business has no site, so each candidate still needs the manual check in
workspace/outreach/PLAYBOOK.md before a demo is built.

Skips anyone already in the pipeline or on the suppression list, so a business is never
researched or contacted twice.

Usage:
    python scripts/find_directory_leads.py            # dry-run: print candidates
    python scripts/find_directory_leads.py --write    # write workspace/outreach/candidates.csv
"""
import argparse
import csv
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTREACH = ROOT / "workspace" / "outreach"
PIPELINE = OUTREACH / "pipeline.csv"
SUPPRESSION = OUTREACH / "suppression.csv"
CANDIDATES = OUTREACH / "candidates.csv"

RESOURCE_ID = "3fc08ca2-9baf-4d77-b03a-aaed1cc936ed"
API = f"https://data.boston.gov/api/3/action/datastore_search?resource_id={RESOURCE_ID}&limit=5000"

_BLANK = {"", "n/a", "na", "none", "-", "null"}
# A free-mail address is the strongest hint that a business has no domain of its own.
_FREE_MAIL = ("gmail.", "yahoo.", "hotmail.", "aol.", "outlook.", "comcast.", "verizon.",
              "icloud.", "msn.", "live.", "me.com")

COLUMNS = ["Business name", "Category", "City", "Contact", "Email", "Phone", "Established",
           "Employees", "Certifications", "Services"]


def _blank(value) -> bool:
    return value is None or str(value).strip().lower() in _BLANK


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _known() -> tuple[set[str], set[str]]:
    """Business names and contact addresses already in the pipeline or suppressed."""
    names, contacts = set(), set()
    for path, name_col, contact_col in ((PIPELINE, "Business name", "Contact email"),
                                        (SUPPRESSION, "Business", "Contact")):
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                names.add(_norm(row.get(name_col, "")))
                contacts.add((row.get(contact_col) or "").strip().lower())
    return names - {""}, contacts - {""}


def fetch() -> list[dict]:
    with urllib.request.urlopen(API, timeout=60) as resp:
        return json.load(resp)["result"]["records"]


def candidates(records: list[dict]) -> list[dict]:
    names, contacts = _known()
    out = []
    for r in records:
        email = (r.get("email") or "").strip()
        if (r.get("state") or "").strip().upper() != "MA" or _blank(email) or not _blank(r.get("website")):
            continue
        if not any(host in email.lower() for host in _FREE_MAIL):
            continue
        if _norm(r.get("company_name", "")) in names or email.lower() in contacts:
            continue
        certs = ", ".join(c for c in (r.get("mbe_wbe_cert"), r.get("small_local_cert"), r.get("veteran_cert")) if c)
        out.append({
            "Business name": (r.get("company_name") or "").strip(),
            "Category": (r.get("cob_category_codes1") or "").strip(),
            "City": (r.get("city") or "").strip(),
            "Contact": (r.get("contact_title") or r.get("contact_name") or "").strip(),
            "Email": email,
            "Phone": (r.get("phone") or "").strip(),
            "Established": (r.get("date_business_established") or "").strip(),
            "Employees": (r.get("number_employees") or "").strip(),
            "Certifications": certs,
            "Services": (r.get("services_provided") or "").strip(),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write candidates.csv (default: dry run)")
    args = ap.parse_args()

    rows = candidates(fetch())
    print(f"{len(rows)} candidates (MA, published free-mail address, blank website field, not already known)")
    for r in rows[:15]:
        print(f"  {r['Business name']} | {r['Category'][:30]} | {r['City']} | {r['Email']}")
    if len(rows) > 15:
        print(f"  ... and {len(rows) - 15} more")

    if not args.write:
        print("\nDry run - nothing written. Re-run with --write to create candidates.csv.")
        return
    with CANDIDATES.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} candidates -> {CANDIDATES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
