import json
from datetime import date, timedelta

from strands import tool

# Sample data for the demo. Replace with the real company list later without touching the tools.
ROLE_ALIASES:dict[str, str] = {
    "developer": "developer", "dev": "developer", "engineer": "developer", "software engineer": "developer",
    "qa": "qa", "tester": "qa", "qa engineer": "qa",
    "ba": "ba", "business analyst": "ba",
    "pm": "pm", "project manager": "pm", "product manager": "pm",
}

COMMON_ACCESS:list[str] = [
    "Company email and calendar",
    "Chat tool (Slack or Teams)",
    "HR portal (leave, payslips)",
    "VPN",
    "Timesheet tool",
]

ROLE_ACCESS:dict[str, list[str]] = {
    "developer": ["GitHub organisation", "Cloud sandbox account", "IDE licence", "CI/CD read access"],
    "qa": ["Test management tool", "Staging environment", "Bug tracker", "Test data folder"],
    "ba": ["Requirements wiki", "Bug tracker (read)", "Prototype tool", "Client meeting calendar"],
    "pm": ["Project board", "Budget and resourcing sheet", "Client contact list", "Reporting dashboard"],
}

# One focus task per role per week. It fills the {focus} slot in WEEKS below.
ROLE_FOCUS:dict[str, list[str]] = {
    "developer": [
        "Clone the main repo and run the app locally",
        "Pick up a small bug fix with your buddy",
        "Ship your first small change to staging",
        "Take a small story from start to finish",
    ],
    "qa": [
        "Run the existing test suite and read the test plan",
        "Write test cases for one existing feature",
        "Run a full test cycle on a small change",
        "Own testing for one story from start to finish",
    ],
    "ba": [
        "Read the product requirements and glossary",
        "Shadow a requirements workshop with the client",
        "Write acceptance criteria for one small story",
        "Own the requirements for one story from start to finish",
    ],
    "pm": [
        "Review the roadmap and current sprint board",
        "Shadow the weekly client status meeting",
        "Prepare one status report with your manager",
        "Run one sprint ceremony yourself",
    ],
}

# (week title, tasks by working day). Week 1 is light: reading and setup only.
WEEKS:list[tuple[str, list[str]]] = [
    ("Week 1: Settle in", [
        "Get your access set up (use the access checklist)",
        "Meet your manager and your buddy",
        "{focus}",
        "Read the security basics and the team handbook",
        "Meet the wider team and learn who to ask for what",
    ]),
    ("Week 2: Learn the work", [
        "Join the team's daily stand-up and planning",
        "Read the project docs and key decisions",
        "{focus}",
        "Learn the team's way of working and tools",
        "Check in with your manager",
    ]),
    ("Week 3: Start contributing", [
        "Pick your first small task with your buddy",
        "Work on your first task",
        "{focus}",
        "Ask for feedback on your work so far",
        "Check in with your manager",
    ]),
    ("Week 4: Work on your own", [
        "Pick a task and plan it yourself",
        "Work on your task",
        "{focus}",
        "Share what you learned with the team",
        "Check in with your manager",
    ]),
    ("Final days: Review", [
        "30-day review with your manager",
        "Write down your goals for the next 60 days",
    ]),
]


def normalise_role(role:str) -> str | None:
    return ROLE_ALIASES.get(role.strip().lower())


def make_access(role:str) -> dict:
    key = normalise_role(role)
    if not key:
        raise ValueError(f"unknown role '{role}'. Use one of: developer, qa, ba, pm.")
    return {"role": key, "access": COMMON_ACCESS + ROLE_ACCESS[key]}


def make_plan(role:str, start_date:str) -> dict:
    key = normalise_role(role)
    if not key:
        raise ValueError(f"unknown role '{role}'. Use one of: developer, qa, ba, pm.")
    try:
        start = date.fromisoformat(start_date.strip())
    except ValueError:
        raise ValueError(f"'{start_date}' is not a valid date. Use YYYY-MM-DD.")

    plan:list[dict] = []
    used_in_week:dict[int, int] = {}
    for offset in range(30):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5:  # shortcut: weekends only, public holidays are not skipped; add a holiday list when HR shares one
            continue
        week = offset // 7  # 0-3 are full weeks, 4 is the last two days
        n = used_in_week.get(week, 0)
        used_in_week[week] = n + 1
        title, tasks = WEEKS[week]
        task = tasks[min(n, len(tasks) - 1)]
        if week < 4:
            task = task.format(focus=ROLE_FOCUS[key][week])
        plan.append({"date": day.isoformat(), "day": day.strftime("%a"), "week": title, "task": task})

    return {"role": key, "start_date": start.isoformat(), "plan": plan}


@tool
def get_access_checklist(role:str) -> str:
    """List the tools and access a new joiner needs on their first day.

    Args:
        role: The job role, for example "developer", "qa", "ba" or "pm".
    """
    try:
        return json.dumps(make_access(role))
    except ValueError as e:
        return f"Error: {e}"


@tool
def build_30_day_plan(role:str, start_date:str) -> str:
    """Build a day-by-day plan for a new joiner's first 30 days. Weekends are skipped.

    Args:
        role: The job role, for example "developer", "qa", "ba" or "pm".
        start_date: The first day at work, as YYYY-MM-DD, for example "2026-12-01".
    """
    try:
        return json.dumps(make_plan(role, start_date))
    except ValueError as e:
        return f"Error: {e}"
