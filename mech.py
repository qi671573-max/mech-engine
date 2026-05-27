#!/usr/bin/env python3
"""
MechEngine — AI 机械设计助手 (CLI Agent)

像 Claude Code 操控代码一样操控 CAD 软件。

用法:
  mech> 直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质
  mech> cad    ← 在 SolidWorks 中生成3D模型
  mech> report ← 生成设计报告
  mech> help   ← 查看命令
"""

import sys
import os
import math

# 确保能找到 app 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engine.gears import GearGeometry, GearPairGeometry, compute_geometry, GearDesignInput
from app.engine.strength import compute_strength
from app.engine.materials import resolve_material, list_materials
from app.ai.parser import parse_gear_request
from app.ai.reporter import build_report_text
from app.output.report import generate_html_report
from app.output.cad_macro import generate_sw_python_script, generate_freecad_script

# ── 终端增强 (可选依赖) ──
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich import box
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def print_banner():
    if HAS_RICH:
        console.print()
        console.print("[bold cyan]MechEngine[/bold cyan] [dim]— 输入齿轮需求即可[/dim]")
        console.print()
    else:
        print("\n  MechEngine — 输入齿轮需求即可\n")


def print_help():
    text = """
  直接输入需求:
    直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质
    5.5kW 960rpm 传动比3.2 中等冲击

  命令: cad | report | materials | q 退出
"""
    if HAS_RICH:
        console.print(text)
    else:
        print(text)


def print_examples():
    examples = [
        "直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质",
        "直齿轮，模数2.5，25齿，传动比3，7.5kW，1200rpm，40Cr调质",
        "斜齿轮，模数3，30齿，螺旋角15度，10kW，960rpm，20CrMnTi渗碳淬火",
        "直齿轮，模数4，18齿，10kW，750rpm，40Cr表面淬火",
    ]
    for e in examples:
        print(f"  {e}")


def print_material_list():
    if HAS_RICH:
        table = Table(title="可用材料", box=box.SIMPLE)
        table.add_column("材料", style="cyan")
        table.add_column("热处理")
        table.add_column("硬度")
        table.add_column("σ_Hlim", justify="right")
        table.add_column("σ_Flim", justify="right")

        from app.engine.materials import MATERIALS
        for m in MATERIALS.values():
            hardness = f"{m.hardness_min}-{m.hardness_max} {m.hardness_unit}"
            table.add_row(
                m.name, m.heat_treatment, hardness,
                str(m.sigma_hlim), str(m.sigma_flim),
            )
        console.print(table)
    else:
        from app.engine.materials import MATERIALS
        print(f"\n{'材料':<12} {'热处理':<10} {'硬度':<16} {'σ_Hlim':>8} {'σ_Flim':>8}")
        print("-" * 60)
        for m in MATERIALS.values():
            hardness = f"{m.hardness_min}-{m.hardness_max} {m.hardness_unit}"
            print(f"{m.name:<12} {m.heat_treatment:<10} {hardness:<16} {m.sigma_hlim:>8} {m.sigma_flim:>8}")


# ── 状态: 保存上一次计算结果 ──
_last_geom = None
_last_strength = None
_last_input_text = ""
_last_proposals = []  # 候选设计方案


def handle_calculate(text: str):
    """解析 + 计算 + 展示结果"""
    global _last_geom, _last_strength, _last_input_text, _last_proposals

    # 方案选择: "方案1" / "方案2" / "方案3"
    import re as _re
    sel = _re.match(r'方案\s*(\d)', text)
    if sel and _last_proposals:
        idx = int(sel.group(1)) - 1
        if 0 <= idx < len(_last_proposals):
            p = _last_proposals[idx]
            text = f"{_last_input_text} 模数{p.m_n} {p.z1}齿 大齿轮{p.z2}齿"

    parsed = parse_gear_request(text)

    # 参数不完整: 尝试设计合成
    if not parsed.is_complete():
        can_synthesize = (
            parsed.power_kw is not None
            and parsed.rpm is not None
        )
        if can_synthesize:
            from app.engine.synthesis import synthesize, format_proposals

            # 从解析结果推断齿数比
            u = 3.0
            if parsed.z1 and parsed.z2:
                u = parsed.z2 / parsed.z1
            else:
                # 从文本提取传动比: "传动比3.2" "速比3" "u=3.2" "比3:1"
                import re as _re2
                for pat in [
                    r'(?:传动比|齿数比|速比|减速比)\s*[=:：]?\s*(\d+\.?\d*)',
                    r'[Uu]\s*[=:：]\s*(\d+\.?\d*)',
                    r'(\d+\.?\d*)\s*[:：]\s*1',
                ]:
                    m = _re2.search(pat, text)
                    if m:
                        u = float(m.group(1))
                        break

            _last_proposals = synthesize(
                power_kw=parsed.power_kw,
                rpm=parsed.rpm,
                u=u,
                material_key=parsed.material_key,
                gear_type=parsed.gear_type,
                K_A=parsed.driver_type != "uniform" and 1.5 or 1.0,
            )
            _last_input_text = text
            if HAS_RICH:
                console.print()
                console.print("[bold yellow]未指定模数和齿数，自动估算中...[/bold yellow]")
                console.print()
                console.print(format_proposals(_last_proposals))
                console.print()
                console.print("[dim]输入 方案1/方案2/方案3 选择，或手动输入完整参数[/dim]")
                console.print()
            else:
                print(f"\n  未指定模数和齿数，自动生成{len(_last_proposals)}个候选方案:")
                print(format_proposals(_last_proposals))
            return
        else:
            missing = []
            if parsed.m_n is None: missing.append("模数")
            if parsed.z1 is None: missing.append("齿数")
            print(f"\n  参数不足: {', '.join(missing)}")
            print(f"  至少需要: 功率(kW) + 转速(rpm)  或  模数 + 齿数")
            print(f"  示例: 5.5kW 960rpm 传动比3.2 45钢调质\n")
            return

    design_input = GearDesignInput(
        gear_type=parsed.gear_type,
        m_n=parsed.m_n,
        z1=parsed.z1,
        z2=parsed.z2,
        beta_deg=parsed.beta_deg,
        power_kw=parsed.power_kw,
        rpm=parsed.rpm,
        material_key=parsed.material_key,
    )

    _last_geom = compute_geometry(design_input)
    _last_input_text = text

    # 强度校核 (需要功率+转速+齿数对)
    _last_strength = None
    if (parsed.power_kw and parsed.rpm
            and _last_geom.pair and _last_geom.wheel):
        _last_strength = compute_strength(
            pinion=_last_geom.pinion,
            wheel=_last_geom.wheel,
            pair=_last_geom.pair,
            power_kw=parsed.power_kw,
            rpm=parsed.rpm,
            material_key=parsed.material_key,
            driver_type=parsed.driver_type,
            driven_type=parsed.driven_type,
        )

    # ── 展示结果 ──
    p = _last_geom.pinion
    w = _last_geom.wheel
    pair = _last_geom.pair

    if HAS_RICH:
        console.print()

        # 输入摘要
        gear_type_str = "斜齿圆柱齿轮" if p.is_helical else "直齿圆柱齿轮"
        console.print(f"[bold]{gear_type_str}[/bold]  "
                      f"mₙ={p.m_n}  z₁={p.z}", end="")
        if w: console.print(f"  z₂={w.z}  u={pair.u:.2f}", end="")
        if parsed.power_kw: console.print(f"  P={parsed.power_kw}kW", end="")
        if parsed.rpm: console.print(f"  n₁={parsed.rpm}rpm", end="")
        console.print(f"  [{parsed.material_key}]")
        console.print()

        # 几何参数表
        table = Table(title="几何参数", box=box.SIMPLE, title_style="bold cyan")
        table.add_column("参数")
        table.add_column("符号")
        table.add_column("小齿轮", justify="right", style="cyan")
        if w: table.add_column("大齿轮", justify="right", style="green")
        table.add_column("单位")

        rows = [
            ("分度圆直径", "d", f"{p.d:.2f}", f"{w.d:.2f}" if w else "—", "mm"),
            ("齿顶圆直径", "dₐ", f"{p.da:.2f}", f"{w.da:.2f}" if w else "—", "mm"),
            ("齿根圆直径", "d𝒻", f"{p.df:.2f}", f"{w.df:.2f}" if w else "—", "mm"),
            ("基圆直径", "dᵦ", f"{p.db:.2f}", f"{w.db:.2f}" if w else "—", "mm"),
            ("全齿高", "h", f"{p.h:.3f}", f"{w.h:.3f}" if w else "—", "mm"),
            ("公法线长度", "Wₖ", f"{p.base_tangent_length:.4f}", f"{w.base_tangent_length:.4f}" if w else "—", "mm"),
            ("跨齿数", "k", str(p.k_span), str(w.k_span) if w else "—", "—"),
        ]

        for row in rows:
            table.add_row(*row)
        console.print(table)

        if pair:
            console.print(f"  中心距 a = [bold]{pair.a:.2f} mm[/bold]  |  "
                          f"重合度 εₐ = [bold]{pair.epsilon_alpha:.4f}[/bold]")

        # 强度校核
        if _last_strength:
            s = _last_strength
            console.print()
            s_table = Table(title="强度校核 (ISO 6336 Method B)", box=box.SIMPLE, title_style="bold yellow")
            s_table.add_column("项目")
            s_table.add_column("计算值", justify="right")
            s_table.add_column("许用值", justify="right")
            s_table.add_column("安全系数", justify="right")
            s_table.add_column("结果")

            contact_ok = "✓" if s.contact_pass else "✗"
            contact_style = "green" if s.contact_pass else "red"
            bending_ok = "✓" if s.bending_pass else "✗"
            bending_style = "green" if s.bending_pass else "red"

            s_table.add_row(
                f"接触强度 σ_H", f"{s.sigma_H:.1f} MPa",
                f"{s.sigma_HP:.1f} MPa",
                f"{s.S_H:.3f} (≥{s.S_Hmin})",
                f"[{contact_style}]{contact_ok}[/{contact_style}]"
            )
            s_table.add_row(
                f"弯曲强度 σ_F (小)", f"{s.sigma_F1:.1f} MPa",
                f"{s.sigma_FP1:.1f} MPa",
                f"{s.S_F1:.3f} (≥{s.S_Fmin})",
                f"[{bending_style}]{bending_ok}[/{bending_style}]"
            )
            s_table.add_row(
                f"弯曲强度 σ_F (大)", f"{s.sigma_F2:.1f} MPa",
                f"{s.sigma_FP2:.1f} MPa",
                f"{s.S_F2:.3f} (≥{s.S_Fmin})",
                f"[{bending_style}]{bending_ok}[/{bending_style}]"
            )

            console.print(s_table)

            # 总评
            if s.passed:
                console.print("\n  [bold green]✓ 齿轮设计满足强度要求[/bold green]")
            else:
                console.print("\n  [bold red]✗ 齿轮设计不满足强度要求[/bold red]")

        console.print()
        console.print("[dim]输入 cad 建模 | report 生成报告 | <参数> 重新计算[/dim]")
        console.print()

    else:
        # 无 Rich 的纯文本输出
        print(f"\n  {'='*50}")
        print(f"  齿轮类型: {'斜齿' if p.is_helical else '直齿'}  |  mₙ={p.m_n}  |  z₁={p.z}")
        print(f"  分度圆 d₁={p.d:.2f} mm  |  齿顶圆 da₁={p.da:.2f} mm")
        if pair:
            print(f"  中心距 a={pair.a:.2f} mm  |  重合度 ε={pair.epsilon_alpha:.4f}")
        if _last_strength:
            s = _last_strength
            print(f"  接触: σ_H={s.sigma_H:.1f} / σ_HP={s.sigma_HP:.1f} MPa  S_H={s.S_H:.3f} {'✓' if s.contact_pass else '✗'}")
            print(f"  弯曲: σ_F1={s.sigma_F1:.1f} / σ_FP1={s.sigma_FP1:.1f} MPa  S_F1={s.S_F1:.3f} {'✓' if s.bending_pass else '✗'}")
        print(f"  {'='*50}\n")


def handle_cad(target: str):
    """生成 CAD 脚本并尝试操控 CAD"""
    global _last_geom, _last_input_text

    if _last_geom is None:
        print("\n  没有计算结果。请先输入齿轮参数。\n")
        return

    gear = _last_geom.pinion

    if target == "freecad":
        script = generate_freecad_script(gear)
        path = f"gear_{gear.z}t_{gear.m_n}m_freecad.py"
    else:
        script = generate_sw_python_script(gear)
        path = f"gear_{gear.z}t_{gear.m_n}m_sw.py"

    # 写入文件
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)

    if HAS_RICH:
        console.print()
        console.print(Panel.fit(
            f"[bold]CAD 脚本已生成[/bold]\n"
            f"文件: [cyan]{path}[/cyan]\n\n"
            f"使用方法:\n"
            f"  [dim]$[/dim] [bold]pip install pywin32[/bold]  (仅首次)\n"
            f"  [dim]$[/dim] [bold]python {path}[/bold]\n\n"
            f"SolidWorks 中会自动生成齿轮 3D 模型。",
            border_style="green",
        ))
        console.print()
    else:
        print(f"\n  CAD 脚本已保存到 {path}")
        print(f"  运行: pip install pywin32 && python {path}\n")


def handle_report():
    global _last_geom, _last_strength

    if _last_geom is None:
        print("\n  没有计算结果。请先输入齿轮参数。\n")
        return

    html = generate_html_report(_last_geom, _last_strength)
    path = "gear_design_report.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  设计报告已保存到 {path}")
    print(f"  在浏览器中打开即可查看，Ctrl+P 打印为 PDF。\n")


# ═══════════════════════════════════════════════════════════════════════════
# 主循环
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print_banner()

    while True:
        try:
            if HAS_RICH:
                cmd = console.input("[bold cyan]mech>[/bold cyan] ").strip()
            else:
                cmd = input("mech> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not cmd:
            continue

        cmd_lower = cmd.lower()

        if cmd_lower in ("q", "quit", "exit"):
            break
        elif cmd_lower in ("help", "h", "?"):
            print_help()
        elif cmd_lower in ("examples",):
            print_examples()
        elif cmd_lower in ("materials", "m"):
            print_material_list()
        elif cmd_lower in ("clear", "cls"):
            os.system("cls" if os.name == "nt" else "clear")
            print_banner()
        elif cmd_lower in ("cad", "cad:sw", "sw"):
            handle_cad("sw")
        elif cmd_lower in ("cad:freecad", "freecad"):
            handle_cad("freecad")
        elif cmd_lower in ("report", "r"):
            handle_report()
        else:
            handle_calculate(cmd)


if __name__ == "__main__":
    main()
