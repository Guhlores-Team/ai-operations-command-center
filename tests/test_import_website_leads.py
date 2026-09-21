"""Test suite for the website-lead importer's parsers.

Each fixture below is a trimmed copy of a real outreach_worker "## Agent Output" section, so the
tests pin the four shapes the agent actually produced across its run history — not invented ones.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from import_website_leads import Leads, _channel_for, _is_business, parse_task  # noqa: E402


def _task(output: str, task_id: str = "AUTO-1", created: str = "20260527") -> str:
    return (f"---\ntask_id: {task_id}\nassigned_agent: outreach_worker\n"
            f"pod: local_outreach_pod\ncreated_at: {created}\n---\n\n"
            f"Do the outreach run.\n\n## Agent Output\n\n{output}\n")


def _parse(output: str, **kw) -> dict:
    leads = Leads()
    parse_task(_task(output, **kw), leads)
    return {r["business"]: r for r in leads.rows.values()}


# --- the four output shapes ----------------------------------------------------------------

def test_pasted_crm_table_is_parsed_with_full_detail():
    rows = _parse("""**CRM Updates:**
| Business | Type | City, MA | contact | channel | status | YYYY-MM-DD | notes |
|---|---|---|---|---|---|---|---|
| Eko's Bar & Grill Restaurant | Restaurant | Lowell, MA | @ekosbarandgrill | instagram | dm_queued | 2026-05-26 | |
| Gummybears Daycare Center | Daycare | Medford, MA | renee@gummybearsdaycare.com | email | email_sent | 2026-05-26 | |
""")
    eko = rows["Eko's Bar & Grill Restaurant"]
    assert eko["instagram"] == "@ekosbarandgrill"
    assert (eko["city"], eko["type"], eko["status"]) == ("Lowell, MA", "Restaurant", "dm_queued")
    assert eko["first_seen"] == "2026-05-26"  # the row's own date, not the task's
    assert rows["Gummybears Daycare Center"]["email"] == "renee@gummybearsdaycare.com"


def test_status_marker_lines_recover_contact_and_channel():
    rows = _parse("""3.  **Attempted Contact & Updated CRM:**
    *   **Tiana's Nail Spa**: Found Instagram handle `@tianasnailspa`. Sent Instagram DM. Status: `dm_queued`.
    *   **Brockton Plumbing & Heating Supply**: Only found phone number `(508) 587-5700`. Status: `call_queued`.
""")
    assert rows["Tiana's Nail Spa"]["instagram"] == "@tianasnailspa"
    assert rows["Brockton Plumbing & Heating Supply"]["phone"] == "(508) 587-5700"
    assert rows["Brockton Plumbing & Heating Supply"]["status"] == "call_queued"


def test_inline_prose_inherits_city_and_category_from_its_header():
    rows = _parse("""*   **Springfield, MA - dog groomers:** Found 2 prospects.
        *   "Lucky Dog Day Spa": Sent an email to `luckydogyukon@gmail.com` and appended the prospect to the CRM with status `email_sent`.
        *   "Elite Pet Groomers": Queued an Instagram DM to `@elitezpetgrooming` with status `dm_queued`.
""")
    lucky = rows["Lucky Dog Day Spa"]
    assert (lucky["email"], lucky["status"]) == ("luckydogyukon@gmail.com", "email_sent")
    assert (lucky["city"], lucky["type"]) == ("Springfield, MA", "Pet Grooming")
    assert rows["Elite Pet Groomers"]["instagram"] == "@elitezpetgrooming"


def test_narrative_line_attaches_contact_despite_the_quoted_search_query():
    # The search query is quoted on the same line as the business — it must not make the line
    # look ambiguous, or the handle is lost.
    rows = _parse('- Searched for "food trucks Somerville MA", found "Stack my Mac food truck" '
                  'without a website, and sent an Instagram DM to `@stackdtruck`.\n')
    assert '"food trucks Somerville MA"' not in rows and "food trucks Somerville MA" not in rows
    truck = rows["Stack my Mac food truck"]
    assert (truck["instagram"], truck["status"], truck["city"]) == (
        "@stackdtruck", "dm_queued", "Somerville, MA")


def test_indented_continuation_line_enriches_the_lead_above_it():
    rows = _parse("""3.  **Prospecting:**
    *   **"food trucks Cambridge MA"**: Found 1 prospect with no website: "Stack my Mac food truck".
        *   **Contact Lookup**: `web_research` found the Instagram handle `@stackdtruck`.
""")
    assert rows["Stack my Mac food truck"]["instagram"] == "@stackdtruck"
    assert "Contact Lookup" not in rows


# --- merging across runs -------------------------------------------------------------------

def test_lead_merges_across_runs_keeping_best_status_and_both_channels():
    leads = Leads()
    parse_task(_task('- Found "Joe\'s Garage" without a website. Only found phone number '
                     '`(508) 111-2222`. Status: `call_queued`.', "AUTO-1", "20260525"), leads)
    parse_task(_task('- Followed up with "Joe\'s Garage" by email at `joe@garage.com`. '
                     'Status: `followed_up`.', "AUTO-2", "20260528"), leads)
    row = next(iter(leads.rows.values()))
    assert row["phone"] == "(508) 111-2222" and row["email"] == "joe@garage.com"
    assert row["status"] == "followed_up"          # most advanced outcome wins
    assert (row["first_seen"], row["last_seen"]) == ("2026-05-25", "2026-05-28")
    assert row["tasks"] == ["AUTO-1", "AUTO-2"]


def test_a_weaker_later_status_does_not_overwrite_a_stronger_one():
    leads = Leads()
    parse_task(_task('- **Joe\'s Garage**: Sent email. Status: `email_sent`.', "AUTO-1"), leads)
    parse_task(_task('- Found "Joe\'s Garage" again. Status: `call_queued`.', "AUTO-2"), leads)
    assert next(iter(leads.rows.values()))["status"] == "email_sent"


def test_only_outreach_tasks_are_read():
    leads = Leads()
    text = ("---\ntask_id: X\nassigned_agent: social_media_worker\npod: social_pod\n---\n\n"
            "## Agent Output\n\n- Found \"Some Business\" without a website. Status: `call_queued`.\n")
    assert parse_task(text, leads) == 0
    assert not leads.rows


# --- noise rejection -----------------------------------------------------------------------

@pytest.mark.parametrize("junk", [
    "food trucks Cambridge MA",            # a search query the agent ran
    '"hair salons Quincy MA"',             # ... still wrapped in its quotes
    "Woburn, MA: Dry Cleaners",            # a city-led section header
    "Andover, MA",                         # a bare city
    "1. Daycares in Boston, MA",           # a numbered plan header
    "Step 9: Schedule Follow-ups",
    "Auto Repair Shops in Worcester, MA",  # a category-in-city header
    "CRM Update", "Next Outreach Scheduling", "Contact Lookup", "Prospect Research",
    "Instagram DMs Sent", "Patterns observed", "STOP", "read_inbox", "Summary of actions",
    "Searched for restaurants", "no new prospects found",
])
def test_narration_is_not_mistaken_for_a_business(junk):
    assert not _is_business(junk)


@pytest.mark.parametrize("name", [
    "Tiana's Nail Spa", "4 Seasons Nails & Spa Taunton", "Eko's Bar & Grill Restaurant",
    "MD's Cleaning Service, LLC", "A-1 Car Wash touchless 24 HOUR", "CT NAILS",
    "J & J Nail Salon", "1636 North", "Stone and Oak Construction, LLC",
])
def test_real_business_names_survive_the_filters(name):
    assert _is_business(name)


def test_handles_do_not_keep_the_sentences_trailing_period():
    rows = _parse('*   **Essence Nail Lounge** (Worcester, MA - nail salons): '
                  'Instagram DM queued to @essencenaillounge.\n')
    assert rows["Essence Nail Lounge"]["instagram"] == "@essencenaillounge"


def test_an_email_address_is_not_read_as_an_instagram_handle():
    rows = _parse('- **Grooming Room LLC**: Sent an email to `info@groomingroom.net`. '
                  'Status: `email_sent`.\n')
    row = rows["Grooming Room LLC"]
    assert row["email"] == "info@groomingroom.net" and row["instagram"] == ""


# --- channel selection ---------------------------------------------------------------------

@pytest.mark.parametrize("status,email,handle,phone,expected", [
    ("email_sent", "a@b.com", "", "", "email"),
    ("dm_queued", "", "@x", "", "instagram"),
    ("call_queued", "", "", "(508) 111-2222", "phone"),
    # the agent said it emailed but only an Instagram handle survived into the output —
    # work the lead where a contact actually exists
    ("email_sent", "", "@ironinktattoos", "", "instagram"),
    ("dm_queued", "a@b.com", "", "", "email"),
    # nothing recovered at all: fall back to what the status implies
    ("call_queued", "", "", "", "phone"),
    ("found", "", "", "", ""),
])
def test_channel_follows_the_contact_on_file(status, email, handle, phone, expected):
    assert _channel_for(status, email, handle, phone) == expected
