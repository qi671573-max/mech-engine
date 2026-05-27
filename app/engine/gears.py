"""
渐开线圆柱齿轮几何计算引擎

实现 GB/T 1357 (模数系列), GB/T 1356 (齿形) 标准
所有公式使用标准压力角 α=20°, 齿顶高系数 ha*=1, 顶隙系数 c*=0.25
"""

import math
from dataclasses import dataclass, field


# ============================================================================
# 标准模数系列 (GB/T 1357-2008, 第一系列优先)
# ============================================================================
STANDARD_MODULES = (
    1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0,
    10.0, 12.0, 16.0, 20.0, 25.0, 32.0, 40.0, 50.0,
)


def nearest_standard_module(m: float) -> float:
    """取最近的标准模数（优先取大值保证强度）"""
    for sm in STANDARD_MODULES:
        if sm >= m:
            return sm
    return STANDARD_MODULES[-1]


# ============================================================================
# 标准压力角
# ============================================================================
ALPHA_DEG = 20.0  # 标准压力角 (°)
ALPHA_RAD = math.radians(ALPHA_DEG)
INV_ALPHA = math.tan(ALPHA_RAD) - ALPHA_RAD  # inv(20°) ≈ 0.014904


# ============================================================================
# 齿形参数 (GB/T 1356)
# ============================================================================
HA_STAR = 1.0   # 齿顶高系数
C_STAR = 0.25   # 顶隙系数


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def involute(theta_rad: float) -> float:
    """渐开线函数 inv(θ) = tan(θ) - θ"""
    return math.tan(theta_rad) - theta_rad


def inverse_involute(inv_val: float, tol: float = 1e-9) -> float:
    """反渐开线函数 (Newton法)"""
    theta = (3 * inv_val) ** (1 / 3)  # 初值近似
    for _ in range(20):
        f = math.tan(theta) - theta - inv_val
        if abs(f) < tol:
            return theta
        df = math.tan(theta) ** 2  # derivative = tan²(θ)
        theta -= f / df
    return theta


@dataclass
class GearGeometry:
    """单个齿轮的几何参数 (直齿或斜齿)"""

    z: int                     # 齿数
    m_n: float                 # 法向模数 (mm), 直齿时 m_n = m
    beta_deg: float = 0.0      # 螺旋角 (°), 0 = 直齿
    x: float = 0.0             # 变位系数
    ha_star: float = HA_STAR   # 齿顶高系数
    c_star: float = C_STAR     # 顶隙系数
    alpha_n_deg: float = ALPHA_DEG  # 法向压力角 (°)
    b: float | None = None     # 齿宽 (mm), 需外部指定

    # ---- 计算值 (初始化后 setattr) ----
    beta_rad: float = field(init=False)
    m_t: float = field(init=False)     # 端面模数
    alpha_n_rad: float = field(init=False)
    alpha_t_rad: float = field(init=False)  # 端面压力角
    d: float = field(init=False)        # 分度圆直径
    db: float = field(init=False)       # 基圆直径
    da: float = field(init=False)       # 齿顶圆直径
    df: float = field(init=False)       # 齿根圆直径
    h: float = field(init=False)        # 全齿高
    ha: float = field(init=False)       # 齿顶高
    hf: float = field(init=False)       # 齿根高
    p: float = field(init=False)        # 分度圆齿距
    pb: float = field(init=False)       # 基圆齿距
    s: float = field(init=False)        # 分度圆齿厚
    is_helical: bool = field(init=False)

    def __post_init__(self):
        self.beta_rad = math.radians(self.beta_deg)
        self.is_helical = abs(self.beta_deg) > 0.001
        self.alpha_n_rad = math.radians(self.alpha_n_deg)

        if self.is_helical:
            self.m_t = self.m_n / math.cos(self.beta_rad)
            self.alpha_t_rad = math.atan(
                math.tan(self.alpha_n_rad) / math.cos(self.beta_rad)
            )
        else:
            self.m_t = self.m_n
            self.alpha_t_rad = self.alpha_n_rad

        m_t = self.m_t
        self.d = m_t * self.z
        self.db = self.d * math.cos(self.alpha_t_rad)
        self.ha = self.ha_star * self.m_n + self.x * self.m_n
        self.hf = (self.ha_star + self.c_star) * self.m_n - self.x * self.m_n
        self.da = self.d + 2 * self.ha
        self.df = self.d - 2 * self.hf
        self.h = self.ha + self.hf
        self.p = math.pi * m_t
        self.pb = math.pi * m_t * math.cos(self.alpha_t_rad)
        self.s = self.p / 2 + 2 * self.x * self.m_t * math.tan(self.alpha_t_rad)

    # ---- 任意圆齿厚 ----
    def tooth_thickness_at(self, dk: float) -> float:
        """计算直径 dk 圆上的弧齿厚"""
        alpha_k = math.acos(self.db / dk) if dk >= self.db else 0.0
        return self.d * (self.s / self.d + involute(self.alpha_t_rad) - involute(alpha_k))

    # ---- 齿顶圆压力角 ----
    @property
    def alpha_a_rad(self) -> float:
        """齿顶圆压力角"""
        return math.acos(self.db / self.da) if self.da >= self.db else 0.0

    # ---- 齿根圆压力角 ----
    @property
    def alpha_f_rad(self) -> float:
        """齿根圆压力角 (仅 df≥db 时有意义)"""
        return math.acos(self.db / self.df) if self.df >= self.db else 0.0

    # ---- 公法线长度 ----
    @property
    def k_span(self) -> int:
        """跨齿数 (α=20° 标准齿轮)"""
        return max(1, round(self.z / 9 + 0.5))

    @property
    def base_tangent_length(self) -> float:
        """
        公法线长度 Wk
        Wk = m_n·cos(α_n)·[π(k-0.5) + z·inv(α_t) + 2x·tan(α_n)]
        """
        inv_at = involute(self.alpha_t_rad)
        k = self.k_span
        wk = self.m_n * math.cos(self.alpha_n_rad) * (
            math.pi * (k - 0.5) + self.z * inv_at + 2 * self.x * math.tan(self.alpha_n_rad)
        )
        return round(wk, 4)

    def base_tangent_length_for_span(self, k: int) -> float:
        """指定跨齿数的公法线长度"""
        inv_at = involute(self.alpha_t_rad)
        return self.m_n * math.cos(self.alpha_n_rad) * (
            math.pi * (k - 0.5) + self.z * inv_at + 2 * self.x * math.tan(self.alpha_n_rad)
        )

    # ---- 当量齿数 (斜齿轮) ----
    @property
    def z_v(self) -> float:
        """当量齿数 (斜齿轮) = z / cos³(β)"""
        cb = math.cos(self.beta_rad)
        return self.z / (cb ** 3)


# ============================================================================
# 齿轮副几何
# ============================================================================
@dataclass
class GearPairGeometry:
    """一对齿轮副的几何关系"""

    pinion: GearGeometry   # 小齿轮
    wheel: GearGeometry    # 大齿轮

    # ---- 计算值 ----
    u: float = field(init=False)        # 齿数比 (≥1)
    a: float = field(init=False)        # 标准中心距
    epsilon_alpha: float = field(init=False)  # 端面重合度

    def __post_init__(self):
        if self.pinion.z > self.wheel.z:
            raise ValueError("pinion must have fewer teeth than wheel")

        self.u = self.wheel.z / self.pinion.z
        self.a = (self.pinion.d + self.wheel.d) / 2

        # ---- 精确重合度 ----
        z1, z2 = self.pinion.z, self.wheel.z
        alpha_t = self.pinion.alpha_t_rad
        alpha_a1 = self.pinion.alpha_a_rad
        alpha_a2 = self.wheel.alpha_a_rad

        self.epsilon_alpha = (
            z1 * (math.tan(alpha_a1) - math.tan(alpha_t))
            + z2 * (math.tan(alpha_a2) - math.tan(alpha_t))
        ) / (2 * math.pi)

    @property
    def is_standard_center_distance(self) -> bool:
        """是否标准中心距安装

        标准中心距安装意味着啮合角=压力角。GearPairGeometry 只计算
        标准中心距 a = (d1+d2)/2，所以始终为标准安装。
        如需非标中心距需额外传入 a_actual 参数。
        """
        return True  # 当前仅支持标准中心距计算

    def approx_epsilon_alpha(self) -> float:
        """重合度近似公式 (仅标准直齿轮有效)"""
        return 1.88 - 3.2 * (1 / self.pinion.z + 1 / self.wheel.z)


# ============================================================================
# 齿轮设计计算入口
# ============================================================================
@dataclass
class GearDesignInput:
    """用户输入的设计参数"""

    gear_type: str = "spur"           # "spur" | "helical"
    m_n: float = 2.0                  # 法向模数
    z1: int = 20                      # 小齿轮齿数
    z2: int | None = None             # 大齿轮齿数 (None = 只算单个齿轮)
    beta_deg: float = 0.0             # 螺旋角
    x1: float = 0.0                   # 小齿轮变位系数
    x2: float = 0.0                   # 大齿轮变位系数
    b: float | None = None            # 齿宽 (mm)
    power_kw: float | None = None     # 传递功率 (用于强度计算)
    rpm: float | None = None          # 小齿轮转速 (用于强度计算)
    material_key: str = "45钢-调质"   # 材料标识


@dataclass
class GearDesignResult:
    """完整的设计结果"""

    input: GearDesignInput
    pinion: GearGeometry
    wheel: GearGeometry | None
    pair: GearPairGeometry | None
    material_label: str = ""

    # 强度结果 (可选)
    contact_safety: float | None = None
    bending_safety_pinion: float | None = None
    bending_safety_wheel: float | None = None
    passed: bool | None = None


def compute_geometry(inp: GearDesignInput) -> GearDesignResult:
    """根据输入参数计算齿轮几何尺寸"""
    pinion = GearGeometry(
        z=inp.z1,
        m_n=inp.m_n,
        beta_deg=inp.beta_deg,
        x=inp.x1,
    )

    wheel = None
    pair = None
    if inp.z2 is not None:
        wheel = GearGeometry(
            z=inp.z2,
            m_n=inp.m_n,
            beta_deg=inp.beta_deg,
            x=inp.x2,
        )
        pair = GearPairGeometry(pinion=pinion, wheel=wheel)

    return GearDesignResult(
        input=inp,
        pinion=pinion,
        wheel=wheel,
        pair=pair,
    )
