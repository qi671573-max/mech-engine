"""
FastAPI 接口测试

依赖: pip install httpx fastapi
"""

import pytest

try:
    from fastapi.testclient import TestClient
    from app.api.main import app

    client = TestClient(app)
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


pytestmark = pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi not installed")


# ── /analyze ─────────────────────────────────────────────────────────────────


def test_analyze_geometry_only():
    resp = client.post("/analyze", json={
        "m_n": 3.0, "z1": 25, "z2": 75,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["pinion"]["d"] == pytest.approx(75.0, abs=0.1)
    assert data["wheel"]["d"] == pytest.approx(225.0, abs=0.1)
    assert data["pair"]["center_distance"] == pytest.approx(150.0, abs=0.1)
    assert data["strength"] is None


def test_analyze_with_strength():
    resp = client.post("/analyze", json={
        "m_n": 3.0, "z1": 25, "z2": 75,
        "b": 75.0, "power_kw": 5.5, "rpm": 960,
        "material_key": "45钢-调质",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["strength"] is not None
    assert data["strength"]["sigma_H"] > 0
    assert isinstance(data["strength"]["passed"], bool)


def test_analyze_helical():
    resp = client.post("/analyze", json={
        "m_n": 3.0, "z1": 25, "z2": 75,
        "beta_deg": 15.0, "gear_type": "helical",
    })
    assert resp.status_code == 200
    data = resp.json()
    # 斜齿轮端面模数 > 法向模数, 故分度圆直径 > 直齿
    assert data["pinion"]["d"] > 75.0


def test_analyze_unknown_material_returns_400():
    resp = client.post("/analyze", json={
        "m_n": 3.0, "z1": 25, "material_key": "火星合金",
    })
    assert resp.status_code == 400


# ── /parse ───────────────────────────────────────────────────────────────────


def test_parse_chinese():
    resp = client.post("/parse", json={"text": "直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["m_n"] == pytest.approx(3.0)
    assert data["z1"] == 20
    assert data["power_kw"] == pytest.approx(5.5)
    assert data["rpm"] == pytest.approx(960.0)


def test_parse_incomplete_returns_422():
    resp = client.post("/parse", json={"text": "功率5.5kW"})
    assert resp.status_code == 422


# ── /synthesize ───────────────────────────────────────────────────────────────


def test_synthesize_returns_proposals():
    resp = client.post("/synthesize", json={
        "power_kw": 5.5, "rpm": 960, "ratio": 3.2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for p in data:
        assert p["z1"] >= 17
        assert p["m_n"] > 0
        assert p["u_actual"] > 1.0


# ── /materials ────────────────────────────────────────────────────────────────


def test_materials_list():
    resp = client.get("/materials")
    assert resp.status_code == 200
    data = resp.json()
    assert "materials" in data
    assert len(data["materials"]) >= 8
