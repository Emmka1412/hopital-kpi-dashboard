"""Source publique optionnelle : lits de soins critiques par département (SAE, DREES).

Le fichier n'est pas versionné : il se télécharge depuis data.drees.solidarites-sante.gouv.fr
(voir ``data/external/README.md``). Le pipeline principal n'en dépend pas ; cette étape sert à
ancrer le projet dans une donnée réelle (contexte départemental des capacités de réanimation).

ATTENTION : les noms de colonnes du fichier réel n'ont pas pu être vérifiés au moment de l'écriture.
Les colonnes sont donc repérées par mots-clés (``SAE_KEYWORDS``). Si l'une est introuvable, l'erreur
liste les colonnes réellement présentes : ajuste alors ``SAE_KEYWORDS`` en conséquence.

Mêmes principes que ``clean.py`` : chaque règle est comptée, aucune ligne ne disparaît sans trace
(les lignes inutilisables vont dans ``reports/rejected_sae.csv`` avec leur motif).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .clean import QualityLog, normalise_text

# Mots-clés testés dans l'ordre, sur les noms de colonnes normalisés (minuscules, sans accents).
SAE_KEYWORDS = {
    "annee": ["annee", "millesime", "year"],
    "departement": ["code departement", "departement", "dep"],
    "nb_lits": ["nombre", "nb", "lits"],
}


def find_column(columns, keywords) -> str | None:
    normalised = {c: normalise_text(c) for c in columns}
    for keyword in keywords:
        for original, name in normalised.items():
            if keyword in name:
                return original
    return None


def clean_sae(raw: pd.DataFrame, log: QualityLog) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retourne (lignes propres, lignes rejetées avec motif). Colonnes de sortie : annee, departement, nb_lits + autres."""
    source = "sae_soins_critiques"
    mapping = {name: find_column(raw.columns, kw) for name, kw in SAE_KEYWORDS.items()}
    missing = [name for name, col in mapping.items() if col is None]
    if missing:
        raise ValueError(
            f"colonnes introuvables : {', '.join(missing)}. Colonnes présentes : {list(raw.columns)}. "
            "Ajuste SAE_KEYWORDS dans src/hkpi/sae.py."
        )
    df = raw.rename(columns={col: name for name, col in mapping.items()}).copy()
    n_raw = len(df)
    rejected: list[pd.DataFrame] = []

    dup = df.duplicated(keep="first")
    log.add(source, "ligne_en_double", int(dup.sum()), "supprimée (première occurrence conservée)")
    df = df[~dup].copy()

    df["annee"] = pd.to_numeric(df["annee"], errors="coerce")
    df["nb_lits"] = pd.to_numeric(df["nb_lits"], errors="coerce")
    df["departement"] = df["departement"].astype("string").str.strip()

    rules = [
        ("annee_illisible", lambda d: d["annee"].isna()),
        ("departement_manquant", lambda d: d["departement"].isna() | (d["departement"] == "")),
        ("nb_lits_illisible", lambda d: d["nb_lits"].isna()),
        ("nb_lits_negatif", lambda d: d["nb_lits"] < 0),
    ]
    for rule, condition in rules:
        mask = condition(df).fillna(False)  # recalculé sur les lignes restantes, jamais sur un index périmé
        if mask.any():
            rejected.append(df[mask].assign(motif_rejet=rule))
            log.add(source, rule, int(mask.sum()), "rejeté (quarantaine)")
            df = df[~mask]

    df["annee"] = df["annee"].astype(int)
    rejected_df = pd.concat(rejected) if rejected else pd.DataFrame(columns=[*raw.columns, "motif_rejet"])
    log.set_counts(source, n_raw, int(dup.sum()), len(rejected_df), len(df))
    return df.reset_index(drop=True), rejected_df


def load_sae(path: Path) -> pd.DataFrame:
    # Les exports Opendatasoft sont en général en UTF-8 avec « ; » ; le séparateur est détecté.
    return pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")


def run(source: Path, out_dir: Path, reports_dir: Path) -> pd.DataFrame:
    log = QualityLog()
    clean, rejected = clean_sae(load_sae(source), log)
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    clean.to_csv(out_dir / "ref_soins_critiques.csv", index=False)
    rejected.to_csv(reports_dir / "rejected_sae.csv", index=False)
    log.to_frame().to_csv(reports_dir / "anomalies_sae.csv", index=False)
    return clean


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="source", default="data/external/lits_soins_critiques.csv")
    parser.add_argument("--out", default="data/processed")
    parser.add_argument("--reports", default="reports")
    args = parser.parse_args(argv)
    source = Path(args.source)
    if not source.exists():
        print(f"Fichier absent : {source}. Voir data/external/README.md pour le télécharger (étape optionnelle).")
        return
    clean = run(source, Path(args.out), Path(args.reports))
    print(f"{len(clean)} lignes propres écrites dans {args.out}/ref_soins_critiques.csv")


if __name__ == "__main__":
    main()
