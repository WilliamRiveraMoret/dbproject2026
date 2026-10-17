from dataclasses import dataclass
from typing import Optional
import pandas as pd

@dataclass
class FileAndQuery:
    file: str
    query: str
    rows_to_transform: Optional[list[str]]=None


def _transform_row(row, columns):
    return tuple(row[col] for col in columns)

def load_tables(conn, files_and_queries: list[FileAndQuery]):
    with conn.cursor() as cursor:
        for file_and_query in files_and_queries:
            df = pd.read_parquet(file_and_query.file)
            print(_transform_row(df.iloc[0], file_and_query.rows_to_transform) if file_and_query.rows_to_transform else tuple("skip"))
            i = 0
            for _, row in df.iterrows():
                rows_to_transform = file_and_query.rows_to_transform
                i += 1
                if rows_to_transform:
                    print(f"Transformed row {i} / {len(df)}")
                values = _transform_row(row, rows_to_transform) if rows_to_transform else tuple(row)
                cursor.execute(file_and_query.query, values)
