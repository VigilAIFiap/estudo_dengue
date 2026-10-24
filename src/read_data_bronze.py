from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import PROCESSED, RAW


CSV_SOURCES = {
    year: RAW / f'DENGBR{year}.csv'
    for year in (23, 24, 25, 26)
}
CSV_CHUNK_SIZE = 10_000


def _write_batches(
    destination: Path,
    batches,
    source: str,
) -> int:
    writer = None
    row_count = 0
    try:
        for frame in batches:
            if frame.empty:
                continue
            # Store raw values uniformly; ETL applies field-specific types later.
            table = pa.Table.from_pandas(
                frame.astype('string'),
                preserve_index=False,
            )
            if writer is None:
                writer = pq.ParquetWriter(destination, table.schema)
            else:
                table = table.cast(writer.schema, safe=False)
            writer.write_table(table)
            row_count += len(frame)
        if writer is None:
            raise ValueError(f'A fonte {source} não contém registros para salvar.')
    finally:
        if writer is not None:
            writer.close()
    return row_count


def _write_csv_year(year: int, destination: Path) -> tuple[int, int]:
    source = CSV_SOURCES[year]
    expected_year = 2000 + year
    if not source.is_file():
        raise FileNotFoundError(
            f'Fonte CSV completa de {expected_year} não encontrada: {source}'
        )
    header = pd.read_csv(source, encoding='latin-1', nrows=0).columns
    required = {'DT_NOTIFIC', 'NU_ANO'}
    missing = required.difference(header)
    if missing:
        raise ValueError(
            f'Colunas obrigatórias ausentes em {source.name}: {sorted(missing)}'
        )

    other_years = 0

    def batches():
        nonlocal other_years
        for chunk in pd.read_csv(
            source,
            encoding='latin-1',
            dtype='string',
            chunksize=CSV_CHUNK_SIZE,
        ):
            year_mask = chunk['NU_ANO'].str.strip().eq(str(expected_year))
            notification_year = pd.to_datetime(
                chunk.loc[year_mask, 'DT_NOTIFIC'],
                errors='coerce',
            ).dt.year
            mismatches = notification_year.notna() & notification_year.ne(
                expected_year
            )
            if mismatches.any():
                raise ValueError(
                    f'{source.name} contém registros com NU_ANO={expected_year} e '
                    'ano de DT_NOTIFIC diferente.'
                )
            other_years += int((~year_mask).sum())
            yield chunk.loc[year_mask]

    selected = _write_batches(destination, batches(), str(source))
    if selected == 0:
        raise ValueError(
            f'{source.name} não contém registros com NU_ANO={2000 + year}.'
        )
    return selected, other_years


def read_data() -> dict[int, int]:
    """Refresh all four Bronze Parquets from the local annual CSV files."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    years = tuple(CSV_SOURCES)
    missing_sources = [
        str(CSV_SOURCES[year])
        for year in years
        if not CSV_SOURCES[year].is_file()
    ]
    if missing_sources:
        raise FileNotFoundError(
            'Fontes CSV anuais ausentes: ' + ', '.join(missing_sources)
        )
    source_signatures = {
        year: (
            CSV_SOURCES[year].stat().st_size,
            CSV_SOURCES[year].stat().st_mtime_ns,
        )
        for year in years
    }
    temporary_paths = {
        year: PROCESSED / f'.df_bronze_{year}.{uuid.uuid4().hex}.parquet'
        for year in years
    }
    try:
        counts: dict[int, int] = {}
        discarded_other_years = {}
        for year in years:
            counts[year], discarded_other_years[year] = _write_csv_year(
                year,
                temporary_paths[year],
            )

        changed_sources = [
            CSV_SOURCES[year].name
            for year in years
            if (
                CSV_SOURCES[year].stat().st_size,
                CSV_SOURCES[year].stat().st_mtime_ns,
            )
            != source_signatures[year]
        ]
        if changed_sources:
            raise RuntimeError(
                'Fontes CSV foram modificadas durante a leitura: '
                + ', '.join(changed_sources)
            )

        for year, temporary_path in temporary_paths.items():
            os.replace(
                temporary_path,
                PROCESSED / f'df_bronze_{year}.parquet',
            )

        for year in years:
            print(
                f'DENGBR{year}.csv: {counts[year]:,} registros de {2000 + year} '
                f'selecionados; {discarded_other_years[year]:,} registros '
                'de outros anos ignorados.'
            )
        return counts
    finally:
        for temporary_path in temporary_paths.values():
            if temporary_path.exists():
                temporary_path.unlink()


if __name__ == '__main__':
    loaded_counts = read_data()
    for year, count in loaded_counts.items():
        print(f'DENGBR{year}: {count:,} registros armazenados.')
