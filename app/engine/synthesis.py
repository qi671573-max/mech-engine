"""
设计合成 — 从需求出发自动估算齿轮参数

当用户只知道 P, n1, u 但不知道 m 和 z1 时,
使用《机械设计》接触强度设计公式自动估算。

来源: 濮良贵《机械设计》第十版 §10-6 齿面接触强度设计
"""

import math
from dataclasses import dataclass

from app.engine.gears import STANDARD_MODULES, nearest_standard_module
from app.engine.materials import resolve_material


@dataclass
class DesignProposal:
    """一个候选设计方案"""
    z1: int
    z2: int
    m_n: float
    u_actual: float
    d1: float
    a: float
    reason: str


def estimate_d1(
    power_kw: float,
    rpm: float,
    u: float,
    material_key: str = "45钢-调质",
    phi_d: float = 1.0,
    K_A: float = 1.0,
) -> float:
    """用接触强度设计公式估算小齿轮分度圆直径 d1

    公式: d1 ≥ ∛(2·K_H·T1/φ_d · (u+1)/u · (Z_H·Z_E·Z_ε/[σ_H])²)

    来源: 《机械设计》式(10-15)
    K_H 初估取 1.3~1.6 (含 K_A 影响), K_A 大会让 K_H 偏大
    """
    mat = resolve_material(material_key)
    if mat is None:
        mat = resolve_material("45钢-调质")

    T1 = 9550.0 * power_kw / rpm  # N·m
    K_H_guess = K_A * 1.6 + 0.3  # K_A=1→1.9, K_A=1.5→2.7 充分保守

    Z_H = 2.5
    Z_E = 189.8
    Z_eps = 0.87

    sigma_HP = mat.sigma_hlim

    d1 = ((2.0 * K_H_guess * T1 * 1000 / phi_d
           * (u + 1) / u
           * (Z_H * Z_E * Z_eps / sigma_HP) ** 2)
          ) ** (1.0 / 3.0)

    return d1


def synthesize(
    power_kw: float,
    rpm: float,
    u: float = 3.0,
    material_key: str = "45钢-调质",
    gear_type: str = "spur",
    K_A: float = 1.0,
) -> list[DesignProposal]:
    """从需求出发生成候选设计方案

    返回 2-3 个候选方案, 用户可选择或自动选最佳。
    """
    d1_est = estimate_d1(power_kw, rpm, u, material_key, K_A=K_A)

    # 方案: 尝试不同的小齿轮齿数
    # 尝试多种齿数 + 在估算值附近尝试大一档模数(更保守)
    candidates = [18, 20, 22, 25, 28, 30]
    proposals = []

    for z1 in candidates:
        m_raw = d1_est / z1
        m_std = nearest_standard_module(m_raw)
        z2 = round(z1 * u)
        u_actual = z2 / z1
        d1 = m_std * z1
        a = m_std * (z1 + z2) / 2

        # 检查合理性
        if z1 < 17:
            continue  # 根切风险

        if abs(u_actual - u) / u > 0.05:
            continue  # 传动比偏差过大

        if m_std < 1.0:
            continue

        proposals.append(DesignProposal(
            z1=z1, z2=z2, m_n=m_std,
            u_actual=u_actual, d1=d1, a=a,
            reason=f"m≈{m_raw:.2f}→取标准值{m_std}",
        ))

    # 去重
    seen = set()
    unique = []
    for p in proposals:
        key = (p.m_n, p.z1)
        if key not in seen:
            seen.add(key)
            unique.append(p)

    # 按 d1 接近估算值排序
    unique.sort(key=lambda p: abs(p.d1 - d1_est))
    return unique[:3]  # 返回前3个候选方案


def format_proposals(proposals: list[DesignProposal]) -> str:
    """格式化候选方案为用户可读文本"""
    if not proposals:
        return "无法自动生成方案，请手动指定模数和齿数。"

    lines = ["## 自动推荐方案\n"]
    for i, p in enumerate(proposals, 1):
        lines.append(f"**方案{i}**: m={p.m_n}, z₁={p.z1}, z₂={p.z2}, "
                     f"d₁={p.d1:.1f}mm, a={p.a:.1f}mm, u={p.u_actual:.2f}")
        lines.append(f"  → {p.reason}\n")

    lines.append("输入方案编号(如 `方案1`)选择，或直接输入 `方案1` 开始计算。")
    return "\n".join(lines)
