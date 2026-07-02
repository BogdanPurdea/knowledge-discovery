#!/usr/bin/env python3
import os
import json
from collections import defaultdict

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "tca_scaled_context.csv")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "tca_state_transitions.json")
OUTPUT_DOT = os.path.join(SCRIPT_DIR, "tca_transition_graph.dot")

# Define the set of Event Part attributes to isolate them from Time Part attributes
EVENT_ATTRIBUTES = {
    "Assigned", "Unassigned", 
    "Major", "Minor", "Critical", 
    "Resolved", "Closed", "Reopened", "In Progress", "Open", "Patch Available"
}

def main():
    print("=" * 60)
    print("TCA LIFECYCLE TRANSITION EXTRACTOR")
    print("=" * 60)

    if not os.path.exists(INPUT_CSV):
        print(f"Error: Scaled context file {INPUT_CSV} does not exist.")
        return

    # 1. Load relation pairs from CSV
    print(f"Loading scaled context from {INPUT_CSV}...")
    granule_to_attrs = defaultdict(list)
    
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) == 2:
                obj, attr = parts[0], parts[1]
                granule_to_attrs[obj].append(attr)

    print(f"Loaded relations for {len(granule_to_attrs):,} unique granules.")

    # 2. Extract Event Part Intents (States) for each granule
    granule_to_state_intent = {}
    for granule_id, attrs in granule_to_attrs.items():
        # Filter for event part attributes only
        event_intent = tuple(sorted([a for a in attrs if a in EVENT_ATTRIBUTES]))
        granule_to_state_intent[granule_id] = event_intent

    # 3. Discover unique visited states
    unique_intents = sorted(list(set(granule_to_state_intent.values())), key=len)
    
    intent_to_state_id = {}
    state_id_to_name = {}
    for idx, intent in enumerate(unique_intents):
        state_id = f"S{idx}"
        intent_to_state_id[intent] = state_id
        state_name = " & ".join(intent) if intent else "Empty State"
        state_id_to_name[state_id] = state_name

    print(f"Discovered {len(unique_intents)} unique visited event states (concepts).")

    # 4. Group granules by Issue Key and Sort by Transition Sequence
    # granule_id format: {issue_key}_G{transition_seq}
    issue_to_granules = defaultdict(list)
    for granule_id in granule_to_attrs.keys():
        parts = granule_id.split("_G")
        if len(parts) == 2:
            issue_key = parts[0]
            try:
                seq = int(parts[1])
            except ValueError:
                seq = 9999
            issue_to_granules[issue_key].append((seq, granule_id))

    # 5. Compile Transitions Matrix
    print("Compiling issue life-tracks & transition matrices...")
    transitions = {}
    state_visits = defaultdict(int)

    for issue_key, seq_granules in issue_to_granules.items():
        # Sort chronologically by transition sequence
        seq_granules.sort()
        state_seq = []
        for seq, g_id in seq_granules:
            intent = granule_to_state_intent[g_id]
            state_id = intent_to_state_id[intent]
            state_seq.append(state_id)
            state_visits[state_id] += 1
            
        # Traverse transitions
        for i in range(len(state_seq) - 1):
            s_from = state_seq[i]
            s_to = state_seq[i+1]
            if s_from not in transitions:
                transitions[s_from] = {}
            transitions[s_from][s_to] = transitions[s_from].get(s_to, 0) + 1

    # 6. Calculate Transition Probabilities
    state_outflow = {}
    for s_from, targets in transitions.items():
        state_outflow[s_from] = sum(targets.values())

    transition_rates = []
    for s_from, targets in transitions.items():
        total = state_outflow[s_from]
        for s_to, count in targets.items():
            prob = count / total
            transition_rates.append({
                "from_id": s_from,
                "from_name": state_id_to_name[s_from],
                "to_id": s_to,
                "to_name": state_id_to_name[s_to],
                "count": count,
                "probability": round(prob, 4)
            })

    # Save to JSON
    output_data = {
        "states": [{"id": k, "name": v} for k, v in state_id_to_name.items()],
        "transitions": transition_rates
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    print(f"Saved state transition data to {OUTPUT_JSON}")

    # 7. Write Graphviz DOT file
    print(f"Generating transition graph DOT representation to {OUTPUT_DOT}...")
    with open(OUTPUT_DOT, "w", encoding="utf-8") as f:
        f.write("digraph TCA_Transition_Graph {\n")
        f.write("  rankdir=LR;\n")
        f.write("  node [shape=box, style=\"rounded,filled\", fillcolor=\"lightblue\", fontname=\"Helvetica\"];\n")
        f.write("  edge [fontname=\"Helvetica\", fontsize=10];\n\n")
        
        # Write state nodes with visit counts
        for state_id, state_name in state_id_to_name.items():
            visits = state_visits[state_id]
            label = f"{state_name}\\n(Visits: {visits:,})"
            f.write(f"  {state_id} [label=\"{label}\", fillcolor=\"#d0e8f8\"];\n")
            
        f.write("\n")
        # Write edges (filter transitions with count < 3 to reduce noise)
        for r in transition_rates:
            if r["count"] >= 3:
                edge_label = f"{r['probability']:.1%} ({r['count']})"
                f.write(f"  {r['from_id']} -> {r['to_id']} [label=\"{edge_label}\", penwidth={1 + r['probability']*4}];\n")
                
        f.write("}\n")
    print(f"Saved: {OUTPUT_DOT}")
    print("=" * 60 + "\nDone. ✓")

if __name__ == "__main__":
    main()
