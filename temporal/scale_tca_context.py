#!/usr/bin/env python3
import os
import re
import xml.etree.ElementTree as ET
import pandas as pd

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "tca_dataset.csv")
INPUT_CSX = os.path.join(SCRIPT_DIR, "tca_context.csx")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "tca_scaled_context.csv")

# Define Time Part and Event Part diagrams
TIME_DIAGRAMS = ["Age Ordinal", "Transition Ordinal", "Day of week Nominal"]
EVENT_DIAGRAMS = ["Has Assignee", "Priority Nominal", "Status Nominal"]

def clean_sql_to_python(sql_cond):
    """
    Translates Elba CSX SQL expressions into valid Python expressions
    to be evaluated against pandas row dictionaries.
    """
    # Remove table prefix
    expr = sql_cond.replace("TCA_DATASET.", "")
    # Lowercase column names to match CSV header
    expr = re.sub(r"\b([A-Z_]+)\b", lambda m: m.group(1).lower(), expr)
    # Replace SQL operators with Python equivalents
    expr = expr.replace(" = ", " == ")
    expr = expr.replace(" <> ", " != ")
    # Replace logic operators
    expr = re.sub(r"\bOR\b", "or", expr)
    expr = re.sub(r"\bAND\b", "and", expr)
    expr = re.sub(r"\bNOT\b", "not", expr)
    return expr

def parse_csx_scales(csx_path):
    """
    Parses tca_context.csx and extracts scale definitions for Time Part and Event Part.
    """
    print(f"Parsing Elba conceptual scales from {csx_path}...")
    tree = ET.parse(csx_path)
    root = tree.getroot()
    
    time_rules = {}
    event_rules = {}
    
    for diagram in root.findall(".//diagram"):
        title = diagram.get("title")
        if title in TIME_DIAGRAMS:
            target_dict = time_rules
        elif title in EVENT_DIAGRAMS:
            target_dict = event_rules
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
                    
                    # For Assignee scale, rename 'True'/'False' to 'Assigned'/'Unassigned' to avoid confusion
                    if title == "Has Assignee":
                        if attr_name == "True":
                            attr_name = "Assigned"
                        elif attr_name == "False":
                            attr_name = "Unassigned"
                            
                    target_dict[attr_name] = clean_sql_to_python(sql_cond)
                    
    return time_rules, event_rules

def main():
    print("=" * 60)
    print("TCA CONCEPT SCALER")
    print("=" * 60)

    # Check files
    for path in [INPUT_CSV, INPUT_CSX]:
        if not os.path.exists(path):
            print(f"Error: Required file {path} does not exist.")
            return

    # 1. Parse scales from CSX
    time_rules, event_rules = parse_csx_scales(INPUT_CSX)
    
    # Combine all rules for context scaling
    all_rules = {**time_rules, **event_rules}
    print(f"Loaded {len(all_rules)} total attributes to evaluate.")

    # 2. Load dataset
    print(f"Loading dataset from {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df):,} observation granules.")

    # 3. Evaluate scales and generate relation context
    print("Performing conceptual scaling and exporting relation pairs...")
    relation_rows = []
    
    for _, row in df.iterrows():
        granule_id = row["granule_id"]
        row_dict = row.to_dict()
        
        # Evaluate each scale condition
        for attr, expr in all_rules.items():
            try:
                if bool(eval(expr, {}, row_dict)):
                    # Save relation (Object, Attribute)
                    relation_rows.append([granule_id, attr])
            except Exception:
                pass
                
    # Save as CSV without header, comma-separated (Object, Attribute)
    relation_df = pd.DataFrame(relation_rows, columns=["Object", "Attribute"])
    relation_df.to_csv(OUTPUT_CSV, index=False, header=False)
    print(f"Saved scaled dyadic context to: {OUTPUT_CSV}")
    print(f"Total relation pairs: {len(relation_df):,}")
    print("=" * 60 + "\nDone. ✓")

if __name__ == "__main__":
    main()
