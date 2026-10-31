"""Download every GLP-1 row from CMS "Medicare Part D Prescribers - by Provider and Drug"
for data years 2023 and 2024, and save them to data/partd_glp1_2023_2024.csv.

The CMS data API is public and needs no key. It returns at most 5,000 rows per call,
so each (year, molecule) slice is paged in parallel.

Usage (from the repo root):  python src/fetch_cms_partd.py
"""
import concurrent.futures as cf
from pathlib import Path

import pandas as pd
import requests

API = "https://data.cms.gov/data-api/v1/dataset/{id}/data"
DATASETS = {  # dataset ids from https://data.cms.gov/data.json
    "2023": "e54db557-cd82-4e91-a0fe-61aad5865d69",
    "2024": "9552739e-3d05-4c1b-8eff-ecabf391e2e5",
}
MOLECULES = ["Semaglutide", "Tirzepatide", "Dulaglutide", "Liraglutide", "Exenatide", "Lixisenatide"]
PAGE = 5000
OUT = Path(__file__).resolve().parents[1] / "data" / "partd_glp1_2023_2024.csv"


def get_json(url: str, params: dict, tries: int = 5):
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, timeout=120)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == tries - 1:
                raise


def row_count(year: str, molecule: str) -> int:
    stats = get_json(API.format(id=DATASETS[year]) + "/stats", {"filter[Gnrc_Name]": molecule})
    return int(stats["found_rows"])


def fetch_page(job):
    year, molecule, offset = job
    rows = get_json(API.format(id=DATASETS[year]),
                    {"filter[Gnrc_Name]": molecule, "size": PAGE, "offset": offset})
    for r in rows:
        r["year"] = year
    return rows


def main() -> None:
    counts = {(y, m): row_count(y, m) for y in DATASETS for m in MOLECULES}
    jobs = [(y, m, off) for (y, m), n in counts.items() for off in range(0, n, PAGE)]
    print(f"{sum(counts.values()):,} rows to fetch in {len(jobs)} pages")

    rows = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for page in ex.map(fetch_page, jobs):
            rows.extend(page)

    df = pd.DataFrame(rows)
    got = df.groupby(["year", "Gnrc_Name"]).size()
    for (y, m), n in counts.items():  # every slice must arrive complete
        assert got.get((y, m), 0) == n, f"{y} {m}: expected {n}, got {got.get((y, m), 0)}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"saved {len(df):,} rows to {OUT}")
    print(got.to_string())


if __name__ == "__main__":
    main()
