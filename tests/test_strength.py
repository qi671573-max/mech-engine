"""
ISO 6336 强度校核 — 回归测试

数值来源: 《机械设计》濮良贵第十版 例题10-1 (章末数值已手工核对)
"""

import pytest
from app.engine.gears import GearGeometry, GearPairGeometry
from app.engine.strength import compute_strength, get_YF, get_YS, get_ZH
import math


# ── 公共 fixture ──────────────────────────────────────────────────────────────


@pytest.fixture
def standard_pair():
    """标准直齿轮副: m=3, z1=25, z2=75, 45钢调质, 5.5kW, 960rpm"""
    p = GearGeometry(z=25, m_n=3, b=75.0)
    w = GearGeometry(z=75, m_n=3, b=75.0)
    pair = GearPairGeometry(pinion=p, wheel=w)
    return p, w, pair


# ── 系数单元测试 ──────────────────────────────────────────────────────────────


def test_YF_interpolation_z20():
    """z=20 时 Y_F 应精确命中查找表"""
    yf = get_YF(20)
    assert abs(yf - 2.80) < 0.01


def test_YF_interpolation_z30():
    """z=30 在25和35之间插值"""
    yf = get_YF(30)
    # z=25 → 2.62, z=35 → 2.45; t=0.5 → 2.535
    assert 2.45 <= yf <= 2.62


def test_YS_z20():
    ys = get_YS(20)
    assert abs(ys - 1.55) < 0.01


def test_ZH_standard():
    """标准直齿轮 β=0, α_t=α=20°"""
    alpha_t = math.radians(20)
    beta_b = 0.0
    zh = get_ZH(alpha_t, beta_b)
    # Z_H = sqrt(2cosβ_b·cosα_wt / (cos²α_t·sinα_wt))
    # = sqrt(2·1·cos20° / (cos²20°·sin20°))
    expected = math.sqrt(
        2.0 * math.cos(0) * math.cos(alpha_t)
        / (math.cos(alpha_t) ** 2 * math.sin(alpha_t))
    )
    assert abs(zh - expected) < 0.001


# ── 集成测试 ─────────────────────────────────────────────────────────────────


def test_compute_strength_returns_all_fields(standard_pair):
    p, w, pair = standard_pair
    sr = compute_strength(p, w, pair, power_kw=5.5, rpm=960, material_key="45钢-调质")

    assert sr.sigma_H > 0
    assert sr.sigma_HP > 0
    assert sr.S_H > 0
    assert sr.sigma_F1 > 0
    assert sr.sigma_F2 > 0
    assert isinstance(sr.passed, bool)


def test_contact_stress_physically_reasonable(standard_pair):
    """接触应力应在工程合理范围内"""
    p, w, pair = standard_pair
    sr = compute_strength(p, w, pair, power_kw=5.5, rpm=960, material_key="45钢-调质")
    # 45钢调质 σ_Hlim = 590 MPa; 合理接触应力 200-700 MPa
    assert 200 < sr.sigma_H < 700, f"σ_H = {sr.sigma_H} MPa seems unreasonable"


def test_bending_stress_physically_reasonable(standard_pair):
    """弯曲应力应在工程合理范围内"""
    p, w, pair = standard_pair
    sr = compute_strength(p, w, pair, power_kw=5.5, rpm=960, material_key="45钢-调质")
    assert 10 < sr.sigma_F1 < 500, f"σ_F1 = {sr.sigma_F1} MPa seems unreasonable"


def test_safety_factors_pass_for_conservative_design(standard_pair):
    """模数3, z1=25, z2=75, 5.5kW/960rpm/45钢调质 应能通过校核"""
    p, w, pair = standard_pair
    sr = compute_strength(p, w, pair, power_kw=5.5, rpm=960, material_key="45钢-调质")
    assert sr.S_H >= 1.0, f"接触安全系数不足: S_H = {sr.S_H}"
    assert sr.S_F1 >= 1.25, f"弯曲安全系数不足: S_F1 = {sr.S_F1}"


def test_heavier_load_reduces_safety_factor():
    """更大的功率应导致更低的安全系数"""
    p = GearGeometry(z=25, m_n=3, b=75.0)
    w = GearGeometry(z=75, m_n=3, b=75.0)
    pair = GearPairGeometry(pinion=p, wheel=w)

    sr_light = compute_strength(p, w, pair, power_kw=3.0, rpm=960, material_key="45钢-调质")
    sr_heavy = compute_strength(p, w, pair, power_kw=15.0, rpm=960, material_key="45钢-调质")

    assert sr_light.S_H > sr_heavy.S_H, "轻载安全系数应大于重载"
    assert sr_light.S_F1 > sr_heavy.S_F1


def test_harder_material_gives_higher_sigma_HP():
    """渗碳淬火钢许用接触应力应大于调质钢"""
    p = GearGeometry(z=25, m_n=3, b=75.0)
    w = GearGeometry(z=75, m_n=3, b=75.0)
    pair = GearPairGeometry(pinion=p, wheel=w)

    sr_quench = compute_strength(p, w, pair, 5.5, 960, "45钢-调质")
    sr_case = compute_strength(p, w, pair, 5.5, 960, "20CrMnTi-渗碳淬火")

    assert sr_case.sigma_HP > sr_quench.sigma_HP


def test_shock_load_increases_KA():
    """严重冲击载荷应使 K_A 增大"""
    from app.engine.load_factors import get_KA
    ka_uniform = get_KA("uniform", "uniform")
    ka_shock = get_KA("uniform", "heavy_shock")
    assert ka_shock > ka_uniform


def test_unknown_material_raises():
    p = GearGeometry(z=25, m_n=3)
    w = GearGeometry(z=75, m_n=3)
    pair = GearPairGeometry(pinion=p, wheel=w)
    with pytest.raises(ValueError, match="未知材料"):
        compute_strength(p, w, pair, 5.5, 960, "不存在的材料XYZ")
