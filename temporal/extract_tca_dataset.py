#!/usr/bin/env python3
import os
import json
import datetime
import pandas as pd

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
ISSUES_JSON = os.path.join(BASE_DIR, "mongo_export_filtered", "issues_2024.json")
EVENTS_JSON = os.path.join(BASE_DIR, "mongo_export_filtered", "events_2024.json")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "tca_dataset.csv")

# Project filter
TARGET_PROJECT = "KAFKA"

def parse_date(date_elem):
    if not date_elem:
        return None
    if isinstance(date_elem, dict):
        date_str = date_elem.get("$date")
    else:
        date_str = date_elem
    if not date_str:
        return None
    try:
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(date_str)
    except Exception:
        return None

def get_time_of_day(dt):
    hour = dt.hour
    if 6 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 18:
        return "Afternoon"
    elif 18 <= hour < 24:
        return "Evening"
    else:
        return "Night"

def main():
    print("=" * 60)
    print("TCA DATASET EXTRACTOR")
    print("=" * 60)

    # Check inputs
    for path in [ISSUES_JSON, EVENTS_JSON]:
        if not os.path.exists(path):
            print(f"Error: Required file {path} does not exist.")
            return

    # Step 1: Load issues for the target project
    print(f"Loading issues from {ISSUES_JSON} for project {TARGET_PROJECT}...")
    issues_dict = {}
    with open(ISSUES_JSON, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            issue = json.loads(line)
            if issue.get("projectname") == TARGET_PROJECT:
                issues_dict[issue["_id"]] = issue

    print(f"Loaded {len(issues_dict)} issues for project {TARGET_PROJECT}.")

    # Step 2: Load and group events
    print(f"Loading events from {EVENTS_JSON}...")
    events_by_issue = {issue_id: [] for issue_id in issues_dict}
    
    with open(EVENTS_JSON, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            issue_id = event.get("issue")
            if issue_id in issues_dict:
                # Check for status changes in event items
                items = event.get("items", [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get("field", "").lower() == "status":
                            events_by_issue[issue_id].append(event)
                            break

    # Step 3: Reconstruct transitions chronologically
    print("Reconstructing issue status lifecycles (life-tracks)...")
    granules = []

    for issue_id, issue in issues_dict.items():
        issue_key = issue.get("key")
        created_dt = parse_date(issue.get("created"))
        if not created_dt:
            continue

        priority = issue.get("priority", {}).get("name", "Major")
        has_assignee = 1 if issue.get("assignee") else 0

        # Sort this issue's status change events chronologically
        issue_events = events_by_issue[issue_id]
        issue_events_sorted = sorted(
            issue_events,
            key=lambda ev: parse_date(ev.get("created")) or datetime.datetime.min
        )

        # Reconstruct state 0 (Creation state)
        # Find the earliest status change event to know what the initial status was
        initial_status = "Open"  # Default fallback
        if issue_events_sorted:
            # Look at the status change item of the first event
            first_event = issue_events_sorted[0]
            for item in first_event.get("items", []):
                if isinstance(item, dict) and item.get("field", "").lower() == "status":
                    initial_status = item.get("fromString") or item.get("from") or "Open"
                    break
        else:
            # If there are no events, the initial status is the current status
            initial_status = issue.get("status", {}).get("name", "Open")

        # Emit Granule 0
        granules.append({
            "issue_key": issue_key,
            "granule_id": f"{issue_key}_G0",
            "timestamp": created_dt.isoformat(),
            "transition_seq": 0,
            # Time part attributes
            "days_since_creation": 0.0,
            "day_of_week": created_dt.strftime("%a"),
            "month": created_dt.strftime("%b"),
            "time_of_day": get_time_of_day(created_dt),
            # Event part attributes
            "status": initial_status,
            "priority": priority,
            "has_assignee": has_assignee
        })

        # Emit subsequent transition granules
        current_status = initial_status
        for k, event in enumerate(issue_events_sorted):
            event_dt = parse_date(event.get("created"))
            if not event_dt:
                continue

            # Extract the new status
            new_status = current_status
            for item in event.get("items", []):
                if isinstance(item, dict) and item.get("field", "").lower() == "status":
                    new_status = item.get("toString") or item.get("to") or current_status
                    break

            days_elapsed = (event_dt - created_dt).total_seconds() / 86400.0

            # Emit Granule k+1
            granules.append({
                "issue_key": issue_key,
                "granule_id": f"{issue_key}_G{k+1}",
                "timestamp": event_dt.isoformat(),
                "transition_seq": k + 1,
                # Time part attributes
                "days_since_creation": round(max(0.0, days_elapsed), 4),
                "day_of_week": event_dt.strftime("%a"),
                "month": event_dt.strftime("%b"),
                "time_of_day": get_time_of_day(event_dt),
                # Event part attributes
                "status": new_status,
                "priority": priority,
                "has_assignee": has_assignee
            })
            current_status = new_status

    # Step 4: Export to CSV
    print(f"Exporting dataset containing {len(granules):,} granules to CSV...")
    df_out = pd.DataFrame(granules)
    df_out.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved: {OUTPUT_CSV}")
    print("=" * 60 + "\nDone. ✓")

if __name__ == "__main__":
    main()
