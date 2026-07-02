#!/usr/bin/env python3
import os
import pandas as pd

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
INPUT_CSV = os.path.join(BASE_DIR, "data_extraction", "issues.csv")
OUTPUT_CXT = os.path.join(SCRIPT_DIR, "kafka_context.cxt")

def main():
    print(f"Step 1: Reading input CSV from {INPUT_CSV}...")
    if not os.path.exists(INPUT_CSV):
        print(f"Error: {INPUT_CSV} does not exist.")
        return
        
    df = pd.read_csv(INPUT_CSV)
    print(f"Original dataset contains {len(df)} rows.")

    print("Step 2: Filtering for KAFKA project...")
    df_kafka = df[df["project"] == "KAFKA"].copy()
    print(f"Found {len(df_kafka)} KAFKA issues.")
    
    print("Limiting to first 200 samples...")
    df_kafka = df_kafka.head(200)

    # Target 6 attributes
    attributes = [
        "Bug", "Closed/Resolved", "Critical/Major", "Assigned", 
        "At least one week old", "At least Moderate Interest"
    ]
    
    print("Step 3: Calculating binary relations for each issue...")
    relations = []
    objects = []
    
    for _, row in df_kafka.iterrows():
        # Get the object name (issue key)
        key = str(row["key"])
        objects.append(key)
        
        attr_vals = []
        
        # 1. Issue Type (Bug)
        itype = row["issuetype_name"]
        attr_vals.append(itype == "Bug")
        
        # 2. Status (Closed/Resolved)
        status = row["status_name"]
        attr_vals.append(status in ["Closed", "Resolved"])
        
        # 3. Priority (Critical/Major)
        priority = row["priority_name"]
        attr_vals.append(priority in ["Critical", "Blocker", "Major"])
        
        # 4. Has Assignee (Assigned)
        has_assignee = row["has_assignee"]
        attr_vals.append(has_assignee > 0)
        
        # 5. Age (At least one week old)
        age = row["age_days"]
        age_val = 0 if pd.isna(age) else float(age)
        attr_vals.append(age_val >= 7)
        
        # 6. Interest (At least Moderate Interest)
        watches = row["watch_count"]
        attr_vals.append(watches > 5)
        
        # Format as string of 'X' and '.'
        row_rel = "".join("X" if val else "." for val in attr_vals)
        relations.append(row_rel)

    print(f"Step 4: Writing CXT file to {OUTPUT_CXT}...")
    with open(OUTPUT_CXT, "w", encoding="utf-8") as f:
        # Header block
        f.write("B\n\n")
        f.write(f"{len(objects)}\n")
        f.write(f"{len(attributes)}\n\n")
        
        # Objects block
        for obj in objects:
            f.write(f"{obj}\n")
            
        # Attributes block
        for attr in attributes:
            f.write(f"{attr}\n")
            
        # Relation block
        for rel in relations:
            f.write(f"{rel}\n")
            
    print(f"Done! Extracted {len(objects)} issues with {len(attributes)} attributes into {OUTPUT_CXT}.")

if __name__ == "__main__":
    main()
