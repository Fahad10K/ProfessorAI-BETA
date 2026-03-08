"""
Neon DB Schema Inspector
========================
Connects to the Neon PostgreSQL database (using DATABASE_URL from .env)
and prints every table's columns, types, constraints, indexes, and foreign keys.
"""

import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)


def main():
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)

    # ── Schemas ──────────────────────────────────────────────
    schemas = inspector.get_schema_names()
    print("=" * 80)
    print("NEON DB – FULL SCHEMA REPORT")
    print("=" * 80)
    print(f"\nAvailable schemas: {schemas}\n")

    # Skip internal schemas
    skip_schemas = {'information_schema', 'pg_catalog'}
    schemas = [s for s in schemas if s not in skip_schemas]
    print(f"Inspecting schemas: {schemas}\n")

    for schema in schemas:
        tables = inspector.get_table_names(schema=schema)
        if not tables:
            continue

        print(f"\n{'#' * 80}")
        print(f"# SCHEMA: {schema}")
        print(f"{'#' * 80}")

        for table in sorted(tables):
            print(f"\n{'-' * 70}")
            print(f"  TABLE: {schema}.{table}")
            print(f"{'-' * 70}")

            # ── Columns ─────────────────────────────────────
            columns = inspector.get_columns(table, schema=schema)
            print(f"\n  {'Column':<30} {'Type':<25} {'Nullable':<10} {'Default'}")
            print(f"  {'-'*30} {'-'*25} {'-'*10} {'-'*30}")
            for col in columns:
                name = col["name"]
                col_type = str(col["type"])
                nullable = "YES" if col.get("nullable", True) else "NO"
                default = col.get("default", "")
                print(f"  {name:<30} {col_type:<25} {nullable:<10} {default}")

            # ── Primary Key ─────────────────────────────────
            pk = inspector.get_pk_constraint(table, schema=schema)
            if pk and pk.get("constrained_columns"):
                print(f"\n  PRIMARY KEY: {pk['constrained_columns']}")
                if pk.get("name"):
                    print(f"    constraint name: {pk['name']}")

            # ── Foreign Keys ────────────────────────────────
            fks = inspector.get_foreign_keys(table, schema=schema)
            if fks:
                print(f"\n  FOREIGN KEYS:")
                for fk in fks:
                    local = fk["constrained_columns"]
                    remote_table = fk["referred_table"]
                    remote_cols = fk["referred_columns"]
                    remote_schema = fk.get("referred_schema", schema)
                    fk_name = fk.get("name", "unnamed")
                    print(f"    {fk_name}: {local} -> {remote_schema}.{remote_table}({remote_cols})")

            # ── Unique Constraints ──────────────────────────
            uniques = inspector.get_unique_constraints(table, schema=schema)
            if uniques:
                print(f"\n  UNIQUE CONSTRAINTS:")
                for uc in uniques:
                    print(f"    {uc.get('name', 'unnamed')}: {uc['column_names']}")

            # ── Check Constraints ───────────────────────────
            try:
                checks = inspector.get_check_constraints(table, schema=schema)
                if checks:
                    print(f"\n  CHECK CONSTRAINTS:")
                    for cc in checks:
                        print(f"    {cc.get('name', 'unnamed')}: {cc.get('sqltext', '')}")
            except Exception:
                pass

            # ── Indexes ─────────────────────────────────────
            indexes = inspector.get_indexes(table, schema=schema)
            if indexes:
                print(f"\n  INDEXES:")
                for idx in indexes:
                    unique_tag = " (UNIQUE)" if idx.get("unique") else ""
                    print(f"    {idx['name']}: {idx['column_names']}{unique_tag}")

    # ── Sequences ───────────────────────────────────────────
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT sequence_schema, sequence_name "
                "FROM information_schema.sequences "
                "ORDER BY sequence_schema, sequence_name"
            ))
            seqs = result.fetchall()
            if seqs:
                print(f"\n\n{'=' * 80}")
                print("SEQUENCES")
                print(f"{'=' * 80}")
                for s in seqs:
                    print(f"  {s[0]}.{s[1]}")
    except Exception as e:
        print(f"\n  (Could not fetch sequences: {e})")

    # ── Views (public schema only) ───────────────────────────
    try:
        for schema in schemas:
            views = inspector.get_view_names(schema=schema)
            if views:
                print(f"\n{'=' * 80}")
                print(f"VIEWS in schema '{schema}'")
                print(f"{'=' * 80}")
                for v in views:
                    print(f"  {v}")
    except Exception as e:
        print(f"\n  (Could not fetch views: {e})")

    # ── Enums / Custom Types ────────────────────────────────
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT t.typname, e.enumlabel "
                "FROM pg_type t "
                "JOIN pg_enum e ON t.oid = e.enumtypid "
                "ORDER BY t.typname, e.enumsortorder"
            ))
            rows = result.fetchall()
            if rows:
                print(f"\n{'=' * 80}")
                print("ENUM TYPES")
                print(f"{'=' * 80}")
                current = None
                for r in rows:
                    if r[0] != current:
                        current = r[0]
                        print(f"\n  {current}:")
                    print(f"    - {r[1]}")
    except Exception as e:
        print(f"\n  (Could not fetch enums: {e})")

    # ── Row Counts ──────────────────────────────────────────
    print(f"\n\n{'=' * 80}")
    print("TABLE ROW COUNTS (public schema)")
    print(f"{'=' * 80}")
    with engine.connect() as conn:
        for schema in [s for s in schemas if s == 'public']:
            tables = inspector.get_table_names(schema=schema)
            for table in sorted(tables):
                try:
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"'))
                    count = result.scalar()
                    print(f"  {schema}.{table}: {count} rows")
                except Exception as e:
                    print(f"  {schema}.{table}: ERROR - {e}")

    print(f"\n{'=' * 80}")
    print("Done.")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
