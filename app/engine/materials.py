"""
GB/T 3480.5 齿轮材料数据库

疲劳极限数据来源: GB/T 3480.5-2008 图5-8 (MQ级质量)
对于没有精确图表数据的材料,使用机械设计手册推荐值。
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 弹性模量 / 泊松比 (钢-钢配对)
# ---------------------------------------------------------------------------
STEEL_ELASTIC_MODULUS = 206000  # MPa
STEEL_POISSON_RATIO = 0.3
# Z_E for steel-steel pair: sqrt(E / (2 * pi * (1 - nu^2)))
STEEL_ZE = 189.8  # sqrt(MPa)


@dataclass(frozen=True)
class GearMaterial:
    """齿轮材料定义"""

    name: str  # 中文名称, 如 "45钢"
    standard: str  # 标准号, 如 "GB/T 699"
    heat_treatment: str  # 热处理, 如 "调质"
    hardness_min: float  # 最低硬度 (HBW 或 HRC)
    hardness_max: float  # 最高硬度
    hardness_unit: str  # "HBW" 或 "HRC"

    # 接触疲劳极限 (参考值, 对应硬度范围中值, MQ级质量)
    sigma_hlim: float  # MPa
    # 弯曲疲劳极限 (参考值, MQ)
    sigma_flim: float  # MPa

    # 适用范围: 模数范围 mm
    module_range: tuple[float, float] = (1.0, 50.0)

    @property
    def hardness_mid(self) -> float:
        return (self.hardness_min + self.hardness_max) / 2

    @property
    def label(self) -> str:
        return f"{self.name} ({self.heat_treatment})"


# ---------------------------------------------------------------------------
# 常用齿轮材料数据库
# 数据来源:
#   - GB/T 3480.5-2008 图5-8 (σ_Hlim, σ_Flim for MQ quality)
#   - 《机械设计》濮良贵 第十版 表10-1
#   - 《机械设计手册》第五版 第3卷
# ---------------------------------------------------------------------------
MATERIALS: dict[str, GearMaterial] = {
    # ===== 优质碳素结构钢 (GB/T 699) =====
    "45钢-正火": GearMaterial(
        name="45钢",
        standard="GB/T 699",
        heat_treatment="正火",
        hardness_min=156,
        hardness_max=217,
        hardness_unit="HBW",
        sigma_hlim=380,
        sigma_flim=310,
    ),
    "45钢-调质": GearMaterial(
        name="45钢",
        standard="GB/T 699",
        heat_treatment="调质",
        hardness_min=197,
        hardness_max=286,
        hardness_unit="HBW",
        sigma_hlim=590,
        sigma_flim=450,
    ),
    "45钢-表面淬火": GearMaterial(
        name="45钢",
        standard="GB/T 699",
        heat_treatment="表面淬火",
        hardness_min=40,
        hardness_max=50,
        hardness_unit="HRC",
        sigma_hlim=1130,
        # 弯曲疲劳极限取决于心部硬度(未淬硬区),非表面硬度
        # 45钢感应淬火前基体~200-250HBW, σ_Flim≈300-450 MPa
        sigma_flim=380,
    ),

    # ===== 合金结构钢 (GB/T 3077) =====
    "40Cr-调质": GearMaterial(
        name="40Cr",
        standard="GB/T 3077",
        heat_treatment="调质",
        hardness_min=241,
        hardness_max=286,
        hardness_unit="HBW",
        sigma_hlim=630,
        sigma_flim=480,
    ),
    "40Cr-表面淬火": GearMaterial(
        name="40Cr",
        standard="GB/T 3077",
        heat_treatment="表面淬火",
        hardness_min=48,
        hardness_max=55,
        hardness_unit="HRC",
        sigma_hlim=1140,
        sigma_flim=690,
    ),

    "20CrMnTi-渗碳淬火": GearMaterial(
        name="20CrMnTi",
        standard="GB/T 3077",
        heat_treatment="渗碳淬火",
        hardness_min=56,
        hardness_max=62,
        hardness_unit="HRC",
        sigma_hlim=1500,
        sigma_flim=480,
    ),
    "20Cr-渗碳淬火": GearMaterial(
        name="20Cr",
        standard="GB/T 3077",
        heat_treatment="渗碳淬火",
        hardness_min=56,
        hardness_max=62,
        hardness_unit="HRC",
        sigma_hlim=1500,
        sigma_flim=460,
    ),

    # ===== 铸钢 (GB/T 11352) =====
    "ZG310-570-正火": GearMaterial(
        name="ZG310-570",
        standard="GB/T 11352",
        heat_treatment="正火",
        hardness_min=163,
        hardness_max=207,
        hardness_unit="HBW",
        sigma_hlim=330,
        sigma_flim=260,
    ),

    # ===== 球墨铸铁 (GB/T 1348) =====
    "QT600-3-正火": GearMaterial(
        name="QT600-3",
        standard="GB/T 1348",
        heat_treatment="正火",
        hardness_min=229,
        hardness_max=302,
        hardness_unit="HBW",
        sigma_hlim=460,
        sigma_flim=360,
    ),
    "QT700-2-正火": GearMaterial(
        name="QT700-2",
        standard="GB/T 1348",
        heat_treatment="正火",
        hardness_min=250,
        hardness_max=350,
        hardness_unit="HBW",
        sigma_hlim=500,
        sigma_flim=390,
    ),

    # ===== 灰铸铁 (GB/T 9439) =====
    "HT300-时效": GearMaterial(
        name="HT300",
        standard="GB/T 9439",
        heat_treatment="时效处理",
        hardness_min=190,
        hardness_max=240,
        hardness_unit="HBW",
        sigma_hlim=320,
        sigma_flim=110,
    ),
}

# ---------------------------------------------------------------------------
# 常用材料 alias 映射 — 方便用户输入模糊匹配
# ---------------------------------------------------------------------------
MATERIAL_ALIASES: dict[str, str] = {
    "45钢": "45钢-调质",
    "45": "45钢-调质",
    "45#": "45钢-调质",
    "45号钢": "45钢-调质",
    "45钢正火": "45钢-正火",
    "45钢调质": "45钢-调质",
    "45钢表面淬火": "45钢-表面淬火",
    "40cr": "40Cr-调质",
    "40Cr": "40Cr-调质",
    "40cr调质": "40Cr-调质",
    "40Cr调质": "40Cr-调质",
    "40cr表面淬火": "40Cr-表面淬火",
    "40Cr表面淬火": "40Cr-表面淬火",
    "20crmnti": "20CrMnTi-渗碳淬火",
    "20CrMnTi": "20CrMnTi-渗碳淬火",
    "20CrMnTi渗碳": "20CrMnTi-渗碳淬火",
    "20cr": "20Cr-渗碳淬火",
    "20Cr": "20Cr-渗碳淬火",
    "20Cr渗碳": "20Cr-渗碳淬火",
    "zg310-570": "ZG310-570-正火",
    "ZG310-570": "ZG310-570-正火",
    "qt600-3": "QT600-3-正火",
    "QT600-3": "QT600-3-正火",
    "qt700-2": "QT700-2-正火",
    "QT700-2": "QT700-2-正火",
    "ht300": "HT300-时效",
    "HT300": "HT300-时效",
}


def resolve_material(name: str) -> GearMaterial | None:
    """根据模糊名称解析材料"""
    key = MATERIAL_ALIASES.get(name, name)
    return MATERIALS.get(key)


def list_materials() -> list[str]:
    """列出所有可用材料的显示名称"""
    return [m.label for m in MATERIALS.values()]
