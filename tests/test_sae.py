"""Tests de l'ingestion SAE sur un jeu construit à la main.

Ce jeu imite la structure décrite par la DREES (année, département, type de lits, nombre de lits) ;
les noms de colonnes sont inventés pour le test et ne prouvent rien sur le fichier réel.
"""

import pandas as pd
import pytest

from hkpi import sae
from hkpi.clean import QualityLog


def _raw():
    return pd.DataFrame(
        {
            "Année": [2023, 2023, 2023, 2023, "x", 2022],
            "Code département": ["75", "75", "69", "", "13", "33"],
            "Type de lits": ["Réanimation adulte", "Réanimation adulte", "Soins intensifs", "Soins intensifs", "Réanimation", "Réanimation"],
            "Nombre de lits": [120, 120, 45, 10, 8, -3],
        }
    )


def test_find_column_prefers_the_number_over_the_type_of_beds():
    cols = ["Année", "Code département", "Type de lits", "Nombre de lits"]
    assert sae.find_column(cols, sae.SAE_KEYWORDS["nb_lits"]) == "Nombre de lits"
    assert sae.find_column(cols, sae.SAE_KEYWORDS["departement"]) == "Code département"


def test_clean_sae_counts_every_row_and_quarantines_with_a_reason():
    log = QualityLog()
    clean, rejected = sae.clean_sae(_raw(), log)
    c = log.counts["sae_soins_critiques"]
    assert c["brutes"] == c["doublons"] + c["rejetees"] + c["propres"] == 6
    assert len(clean) == 2 and c["doublons"] == 1
    assert set(rejected["motif_rejet"]) == {"annee_illisible", "departement_manquant", "nb_lits_negatif"}
    assert clean["annee"].dtype.kind == "i"


def test_unknown_columns_raise_a_message_that_lists_the_real_ones():
    with pytest.raises(ValueError) as err:
        sae.clean_sae(pd.DataFrame({"a": [1], "b": [2]}), QualityLog())
    assert "Colonnes présentes" in str(err.value) and "SAE_KEYWORDS" in str(err.value)


def test_main_without_the_file_is_a_polite_no_op(tmp_path, capsys):
    sae.main(["--in", str(tmp_path / "absent.csv"), "--out", str(tmp_path), "--reports", str(tmp_path)])
    assert "Fichier absent" in capsys.readouterr().out
