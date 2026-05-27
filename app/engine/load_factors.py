"""
ISO 6336 / GB/T 3480 载荷系数计算

各个系数的计算方法:
  K_A — 使用系数, 查表
  K_V — 动载系数, 简化方法 (GB/T 3480.1 附录)
  K_Hβ — 齿向载荷分布系数 (接触强度)
  K_Fβ — 齿向载荷分布系数 (弯曲强度)
  K_Hα — 齿间载荷分配系数 (接触强度)
  K_Fα — 齿间载荷分配系数 (弯曲强度)
"""

import math

# ============================================================================
# K_A — 使用系数 (GB/T 3480.1-2019 表1)
# 行: 原动机, 列: 工作机
# ============================================================================
KA_TABLE: dict[str, dict[str, float]] = {
    # 原动机: 均匀平稳
    "uniform": {
        "uniform":      1.00,  # 发电机、均匀送料
        "light_shock":  1.25,  # 机床主传动、起重机
        "moderate_shock": 1.50,  # 冲床、振动筛
        "heavy_shock":  1.75,  # 轧钢机、破碎机
    },
    # 原动机: 轻微冲击 (多缸内燃机)
    "light_shock": {
        "uniform":      1.10,
        "light_shock":  1.35,
        "moderate_shock": 1.60,
        "heavy_shock":  1.85,
    },
    # 原动机: 中等冲击 (单缸内燃机)
    "moderate_shock": {
        "uniform":      1.25,
        "light_shock":  1.50,
        "moderate_shock": 1.75,
        "heavy_shock":  2.00,
    },
    # 原动机: 严重冲击
    "heavy_shock": {
        "uniform":      1.50,
        "light_shock":  1.75,
        "moderate_shock": 2.00,
        "heavy_shock":  2.25,
    },
}


def get_KA(
    driver_type: str = "uniform",
    driven_type: str = "uniform",
) -> float:
    """获取使用系数 K_A

    driver_type: "uniform" | "light_shock" | "moderate_shock" | "heavy_shock"
    driven_type: same options
    """
    return KA_TABLE.get(driver_type, {}).get(driven_type, 1.25)


# ═════════════════════════════════════════════════════════════════════════
# K_V — 动载系数 (GB/T 3480.1 附录C 简化方法 / GB/T 10063)
#
# K_V = 1 + (K1 / (K_A * F_t / b)) + (K2 * v * z1 / 100)
# K1, K2 由精度等级决定:
#   6级: K1=0.28, K2=0.019
#   7级: K1=0.56, K2=0.033
#   8级: K1=1.12, K2=0.061
#   9级: K1=2.24, K2=0.117
#
# 关键: K_V 不仅依赖速度,还依赖齿数(z1)和载荷(F_t/b)。
# z1大→啮合频率高→K_V大; F_t/b大→重载→动载效应相对小→K_V小。
# ═════════════════════════════════════════════════════════════════════════

# K1, K2 系数表 (GB/T 10063)
_KV_K_TABLE = {
    5: (0.14, 0.009),
    6: (0.28, 0.019),
    7: (0.56, 0.033),
    8: (1.12, 0.061),
    9: (2.24, 0.117),
    10: (4.48, 0.234),
}


def get_KV(
    v_ms: float,              # 节线速度 (m/s)
    z1: int = 20,              # 小齿轮齿数
    F_t_per_b: float = 100.0,  # 单位齿宽载荷 F_t/b (N/mm)
    K_A: float = 1.0,          # 使用系数 (KV公式需要)
    accuracy_grade: int = 8,
) -> float:
    """动载系数 K_V — GB/T 10063 简化方法

    参考: GB/T 3480.1-2019 附录C / GB/T 10063-88

    K_V = 1 + K1/(K_A·F_t/b) + K2·v·z1/100
    """
    grade = max(5, min(10, accuracy_grade))
    K1, K2 = _KV_K_TABLE.get(grade, (1.12, 0.061))

    kv = 1.0 + K1 / (K_A * F_t_per_b) + K2 * v_ms * z1 / 100.0
    return round(kv, 4)


# ============================================================================
# K_Hβ — 齿向载荷分布系数 (接触强度)
# ============================================================================
def get_KHbeta(
    b: float,              # 齿宽 (mm)
    d1: float,             # 小齿轮分度圆直径 (mm)
    arrangement: str = "asymmetric",  # "symmetric" | "asymmetric" | "overhung"
    accuracy_grade: int = 8,
    hardness: str = "soft",  # "soft" (HB≤350) | "hard" (HB>350)
) -> float:
    """齿向载荷分布系数 K_Hβ — 简化查表/公式法

    参考: GB/T 3480.1-2019 附录C (Method B)
    对于无螺旋线修形、无鼓形修形的齿轮:
      K_Hβ = f(phi_d, arrangement, hardness, accuracy)

    phi_d = b / d1 (齿宽系数)
    """
    phi_d = b / d1

    # 简化计算 (基于 GB/T 3480 方法B 的工程近似)
    # K_Hβ = 1 + (phi_d - 0.6) * C_beta
    if phi_d <= 0.6:
        return 1.05

    if arrangement == "symmetric":
        base = 0.12  # 对称布置 — 载荷分布最均匀
    elif arrangement == "asymmetric":
        base = 0.18  # 非对称布置
    else:
        base = 0.28  # 悬臂布置

    if hardness == "hard":
        base *= 1.3  # 硬齿面跑合能力差

    khb = 1.05 + base * (phi_d - 0.6) * phi_d
    return round(khb, 4)


# ============================================================================
# K_Fβ — 齿向载荷分布系数 (弯曲强度)
# ============================================================================
def get_KFbeta(
    KHbeta: float,
    b: float,
    h: float,  # 全齿高 (mm)
) -> float:
    """齿向载荷分布系数 K_Fβ

    K_Fβ = (K_Hβ)^N
    where N = (b/h)^2 / (1 + b/h + (b/h)^2)
    """
    ratio = b / h
    if ratio <= 0:
        return KHbeta
    N = (ratio ** 2) / (1 + ratio + ratio ** 2)
    return round(KHbeta ** N, 4)


# ============================================================================
# K_Hα / K_Fα — 齿间载荷分配系数
# ============================================================================
def get_KHalpha(
    epsilon_gamma: float,   # 总重合度 ε_γ
    accuracy_grade: int = 8,
) -> float:
    """齿间载荷分配系数 K_Hα (接触强度)

    参考: GB/T 3480.1-2019 表5
    """
    if epsilon_gamma <= 2.0:
        # 精度等级数字越大 = 精度越低 → K_Hα 越大
        if accuracy_grade <= 6:
            return 1.0
        else:
            return round(1.0 + (accuracy_grade - 6) * 0.05, 4)
    else:
        # ε_γ > 2: 高重合度
        base = 0.9 + 0.4 * math.sqrt(
            2.0 * (epsilon_gamma - 1.0) / epsilon_gamma
        )
        if accuracy_grade <= 6:
            return round(base, 4)
        else:
            return round(base + (accuracy_grade - 6) * 0.02, 4)


def get_KFalpha(
    epsilon_gamma: float,
    accuracy_grade: int = 8,
) -> float:
    """齿间载荷分配系数 K_Fα (弯曲强度)

    一般 K_Fα = K_Hα (保守)
    """
    return get_KHalpha(epsilon_gamma, accuracy_grade)
