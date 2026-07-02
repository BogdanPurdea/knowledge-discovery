#!/usr/bin/env python3

import argparse
import csv
import os
import re
import sys


def sanitize_name(name: str) -> str:
    """Sanitize a string to be a valid SQL identifier."""
    # Replace non-alphanumeric characters (except underscore) with underscore
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    # If the name starts with a digit, prepend an underscore
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized or "_col"


def infer_sql_type(values: list[str]) -> str:
    """
    Infer the SQL column type from a list of string values sampled from the column.
    Returns one of: integer, real, varchar.
    """
    non_empty = [v for v in values if v.strip() != ""]
    if not non_empty:
        return "varchar"

    # Try integer
    try:
        [int(v) for v in non_empty]
        return "integer"
    except ValueError:
        pass

    # Try real / float
    try:
        [float(v) for v in non_empty]
        return "real"
    except ValueError:
        pass

    return "varchar"


def format_value(value: str, sql_type: str) -> str:
    """Format a single CSV value for inclusion in an INSERT statement."""
    stripped = value.strip()

    if sql_type == "varchar":
        # Escape single quotes by doubling them
        escaped = stripped.replace("'", "''")
        return f"'{escaped}'"

    if stripped == "":
        return "NULL"

    if sql_type == "integer":
        try:
            return str(int(stripped))
        except ValueError:
            # Fallback – shouldn't normally happen after type inference
            return "NULL"

    if sql_type == "real":
        try:
            return str(float(stripped))
        except ValueError:
            return "NULL"

    return f"'{stripped}'"


def csv_to_sql(
    input_path: str,
    output_path: str,
    table_name: str | None = None,
) -> None:
    """
    Read the CSV at *input_path* and write a SQL file to *output_path*
    containing a CREATE TABLE statement followed by one INSERT per row.
    """
    # Derive a default table name from the CSV filename if none is provided
    if not table_name:
        base = os.path.splitext(os.path.basename(input_path))[0]
        table_name = sanitize_name(base).upper()

    with open(input_path, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)

        try:
            raw_headers = next(reader)
        except StopIteration:
            print("Error: The CSV file is empty.", file=sys.stderr)
            sys.exit(1)

        if not raw_headers:
            print("Error: No header row found in the CSV file.", file=sys.stderr)
            sys.exit(1)

        headers = [sanitize_name(h) for h in raw_headers]

        # Read all rows into memory so we can infer types from the full column
        rows = list(reader)

    if not rows:
        print("Warning: The CSV file contains a header but no data rows.", file=sys.stderr)

    # Infer SQL type for each column
    column_types: list[str] = []
    for col_idx in range(len(headers)):
        column_values = [row[col_idx] for row in rows if col_idx < len(row)]
        column_types.append(infer_sql_type(column_values))

    # Build SQL
    lines: list[str] = []

    # CREATE TABLE
    lines.append(f"CREATE TABLE {table_name} (")
    col_defs = []
    for header, sql_type in zip(headers, column_types):
        col_defs.append(f"  {header} {sql_type}")
    lines.append(",\n".join(col_defs))
    lines.append(");")
    lines.append("")

    # INSERT INTO … VALUES (…)
    for row in rows:
        # Pad short rows with empty strings
        padded_row = row + [""] * (len(headers) - len(row))
        formatted_values = [
            format_value(padded_row[i], column_types[i])
            for i in range(len(headers))
        ]
        values_str = ", ".join(formatted_values)
        lines.append(f"INSERT INTO {table_name} VALUES ({values_str});")

    sql_content = "\n".join(lines) + "\n"

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(sql_content)

    print(
        f"Done! Wrote {len(rows)} row(s) into '{output_path}' "
        f"(table: {table_name}, columns: {len(headers)})."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a CSV file to a SQL file (CREATE TABLE + INSERTs).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", help="Path to the input CSV file")
    parser.add_argument("output", help="Path to the output SQL file")
    parser.add_argument(
        "--table",
        default=None,
        metavar="TABLE_NAME",
        help="Name for the SQL table (default: derived from the CSV filename)",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    csv_to_sql(args.input, args.output, args.table)


if __name__ == "__main__":
    main()
