from dataclasses import dataclass
from typing import Optional, List
import pandas as pd


@dataclass
class FileAndQuery:
    file: str
    query: str
    rows_to_transform: Optional[List[str]] = None


def _clean(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _transform_row(row, columns):
    if not columns:
        raise ValueError("rows_to_transform must be set on every FileAndQuery.")
    return tuple(_clean(row[col]) for col in columns)


def load_tables(conn, files_and_queries: List[FileAndQuery]):
    results = []
    for fq in files_and_queries:
        name = fq.file
        try:
            df = pd.read_parquet(fq.file)
        except Exception as e:
            print(f"[READ FAIL] {name}: {e}")
            results.append((name, 0, f"read failed: {e}"))
            continue

        inserted = 0
        try:
            with conn.cursor() as cursor:
                for _, row in df.iterrows():
                    values = _transform_row(row, fq.rows_to_transform)
                    cursor.execute(fq.query, values)
                    inserted += 1
            conn.commit()
            print(f"[OK] {name}: {inserted} rows")
            results.append((name, inserted, None))
        except Exception as e:
            conn.rollback()
            print(f"[FAIL] {name}: {e} (rolled back)")
            results.append((name, 0, str(e)))

    return results