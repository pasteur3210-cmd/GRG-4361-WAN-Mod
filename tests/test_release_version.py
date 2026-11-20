from pathlib import Path


def test_release_version_consistency():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "GRG4361_WAN.spec").read_text(encoding="utf-8")
    main = (root / "main.py").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/build.yml").read_text(encoding="utf-8")
    version = "V1.1.1"
    assert f"name='GRG4361_WAN_Setting_{version}'" in spec
    assert f"WAN Setting Tool {version}" in main
    assert f"name: GRG4361_WAN_Setting_{version}" in workflow
    assert "V1.0.0" not in spec
