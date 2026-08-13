#!/usr/bin/env python
"""Generate the synthetic datasets (CLAUDE.md Section 20).

    npm run demo-data

Everything here is invented. No real person, agency, or booking appears in any
output file. The generator is seeded, so it produces the same data on every
machine — which is what makes screenshots, tests, and demos reproducible.

The datasets carry deliberate, realistic signal so the Dashboard and Report
Generator have something true to find: a cancellation-rate rise in the last
fortnight, a delay cluster on one route, and one agent whose ticket volume
spikes. These are planted patterns in fake data, not claims about the world.
"""

from __future__ import annotations

import csv
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from aiops_config import generated_data_dir

# A fixed seed makes every run byte-identical.
SEED = 20260813
DAYS_OF_HISTORY = 90

AGENCIES = [
    ("AG-1001", "Meridian Travel Partners"),
    ("AG-1002", "Skyline Holidays"),
    ("AG-1003", "Kaveri Tours & Travel"),
    ("AG-1004", "Northgate Business Travel"),
    ("AG-1005", "Blue Lotus Voyages"),
    ("AG-1006", "Deccan Trails"),
    ("AG-1007", "Harbour Line Travel"),
    ("AG-1008", "Cedar & Co. Corporate Travel"),
]

ROUTES = [
    "DEL-BOM",
    "DEL-BLR",
    "BOM-GOI",
    "DEL-DXB",
    "BLR-MAA",
    "DEL-CCU",
    "BOM-DEL",
    "HYD-DEL",
    "DEL-SIN",
    "BLR-BOM",
]
AIRLINES = ["IndiGo", "Air India", "Vistara", "SpiceJet", "Emirates"]
HOTELS = [
    "Grand Meridian, Mumbai",
    "The Residency, Bengaluru",
    "Lakeview Suites, Udaipur",
    "Palm Court, Goa",
    "Skyline Inn, Delhi",
    "Harbour Rock, Kochi",
]
HOLIDAY_PACKAGES = [
    "Kerala Backwaters 5N",
    "Rajasthan Heritage 7N",
    "Bali Escape 6N",
    "Dubai City Break 4N",
    "Himalayan Trek 8N",
]

FIRST_NAMES = [
    "Aarav",
    "Priya",
    "Rohan",
    "Meera",
    "Kabir",
    "Ananya",
    "Vikram",
    "Divya",
    "Arjun",
    "Nisha",
    "Farhan",
    "Ishita",
    "Rahul",
    "Sneha",
    "Karan",
    "Tara",
]
LAST_NAMES = [
    "Sharma",
    "Iyer",
    "Bose",
    "Nair",
    "Reddy",
    "Kapoor",
    "Menon",
    "Chandra",
    "Verma",
    "Pillai",
    "Joshi",
    "Rao",
]

TEAM = [
    "ops.anita@example-travel.test",
    "ops.deepak@example-travel.test",
    "ops.sana@example-travel.test",
    "ops.vikas@example-travel.test",
]

EMAIL_CATEGORIES = [
    "Agent Partner",
    "Booking Ops",
    "Vendor/Hotel",
    "Finance",
    "Internal",
    "Urgent",
]


def _traveller(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _write(filename: str, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    """Write one dataset and return its path."""
    directory = generated_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {filename:<32} {len(rows):>5} rows")
    return path


# ---------------------------------------------------------------- datasets


def generate_bookings(rng: random.Random, now: datetime) -> list[dict[str, Any]]:
    """travel_bookings.csv — the flagship project's core dataset."""
    rows: list[dict[str, Any]] = []
    # A planted delay cluster: this route on this date is the incident the
    # Travel Operations demo walks through.
    incident_route = "DEL-BOM"
    incident_date = (now - timedelta(days=3)).date()

    for index in range(1, 901):
        created = now - timedelta(days=rng.randint(0, DAYS_OF_HISTORY), hours=rng.randint(0, 23))
        agent_id, agent_name = rng.choice(AGENCIES)
        booking_type = rng.choices(["flight", "hotel", "holiday"], weights=[60, 28, 12])[0]

        route: str | None = None
        supplier: str | None = None
        departure: datetime | None = None

        if booking_type == "flight":
            route = rng.choice(ROUTES)
            supplier = rng.choice(AIRLINES)
            departure = created + timedelta(days=rng.randint(1, 45))
            value = round(rng.uniform(4_500, 62_000), 2)
        elif booking_type == "hotel":
            supplier = rng.choice(HOTELS)
            departure = created + timedelta(days=rng.randint(2, 60))
            value = round(rng.uniform(6_000, 95_000), 2)
        else:
            supplier = rng.choice(HOLIDAY_PACKAGES)
            departure = created + timedelta(days=rng.randint(10, 90))
            value = round(rng.uniform(45_000, 380_000), 2)

        # Cancellation rate rises over the last 14 days — the trend the
        # Dashboard should surface as an observation.
        recent = (now - created).days <= 14
        status = rng.choices(
            ["confirmed", "pending", "delayed", "cancelled", "refunded"],
            weights=[70, 8, 6, 13, 3] if recent else [78, 9, 5, 6, 2],
        )[0]

        # Force the planted incident.
        if route == incident_route and departure is not None and departure.date() == incident_date:
            status = "delayed"

        rows.append(
            {
                "id": f"BK-{index:05d}",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "traveller_name": _traveller(rng),
                "booking_type": booking_type,
                "route": route or "",
                "supplier": supplier or "",
                "departure_at": departure.isoformat() if departure else "",
                "status": status,
                "value_inr": value,
                "created_at": created.isoformat(),
            }
        )

    rows.sort(key=lambda row: row["created_at"])
    return rows


def generate_support_tickets(rng: random.Random, now: datetime) -> list[dict[str, Any]]:
    """support_tickets.csv — agent-raised issues."""
    categories = [
        "Booking change",
        "Refund request",
        "Flight delay",
        "Hotel complaint",
        "Payment issue",
        "Visa documentation",
        "Cancellation",
    ]
    rows: list[dict[str, Any]] = []

    for index in range(1, 421):
        opened = now - timedelta(days=rng.randint(0, DAYS_OF_HISTORY), hours=rng.randint(0, 23))
        # One agency's volume spikes — a planted pattern for the agent/partner view.
        agent_id, agent_name = AGENCIES[2] if rng.random() < 0.22 else rng.choice(AGENCIES)
        priority = rng.choices(["low", "medium", "high", "urgent"], weights=[30, 40, 22, 8])[0]
        status = rng.choices(
            ["open", "in_progress", "resolved", "closed"], weights=[18, 22, 35, 25]
        )[0]
        resolution_hours = (
            round(rng.uniform(0.5, 96.0), 1) if status in ("resolved", "closed") else ""
        )

        rows.append(
            {
                "id": f"TK-{index:05d}",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "booking_id": f"BK-{rng.randint(1, 900):05d}",
                "category": rng.choice(categories),
                "priority": priority,
                "status": status,
                "subject": f"{rng.choice(categories)} for booking",
                "opened_at": opened.isoformat(),
                "resolution_hours": resolution_hours,
                "assigned_to": rng.choice(TEAM),
            }
        )

    rows.sort(key=lambda row: row["opened_at"])
    return rows


def generate_sales_data(rng: random.Random, now: datetime) -> list[dict[str, Any]]:
    """sales_data.csv — daily booking value per agency."""
    rows: list[dict[str, Any]] = []
    for day_offset in range(DAYS_OF_HISTORY, -1, -1):
        day = (now - timedelta(days=day_offset)).date()
        # Weekends are quieter — a real seasonal shape rather than flat noise.
        weekend = day.weekday() >= 5
        for agent_id, agent_name in AGENCIES:
            base = rng.uniform(180_000, 720_000) * (0.55 if weekend else 1.0)
            rows.append(
                {
                    "date": day.isoformat(),
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "bookings_count": max(0, int(rng.gauss(14 if not weekend else 7, 4))),
                    "gross_value_inr": round(base, 2),
                    "commission_inr": round(base * rng.uniform(0.04, 0.09), 2),
                }
            )
    return rows


def generate_employee_tasks(rng: random.Random, now: datetime) -> list[dict[str, Any]]:
    """employee_tasks.csv — the Project Tracker's dataset."""
    projects = [
        "Agent onboarding automation",
        "Refund SLA improvement",
        "Hotel supplier audit",
        "Delay-alert rollout",
        "Q3 ops reporting",
    ]
    titles = [
        "Draft SOP",
        "Review supplier contract",
        "Build tracker",
        "Run data cleanup",
        "Prepare weekly report",
        "Escalate open tickets",
        "Update agent onboarding pack",
        "Verify refund backlog",
    ]
    rows: list[dict[str, Any]] = []

    for index in range(1, 161):
        created = now - timedelta(days=rng.randint(0, 60))
        due = created + timedelta(days=rng.randint(2, 30))
        status = rng.choices(["todo", "in_progress", "blocked", "done"], weights=[28, 32, 12, 28])[
            0
        ]
        rows.append(
            {
                "id": f"TS-{index:04d}",
                "project": rng.choice(projects),
                "title": rng.choice(titles),
                "owner": rng.choice(TEAM),
                "priority": rng.choice(["low", "medium", "high"]),
                "status": status,
                "created_at": created.isoformat(),
                "due_at": due.isoformat(),
                "is_overdue": str(status != "done" and due < now).lower(),
                "blocker": "Awaiting supplier response" if status == "blocked" else "",
            }
        )
    return rows


def generate_inbox_emails(rng: random.Random, now: datetime) -> list[dict[str, Any]]:
    """operations_inbox_emails.csv — Project 8's dataset."""
    templates = [
        (
            "Booking Ops",
            "Change request for {bk}",
            "Our client needs to move {bk} to the following week. Please advise on "
            "fare difference and whether the current fare rules allow a change.",
        ),
        (
            "Urgent",
            "URGENT: flight delayed on {route}",
            "Passengers on {route} are reporting a long delay. Several of our "
            "clients are affected and are asking for rebooking options today.",
        ),
        (
            "Vendor/Hotel",
            "Room availability for {hotel}",
            "Confirming we still hold four rooms at {hotel} for the dates "
            "discussed. Please confirm the rate before end of day.",
        ),
        (
            "Finance",
            "Invoice query for {bk}",
            "The commission on invoice for {bk} does not match our records. "
            "Could you share the breakdown?",
        ),
        (
            "Agent Partner",
            "Onboarding questions",
            "We are setting up our team on the portal and have a few questions "
            "about agent seat limits and the approval process.",
        ),
        (
            "Internal",
            "Weekly ops summary",
            "Sharing this week's open incidents and the refund backlog position "
            "ahead of tomorrow's review.",
        ),
    ]
    rows: list[dict[str, Any]] = []

    for index in range(1, 181):
        category, subject_template, body_template = rng.choice(templates)
        agent_id, agent_name = rng.choice(AGENCIES)
        received = now - timedelta(
            days=rng.randint(0, 21), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
        )
        substitutions = {
            "bk": f"BK-{rng.randint(1, 900):05d}",
            "route": rng.choice(ROUTES),
            "hotel": rng.choice(HOTELS),
        }
        # A thread id shared by a few messages so thread summarisation has
        # something real to summarise.
        thread_id = f"TH-{(index // 3) + 1:04d}"
        has_reply = rng.random() < 0.55

        rows.append(
            {
                "id": f"EM-{index:05d}",
                "thread_id": thread_id,
                "sender": f"contact@{agent_name.lower().replace(' ', '').replace('.', '').replace('&', 'and')}.test",
                "recipient": "ops@example-travel.test",
                "subject": subject_template.format(**substitutions),
                "body": body_template.format(**substitutions),
                "received_at": received.isoformat(),
                "is_read": str(rng.random() < 0.6).lower(),
                "has_reply": str(has_reply).lower(),
                "labels": f"{category}|{agent_id}",
            }
        )

    rows.sort(key=lambda row: row["received_at"])
    return rows


def generate_calendar(rng: random.Random, now: datetime) -> list[dict[str, Any]]:
    """operations_calendar.csv — backs the mock CalendarProvider.

    Not in CLAUDE.md Section 20's original list; added because Section 3c
    requires a mock CalendarProvider and an adapter needs something to read.
    """
    meetings = [
        "Daily ops stand-up",
        "Agent escalation review",
        "Supplier call",
        "Refund backlog review",
        "Weekly ops review",
        "New agent onboarding",
    ]
    rows: list[dict[str, Any]] = []
    index = 0

    for day_offset in range(-14, 15):
        day = now + timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue
        for _ in range(rng.randint(1, 3)):
            index += 1
            start = day.replace(
                hour=rng.randint(9, 17),
                minute=rng.choice([0, 30]),
                second=0,
                microsecond=0,
            )
            rows.append(
                {
                    "id": f"EV-{index:04d}",
                    "title": rng.choice(meetings),
                    "starts_at": start.isoformat(),
                    "ends_at": (start + timedelta(minutes=rng.choice([30, 45, 60]))).isoformat(),
                    "attendees": "|".join(rng.sample(TEAM, rng.randint(2, 4))),
                    "location": rng.choice(["Ops room", "Video call", "Client office"]),
                    "notes": "",
                }
            )

    rows.sort(key=lambda row: row["starts_at"])
    return rows


def generate_metrics(rng: random.Random, now: datetime) -> list[dict[str, Any]]:
    """operations_metrics.csv — daily KPIs for the Dashboard."""
    rows: list[dict[str, Any]] = []
    for day_offset in range(DAYS_OF_HISTORY, -1, -1):
        day = (now - timedelta(days=day_offset)).date()
        recent = day_offset <= 14

        # The planted trend: cancellations climb over the last fortnight, so
        # trend detection has a genuine signal to find.
        cancellation_rate = round(rng.uniform(11.0, 14.5) if recent else rng.uniform(6.0, 9.0), 2)
        rows.append(
            {
                "date": day.isoformat(),
                "bookings_created": max(0, int(rng.gauss(96, 18))),
                "bookings_cancelled": max(0, int(rng.gauss(11 if recent else 6, 3))),
                "cancellation_rate_pct": cancellation_rate,
                "tickets_opened": max(0, int(rng.gauss(14, 5))),
                "tickets_resolved": max(0, int(rng.gauss(13, 5))),
                "avg_resolution_hours": round(rng.uniform(4.0, 28.0), 2),
                "on_time_departure_pct": round(rng.uniform(72.0, 94.0), 2),
                "gross_value_inr": round(rng.uniform(2_100_000, 4_800_000), 2),
            }
        )
    return rows


def main() -> None:
    rng = random.Random(SEED)
    now = datetime.now(UTC).replace(microsecond=0)

    print(f"Generating synthetic demo data (seed={SEED})")
    print(f"Output: {generated_data_dir()}\n")

    bookings = generate_bookings(rng, now)
    _write(
        "travel_bookings.csv",
        bookings,
        [
            "id",
            "agent_id",
            "agent_name",
            "traveller_name",
            "booking_type",
            "route",
            "supplier",
            "departure_at",
            "status",
            "value_inr",
            "created_at",
        ],
    )
    _write(
        "support_tickets.csv",
        generate_support_tickets(rng, now),
        [
            "id",
            "agent_id",
            "agent_name",
            "booking_id",
            "category",
            "priority",
            "status",
            "subject",
            "opened_at",
            "resolution_hours",
            "assigned_to",
        ],
    )
    _write(
        "sales_data.csv",
        generate_sales_data(rng, now),
        ["date", "agent_id", "agent_name", "bookings_count", "gross_value_inr", "commission_inr"],
    )
    _write(
        "employee_tasks.csv",
        generate_employee_tasks(rng, now),
        [
            "id",
            "project",
            "title",
            "owner",
            "priority",
            "status",
            "created_at",
            "due_at",
            "is_overdue",
            "blocker",
        ],
    )
    _write(
        "operations_inbox_emails.csv",
        generate_inbox_emails(rng, now),
        [
            "id",
            "thread_id",
            "sender",
            "recipient",
            "subject",
            "body",
            "received_at",
            "is_read",
            "has_reply",
            "labels",
        ],
    )
    _write(
        "operations_calendar.csv",
        generate_calendar(rng, now),
        ["id", "title", "starts_at", "ends_at", "attendees", "location", "notes"],
    )
    _write(
        "operations_metrics.csv",
        generate_metrics(rng, now),
        [
            "date",
            "bookings_created",
            "bookings_cancelled",
            "cancellation_rate_pct",
            "tickets_opened",
            "tickets_resolved",
            "avg_resolution_hours",
            "on_time_departure_pct",
            "gross_value_inr",
        ],
    )

    print("\nDone. All data is synthetic — no real people or bookings.")


if __name__ == "__main__":
    main()
