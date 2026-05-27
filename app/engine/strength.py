"""
ISO 6336 / GB/T 3480 齿轮强度校核引擎

实现齿面接触疲劳强度 (pitting) 和齿根弯曲疲劳强度计算。
所有计算使用 Method B (分析计算法)。

等课本例题交叉验证后将标注验证状态到各个系数函数。
"""

import math
from dataclasses import dataclass

from app.engine.gears import GearGeometry, GearPairGeometry, GearDesignInput, GearDesignResult
from app.engine.materials import (
    GearMaterial, STEEL_ZE, STEEL_ELASTIC_MODULUS,
    resolve_material,
)
from app.engine.load_factors import (
    get_KA, get_KV, get_KHbeta, get_KFbeta, get_KHalpha, get_KFalpha,
)


# ============================================================================
# 齿形系数 Y_F 和应力修正系数 Y_S 查找表
#
# 条件: 标准齿条型刀具 (α=20°, ha*=1, c*=0.25, ρ_f=0.38m_n)
#       变位系数 x = 0
# 来源: ISO 6336-3 Figure 4/5, GB/T 3480.3
# ============================================================================
YF_TABLE = [
    # (z_v, Y_F, Y_S)
    (17,   2.97,  1.52),
    (18,   2.91,  1.53),
    (19,   2.85,  1.54),
    (20,   2.80,  1.55),
    (22,   2.72,  1.57),
    (25,   2.62,  1.59),
    (28,   2.54,  1.61),
    (30,   2.52,  1.625),
    (35,   2.45,  1.65),
    (40,   2.40,  1.67),
    (45,   2.35,  1.68),
    (50,   2.32,  1.70),
    (60,   2.28,  1.73),
    (70,   2.24,  1.75),
    (80,   2.22,  1.77),
    (100,  2.18,  1.79),
    (150,  2.14,  1.82),
    (200,  2.12,  1.84),
    (400,  2.08,  1.90),
    (1000, 2.06,  1.97),
]


def _interp(zv: float, table: list[tuple[float, float, float]], col: int) -> float:
    """在查找表中线性插值"""
    if zv <= table[0][0]:
        return table[0][col]
    if zv >= table[-1][0]:
        return table[-1][col]
    for i in range(len(table) - 1):
        z1, v1, _ = table[i][0], table[i][1], table[i][2]
        z2, v2, _ = table[i + 1][0], table[i + 1][1], table[i + 1][2]
        if z1 <= zv <= z2:
            t = (zv - z1) / (z2 - z1)
            v1_val = v1 if col == 1 else table[i][col]
            v2_val = v2 if col == 1 else table[i + 1][col]
            return v1_val + t * (v2_val - v1_val)
    return table[-1][col]


def get_YF(z_v: float) -> float:
    """齿形系数 Y_F (载荷作用于齿顶)"""
    return _interp(z_v, YF_TABLE, 1)


def get_YS(z_v: float) -> float:
    """应力修正系数 Y_S"""
    return _interp(z_v, YF_TABLE, 2)


# ============================================================================
# 区域系数 Z_H
# ============================================================================
def get_ZH(
    alpha_t_rad: float,
    beta_b_rad: float,
    alpha_wt_rad: float | None = None,
) -> float:
    """区域系数 Z_H

    对于标准中心距安装 (α_wt = α_t):
      Z_H = √(2·cos(β_b) / (cos(α_t)·sin(α_t)))
    """
    if alpha_wt_rad is None:
        alpha_wt_rad = alpha_t_rad

    zh = math.sqrt(
        2.0 * math.cos(beta_b_rad) * math.cos(alpha_wt_rad)
        / (math.cos(alpha_t_rad) ** 2 * math.sin(alpha_wt_rad))
    )
    return zh


# ============================================================================
# 重合度系数 Z_ε
# ============================================================================
def get_Zepsilon(
    epsilon_alpha: float,
    epsilon_beta: float = 0.0,
) -> float:
    """重合度系数 Z_ε

    直齿轮 (ε_β < 1): Z_ε = √((4 - ε_α) / 3)
    斜齿轮 (ε_β ≥ 1): Z_ε = √(1 / ε_α)
    """
    if epsilon_beta < 1.0:
        return math.sqrt((4.0 - epsilon_alpha) / 3.0)
    else:
        return math.sqrt(1.0 / epsilon_alpha)


# ============================================================================
# 螺旋角系数 Z_β (接触强度)
# ============================================================================
def get_Zbeta(beta_rad: float) -> float:
    """螺旋角系数 Z_β = √(cos(β))"""
    return math.sqrt(math.cos(beta_rad))


# ============================================================================
# 螺旋角系数 Y_β (弯曲强度)
# ============================================================================
def get_Ybeta(
    beta_rad: float,
    epsilon_beta: float = 0.0,
) -> float:
    """螺旋角系数 Y_β

    Y_β = 1 - ε_β·β/120°  (β in degrees, min 0.75)
    对于直齿轮: Y_β = 1.0
    """
    if abs(beta_rad) < 0.001:
        return 1.0
    beta_deg = math.degrees(beta_rad)
    yb = 1.0 - epsilon_beta * abs(beta_deg) / 120.0
    return max(0.75, yb)


# ============================================================================
# 轮缘厚度系数 Y_B (简化: 实心齿轮 Y_B = 1.0)
# ============================================================================
def get_YB() -> float:
    return 1.0  # 实心齿轮 (s_R/h ≥ 1.2)


# ============================================================================
# 寿命系数 (简化, 按无限寿命)
# ============================================================================
def get_ZN() -> float:
    """接触强度寿命系数 Z_N (无限寿命 N ≥ N_C)"""
    return 1.0


def get_YN() -> float:
    """弯曲强度寿命系数 Y_N (无限寿命)"""
    return 1.0


# ============================================================================
# 润滑油膜影响系数 (简化, 标准条件)
# ============================================================================
def get_ZL() -> float: return 1.0   # 润滑剂系数
def get_ZV() -> float: return 1.0   # 速度系数
def get_ZR() -> float: return 1.0   # 粗糙度系数
def get_ZW() -> float: return 1.0   # 工作硬化系数


# ============================================================================
# 尺寸系数
# ============================================================================
def get_ZX(m_n: float, material_type: str = "quenched") -> float:
    """接触强度尺寸系数 Z_X"""
    if m_n < 5.0:
        return 1.0
    if material_type == "nitrided":
        return 1.067 - 0.056 * m_n
    elif material_type in ("case_hardened", "induction"):
        return max(1.0, 1.076 - 0.0109 * m_n)
    else:
        return 1.0  # 调质钢/结构钢 Z_X = 1.0


def get_YX(m_n: float, material_type: str = "quenched") -> float:
    """弯曲强度尺寸系数 Y_X"""
    if m_n < 5.0:
        return 1.0
    if material_type in ("quenched", "structural"):
        return 1.03 - 0.006 * m_n
    elif material_type in ("case_hardened",):
        return max(1.0, 1.05 - 0.01 * m_n)
    elif material_type == "cast_iron":
        return 1.075 - 0.015 * m_n
    else:
        return 1.0


# ============================================================================
# 相对齿根圆角敏感系数 & 相对齿根表面状况系数 (简化)
# ============================================================================
def get_YdeltaRelT() -> float: return 1.0
def get_YRrelT() -> float: return 1.0


# ============================================================================
# 强度计算主函数
# ============================================================================

@dataclass
class StrengthResult:
    """强度校核结果"""

    # 接触强度
    sigma_H: float          # 计算接触应力 (MPa)
    sigma_HP: float         # 许用接触应力 (MPa)
    S_H: float              # 接触安全系数
    S_Hmin: float           # 最小安全系数
    contact_pass: bool

    # 弯曲强度 (小齿轮)
    sigma_F1: float         # 小齿轮计算弯曲应力 (MPa)
    sigma_FP1: float        # 小齿轮许用弯曲应力 (MPa)
    S_F1: float             # 小齿轮弯曲安全系数

    # 弯曲强度 (大齿轮)
    sigma_F2: float         # 大齿轮计算弯曲应力 (MPa)
    sigma_FP2: float        # 大齿轮许用弯曲应力 (MPa)
    S_F2: float             # 大齿轮弯曲安全系数

    S_Fmin: float           # 最小弯曲安全系数
    bending_pass: bool

    # 总体
    passed: bool

    # 载荷系数 (记录以便报告展示)
    K_A: float = 1.0
    K_V: float = 1.0
    K_Hbeta: float = 1.0
    K_Halpha: float = 1.0
    K_Fbeta: float = 1.0
    K_Falpha: float = 1.0


def compute_strength(
    pinion: GearGeometry,
    wheel: GearGeometry,
    pair: GearPairGeometry,
    power_kw: float,
    rpm: float,
    material_key: str = "45钢-调质",
    accuracy_grade: int = 8,
    driver_type: str = "uniform",
    driven_type: str = "uniform",
    S_Hmin: float = 1.0,
    S_Fmin: float = 1.25,
) -> StrengthResult:
    """执行 ISO 6336 Method B 强度校核"""

    mat = resolve_material(material_key)
    if mat is None:
        raise ValueError(f"未知材料: {material_key}")

    # ---- 基本参数 ----
    z1, z2 = pinion.z, wheel.z
    m_n = pinion.m_n
    d1, d2 = pinion.d, wheel.d
    u = pair.u
    alpha_t = pinion.alpha_t_rad
    alpha_n = pinion.alpha_n_rad
    beta = pinion.beta_rad

    # 齿宽 (默认取 ψ_d = 1.0)
    if pinion.b is not None:
        b = pinion.b
    else:
        b = d1  # 默认 ψ_d ≈ 1.0

    # ---- 切向力 ----
    T1 = 9550.0 * power_kw / rpm  # 小齿轮转矩 (N·m)
    F_t = 2000.0 * T1 / d1        # 分度圆切向力 (N)

    # 节线速度
    v_ms = math.pi * d1 * rpm / 60000.0  # m/s

    # ---- 轴向重合度 (斜齿, 需在载荷系数之前计算) ----
    epsilon_beta = b * math.sin(abs(beta)) / (math.pi * m_n) if abs(beta) > 0.001 else 0.0

    # ---- 载荷系数 ----
    K_A = get_KA(driver_type, driven_type)

    # K_V 需要 z1 和 F_t/b (含这两个参数能更准确反映动载效应)
    F_t_per_b = F_t / b  # N/mm
    K_V = get_KV(v_ms, z1=z1, F_t_per_b=F_t_per_b, K_A=K_A, accuracy_grade=accuracy_grade)

    K_Hbeta = get_KHbeta(b, d1, accuracy_grade=accuracy_grade)

    # 总重合度 ε_γ (直齿: ε_γ=ε_α; 斜齿: ε_γ=ε_α+ε_β)
    epsilon_gamma = pair.epsilon_alpha + epsilon_beta
    K_Halpha = get_KHalpha(epsilon_gamma, accuracy_grade)
    K_Fbeta = get_KFbeta(K_Hbeta, b, pinion.h)
    K_Falpha = get_KFalpha(epsilon_gamma, accuracy_grade)
    K_H = K_A * K_V * K_Hbeta * K_Halpha
    K_F = K_A * K_V * K_Fbeta * K_Falpha

    # ---- 系数 ----
    beta_b = math.atan(math.tan(beta) * math.cos(alpha_t))  # 基圆螺旋角
    Z_H = get_ZH(alpha_t, beta_b)
    Z_E = STEEL_ZE
    # epsilon_beta 已在载荷系数段计算
    Z_epsilon = get_Zepsilon(pair.epsilon_alpha, epsilon_beta)
    Z_beta = get_Zbeta(beta)

    # ---- 接触应力 ----
    sigma_H0 = Z_H * Z_E * Z_epsilon * Z_beta * math.sqrt(
        F_t / (b * d1) * (u + 1) / u
    )
    sigma_H = sigma_H0 * math.sqrt(K_H)

    # 许用接触应力
    sigma_HP = (
        mat.sigma_hlim
        * get_ZN() * get_ZL() * get_ZV() * get_ZR() * get_ZW() * get_ZX(m_n)
        / S_Hmin
    )
    S_H = sigma_HP / sigma_H

    # ---- 弯曲应力 ----
    Y_beta = get_Ybeta(beta, epsilon_beta)
    Y_B = get_YB()

    Y_F1 = get_YF(pinion.z_v)
    Y_S1 = get_YS(pinion.z_v)
    sigma_F0_1 = F_t / (b * m_n) * Y_F1 * Y_S1 * Y_beta * Y_B
    sigma_F1 = sigma_F0_1 * K_F

    Y_F2 = get_YF(wheel.z_v)
    Y_S2 = get_YS(wheel.z_v)
    sigma_F0_2 = F_t / (b * m_n) * Y_F2 * Y_S2 * Y_beta * Y_B
    sigma_F2 = sigma_F0_2 * K_F

    # 许用弯曲应力: Y_ST = 2.0 (reference test gear)
    sigma_FP1 = (
        mat.sigma_flim * 2.0
        * get_YN() * get_YdeltaRelT() * get_YRrelT() * get_YX(m_n)
        / S_Fmin
    )
    sigma_FP2 = sigma_FP1  # 假设大小齿轮同材料

    S_F1 = sigma_FP1 / sigma_F1
    S_F2 = sigma_FP2 / sigma_F2

    # ---- 判定 ----
    contact_pass = S_H >= S_Hmin
    bending_pass = S_F1 >= S_Fmin and S_F2 >= S_Fmin

    return StrengthResult(
        sigma_H=round(sigma_H, 2),
        sigma_HP=round(sigma_HP, 2),
        S_H=round(S_H, 3),
        S_Hmin=S_Hmin,
        contact_pass=contact_pass,
        sigma_F1=round(sigma_F1, 2),
        sigma_FP1=round(sigma_FP1, 2),
        S_F1=round(S_F1, 3),
        sigma_F2=round(sigma_F2, 2),
        sigma_FP2=round(sigma_FP2, 2),
        S_F2=round(S_F2, 3),
        S_Fmin=S_Fmin,
        bending_pass=bending_pass,
        passed=contact_pass and bending_pass,
        K_A=K_A, K_V=K_V, K_Hbeta=K_Hbeta, K_Halpha=K_Halpha,
        K_Fbeta=K_Fbeta, K_Falpha=K_Falpha,
    )
