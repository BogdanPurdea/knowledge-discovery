#!/usr/bin/env python3
import os
import json
import itertools
import argparse
import pandas as pd

def calculate_support(A, B, C, relations, K1):
    X = set(A) | set(B)
    count = 0
    for g in K1:
        has_all = True
        for m in X:
            for c in C:
                if (g, m, c) not in relations:
                    has_all = False
                    break
            if not has_all:
                break
        if has_all:
            count += 1
    return count / len(K1)

def mine_triadic_rules(K1, K2, K3, relations, min_supp, min_conf):
    rules = []
    
    # Generate condition subsets of size 1 and 2
    c_subsets = []
    for r in range(1, 3):
        for combo in itertools.combinations(K3, r):
            c_subsets.append(list(combo))
            
    for C in c_subsets:
        for m_a in K2:
            for m_b in K2:
                if m_a == m_b:
                    continue
                A = [m_a]
                B = [m_b]
                
                # Calculate support and confidence
                supp_A_C = calculate_support(A, [], C, relations, K1)
                if supp_A_C == 0:
                    continue
                supp_AB_C = calculate_support(A, B, C, relations, K1)
                conf = supp_AB_C / supp_A_C
                
                if supp_AB_C >= min_supp and conf >= min_conf:
                    rules.append({
                        "A": A,
                        "B": B,
                        "C": C,
                        "support": supp_AB_C,
                        "confidence": conf
                    })
    return rules

def main():
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    default_input = os.path.join(SCRIPT_DIR, "project_triadic_context.csv")

    parser = argparse.ArgumentParser(description="Mine Triadic Association Rules & Conditional Implications")
    parser.add_argument("--input", type=str, default=default_input, help="Path to project_triadic_context.csv")
    parser.add_argument("--min-support", type=float, default=0.2, help="Minimum support threshold (0.0 to 1.0, default 0.2)")
    parser.add_argument("--min-confidence", type=float, default=0.6, help="Minimum confidence threshold (0.0 to 1.0, default 0.6)")
    parser.add_argument("--output", type=str, default=None, help="Optional JSON file to save the mined rules")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} does not exist.")
        return

    # Ingest triadic CSV
    try:
        df = pd.read_csv(args.input, header=None, names=['Object', 'Attribute', 'Condition'])
        if df.iloc[0]['Object'] == 'Object':
            df = df.iloc[1:].reset_index(drop=True)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    relations = set(tuple(x) for x in df[['Object', 'Attribute', 'Condition']].values)
    K1 = sorted(df['Object'].unique())
    K2 = sorted(df['Attribute'].unique())
    K3 = sorted(df['Condition'].unique())

    print("=" * 60)
    print("TRIADIC CONTEXT METRICS")
    print("=" * 60)
    print(f"Objects (Projects):   {len(K1)} {K1}")
    print(f"Attributes (Types):   {len(K2)} {K2}")
    print(f"Conditions (Modi):    {len(K3)} {K3}")
    print(f"Relation size (|Y|):  {len(relations)}")
    print("=" * 60 + "\n")

    print(f"Mining rules with Min Support >= {args.min_support:.0%}, Min Confidence >= {args.min_confidence:.0%}...")
    rules = mine_triadic_rules(K1, K2, K3, relations, args.min_support, args.min_confidence)

    exact = [r for r in rules if r["confidence"] == 1.0]
    partial = [r for r in rules if r["confidence"] < 1.0]

    print(f"Mined {len(rules)} total rules ({len(exact)} exact implications, {len(partial)} partial rules).\n")

    # Display Exact implications
    print("-" * 60)
    print("EXACT CONDITIONAL IMPLICATIONS (Confidence = 100%)")
    print("-" * 60)
    if exact:
        print(f"{'Rule (A -> B | C)':<45} {'Support':<10}")
        print("-" * 60)
        for r in exact:
            rule_str = f"{{{r['A'][0]}}} -> {{{r['B'][0]}}} | {{{', '.join(r['C'])}}}"
            print(f"{rule_str:<45} {r['support']:.0%}")
    else:
        print("None")
    print()

    # Display Partial Association Rules
    print("-" * 60)
    print("PARTIAL TRIADIC ASSOCIATION RULES (Confidence < 100%)")
    print("-" * 60)
    if partial:
        # Sort by confidence descending, then support descending
        partial = sorted(partial, key=lambda x: (x["confidence"], x["support"]), reverse=True)
        print(f"{'Rule (A -> B | C)':<45} {'Support':<10} {'Confidence':<10}")
        print("-" * 60)
        for r in partial:
            rule_str = f"{{{r['A'][0]}}} -> {{{r['B'][0]}}} | {{{', '.join(r['C'])}}}"
            print(f"{rule_str:<45} {r['support']:.0%}       {r['confidence']:.0%}")
    else:
        print("None")
    print()

    # Optionally write to JSON
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(rules, fh, indent=2)
        print(f"Saved mined rules to {args.output}")

if __name__ == "__main__":
    main()
