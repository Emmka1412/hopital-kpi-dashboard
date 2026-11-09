"""Écriture du rapport qualité (Markdown + CSV) et des fichiers de quarantaine."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .clean import QualityLog


def _n(value: int) -> str:
    """Nombre avec espace comme séparateur de milliers (usage français)."""
    return f"{value:,}".replace(",", " ")


def write_reports(log: QualityLog, rejected: dict[str, pd.DataFrame], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    anomalies = log.to_frame()
    anomalies.to_csv(reports_dir / "anomalies.csv", index=False)
    for name, df in rejected.items():
        df.to_csv(reports_dir / f"rejected_{name}.csv", index=False)

    lines = ["# Rapport qualité des données", "", "Généré automatiquement par `python -m hkpi.pipeline`.", ""]
    lines += ["## Volumétrie par source", ""]
    lines += ["| Source | Lignes brutes | Doublons supprimés | Lignes rejetées | Lignes propres | Part conservée |", "|---|---:|---:|---:|---:|---:|"]
    for source, c in log.counts.items():
        kept = 100 * c["propres"] / c["brutes"] if c["brutes"] else 0
        lines.append(f"| {source} | {_n(c['brutes'])} | {_n(c['doublons'])} | {_n(c['rejetees'])} | {_n(c['propres'])} | {kept:.1f} % |")
    lines += ["", "## Anomalies détectées et traitement", ""]
    lines += ["| Source | Règle | Nombre | % des lignes brutes | Traitement |", "|---|---|---:|---:|---|"]
    for row in anomalies.itertuples():
        total = log.counts[row.source]["brutes"]
        lines.append(f"| {row.source} | {row.regle} | {_n(row.nombre)} | {100 * row.nombre / total:.2f} % | {row.traitement} |")
    lines += [
        "",
        "## Lecture",
        "",
        "- **Corrigé** : normalisation (formats de dates, libellés de services, identifiants patients, sexe, modes d'entrée/sortie).",
        "- **Conservé avec valeur vide** : l'information manquante ou aberrante est vidée, la ligne reste exploitable pour les autres indicateurs.",
        "- **Rejeté** : la ligne ne peut pas être utilisée de façon fiable ; elle est écrite dans `reports/rejected_*.csv` avec son motif.",
        "- Contrôle de cohérence : lignes brutes = doublons + rejetées + propres (vérifié par les tests).",
        "",
    ]
    (reports_dir / "quality_report.md").write_text("\n".join(lines), encoding="utf-8")
