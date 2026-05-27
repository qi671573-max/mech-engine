"""
齿轮几何计算 — 验证测试

每个测试用例标注了数据来源和手工验证过程。
"""

import math
from app.engine.gears import GearGeometry, GearPairGeometry


def test_spur_gear_basic():
    """直齿轮基本几何 — 手工可验证
    z=20, m=3, α=20°, ha*=1, c*=0.25
    所有值均可从分度圆公式直接推导。
    """
    g = GearGeometry(z=20, m_n=3)

    assert g.d == 60.0, f"d = m·z = 3×20 = 60, got {g.d}"  # noqa: E702
    assert g.da == 66.0, f"da = m(z+2) = 3×22 = 66, got {g.da}"  # noqa: E702
    assert g.df == 52.5, f"df = m(z-2.5) = 3×17.5 = 52.5, got {g.df}"  # noqa: E702

    # db = m·z·cos(20°) = 60 × 0.9396926 = 56.3816
    assert abs(g.db - 56.3816) < 0.01, f"db expected 56.3816, got {g.db}"

    # inv(20°) = tan(20°) - 20°×π/180
    inv20 = math.tan(math.radians(20)) - math.radians(20)
    assert abs(inv20 - 0.01490438) < 1e-6, f"inv(20°) = {inv20}"

    # k = round(z/9 + 0.5) = round(20/9 + 0.5) = round(2.722) = 3
    assert g.k_span == 3, f"k expected 3, got {g.k_span}"

    # Wk = m·cosα[π(k-0.5) + z·invα]
    #    = 3 × 0.939693 × [π×2.5 + 20×0.014904]
    #    = 2.81908 × [7.85398 + 0.29809]
    #    = 2.81908 × 8.15207
    #    = 22.987
    wk_expected = 3 * math.cos(math.radians(20)) * (
        math.pi * 2.5 + 20 * inv20
    )
    assert abs(g.base_tangent_length - wk_expected) < 0.01, \
        f"Wk expected {wk_expected:.3f}, got {g.base_tangent_length}"


def test_gear_pair():
    """齿轮副 — z1=25, z2=75, m=3"""
    p = GearGeometry(z=25, m_n=3)
    w = GearGeometry(z=75, m_n=3)
    pair = GearPairGeometry(pinion=p, wheel=w)

    # 中心距 a = m(z1+z2)/2 = 3×100/2 = 150
    assert abs(pair.a - 150.0) < 0.01, f"a expected 150, got {pair.a}"

    # 齿数比 u = 75/25 = 3
    assert abs(pair.u - 3.0) < 0.001

    # 重合度精确公式:
    # α_a1 = arccos(db1/da1), α_a2 = arccos(db2/da2)
    # ε = [25×(tan(α_a1)-tan20°) + 75×(tan(α_a2)-tan20°)] / (2π)
    alpha_t = math.radians(20)
    alpha_a1 = math.acos(p.db / p.da)
    alpha_a2 = math.acos(w.db / w.da)
    eps = (25 * (math.tan(alpha_a1) - math.tan(alpha_t))
           + 75 * (math.tan(alpha_a2) - math.tan(alpha_t))) / (2 * math.pi)
    assert abs(pair.epsilon_alpha - eps) < 0.001, \
        f"ε expected {eps:.4f}, got {pair.epsilon_alpha}"

    # 近似公式: ε ≈ 1.88 - 3.2(1/25 + 1/75) = 1.88 - 0.1707 = 1.709
    eps_approx = 1.88 - 3.2 * (1/25 + 1/75)
    assert 1.65 < pair.epsilon_alpha < 1.80, \
        f"ε should be near {eps_approx:.3f}, got {pair.epsilon_alpha}"


def test_helical_gear():
    """斜齿轮: z=30, m_n=3, β=15°"""
    g = GearGeometry(z=30, m_n=3, beta_deg=15)

    # mt = mn/cosβ = 3/0.965926 = 3.1058
    assert abs(g.m_t - 3.1058) < 0.01, f"mt expected 3.106, got {g.m_t}"

    # d = mt × z = 3.1058 × 30 = 93.174
    assert abs(g.d - 93.174) < 0.1

    # αt = arctan(tan(20°)/cos(15°)) = arctan(0.36397/0.96593) = arctan(0.3768) = 20.647°
    alpha_t_expected = math.atan(math.tan(math.radians(20)) / math.cos(math.radians(15)))
    assert abs(g.alpha_t_rad - alpha_t_expected) < 0.001

    # zv = z/cos³(β) = 30/0.9019 = 33.26
    assert abs(g.z_v - 33.26) < 0.1

    assert g.is_helical, "β=15° should be helical"


def test_small_gear_boundary():
    """z=17 — 根切临界齿数"""
    g = GearGeometry(z=17, m_n=2)

    # db = 2×17×cos20° = 31.949
    # df = 2×(17-2.5) = 29.0
    # db > df: 基圆在齿根圆之上, 渐开线从基圆开始
    assert g.db > g.df, f"z=17: db({g.db:.3f}) should be > df({g.df:.3f})"


def test_large_gear_boundary():
    """z=100 — 基圆 < 齿根圆"""
    g = GearGeometry(z=100, m_n=1)

    # db = 1×100×cos20° = 93.969
    # df = 1×(100-2.5) = 97.5
    # db < df: 齿根部分是非渐开线
    assert g.db < g.df, f"z=100: db({g.db:.3f}) should be < df({g.df:.3f})"


def test_profile_shift():
    """正变位: z=15, m=3, x=+0.3"""
    g = GearGeometry(z=15, m_n=3, x=0.3)

    # 变位增大齿顶高: ha = (ha*+x)m = 1.3×3 = 3.9
    # da = d + 2ha = 45 + 7.8 = 52.8
    assert abs(g.ha - 3.9) < 0.01
    assert abs(g.da - 52.8) < 0.01

    # 分度圆齿厚: s = πm/2 + 2xm·tanα = 4.7124 + 2×0.3×3×0.36397 = 4.7124 + 0.6551 = 5.3676
    s_expected = math.pi * 3 / 2 + 2 * 0.3 * 3 * math.tan(math.radians(20))
    assert abs(g.s - s_expected) < 0.01
