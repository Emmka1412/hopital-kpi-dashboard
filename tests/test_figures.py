from hkpi import analysis, figures, generate, pipeline


def test_figures_are_rendered_from_a_fresh_run(tmp_path):
    generate.main(["--out", str(tmp_path / "raw"), "--scale", "0.1", "--seed", "11"])
    pipeline.run(tmp_path / "raw", tmp_path / "processed", tmp_path / "reports")
    analysis.run(tmp_path / "processed", tmp_path / "reports")
    files = figures.run(tmp_path / "processed", tmp_path / "reports", tmp_path / "img")
    assert [f.name for f in files] == ["01-vue-ensemble.png", "02-consultations.png", "03-qualite.png", "04-prevision.png"]
    assert all(f.stat().st_size > 10_000 for f in files)
