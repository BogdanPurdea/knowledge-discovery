#!/usr/bin/env python3
import os
import re
import xml.etree.ElementTree as ET
import pandas as pd
import argparse

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
INPUT_CSV = os.path.join(BASE_DIR, "data_extraction", "issues.csv")
INPUT_CSX = os.path.join(BASE_DIR, "scaling", "issues.csx")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "project_triadic_context.csv")

# Target dimensions
TARGET_PROJECTS = ["FLINK", "HDDS", "IGNITE", "KAFKA", "SPARK"]
TARGET_ISSUE_TYPES = ["Bug", "Improvement", "New Feature", "Sub-task", "Task", "Test"]

def clean_sql_to_python(sql_cond):
    """
    Translates basic SQL expressions in issues.csx into valid Python expressions
    to be evaluated against pandas row dictionaries.
    """
    # Remove table prefixes like ISSUES.
    expr = re.sub(r"\bISSUES\.", "", sql_cond)
    
    # Lowercase column names to match the CSV header
    expr = re.sub(r"\b([A-Z_]+)\b", lambda m: m.group(1).lower(), expr)
    
    # Replace SQL operators with Python equivalents
    expr = expr.replace(" = ", " == ")
    expr = expr.replace(" <> ", " != ")
    
    # Case-insensitive SQL logical operators replacement
    expr = re.sub(r"\bOR\b", "or", expr)
    expr = re.sub(r"\bAND\b", "and", expr)
    expr = re.sub(r"\bNOT\b", "not", expr)
    
    return expr

def parse_csx_scales(csx_path):
    """
    Parses issues.csx and extracts scale definitions for the target scales.
    Returns:
      - issue_type_rules: dict of type -> condition
      - priority_rules: dict of priority_attr -> condition
      - status_rules: dict of status_attr -> condition
    """
    print(f"Parsing conceptual schema from {csx_path}...")
    tree = ET.parse(csx_path)
    root = tree.getroot()
    
    issue_type_rules = {}
    priority_rules = {}
    status_rules = {}
    
    for diagram in root.findall(".//diagram"):
        title = diagram.get("title")
        if title == "Issue Type Nominal":
            target_dict = issue_type_rules
        elif title == "Priority Nominal":
            target_dict = priority_rules
        elif title == "Status Nominal":
            target_dict = status_rules
        else:
            continue
            
        for node in diagram.findall(".//node"):
            concept = node.find("concept")
            if concept is not None:
                attr_elem = concept.find(".//attribute")
                obj_elem = concept.find(".//object")
                if attr_elem is not None and obj_elem is not None:
                    attr_name = attr_elem.text.strip()
                    sql_cond = obj_elem.text.strip()
                    target_dict[attr_name] = clean_sql_to_python(sql_cond)
                    
    return issue_type_rules, priority_rules, status_rules

def main():
    parser = argparse.ArgumentParser(description="Construct JIRA Triadic Formal Context (K-ecosystem)")
    parser.add_argument("--min-support", type=int, default=5, help="Minimum issue count per project-type group")
    parser.add_argument("--threshold", type=float, default=0.5, help="Majority threshold for incidence relation (default 0.5)")
    args = parser.parse_args()

    # Parse scales from CSX
    if not os.path.exists(INPUT_CSX):
        print(f"Error: {INPUT_CSX} does not exist.")
        return
    type_rules, priority_rules, status_rules = parse_csx_scales(INPUT_CSX)
    
    # Filter for target attributes
    type_rules = {k: v for k, v in type_rules.items() if k in TARGET_ISSUE_TYPES}
    print(f"Loaded {len(type_rules)} target issue type attributes: {list(type_rules.keys())}")
    print(f"Loaded {len(priority_rules)} priority attributes: {list(priority_rules.keys())}")
    print(f"Loaded {len(status_rules)} status attributes: {list(status_rules.keys())}")
    
    # Load issues CSV
    if not os.path.exists(INPUT_CSV):
        print(f"Error: {INPUT_CSV} does not exist.")
        return
    print(f"Reading JIRA issues from {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    
    # Filter for the 5 target projects
    df_filtered = df[df["project"].isin(TARGET_PROJECTS)].copy()
    print(f"Filtered to {len(df_filtered)} issues for projects: {TARGET_PROJECTS}")
    
    # We will build the list of triplets
    triplets = []
    
    # Set of conditions (K3)
    conditions = list(priority_rules.keys()) + list(status_rules.keys())
    
    # Evaluate conditions and attributes row-by-row
    # We create a column for each attribute/condition for easy aggregation
    all_rules = {}
    all_rules.update(type_rules)
    all_rules.update(priority_rules)
    all_rules.update(status_rules)
    
    for attr_name, py_expr in all_rules.items():
        # Evaluate condition for each row
        # To make eval safe and fast, construct row dicts
        def eval_row(row):
            try:
                return bool(eval(py_expr, {}, row.to_dict()))
            except Exception as e:
                # Fallback if evaluation fails
                return False
        df_filtered[attr_name] = df_filtered.apply(eval_row, axis=1)
        
    print("Evaluating aggregate incidence relation Y...")
    # Group by project and issue type
    grouped = df_filtered.groupby(["project", "issuetype_name"])
    
    for (project, type_name), group in grouped:
        if type_name not in TARGET_ISSUE_TYPES:
            continue
        
        group_size = len(group)
        if group_size < args.min_support:
            continue  # Skip sparse categories
            
        # Check majority for each condition
        for cond in conditions:
            # Count how many issues in this group satisfy the condition
            cond_count = group[cond].sum()
            ratio = cond_count / group_size
            
            if ratio > args.threshold:
                # Emit triplet (Project, IssueType, Condition)
                triplets.append({
                    "Object": project,
                    "Attribute": type_name,
                    "Condition": cond
                })
                
    # Build dataframes for export
    df_triplets = pd.DataFrame(triplets)
    
    # Handle empty output case safely
    if df_triplets.empty:
        df_triplets = pd.DataFrame(columns=["Object", "Attribute", "Condition"])
        
    # Export to CSV
    df_triplets.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved triadic context CSV to {OUTPUT_CSV}")
    
    # Calculate density
    num_objects = len(TARGET_PROJECTS)
    num_attributes = len(TARGET_ISSUE_TYPES)
    num_conditions = len(conditions)
    num_triplets = len(df_triplets)
    max_triplets = num_objects * num_attributes * num_conditions
    density = num_triplets / max_triplets if max_triplets > 0 else 0
    
    print("\n" + "=" * 50)
    print("TRIADIC CONTEXT SUMMARY (Project Ecosystem)")
    print("=" * 50)
    print(f"Objects (K1 - Projects):      {num_objects} {TARGET_PROJECTS}")
    print(f"Attributes (K2 - Issue Types): {num_attributes} {TARGET_ISSUE_TYPES}")
    print(f"Conditions (K3 - Attributes):  {num_conditions} {conditions}")
    print(f"Incidence Triples (|Y|):       {num_triplets} / {max_triplets}")
    print(f"Context Density:               {density:.2%}")
    print("=" * 50)

if __name__ == "__main__":
    main()
