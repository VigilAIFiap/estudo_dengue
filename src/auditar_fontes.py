from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from config import RAW


YEARS = (2023, 2024, 2025, 2026)


def auditar_fontes(
    data_dir: Path = RAW,
    as_of: date | str | None = None,
) -> dict[int, dict]:
    reference_date = _parse_reference_date(as_of)
    report = {}

    for year in YEARS:
        path = Path(data_dir) / f"DENGBR{year % 100:02d}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"Fonte anual não encontrada: {path}")
        print(f"Auditando {path.name}...", flush=True)

        with path.open("r", encoding="latin-1", newline="") as source:
            reader = csv.reader(source)
            header = next(reader, [])
        missing = {"NU_ANO", "DT_NOTIFIC"}.difference(header)
        if missing:
            raise ValueError(
                f"{path.name} não contém colunas obrigatórias: {sorted(missing)}"
            )

        year_column = header.index("NU_ANO")
        date_column = header.index("DT_NOTIFIC")
        total = year_rows = other_year_rows = 0
        invalid_dates = date_year_mismatches = future_dates = 0
        monthly = Counter()

        with path.open("r", encoding="latin-1", newline="") as source:
            reader = csv.reader(source)
            next(reader, None)
            for row in reader:
                total += 1
                source_year = (
                    row[year_column].strip() if year_column < len(row) else ""
                )
                if source_year != str(year):
                    other_year_rows += 1
                    continue
                year_rows += 1
                raw_date = (
                    row[date_column].strip() if date_column < len(row) else ""
                )
                try:
                    parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                except ValueError:
                    invalid_dates += 1
                    continue
                if parsed_date.year != year:
                    date_year_mismatches += 1
                if parsed_date > reference_date:
                    future_dates += 1
                    continue
                monthly[parsed_date.strftime("%Y-%m")] += 1

        report[year] = {
            "arquivo": path.name,
            "bytes": path.stat().st_size,
            "linhas_total": total,
            "linhas_ano": year_rows,
            "linhas_outros_anos": other_year_rows,
            "datas_invalidas": invalid_dates,
            "ano_data_divergente": date_year_mismatches,
            "datas_futuras": future_dates,
            "meses": dict(sorted(monthly.items())),
        }

    return report


def _parse_reference_date(value: date | str | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError("--as-of deve usar o formato YYYY-MM-DD.") from error


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audita cobertura anual e mensal dos CSVs locais SINAN."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=RAW,
        help="Pasta com DENGBR23.csv até DENGBR26.csv.",
    )
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="Data de referência para contar notificações futuras (YYYY-MM-DD).",
    )
    args = parser.parse_args()

    report = auditar_fontes(args.data_dir, args.as_of)
    has_critical_issues = False
    for year, result in report.items():
        print(
            f"\n[{year}] {result['arquivo']}: {result['linhas_total']:,} linhas "
            f"totais; {result['linhas_ano']:,} com NU_ANO={year}; "
            f"{result['linhas_outros_anos']:,} de outros anos."
        )
        print(
            f"  Datas inválidas: {result['datas_invalidas']:,}; "
            f"ano da data divergente: {result['ano_data_divergente']:,}; "
            f"datas futuras: {result['datas_futuras']:,}."
        )
        for month, count in result["meses"].items():
            print(f"  {month}: {count:,}")
        if not result["linhas_ano"] or result["ano_data_divergente"]:
            has_critical_issues = True

    if has_critical_issues:
        raise SystemExit(
            "Auditoria encontrou fonte vazia ou divergência entre NU_ANO e DT_NOTIFIC."
        )


if __name__ == "__main__":
    main()
