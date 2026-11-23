import json
from datetime import date

from onboarding_tools import build_30_day_plan, get_access_checklist


def plan_for(role:str, start:str) -> list[dict]:
    return json.loads(build_30_day_plan(role, start))["plan"]


def test_access_checklist_has_common_and_role_items():
    result = json.loads(get_access_checklist("QA"))
    assert result["role"] == "qa"
    assert "VPN" in result["access"]
    assert "Staging environment" in result["access"]


def test_access_checklist_accepts_aliases():
    assert json.loads(get_access_checklist("Business Analyst"))["role"] == "ba"


def test_unknown_role_returns_error_for_both_tools():
    assert get_access_checklist("wizard").startswith("Error")
    assert build_30_day_plan("wizard", "2026-12-01").startswith("Error")


def test_plan_bad_date_returns_error():
    assert build_30_day_plan("dev", "01/12/2026").startswith("Error")


def test_plan_has_no_weekends_and_stays_within_30_days():
    plan = plan_for("dev", "2026-12-01")
    days = [date.fromisoformat(p["date"]) for p in plan]
    assert all(d.weekday() < 5 for d in days)
    assert days[-1] <= date(2026, 12, 30)


def test_plan_first_day_is_access_setup():
    # The Week 4 reviewer agent will check this too.
    assert "access" in plan_for("pm", "2026-12-01")[0]["task"].lower()


def test_plan_starting_on_a_weekend_begins_next_monday():
    plan = plan_for("qa", "2026-11-28")  # a Saturday
    assert plan[0]["date"] == "2026-11-30"


def test_plan_week_one_is_light_and_role_specific():
    week1 = [p["task"] for p in plan_for("qa", "2026-12-07") if p["week"].startswith("Week 1")]
    assert len(week1) == 5
    assert any("test suite" in t for t in week1)  # QA focus task is in


def test_plan_works_for_every_start_weekday_and_role():
    for role in ("developer", "qa", "ba", "pm"):
        for start_day in range(1, 8):  # 7 different weekdays
            plan = plan_for(role, f"2026-12-{start_day:02d}")
            assert 20 <= len(plan) <= 22
            assert all("{focus}" not in p["task"] for p in plan)
