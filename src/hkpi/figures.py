"""Aperçus du tableau de bord en PNG (docs/img), rendus avec matplotlib à partir des tables du modèle.

Ces images montrent les mêmes indicateurs que les mesures DAX de ``powerbi/measures.dax`` ; ce n'est PAS
le rapport Power BI (le ``.pbix`` se construit avec ``powerbi/GUIDE.md``). Elles servent d'aperçu dans le README
et permettent de vérifier visuellement les chiffres avant de construire le rapport.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .analysis import SEUIL_SATURATION, SEUIL_TENSION, fr, monthly_admissions  # noqa: E402
from .forecast import backtest, seasonal_naive  # noqa: E402

# Palette de référence (clair) : bleu, orange, turquoise ; encre primaire/secondaire sur fond clair.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#a8a79f"
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]

plt.rcParams.update(
    {
        "font.family": ["Carlito", "DejaVu Sans"],
        "font.size": 11,
        "axes.facecolor": SURFACE,
        "figure.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "text.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _title(fig, title: str, subtitle: str) -> None:
    fig.text(0.04, 0.955, title, fontsize=21, fontweight="bold", va="top")
    fig.text(0.04, 0.915, subtitle, fontsize=11.5, color=INK2, va="top")


def _footer(fig, text: str = "Aperçu généré par Python (hkpi.figures) · données synthétiques · mêmes KPI que powerbi/measures.dax") -> None:
    fig.text(0.04, 0.012, text, fontsize=9, color=INK2)


def _panel_title(ax, text: str) -> None:
    ax.set_title(text, loc="left", fontsize=12.5, fontweight="bold", color=INK, pad=10)


def _tile(ax, label: str, value: str, note: str = "") -> None:
    ax.set_axis_off()
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, facecolor="white", edgecolor=GRID, lw=1.2))
    ax.text(0.06, 0.74, label, transform=ax.transAxes, fontsize=11, color=INK2)
    ax.text(0.06, 0.36, value, transform=ax.transAxes, fontsize=26, fontweight="bold", color=INK)
    if note:
        ax.text(0.06, 0.10, note, transform=ax.transAxes, fontsize=9.5, color=INK2)


def _hbar(ax, labels, values, color, fmt, xmax=None) -> None:
    y = np.arange(len(labels))
    ax.barh(y, values, color=color, height=0.55)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.tick_params(axis="y", length=0)
    top = xmax or max(values) * 1.18
    ax.set_xlim(0, top)
    for yi, v in zip(y, values):
        ax.text(v + top * 0.012, yi, fmt(v), va="center", fontsize=10.5, color=INK)


def _indent(ax, dx: float) -> None:
    """Décale le bord gauche d'un graphique pour laisser la place à de longs libellés."""
    pos = ax.get_position()
    ax.set_position([pos.x0 + dx, pos.y0, pos.width - dx, pos.height])


def _load(processed: Path):
    kpi = pd.read_csv(processed / "kpi_monthly_service.csv", parse_dates=["mois_debut"])
    services = pd.read_csv(processed / "dim_service.csv")
    adm = pd.read_csv(processed / "fact_admission.csv")
    cons = pd.read_csv(processed / "fact_consultation.csv", parse_dates=["date_rdv"])
    return kpi, services, adm, cons


def fig_overview(kpi, services, adm, out: Path) -> None:
    names = services.set_index("code_service")["libelle"]
    fig = plt.figure(figsize=(16, 10), dpi=100)
    _title(fig, "Vue d'ensemble de l'activité", "Hospitalisation, 2024-2025 · tous services")
    gs = fig.add_gridspec(3, 4, left=0.04, right=0.97, top=0.86, bottom=0.07, hspace=0.55, wspace=0.28, height_ratios=[0.55, 1.5, 1.5])

    done = adm["duree_sejour_j"].dropna()
    occ_den = kpi["jours_lit_disponibles"].sum()
    occ = kpi["jours_lit_occupes"].sum() / occ_den
    abs_rate = kpi["nb_absents"].sum() / kpi["nb_rdv"].sum()
    for i, (lab, val, note) in enumerate(
        [
            ("Admissions", fr(len(adm), 0), "séjours nettoyés"),
            ("Durée moyenne de séjour", f"{fr(done.mean(), 1)} j", f"{fr(len(done), 0)} séjours terminés"),
            ("Taux d'occupation", f"{fr(100 * occ, 1)} %", "jours-lits occupés / disponibles"),
            ("Taux d'absence en consultation", f"{fr(100 * abs_rate, 1)} %", "absents / rendez-vous"),
        ]
    ):
        _tile(fig.add_subplot(gs[0, i]), lab, val, note)

    # Admissions par mois civil : année en cours contre année précédente (mesure « Admissions N-1 »)
    ax = fig.add_subplot(gs[1, :2])
    y = monthly_admissions(kpi)
    last_year, prev_year = y.index[-1].year, y.index[-1].year - 1
    cur = y[y.index.year == last_year].to_numpy()
    prev = y[y.index.year == prev_year].to_numpy()
    x = np.arange(1, 13)
    ax.plot(x, prev, color=ORANGE, lw=2, marker="o", ms=5, mec=SURFACE, mew=1.5)
    ax.plot(x, cur, color=BLUE, lw=2, marker="o", ms=5, mec=SURFACE, mew=1.5)
    ax.annotate(str(last_year), (x[0], cur[0]), xytext=(0, 12), textcoords="offset points", color=BLUE, fontsize=11, fontweight="bold", ha="center")
    ax.annotate(str(prev_year), (x[0], prev[0]), xytext=(0, -20), textcoords="offset points", color=ORANGE, fontsize=11, fontweight="bold", ha="center")
    ax.set_xticks(x, MOIS, fontsize=9.5)
    ax.set_xlim(0.7, 12.4)
    ax.set_ylim(min(cur.min(), prev.min()) * 0.85, max(cur.max(), prev.max()) * 1.1)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    _panel_title(ax, f"Admissions par mois : {last_year} contre {prev_year}")

    ax = fig.add_subplot(gs[1, 2:])
    by_service = adm.groupby("service_code").size().sort_values(ascending=False)
    _hbar(ax, [names[c] for c in by_service.index], by_service.to_numpy(), BLUE, lambda v: fr(v, 0))
    _panel_title(ax, "Admissions par service")

    ax = fig.add_subplot(gs[2, :2])
    k = kpi.dropna(subset=["jours_lit_disponibles"])
    k = k[k["jours_lit_disponibles"] > 0].groupby("service_code")[["jours_lit_occupes", "jours_lit_disponibles"]].sum()
    occ_s = (k["jours_lit_occupes"] / k["jours_lit_disponibles"]).sort_values(ascending=False)
    _hbar(ax, [names[c] for c in occ_s.index], 100 * occ_s.to_numpy(), BLUE, lambda v: f"{fr(v, 1)} %", xmax=110)
    for seuil, lab, ha in [(SEUIL_TENSION, "tension 80 %", "right"), (SEUIL_SATURATION, "saturation 90 %", "left")]:
        ax.axvline(100 * seuil, color=GREY, lw=1, ls=(0, (4, 3)))
        ax.text(100 * seuil + (-1 if ha == "right" else 1), -0.62, lab, fontsize=9, color=INK2, ha=ha)
    _indent(ax, 0.09)
    _panel_title(ax, "Taux d'occupation par service")

    ax = fig.add_subplot(gs[2, 2:])
    dms = adm.dropna(subset=["duree_sejour_j"]).groupby("service_code")["duree_sejour_j"].mean().sort_values(ascending=False)
    _hbar(ax, [names[c] for c in dms.index], dms.to_numpy(), BLUE, lambda v: f"{fr(v, 1)} j")
    _panel_title(ax, "Durée moyenne de séjour par service")
    _footer(fig)
    fig.savefig(out / "01-vue-ensemble.png")
    plt.close(fig)


def fig_consultations(kpi, services, cons, out: Path) -> None:
    names = services.set_index("code_service")["libelle"]
    fig = plt.figure(figsize=(16, 9), dpi=100)
    _title(fig, "Consultations", "Rendez-vous par statut et taux d'absence, 2024-2025")
    gs = fig.add_gridspec(2, 3, left=0.04, right=0.97, top=0.86, bottom=0.08, hspace=0.45, wspace=0.28, height_ratios=[0.45, 2.2])
    n = len(cons)
    honored = cons.loc[cons["statut"] == "Honoré", "duree_min"].dropna()
    for i, (lab, val, note) in enumerate(
        [
            ("Rendez-vous", fr(n, 0), "après dédoublonnage"),
            ("Taux d'absence", f"{fr(100 * (cons['statut'] == 'Absent').mean(), 1)} %", "absents / rendez-vous"),
            ("Durée moyenne de consultation", f"{fr(honored.mean(), 1)} min", "rendez-vous honorés, durée renseignée"),
        ]
    ):
        _tile(fig.add_subplot(gs[0, i]), lab, val, note)

    ax = fig.add_subplot(gs[1, :2])
    monthly = cons.assign(mois=cons["date_rdv"].dt.to_period("M").dt.to_timestamp()).groupby(["mois", "statut"]).size().unstack(fill_value=0)
    bottom = np.zeros(len(monthly))
    x = np.arange(len(monthly))
    for statut, color in [("Honoré", BLUE), ("Absent", ORANGE), ("Annulé", GREY)]:
        ax.bar(x, monthly[statut], bottom=bottom, color=color, width=0.78, edgecolor=SURFACE, linewidth=1.5, label=statut)
        bottom += monthly[statut].to_numpy()
    labels = [f"{MOIS[d.month - 1]}\n{d.year}" if d.month == 1 else MOIS[d.month - 1] for d in monthly.index]
    ax.set_xticks(x, labels, fontsize=9)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, 1.0), fontsize=10.5)
    ax.set_ylim(0, bottom.max() * 1.18)
    _panel_title(ax, "Rendez-vous par mois et par statut")

    ax = fig.add_subplot(gs[1, 2])
    g = kpi[kpi["nb_rdv"] > 0].groupby("service_code")[["nb_absents", "nb_rdv"]].sum()
    rate = (100 * g["nb_absents"] / g["nb_rdv"]).sort_values(ascending=False)
    _hbar(ax, [names[c] for c in rate.index], rate.to_numpy(), BLUE, lambda v: f"{fr(v, 1)} %", xmax=14)
    _panel_title(ax, "Taux d'absence par service")
    _footer(fig)
    fig.savefig(out / "02-consultations.png")
    plt.close(fig)


def _read_volumetry(report: Path) -> pd.DataFrame:
    rows = []
    for line in report.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(admissions|consultations|services)\s*\|\s*([\d  ]+)\|\s*([\d  ]+)\|\s*([\d  ]+)\|\s*([\d  ]+)\|", line)
        if m:
            rows.append([m.group(1)] + [int(re.sub(r"\D", "", g)) for g in m.groups()[1:]])
    return pd.DataFrame(rows, columns=["source", "brutes", "doublons", "rejetees", "propres"])


def fig_quality(reports: Path, out: Path) -> None:
    anomalies = pd.read_csv(reports / "anomalies.csv")
    vol = _read_volumetry(reports / "quality_report.md")
    fig = plt.figure(figsize=(16, 9), dpi=100)
    _title(fig, "Qualité des données", "Ce que le nettoyage a détecté, et ce qu'il en a fait : aucune ligne n'est supprimée sans trace")
    gs = fig.add_gridspec(2, 3, left=0.04, right=0.97, top=0.86, bottom=0.08, hspace=0.45, wspace=0.28, height_ratios=[0.45, 2.2])
    for i, r in enumerate(vol[vol["source"] != "services"].itertuples()):
        _tile(fig.add_subplot(gs[0, i]), f"Lignes {r.source}", f"{fr(r.brutes, 0)} brutes", f"{fr(r.propres, 0)} propres · {fr(r.doublons, 0)} doublons · {fr(r.rejetees, 0)} rejetées")
    classes = {"rejeté": ("Rejeté (quarantaine)", ORANGE), "supprimé": ("Doublon supprimé", BLUE), "conservé": ("Conservé, valeur vidée ou exclue", GREY), "vidée": ("Conservé, valeur vidée ou exclue", GREY), "ignorée": ("Conservé, valeur vidée ou exclue", GREY)}

    def klass(t: str):
        return next(v for k, v in classes.items() if t.startswith(k) or k in t)

    ax = fig.add_subplot(gs[1, :])
    a = anomalies.sort_values("nombre", ascending=False).reset_index(drop=True)
    labels = [f"{r.source} · {r.regle}" for r in a.itertuples()]
    colors = [klass(t)[1] for t in a["traitement"]]
    y = np.arange(len(a))
    ax.barh(y, a["nombre"], color=colors, height=0.6)
    ax.set_yticks(y, labels, fontsize=10.5)
    ax.invert_yaxis()
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    top = a["nombre"].max() * 1.5
    ax.set_xlim(0, top)
    for yi, r in zip(y, a.itertuples()):
        ax.text(r.nombre + top * 0.01, yi, f"{fr(r.nombre, 0)} · {r.traitement}", va="center", fontsize=10, color=INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (BLUE, ORANGE, GREY)]
    ax.legend(handles, ["Doublon supprimé", "Rejeté (quarantaine)", "Conservé, valeur vidée ou exclue"], frameon=False, loc="lower right", fontsize=10.5)
    _indent(ax, 0.2)
    _panel_title(ax, "Anomalies par règle")
    _footer(fig)
    fig.savefig(out / "03-qualite.png")
    plt.close(fig)


def fig_forecast(kpi, out: Path, horizon: int = 3) -> None:
    y = monthly_admissions(kpi)
    fc = seasonal_naive(y, horizon, growth=True)
    bt = backtest(y, horizon)
    mae_n, mae_s = bt["mae_naif"].mean(), bt["mae_saisonnier"].mean()
    fig = plt.figure(figsize=(16, 8), dpi=100)
    _title(fig, "Prévision des admissions à 3 mois", "Méthode saisonnière naïve corrigée de la croissance, validée par un backtest à origine glissante")
    gs = fig.add_gridspec(2, 4, left=0.04, right=0.97, top=0.82, bottom=0.12, wspace=0.3, hspace=0.35)
    ax = fig.add_subplot(gs[:, :3])
    ax.plot(y.index, y.to_numpy(), color=BLUE, lw=2, marker="o", ms=5, mec=SURFACE, mew=1.5)
    ax.plot([y.index[-1], *fc.index], [y.iloc[-1], *fc.to_numpy()], color=ORANGE, lw=2, ls=(0, (5, 3)), marker="o", ms=5, mec=SURFACE, mew=1.5)
    ax.fill_between(fc.index, fc.to_numpy() - mae_s, fc.to_numpy() + mae_s, color=ORANGE, alpha=0.15, lw=0)
    ax.annotate("Historique", (y.index[5], y.iloc[5]), xytext=(0, -26), textcoords="offset points", color=BLUE, fontsize=11, fontweight="bold", ha="center")
    ax.annotate("Prévision ± erreur du backtest", (fc.index[1], fc.max() + mae_s), xytext=(0, 12), textcoords="offset points", color=ORANGE, fontsize=11, fontweight="bold", ha="center")
    ticks = y.index.append(fc.index)[::3]
    ax.set_xticks(ticks, [f"{MOIS[d.month - 1]} {d.year}" for d in ticks], fontsize=9.5)
    ax.set_ylim(min(y.min(), fc.min() - mae_s) * 0.9, max(y.max(), fc.max() + mae_s) * 1.08)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    _panel_title(ax, "Admissions mensuelles, tous services")
    _tile(fig.add_subplot(gs[0, 3]), "Erreur, méthode naïve", f"{fr(mae_n, 0)} adm./mois", f"{fr(100 * mae_n / y.mean(), 1)} % du niveau moyen · répète le dernier mois")
    _tile(fig.add_subplot(gs[1, 3]), "Erreur, méthode saisonnière", f"{fr(mae_s, 0)} adm./mois", f"{fr(100 * mae_s / y.mean(), 1)} % du niveau moyen · mêmes mois de l'an passé")
    fig.text(0.04, 0.045, "Prévision : " + " · ".join(f"{MOIS[d.month - 1]} {d.year} : {fr(v, 0)}" for d, v in fc.items()), fontsize=11, color=INK)
    _footer(fig, "Données synthétiques : la saisonnalité est codée dans le générateur ; la validation porte sur la méthode, pas sur un phénomène réel.")
    fig.savefig(out / "04-prevision.png")
    plt.close(fig)


def run(processed: Path, reports: Path, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    kpi, services, adm, cons = _load(processed)
    fig_overview(kpi, services, adm, out)
    fig_consultations(kpi, services, cons, out)
    fig_quality(reports, out)
    fig_forecast(kpi, out)
    return sorted(out.glob("0*.png"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--processed", default="data/processed")
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--out", default="docs/img")
    args = parser.parse_args(argv)
    files = run(Path(args.processed), Path(args.reports), Path(args.out))
    print("Images écrites :", ", ".join(f.name for f in files))


if __name__ == "__main__":
    main()
