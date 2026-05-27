"""
设计报告生成 — HTML + 可打印PDF

MVP: 生成 HTML 报告 (浏览器可直接打印为PDF)
后期: 接入 WeasyPrint 做服务端PDF生成
"""

from app.engine.gears import GearGeometry, GearPairGeometry, GearDesignResult
from app.engine.strength import StrengthResult


def generate_html_report(
    result: GearDesignResult,
    strength: StrengthResult | None = None,
) -> str:
    """生成完整的 HTML 设计报告"""
    p = result.pinion
    w = result.wheel
    pair = result.pair

    lines = ['''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>齿轮设计报告</title>
<style>
  body { font-family: "SimSun", "Noto Serif CJK SC", serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.6; }
  h1 { text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; }
  h2 { margin-top: 24px; border-left: 4px solid #2563eb; padding-left: 10px; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; }
  th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; }
  th { background: #f5f5f5; font-weight: bold; }
  .pass { color: #16a34a; font-weight: bold; }
  .fail { color: #dc2626; font-weight: bold; }
  .note { background: #fff3cd; border: 1px solid #ffc107; padding: 10px; margin: 16px 0; border-radius: 4px; font-size: 13px; }
  .footer { text-align: center; font-size: 12px; color: #999; margin-top: 40px; border-top: 1px solid #eee; padding-top: 15px; }
  @media print { body { font-size: 12px; } }
</style>
</head>
<body>
<h1>齿轮传动设计报告</h1>
<p style="text-align:center;color:#666">MechEngine — AI 机械设计助手</p>
''']

    # ---- 设计输入 ----
    lines.append('<h2>1. 设计输入</h2>')
    lines.append('<table>')
    lines.append(f'<tr><th>参数</th><th>数值</th><th>单位</th></tr>')
    lines.append(f'<tr><td>齿轮类型</td><td>{"斜齿圆柱齿轮" if p.is_helical else "直齿圆柱齿轮"}</td><td>—</td></tr>')
    lines.append(f'<tr><td>法向模数 mₙ</td><td>{p.m_n}</td><td>mm</td></tr>')
    if p.is_helical:
        lines.append(f'<tr><td>螺旋角 β</td><td>{p.beta_deg}</td><td>°</td></tr>')
    lines.append(f'<tr><td>小齿轮齿数 z₁</td><td>{p.z}</td><td>—</td></tr>')
    if w:
        lines.append(f'<tr><td>大齿轮齿数 z₂</td><td>{w.z}</td><td>—</td></tr>')
    if pair:
        lines.append(f'<tr><td>齿数比 u</td><td>{pair.u:.3f}</td><td>—</td></tr>')
    if result.input.power_kw:
        lines.append(f'<tr><td>传递功率 P</td><td>{result.input.power_kw}</td><td>kW</td></tr>')
    if result.input.rpm:
        lines.append(f'<tr><td>小齿轮转速 n₁</td><td>{result.input.rpm}</td><td>rpm</td></tr>')
    lines.append(f'<tr><td>材料</td><td>{result.input.material_key}</td><td>—</td></tr>')
    lines.append('</table>')

    # ---- 几何计算 ----
    lines.append('<h2>2. 几何参数计算</h2>')

    def gear_table(g: GearGeometry, label: str):
        rows = f'''<h3>{label}</h3>
<table>
<tr><th>参数</th><th>符号</th><th>公式</th><th>结果</th><th>单位</th></tr>
<tr><td>分度圆直径</td><td>d</td><td>m·z</td><td>{g.d:.4f}</td><td>mm</td></tr>
<tr><td>齿顶圆直径</td><td>dₐ</td><td>d + 2hₐ*mₙ</td><td>{g.da:.4f}</td><td>mm</td></tr>
<tr><td>齿根圆直径</td><td>d𝒻</td><td>d − 2(hₐ*+c*)mₙ</td><td>{g.df:.4f}</td><td>mm</td></tr>
<tr><td>基圆直径</td><td>dᵦ</td><td>d·cos(α)</td><td>{g.db:.4f}</td><td>mm</td></tr>
<tr><td>全齿高</td><td>h</td><td>hₐ + h𝒻</td><td>{g.h:.4f}</td><td>mm</td></tr>
<tr><td>公法线长度</td><td>Wₖ</td><td>k={g.k_span}</td><td>{g.base_tangent_length:.4f}</td><td>mm</td></tr>
'''
        if g.is_helical:
            rows += f'<tr><td>当量齿数</td><td>zᵥ</td><td>z/cos³(β)</td><td>{g.z_v:.2f}</td><td>—</td></tr>'
        rows += '</table>'
        return rows

    lines.append(gear_table(p, "小齿轮"))
    if w:
        lines.append(gear_table(w, "大齿轮"))

    if pair:
        lines.append('<h3>齿轮副参数</h3>')
        lines.append('<table>')
        lines.append(f'<tr><td>中心距 a</td><td>(d₁+d₂)/2</td><td>{pair.a:.4f} mm</td></tr>')
        lines.append(f'<tr><td>端面重合度 εₐ</td><td>—</td><td>{pair.epsilon_alpha:.4f}</td></tr>')
        lines.append('</table>')

    # ---- 强度校核 ----
    if strength:
        lines.append('<h2>3. 强度校核</h2>')
        lines.append('<p>依据: GB/T 3480 / ISO 6336 Method B</p>')

        # 载荷系数
        lines.append('<h3>3.1 载荷系数</h3>')
        lines.append('<table>')
        for name, value in [
            ("使用系数 K_A", strength.K_A),
            ("动载系数 K_V", round(strength.K_V, 3)),
            ("齿向分布系数 K_Hβ", round(strength.K_Hbeta, 4)),
            ("齿间分配系数 K_Hα", round(strength.K_Halpha, 3)),
        ]:
            lines.append(f'<tr><td>{name}</td><td>{value}</td></tr>')
        lines.append('</table>')

        # 接触强度
        lines.append('<h3>3.2 齿面接触疲劳强度</h3>')
        lines.append('<table>')
        lines.append(f'<tr><th>项目</th><th>数值</th><th>单位</th></tr>')
        lines.append(f'<tr><td>计算应力 σ_H</td><td>{strength.sigma_H:.2f}</td><td>MPa</td></tr>')
        lines.append(f'<tr><td>许用应力 σ_HP</td><td>{strength.sigma_HP:.2f}</td><td>MPa</td></tr>')
        lines.append(f'<tr><td>安全系数 S_H</td><td>{strength.S_H:.3f}</td><td>—</td></tr>')
        lines.append(f'<tr><td>最小安全系数 S_Hmin</td><td>{strength.S_Hmin}</td><td>—</td></tr>')
        status = "✓ 通过" if strength.contact_pass else "✗ 不通过"
        cls = "pass" if strength.contact_pass else "fail"
        lines.append(f'<tr><td>结论</td><td class="{cls}">{status}</td><td>—</td></tr>')
        lines.append('</table>')

        # 弯曲强度
        lines.append('<h3>3.3 齿根弯曲疲劳强度</h3>')
        lines.append('<table>')
        lines.append('<tr><th>项目</th><th>小齿轮</th><th>大齿轮</th><th>单位</th></tr>')
        lines.append(f'<tr><td>计算应力 σ_F</td><td>{strength.sigma_F1:.2f}</td><td>{strength.sigma_F2:.2f}</td><td>MPa</td></tr>')
        lines.append(f'<tr><td>许用应力 σ_FP</td><td>{strength.sigma_FP1:.2f}</td><td>{strength.sigma_FP2:.2f}</td><td>MPa</td></tr>')
        lines.append(f'<tr><td>安全系数 S_F</td><td>{strength.S_F1:.3f}</td><td>{strength.S_F2:.3f}</td><td>—</td></tr>')
        status2 = "✓ 通过" if strength.bending_pass else "✗ 不通过"
        cls2 = "pass" if strength.bending_pass else "fail"
        lines.append(f'<tr><td>结论</td><td colspan="2" class="{cls2}">{status2}</td></tr>')
        lines.append('</table>')

        # 总评
        overall = "✓ 齿轮设计满足强度要求" if strength.passed else "✗ 齿轮设计不满足强度要求"
        overall_cls = "pass" if strength.passed else "fail"
        lines.append(f'<h3>3.4 结论</h3>')
        lines.append(f'<p class="{overall_cls}" style="font-size:16px">{overall}</p>')

    # ---- 免责声明 ----
    lines.append('<div class="note">')
    lines.append('<strong>⚠ 免责声明</strong><br>')
    lines.append('本报告由 MechEngine 自动生成，计算结果仅供参考。<br>')
    lines.append('工程应用需经专业人员审核。使用者应自行承担因使用本报告而产生的任何风险。')
    lines.append('</div>')

    lines.append('<div class="footer">')
    lines.append('<p>Generated by MechEngine v0.1.0 | Calculation per GB/T 3480 / ISO 6336</p>')
    lines.append('</div>')

    lines.append('</body></html>')
    return '\n'.join(lines)
