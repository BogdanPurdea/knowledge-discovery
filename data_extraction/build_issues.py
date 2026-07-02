import json
import pathlib
from typing import Optional

import pandas as pd

SCRIPT_DIR   = pathlib.Path(__file__).parent
FILTERED_DIR = SCRIPT_DIR.parent / "mongo_export_filtered"
FULL_DIR     = SCRIPT_DIR.parent / "mongo_export"
OUTPUT_CSV   = SCRIPT_DIR / "issues.csv"

# Number of most-active projects to include
TOP_N = 5

def load_ndjson(path: pathlib.Path, max_rows: Optional[int] = None) -> list[dict]:
    """Read a newline-delimited JSON file and return a list of dicts."""
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if max_rows is not None and i >= max_rows:
                break
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def parse_mongo_date(val) -> pd.Timestamp:
    """Parse a MongoDB Extended JSON date value into a timezone-aware Timestamp."""
    if isinstance(val, dict):
        inner = val.get("$date", val)
        if isinstance(inner, dict):
            ms = int(inner.get("$numberLong", 0))
            return pd.Timestamp(ms, unit="ms", tz="UTC")
        return pd.to_datetime(inner, utc=True, errors="coerce")
    if isinstance(val, str):
        return pd.to_datetime(val, utc=True, errors="coerce")
    return pd.NaT


def safe_get(d, *keys, default=None):
    """Safely traverse nested dicts; return default on any missing key."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


# Step 1: Load issues and find the top-N most active projects

print("=" * 65)
print(f"Step 1 — Loading issues_2024.json …")
raw_issues = load_ndjson(FILTERED_DIR / "issues_2024.json")
print(f"  Total 2024 issues loaded: {len(raw_issues):,}")

project_counts = pd.Series(
    [r.get("projectname") for r in raw_issues]
).value_counts()

print(f"\nTop 10 most active projects in 2024:")
print(project_counts.head(10).to_string())

TOP_PROJECTS = project_counts.index[:TOP_N].tolist()
print(f"\n  ✔ Selected top-{TOP_N} projects: {TOP_PROJECTS}")

# Partition raw issues by project (one pass)
project_records: dict[str, list[dict]] = {p: [] for p in TOP_PROJECTS}
for r in raw_issues:
    pname = r.get("projectname")
    if pname in project_records:
        project_records[pname].append(r)

for p, recs in project_records.items():
    print(f"    {p}: {len(recs):,} issues")


#  Step 2: Flatten and clean issues for every selected project 

print("\n" + "=" * 65)
print("Step 2 — Flattening and cleaning issues …")

def flatten_project(records: list[dict], projectname: str) -> pd.DataFrame:
    rows = []
    for r in records:
        issue_id        = str(r.get("_id", ""))
        issuetype_name  = safe_get(r, "issuetype", "name")
        priority_name   = safe_get(r, "priority",  "name")
        status_name     = safe_get(r, "status",    "name")
        status_category = safe_get(r, "status",    "statusCategory", "name")

        votes_count   = safe_get(r, "votes",   "votes",      default=0)
        watches_count = safe_get(r, "watches", "watchCount", default=0)

        components       = r.get("components", [])
        components_count = len(components) if isinstance(components, list) else 0

        created  = parse_mongo_date(r.get("created"))
        updated  = parse_mongo_date(r.get("updated"))
        age_days = (updated - created).days if pd.notna(created) and pd.notna(updated) else None

        has_assignee    = bool(r.get("assignee"))
        has_description = bool(r.get("description"))
        description     = r.get("description") or r.get("summary", "")
        summary         = r.get("summary", "")

        rows.append({
            "issue_id":        issue_id,
            "key":             r.get("key"),
            "projectname":     projectname,
            "issuetype_name":  issuetype_name,
            "priority_name":   priority_name,
            "status_name":     status_name,
            "status_category": status_category,
            "votes_count":     votes_count,
            "watches_count":   watches_count,
            "components_count": components_count,
            "created":         created,
            "updated":         updated,
            "age_days":        age_days,
            "has_assignee":    int(has_assignee),
            "has_description": int(has_description),
            "summary":         summary,
            "description":     description,
            "reporter":        r.get("reporter"),
            "assignee":        r.get("assignee"),
        })

    df = pd.DataFrame(rows)
    return df

project_dfs: dict[str, pd.DataFrame] = {}
for p, recs in project_records.items():
    df = flatten_project(recs, p)
    print(f"  {p}: {df.shape[0]:,} rows × {df.shape[1]} cols")
    project_dfs[p] = df


#  Step 3: Load secondary collections once, filter per project 

# Collect all issue IDs across all selected projects
all_issue_ids: set[str] = set()
for df in project_dfs.values():
    all_issue_ids.update(df["issue_id"].astype(str))

# Comments
print("\n" + "=" * 65)
print("Step 3a — Loading comments_2024.json …")
comments_raw = load_ndjson(FILTERED_DIR / "comments_2024.json")
comments_top = [
    c for c in comments_raw
    if c.get("projectname") in TOP_PROJECTS or str(c.get("issue")) in all_issue_ids
]
comment_agg = (
    pd.DataFrame([{"issue_id": str(c["issue"])} for c in comments_top])
    .groupby("issue_id").size().reset_index(name="comment_count")
    if comments_top else pd.DataFrame(columns=["issue_id", "comment_count"])
)
print(f"  Comments across top-{TOP_N} projects: {len(comments_top):,}")

# Events
print("Step 3b — Loading events_2024.json …")
events_raw = load_ndjson(FILTERED_DIR / "events_2024.json")
events_top = [
    e for e in events_raw
    if e.get("projectname") in TOP_PROJECTS or str(e.get("issue")) in all_issue_ids
]
status_rows = []
for e in events_top:
    eid   = str(e.get("issue"))
    items = e.get("items", [])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("field", "").lower() == "status":
                status_rows.append({"issue_id": eid})

status_agg = (
    pd.DataFrame(status_rows).groupby("issue_id").size().reset_index(name="status_changes_count")
    if status_rows else pd.DataFrame(columns=["issue_id", "status_changes_count"])
)
print(f"  Events: {len(events_top):,}  |  status-change rows: {len(status_rows):,}")


#  Step 4: Merge secondary data into each project frame, then combine 

print("\n" + "=" * 65)
print("Step 4 — Merging secondary collections into each project …")

merged_frames = []
for p, df in project_dfs.items():
    mvc = df.copy()
    mvc["issue_id"] = mvc["issue_id"].astype(str)

    mvc = mvc.merge(comment_agg, on="issue_id", how="left")
    mvc["comment_count"] = mvc["comment_count"].fillna(0).astype(int)

    mvc = mvc.merge(status_agg, on="issue_id", how="left")
    mvc["status_changes_count"] = mvc["status_changes_count"].fillna(0).astype(int)


    # Drop rows missing core categoricals
    before = len(mvc)
    mvc.dropna(subset=["issuetype_name", "priority_name", "status_name"], inplace=True)
    print(f"  {p}: {len(mvc):,} rows  (dropped {before - len(mvc):,} missing categoricals)")

    merged_frames.append(mvc)

combined = pd.concat(merged_frames, ignore_index=True)
print(f"\n  Combined shape before export: {combined.shape[0]:,} rows × {combined.shape[1]} cols")


#  Step 5: Export 

print("\n" + "=" * 65)
print("Step 5 — Exporting to issues.csv …")

# Rename to match the canonical output schema
combined = combined.rename(columns={
    "issue_id":     "_id",
    "watches_count": "watch_count",
    "projectname":   "project",
})

EXPORT_COLS = [
    "project",
    "_id",
    "key",
    "issuetype_name",
    "priority_name",
    "status_name",
    "age_days",
    "watch_count",
    "votes_count",
    "has_assignee",
    "components_count",
    "comment_count",
    "status_changes_count",
]
export_cols = [c for c in EXPORT_COLS if c in combined.columns]
out = combined[export_cols]
out.to_csv(OUTPUT_CSV, index=False)

print(f"\n  ✔ Saved: {OUTPUT_CSV}")
print(f"  Rows   : {len(out):,}")
print(f"  Columns: {len(out.columns)}")
print(f"\n  Column list:")
for col in out.columns:
    dtype = str(out[col].dtype)
    nulls = out[col].isna().sum()
    print(f"    {col:<25}  dtype={dtype:<12}  nulls={nulls:,}")

print("\n  Issue count per project:")
print(out.groupby("project").size().rename("issues").to_string())

print("\nDone. ✓")
