# MechEngine

AI 机械设计助手 — 像 Claude Code 操控代码一样操控 CAD 软件。

自然语言输入设计需求 → ISO 6336 标准计算 → 强度校核 → CAD 建模脚本。

## 快速开始

双击 `MechEngine.exe`，或：

```powershell
pip install rich
python mech.py
```

## 使用

```
MechEngine — 输入齿轮需求即可

mech> 直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质
mech> 5.5kW 960rpm 传动比3.2 中等冲击       ← 不知道模数也能用
mech> cad                                       ← 生成 SolidWorks 脚本
mech> report                                    ← 生成设计报告
```

## 功能

- 直齿/斜齿圆柱齿轮几何计算 (GB/T 1356)
- 齿面接触疲劳强度校核 (ISO 6336-2 / GB/T 3480.2)
- 齿根弯曲疲劳强度校核 (ISO 6336-3)
- 材料数据库 (GB/T 3480.5, 常见齿轮材料)
- 自然语言解析 (支持 "中等冲击" "40Cr调质" 等中文表述)
- 设计合成 (只知功率转速, 自动推荐模数齿数方案)
- SolidWorks Python COM 脚本生成 (正版/盗版SW均可)
- FreeCAD 脚本生成
- HTML 设计报告

## 验证状态

| 模块 | 状态 | 方法 |
|------|------|------|
| 几何计算 | ✓ 6/6 测试通过 | 手工公式推导对照 |
| 材料数据库 | 数据来源标注 | GB/T 3480.5 图表 |
| 载荷系数 K_A | ✓ 查表验证 | GB/T 3480.1 表1 |
| 载荷系数 K_V | GB/T 10063 方法 | 含z1和F_t/b影响 |
| 载荷系数 K_Hα/K_Fα | GB/T 3480.1 表5 | 单调性验证 |
| 接触强度 σ_H | 公式结构正确 | 待课本算例交叉验证 |
| 弯曲强度 σ_F | 公式结构正确 | 待课本算例交叉验证 |

## 项目结构

```
mech-engine/
├── MechEngine.exe      # 打包的可执行文件
├── mech.py             # CLI 入口
├── 启动.bat             # Windows 双击启动
├── app/
│   ├── engine/
│   │   ├── gears.py        # 几何计算
│   │   ├── strength.py     # ISO 6336 强度校核
│   │   ├── load_factors.py # 载荷系数
│   │   ├── materials.py    # 材料数据库
│   │   └── synthesis.py    # 设计合成 (需求→方案)
│   ├── ai/
│   │   ├── parser.py       # NL 解析
│   │   └── reporter.py     # 报告生成
│   └── output/
│       ├── cad_macro.py    # SW/FreeCAD 脚本生成
│       └── report.py       # HTML 报告
├── tests/
│   └── test_geometry.py    # 几何验证 (6/6)
└── knowledge/              # 内部参考
```

## 免责声明

本工具计算结果仅供参考。工程应用需经专业人员审核。使用者应自行承担因使用本工具而产生的任何风险。

## License

Apache 2.0
