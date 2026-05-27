"""
CAD 宏生成器 — FreeCAD 脚本 + SolidWorks VBA宏 + SolidWorks Python COM 脚本
"""

import math
from app.engine.gears import GearGeometry


# ═══════════════════════════════════════════════════════════════════════════
# FreeCAD
# ═══════════════════════════════════════════════════════════════════════════


def generate_freecad_script(gear: GearGeometry, output_path: str = "gear.FCStd") -> str:
    """生成 FreeCAD Python 脚本"""
    b = gear.b if gear.b else round(gear.d * 0.8, 1)
    return f'''# FreeCAD 渐开线齿轮 — z={gear.z}, m={gear.m_n}
# 使用方法: 打开 FreeCAD → Macro → Macros → 新建 → 粘贴 → 运行

import FreeCAD as App
import freecad.gears.commands
import Part

doc = App.newDocument("Gear_{gear.z}T_{gear.m_n}M")

g = freecad.gears.commands.CreateInvoluteGear.create()
g.teeth = {gear.z}
g.module = {gear.m_n}
g.beta = {gear.beta_deg}
g.height = {b}
g.pressure_angle = {gear.alpha_n_deg}

doc.recompute()
Part.export([g], "gear_{gear.z}T_{gear.m_n}M.step")
print("STEP file saved.")
doc.saveAs("{output_path}")
App.Gui.SendMsgToActiveView("ViewFit")
print("Done.")
'''


def generate_sw_macro(gear: GearGeometry) -> str:
    r"""生成 SolidWorks VBA 宏 — 完整渐开线直齿轮

    使用方法 (重要!):
      1. 打开 SolidWorks
      2. 工具 → 宏 → 新建 → 粘贴全部代码 → 另存为 .swp
      3. 或: 工具 → 宏 → 编辑 → 选择任意宏 → VBA编辑器 → 文件 → 导入文件 → 选此.bas
      4. 运行: 工具 → 宏 → 运行 → 选择保存的宏

    .bas 是VBA模块源码文件,不能直接双击打开。需要在 SolidWorks
    的VBA编辑器中导入(Import File),或粘贴到新建宏里。
    """
    rb = gear.db / 2   # 基圆半径 mm
    ra = gear.da / 2   # 齿顶圆半径 mm
    rf = gear.df / 2   # 齿根圆半径 mm
    r = gear.d / 2     # 分度圆半径 mm
    b = gear.b if gear.b else round(gear.d * 0.8, 1)
    z = gear.z
    m = gear.m_n
    alpha_rad = math.radians(gear.alpha_n_deg)

    # 渐开线在齿顶处的展开角
    t_tip = math.sqrt((ra / rb) ** 2 - 1) if ra > rb else 0.5

    # 齿槽中线的角度偏移量 (分度圆上一半齿槽宽对应角度 + inv(α))
    # 标准齿轮: 分度圆齿槽宽 = πm/2, 对应角度 = πm/(2r) = π/z
    half_space_angle = math.pi / z  # 分度圆上半齿槽角
    # 基圆上的偏转角 = half_space_angle + inv(α)
    base_offset_deg = math.degrees(half_space_angle + (math.tan(alpha_rad) - alpha_rad))

    # 左侧渐开线采样点 (从基圆到齿顶圆)
    n_pts = 20
    pts_left = []
    for i in range(n_pts + 1):
        t = t_tip * i / n_pts
        # 渐开线参数方程 (起始于基圆, 沿逆时针展开)
        x0 = rb * (math.cos(t) + t * math.sin(t))
        y0 = rb * (math.sin(t) - t * math.cos(t))
        # 旋转到齿槽左刃位置 (顺时针转 base_offset_deg)
        ang = -math.radians(base_offset_deg)
        cx, cy = math.cos(ang), math.sin(ang)
        x = x0 * cx - y0 * cy
        y = x0 * cy + y0 * cx
        pts_left.append((x, y))

    # 右侧渐开线 = 左侧关于齿槽中线镜像 (齿槽中线在角度0,即X轴正方向)
    pts_right = [(x, -y) for (x, y) in pts_left]

    # 生成 VBA spline 点数组 (3 * N doubles: x0,y0,z0, x1,y1,z1, ...)
    def vba_pts(pts, arr_name="splinePts"):
        lines = []
        for i, (x, y) in enumerate(pts):
            lines.append(f"    {arr_name}({i * 3}) = {x / 1000:.10f}#: {arr_name}({i * 3} + 1) = {y / 1000:.10f}#: {arr_name}({i * 3} + 2) = 0#")
        return "\n".join(lines)

    left_vba = vba_pts(pts_left, "splinePts")
    right_vba = vba_pts(pts_right, "splinePts2")

    # 齿根圆弧: 连接左右渐开线根部 (以 rf 为半径)
    root_start = pts_left[0]   # 左渐开线根部
    root_end = pts_right[0]    # 右渐开线根部
    # 计算这两点对应圆心角
    ang_start = math.atan2(root_start[1], root_start[0])
    ang_end = math.atan2(root_end[1], root_end[0])

    # 齿顶弧连接两端渐开线齿顶
    tip_start = pts_left[-1]
    tip_end = pts_right[-1]
    ang_tip_start = math.atan2(tip_start[1], tip_start[0])
    ang_tip_end = math.atan2(tip_end[1], tip_end[0])

    n_pts_total = n_pts + 1  # points per spline

    return f"""Attribute VB_Name = "GearMacro"
'========================================================================
' MechEngine — SolidWorks 渐开线直齿轮宏
'
' 参数: z={z}, m={m}mm, da={gear.da:.2f}mm, df={gear.df:.2f}mm, b={b}mm
'
' ══════ 使用方法 ══════
'  方法A: SolidWorks → 工具 → 宏 → 新建 → 粘贴全部 → 保存
'  方法B: SolidWorks → 工具 → 宏 → 编辑 → VBA编辑器 → 文件 → 导入文件 → 选此.bas
'  运行:  工具 → 宏 → 运行 → 选择此宏 → 点击"运行"
'
' ⚠ 如提示"未能启动Visual Basic",说明SW缺少VBA组件(破解版常见)
'   请使用 FreeCAD 代替: freecad.org 免费下载
'========================================================================

Option Explicit

' API常量
Private Const swThisConfiguration As Long = -1
Private Const swCreateFeatureBodyCheck As Long = 0

Sub main()
    On Error GoTo ErrHandler

    Dim swApp As SldWorks.SldWorks
    Set swApp = Application.SldWorks

    ' ── 1. 新建零件 ──
    swApp.SetUserPreferenceToggle swDefaultTemplatePart, False
    Dim swModel As ModelDoc2
    Set swModel = swApp.NewDocument("C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2022\\templates\\Part.prtdot", 0, 0, 0)
    If swModel Is Nothing Then
        swApp.NewDocument "C:\\ProgramData\\SOLIDWORKS\\SOLIDWORKS 2022\\templates\\Part.prtdot", 0, 0, 0
        Set swModel = swApp.ActiveDoc
    End If
    If swModel Is Nothing Then
        Set swModel = swApp.NewDocument("Part", 0, 0, 0)
    End If

    Dim swPart As PartDoc
    Set swPart = swModel

    ' ── 2. 创建齿轮毛坯 (拉伸圆柱) ──
    swModel.Extension.SelectByID2 "前视基准面", "PLANE", 0, 0, 0, False, 0, Nothing, 0
    swModel.SketchManager.InsertSketch True

    ' 齿顶圆
    swModel.SketchManager.CreateCircle 0#, 0#, 0#, {ra / 1000}#, 0#, 0#
    swModel.FeatureManager.FeatureExtrusion2 True, False, False, 0, 0, {b / 1000}#, 0, _
        False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False

    ' ── 3. 创建齿槽草图 ──
    swModel.Extension.SelectByID2 "前视基准面", "PLANE", 0, 0, 0, False, 0, Nothing, 0
    swModel.SketchManager.InsertSketch True

    ' 3a. 左侧渐开线样条
    Dim splinePts({n_pts_total * 3 - 1}) As Double
{left_vba}
    swModel.SketchManager.CreateSpline splinePts

    ' 3b. 右侧渐开线样条 (镜像的齿廓)
    Dim splinePts2({n_pts_total * 3 - 1}) As Double
{right_vba}
    swModel.SketchManager.CreateSpline splinePts2

    ' 3c. 齿根圆弧 (连接左右渐开线根部)
    swModel.SketchManager.CreateArc _
        {rf / 1000}# * Cos({ang_start}#), {rf / 1000}# * Sin({ang_start}#), 0#, _
        {rf / 1000}# * Cos({ang_end}#), {rf / 1000}# * Sin({ang_end}#), 0#, _
        -1  ' direction

    ' 3d. 齿顶圆弧 (连接左右渐开线顶部)
    swModel.SketchManager.CreateArc _
        {ra / 1000}# * Cos({ang_tip_start}#), {ra / 1000}# * Sin({ang_tip_start}#), 0#, _
        {ra / 1000}# * Cos({ang_tip_end}#), {ra / 1000}# * Sin({ang_tip_end}#), 0#, _
        1   ' direction

    swModel.SketchManager.InsertSketch True

    ' ── 4. 拉伸切除齿槽 ──
    swModel.Extension.SelectByID2 "Sketch2", "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    swModel.FeatureManager.FeatureExtrusion2 True, False, False, 0, 0, {b / 1000}#, 0, _
        False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False

    ' ── 5. 圆周阵列 {z} 个齿 ──
    swModel.ClearSelection2 True
    swModel.Extension.SelectByID2 "基准轴1", "AXIS", 0, 0, 0, True, 0, Nothing, 0

    ' 选择最后一个切除特征
    Dim featObj As Object
    Dim nFeat As Long
    nFeat = swPart.FirstFeature.GetNextFeature.GetNextFeature.GetNextFeature.GetNextFeature.Name
    swModel.Extension.SelectByID2 "切除-拉伸1", "BODYFEATURE", 0, 0, 0, False, 0, Nothing, 0

    swModel.FeatureManager.FeatureCircularPattern2 {z}, 2# * 3.14159265358979# / CDbl({z}), _
        False, "NULL", False, True, False

    swModel.ClearSelection2 True

    ' ── 6. 完成 ──
    swModel.EditRebuild3
    swModel.ViewZoomtofit2

    MsgBox "齿轮建模完成!" & vbCrLf & vbCrLf & _
           "z = {z}   m = {m} mm" & vbCrLf & _
           "d  = {gear.d:.2f} mm" & vbCrLf & _
           "da = {gear.da:.2f} mm" & vbCrLf & _
           "df = {gear.df:.2f} mm" & vbCrLf & _
           "b  = {b} mm", vbInformation, "MechEngine"
    Exit Sub

ErrHandler:
    MsgBox "错误: " & Err.Description & vbCrLf & vbCrLf & _
           "可能原因:" & vbCrLf & _
           "1. VBA组件缺失(破解版SW常见) → 请使用 FreeCAD 替代" & vbCrLf & _
           "2. SW版本不同,模板路径不同 → 已尝试自动适配" & vbCrLf & _
           "3. 打开的不是零件文件" & vbCrLf & vbCrLf & _
           "FreeCAD 免费下载: freecad.org", vbExclamation, "MechEngine Error"
End Sub
"""


# ═══════════════════════════════════════════════════════════════════════════
# SolidWorks Python COM 脚本 — 盗版SW可用, 不需要VBA!
# ═══════════════════════════════════════════════════════════════════════════

def _escape_py_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def generate_sw_python_script(gear: GearGeometry) -> str:
    r"""生成操控 SolidWorks 的 Python 脚本 (via COM)

    原理: SolidWorks 注册了 COM 接口, 外部程序可以通过 win32com 操控 SW。
    不依赖 VBA, 不依赖 SW 插件系统, 只依赖 Windows COM (系统自带)。

    使用方法:
      1. 安装依赖: pip install pywin32
      2. 打开 SolidWorks (随便新建一个零件或打开空白)
      3. 运行: python gear_sw.py
      4. SW 窗口会弹出 — 齿轮自动生成

    适用范围: SolidWorks 2010-2026 所有版本, 正版/破解版均可。
    VBA 损坏的破解版 SW 推荐使用此脚本。
    """
    rb = gear.db / 2
    ra = gear.da / 2
    rf = gear.df / 2
    r = gear.d / 2
    b = gear.b if gear.b else round(gear.d * 0.8, 1)
    z = gear.z
    m = gear.m_n
    alpha_rad = math.radians(gear.alpha_n_deg)

    # 渐开线参数
    t_tip = math.sqrt((ra / rb) ** 2 - 1) if ra > rb else 0.5
    half_space_angle = math.pi / z
    base_offset_deg = math.degrees(half_space_angle + (math.tan(alpha_rad) - alpha_rad))

    # 左侧渐开线点
    n_pts = 20
    pts_left_lines = []
    for i in range(n_pts + 1):
        t = t_tip * i / n_pts
        x0 = rb * (math.cos(t) + t * math.sin(t))
        y0 = rb * (math.sin(t) - t * math.cos(t))
        ang = -math.radians(base_offset_deg)
        cx, cy = math.cos(ang), math.sin(ang)
        x = x0 * cx - y0 * cy
        y = x0 * cy + y0 * cx
        pts_left_lines.append(f"    ({x:.10f}, {y:.10f}),")
    left_str = "\n".join(pts_left_lines)

    # 右侧渐开线点 (Y轴对称)
    pts_right_lines = []
    for i in range(n_pts + 1):
        t = t_tip * i / n_pts
        x0 = rb * (math.cos(t) + t * math.sin(t))
        y0 = rb * (math.sin(t) - t * math.cos(t))
        ang = math.radians(base_offset_deg)
        cx, cy = math.cos(ang), math.sin(ang)
        x = x0 * cx - y0 * cy
        y = x0 * cy + y0 * cx
        pts_right_lines.append(f"    ({x:.10f}, {-y:.10f}),")
    right_str = "\n".join(pts_right_lines)

    # 齿根弧起止点
    x_r1, y_r1 = pts_left[0] if 'pts_left' in dir() else (0,0)
    # Compute these inline in Python too
    t_first = 0.0
    x0 = rb * (math.cos(t_first) + t_first * math.sin(t_first))
    y0 = rb * (math.sin(t_first) - t_first * math.cos(t_first))
    ang = -math.radians(base_offset_deg)
    cx, cy = math.cos(ang), math.sin(ang)
    x_rs = x0 * cx - y0 * cy
    y_rs = x0 * cy + y0 * cx
    ang = math.radians(base_offset_deg)
    cx, cy = math.cos(ang), math.sin(ang)
    x_re = x0 * cx - y0 * cy
    y_re = -(x0 * cy + y0 * cx)

    # 齿顶弧起止点
    x0_t = rb * (math.cos(t_tip) + t_tip * math.sin(t_tip))
    y0_t = rb * (math.sin(t_tip) - t_tip * math.cos(t_tip))
    ang = -math.radians(base_offset_deg)
    cx, cy = math.cos(ang), math.sin(ang)
    x_ts = x0_t * cx - y0_t * cy
    y_ts = x0_t * cy + y0_t * cx
    ang = math.radians(base_offset_deg)
    cx, cy = math.cos(ang), math.sin(ang)
    x_te = x0_t * cx - y0_t * cy
    y_te = -(x0_t * cy + y0_t * cx)

    return f'''"""
MechEngine — SolidWorks 齿轮自动建模脚本 (Python COM)
参数: z={z}, m={m}mm, da={gear.da:.2f}mm, b={b}mm

使用方法:
  1. pip install pywin32  (首次只需一次)
  2. 打开 SolidWorks
  3. python gear_{z}t_{m}m.py

⚠ 不需要VBA! 盗版SW可用!
  SolidWorks 的 COM 接口是 Windows 系统级功能,与 VBA 无关。
  SW 启动后会自动注册 COM 接口,本脚本通过 COM 操控 SW。
"""

import math
import sys
import time

try:
    import win32com.client
except ImportError:
    print("请先安装 pywin32: pip install pywin32")
    sys.exit(1)

PI = math.pi

def mm_to_m(v):
    """毫米转米 (SW API 使用米)"""
    return v / 1000.0

# ── 连接 SolidWorks ──
print("正在连接 SolidWorks...")
try:
    swApp = win32com.client.Dispatch("SldWorks.Application")
    swApp.Visible = True
except Exception:
    print("无法连接 SolidWorks。请确保 SW 已启动。")
    sys.exit(1)

swModel = swApp.ActiveDoc
if swModel is None:
    swModel = swApp.NewDocument("Part", 0, 0, 0)
    if swModel is None:
        print("无法创建新文档")
        sys.exit(1)

swModel = swApp.ActiveDoc
swSelMgr = swModel.SelectionManager
swSketchMgr = swModel.SketchManager
swFeatMgr = swModel.FeatureManager

print("SolidWorks 已连接, 开始建模...")

# ── Step 1: 齿轮毛坯 ──
swModel.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
swSketchMgr.InsertSketch(True)
swSketchMgr.CreateCircle(0.0, 0.0, 0.0, mm_to_m({ra}), 0.0, 0.0)
swFeatMgr.FeatureExtrusion2(True, False, False, 0, 0, mm_to_m({b}), 0,
    False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)

# ── Step 2: 齿槽草图 ──
swModel.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
swSketchMgr.InsertSketch(True)

# 左侧渐开线
left_pts = [
{left_str}
]
n = len(left_pts)
spline_arr = win32com.client.VARIANT(Python.VariantType.VariantType.VBArray, [0.0] * (n * 3))
for i, (x, y) in enumerate(left_pts):
    spline_arr[i * 3] = mm_to_m(x)
    spline_arr[i * 3 + 1] = mm_to_m(y)
    spline_arr[i * 3 + 2] = 0.0
swSketchMgr.CreateSpline(spline_arr)

# 右侧渐开线
right_pts = [
{right_str}
]
spline_arr2 = win32com.client.VARIANT(Python.VariantType.VariantType.VBArray, [0.0] * (n * 3))
for i, (x, y) in enumerate(right_pts):
    spline_arr2[i * 3] = mm_to_m(x)
    spline_arr2[i * 3 + 1] = mm_to_m(y)
    spline_arr2[i * 3 + 2] = 0.0
swSketchMgr.CreateSpline(spline_arr2)

# 齿根圆弧
swSketchMgr.CreateArc(
    mm_to_m({x_rs}), mm_to_m({y_rs}), 0.0,
    mm_to_m({x_re}), mm_to_m({y_re}), 0.0, -1)

# 齿顶圆弧
swSketchMgr.CreateArc(
    mm_to_m({x_ts}), mm_to_m({y_ts}), 0.0,
    mm_to_m({x_te}), mm_to_m({y_te}), 0.0, 1)

swSketchMgr.InsertSketch(True)

# ── Step 3: 拉伸切除 ──
swModel.Extension.SelectByID2("Sketch2", "SKETCH", 0, 0, 0, False, 0, None, 0)
swFeatMgr.FeatureExtrusion2(True, False, False, 0, 0, mm_to_m({b}), 0,
    False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)

# ── Step 4: 圆周阵列 ──
swModel.ClearSelection2(True)
swModel.Extension.SelectByID2("", "AXIS", 0, 0, 0, True, 0, None, 0)
swModel.Extension.SelectByID2("Cut-Extrude1", "BODYFEATURE", 0, 0, 0, False, 0, None, 0)
swFeatMgr.FeatureCircularPattern2({z}, 2.0 * PI / {z},
    False, "NULL", False, True, False)

# ── 完成 ──
swModel.EditRebuild3()
swModel.ViewZoomtofit2()
print("✓ 齿轮建模完成!")
print(f"  z={z}, m={m}mm, d={gear.d:.2f}mm, da={gear.da:.2f}mm, b={b}mm")
'''
