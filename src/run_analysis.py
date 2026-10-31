"""Run every tagged query in sql/02_analysis.sql against MySQL and save each result
to outputs/tables/<name>.csv.

Connection settings come from environment variables (defaults in brackets):
  MYSQL_HOST [localhost]  MYSQL_PORT [3306]  MYSQL_USER [root]  MYSQL_PASSWORD [""]  MYSQL_DB [partd]

Usage (from the repo root, after loading the data with sql/01_schema_load.sql):
  python src/run_analysis.py
"""
import os
import re
from pathlib import Path

import pandas as pd
import pymysql

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "sql" / "02_analysis.sql"
OUT = ROOT / "outputs" / "tables"


def tagged_queries(text: str) -> dict[str, str]:
    """Split the SQL file on '-- name: <x>' markers."""
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)
    # parts = [preamble, name1, body1, name2, body2, ...]
    return {name: body.strip().rstrip(";") for name, body in zip(parts[1::2], parts[2::2])}


def main() -> None:
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "partd"),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    for name, sql in tagged_queries(SQL_FILE.read_text()).items():
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [c[0] for c in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=cols)
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name:40s} {len(df):>4d} rows")
    conn.close()


if __name__ == "__main__":
    main()
