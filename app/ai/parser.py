"""
自然语言 → 齿轮设计参数 解析器

MVP使用规则引擎+正则匹配。后期接入 DeepSeek API 做模糊意图理解。

规则引擎优先级:
  1. 关键词匹配 (精确)
  2. 数字+单位提取 (正则)
  3. 默认值填充
"""

import re
from dataclasses import dataclass


@dataclass
class ParsedGearInput:
    gear_type: str = "spur"
    m_n: float | None = None        # 模数
    z1: int | None = None           # 小齿轮齿数
    z2: int | None = None           # 大齿轮齿数
    beta_deg: float = 0.0           # 螺旋角
    power_kw: float | None = None   # 功率
    rpm: float | None = None        # 转速
    material_key: str = "45钢-调质"
    driver_type: str = "uniform"    # 原动机类型
    driven_type: str = "uniform"    # 工作机类型
    raw_text: str = ""

    def is_complete(self) -> bool:
        """最小参数集: 模数 + 小齿轮齿数"""
        return self.m_n is not None and self.z1 is not None


def parse_gear_request(text: str) -> ParsedGearInput:
    """从自然语言解析齿轮设计参数"""
    result = ParsedGearInput(raw_text=text)
    text_lower = text.lower()

    # ---- 齿轮类型 ----
    if any(w in text_lower for w in ("斜齿", "helical", "螺旋")):
        result.gear_type = "helical"
    elif any(w in text_lower for w in ("直齿", "spur")):
        result.gear_type = "spur"

    # ---- 模数 ----
    m = re.search(r"模(?:数|量)?\s*[=:：]?\s*([\d.]+)", text_lower)
    if not m:
        m = re.search(r"[Mm]\s*[=:：]?\s*([\d.]+)", text)
    if m:
        result.m_n = float(m.group(1))

    # ---- 齿数 ----
    # 模式: "20齿" / "z1=20" / "小齿轮20" / "齿数20"
    z1_match = re.search(r"(?:小齿轮|主动轮|齿数|[Zz]1?)[=:：]?\s*(\d+)\s*(?:齿|个)?", text)
    if z1_match:
        result.z1 = int(z1_match.group(1))

    # 如果正则没匹配到 z1, 尝试 "20齿" 这种裸数字+齿格式
    if result.z1 is None:
        bare_teeth = re.findall(r"(\d+)\s*齿", text)
        if bare_teeth:
            teeth_vals = [int(t) for t in bare_teeth]
            result.z1 = teeth_vals[0]  # 第一个出现的当小齿轮
            if len(teeth_vals) >= 2:
                result.z2 = teeth_vals[1]

    # 大齿轮齿数 (特定关键词)
    z2_match = re.search(r"(?:大齿轮|从动轮|[Zz]2)[=:：]?\s*(\d+)", text)
    if z2_match:
        result.z2 = int(z2_match.group(1))

    # 齿数比 / 传动比
    ratio_match = re.search(r"(?:齿数比|传动比|速比|减速比|[Uu])[=:：]?\s*([\d.]+)", text)
    if ratio_match and result.z1 and not result.z2:
        ratio = float(ratio_match.group(1))
        result.z2 = round(result.z1 * ratio)

    # ---- 螺旋角 ----
    beta_match = re.search(r"(?:螺旋角|β|beta)[=:：]?\s*([\d.]+)\s*[°度]?", text_lower)
    if beta_match:
        result.beta_deg = float(beta_match.group(1))

    # ---- 功率 ----
    p_match = re.search(r"(\d+\.?\d*)\s*[Kk][Ww]", text)
    if not p_match:
        p_match = re.search(r"功率\s*[=:：]?\s*([\d.]+)", text_lower)
    if not p_match:
        p_match = re.search(r"传递\s*[=:：]?\s*([\d.]+)", text_lower)
    if p_match:
        result.power_kw = float(p_match.group(1))

    # ---- 转速 ----
    rpm_match = re.search(r"(\d+\.?\d*)\s*(?:rpm|[转转]/?分|[Rr]/min)", text)
    if not rpm_match:
        rpm_match = re.search(r"(?:转速|[Rr][Pp][Mm])[=:：]?\s*([\d.]+)", text)
    if rpm_match:
        result.rpm = float(rpm_match.group(1))

    # ---- 材料 ----
    from app.engine.materials import MATERIAL_ALIASES
    for alias in MATERIAL_ALIASES:
        if alias.lower() in text_lower:
            result.material_key = MATERIAL_ALIASES[alias]
            break

    # ---- 工况 (使用系数 K_A 的驱动端/被驱动端) ----
    # 解析 "中等冲击" "轻微冲击" 等关键词 → 自动匹配驱动/被驱动工况
    result.driver_type = "uniform"   # 默认: 电动机驱动(均匀)
    result.driven_type = "uniform"   # 默认: 均匀载荷

    # 工作机冲击级别
    if any(w in text_lower for w in ("严重冲击", "破碎机", "轧钢机", "重型")):
        result.driven_type = "heavy_shock"
    elif any(w in text_lower for w in ("中等冲击", "冲床", "振动", "中等震动")):
        result.driven_type = "moderate_shock"
    elif any(w in text_lower for w in ("轻微冲击", "轻震", "轻微震动", "起重机", "机床")):
        result.driven_type = "light_shock"

    # 原动机类型
    if any(w in text_lower for w in ("内燃机", "柴油机", "汽油机", "发动机")):
        result.driver_type = "light_shock"

    return result
