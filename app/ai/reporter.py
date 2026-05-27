"""
计算结果 → 自然语言设计报告 + 格式化结果
"""

from dataclasses import dataclass, field
from app.engine.gears import GearGeometry, GearPairGeometry, GearDesignResult
from app.engine.strength import StrengthResult


@dataclass
class GearResultItem:
    label: str
    value: str
    unit: str = ""


@dataclass
class GearResultGroup:
    title: str
    items: list[GearResultItem] = field(default_factory=list)


@dataclass
class StrengthResultData:
    sigma_H: float = 0
    sigma_HP: float = 0
    S_H: float = 0
    S_Hmin: float = 1.0
    contact_pass: bool = False
    sigma_F1: float = 0
    sigma_FP1: float = 0
    S_F1: float = 0
    sigma_F2: float = 0
    sigma_FP2: float = 0
    S_F2: float = 0
    S_Fmin: float = 1.25
    bending_pass: bool = False
    passed: bool = False
    load_factors: dict = field(default_factory=dict)


def format_geometry(g: GearGeometry, label: str = "小齿轮") -> list[GearResultGroup]:
    """格式化单个齿轮的几何参数"""
    groups = []

    items = [
        GearResultItem(label="齿数 z", value=str(g.z)),
        GearResultItem(label="模数 mₙ", value=str(g.m_n), unit="mm"),
    ]
    if g.is_helical:
        items.append(GearResultItem(label="螺旋角 β", value=str(g.beta_deg), unit="°"))
        items.append(GearResultItem(label="端面模数 mₜ", value=f"{g.m_t:.4f}", unit="mm"))

    items += [
        GearResultItem(label="分度圆直径 d", value=f"{g.d:.2f}", unit="mm"),
        GearResultItem(label="齿顶圆直径 dₐ", value=f"{g.da:.2f}", unit="mm"),
        GearResultItem(label="齿根圆直径 d𝒻", value=f"{g.df:.2f}", unit="mm"),
        GearResultItem(label="基圆直径 dᵦ", value=f"{g.db:.2f}", unit="mm"),
        GearResultItem(label="全齿高 h", value=f"{g.h:.3f}", unit="mm"),
        GearResultItem(label="分度圆齿距 p", value=f"{g.p:.4f}", unit="mm"),
        GearResultItem(label="基圆齿距 pᵦ", value=f"{g.pb:.4f}", unit="mm"),
        GearResultItem(label="分度圆齿厚 s", value=f"{g.s:.4f}", unit="mm"),
        GearResultItem(label="公法线长度 Wₖ", value=f"{g.base_tangent_length:.4f}", unit="mm"),
        GearResultItem(label="跨齿数 k", value=str(g.k_span)),
    ]

    if g.is_helical:
        items.append(GearResultItem(label="当量齿数 zᵥ", value=f"{g.z_v:.2f}"))

    groups.append(GearResultGroup(title=f"{label} 几何参数", items=items))
    return groups


def format_pair(pair: GearPairGeometry) -> GearResultGroup:
    """格式化齿轮副参数"""
    return GearResultGroup(
        title="齿轮副参数",
        items=[
            GearResultItem(label="中心距 a", value=f"{pair.a:.2f}", unit="mm"),
            GearResultItem(label="齿数比 u", value=f"{pair.u:.3f}"),
            GearResultItem(label="端面重合度 εₐ", value=f"{pair.epsilon_alpha:.4f}"),
        ],
    )


def format_strength(s: StrengthResult) -> StrengthResultData:
    """格式化强度校核结果"""
    return StrengthResultData(
        sigma_H=s.sigma_H,
        sigma_HP=s.sigma_HP,
        S_H=s.S_H,
        S_Hmin=s.S_Hmin,
        contact_pass=s.contact_pass,
        sigma_F1=s.sigma_F1,
        sigma_FP1=s.sigma_FP1,
        S_F1=s.S_F1,
        sigma_F2=s.sigma_F2,
        sigma_FP2=s.sigma_FP2,
        S_F2=s.S_F2,
        S_Fmin=s.S_Fmin,
        bending_pass=s.bending_pass,
        passed=s.passed,
        load_factors={
            "K_A": round(s.K_A, 3),
            "K_V": round(s.K_V, 3),
            "K_Hβ": round(s.K_Hbeta, 4),
            "K_Hα": round(s.K_Halpha, 3),
            "K_Fβ": round(s.K_Fbeta, 4),
            "K_Fα": round(s.K_Falpha, 3),
        },
    )


def build_report_text(result: GearDesignResult, strength: StrengthResult | None = None) -> str:
    """生成自然语言设计报告"""
    p = result.pinion
    lines = ["## 齿轮设计报告\n"]

    lines.append("### 设计输入")
    lines.append(f"- 齿轮类型: {'斜齿圆柱齿轮' if p.is_helical else '直齿圆柱齿轮'}")
    lines.append(f"- 模数: mₙ = {p.m_n} mm")
    lines.append(f"- 小齿轮齿数: z₁ = {p.z}")
    if result.wheel:
        lines.append(f"- 大齿轮齿数: z₂ = {result.wheel.z}")
        lines.append(f"- 齿数比: u = {result.pair.u:.3f}")
    if p.is_helical:
        lines.append(f"- 螺旋角: β = {p.beta_deg}°")
    if result.input.power_kw:
        lines.append(f"- 传递功率: P = {result.input.power_kw} kW")
    if result.input.rpm:
        lines.append(f"- 小齿轮转速: n₁ = {result.input.rpm} rpm")

    lines.append(f"\n### 几何计算结果")
    lines.append(f"| 参数 | 小齿轮 | 大齿轮 |")
    lines.append(f"|------|--------|--------|")
    lines.append(f"| 分度圆直径 d | {p.d:.2f} mm | {result.wheel.d:.2f} mm |" if result.wheel else f"| 分度圆直径 d | {p.d:.2f} mm | — |")
    lines.append(f"| 齿顶圆直径 dₐ | {p.da:.2f} mm | {result.wheel.da:.2f} mm |" if result.wheel else f"| 齿顶圆直径 dₐ | {p.da:.2f} mm | — |")
    lines.append(f"| 齿根圆直径 d𝒻 | {p.df:.2f} mm | {result.wheel.df:.2f} mm |" if result.wheel else "")
    if result.pair:
        lines.append(f"\n中心距: **a = {result.pair.a:.2f} mm**")
        lines.append(f"重合度: **εₐ = {result.pair.epsilon_alpha:.4f}**")

    if strength:
        lines.append(f"\n### 强度校核")
        lines.append(f"#### 齿面接触疲劳强度")
        lines.append(f"- 计算应力 σ_H = **{strength.sigma_H:.1f} MPa**")
        lines.append(f"- 许用应力 σ_HP = **{strength.sigma_HP:.1f} MPa**")
        lines.append(f"- 安全系数 S_H = **{strength.S_H:.3f}**")
        lines.append(f"- 结论: {'✓ 通过' if strength.contact_pass else '✗ 不通过'}")

        lines.append(f"\n#### 齿根弯曲疲劳强度")
        lines.append(f"- 小齿轮 σ_F₁ = **{strength.sigma_F1:.1f} MPa**, S_F₁ = **{strength.S_F1:.3f}**")
        lines.append(f"- 大齿轮 σ_F₂ = **{strength.sigma_F2:.1f} MPa**, S_F₂ = **{strength.S_F2:.3f}**")
        lines.append(f"- 结论: {'✓ 通过' if strength.bending_pass else '✗ 不通过'}")

        if strength.passed:
            lines.append(f"\n### ✅ 结论: 齿轮设计满足强度要求")
        else:
            lines.append(f"\n### ❌ 结论: 齿轮设计不满足强度要求，建议增大模数或更换材料")

    lines.append(f"\n---")
    lines.append(f"> ⚠️ 本计算结果仅供参考，工程应用需经专业人员审核。")
    lines.append(f"> 强度校核依据: GB/T 3480 / ISO 6336 Method B")

    return "\n".join(lines)
