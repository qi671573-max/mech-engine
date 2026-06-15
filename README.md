# MechEngine

[![CI](https://github.com/qi671573-max/mech-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/qi671573-max/mech-engine/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)

**AI-powered gear design assistant** — natural language in, ISO 6336 strength report out.

```
mech> 直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质
mech> 5.5kW 960rpm 传动比3.2 中等冲击    ← 不知模数也能用
mech> cad                                  ← 生成 SolidWorks / FreeCAD 脚本
mech> report                               ← 生成 HTML 设计报告
```

```
mech> 直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质

  MechEngine — 计算结果

  ─────────────────── 小齿轮 ───────────────────
  齿数 z            20
  模数 mₙ           3 mm
  分度圆直径 d       60.0 mm
  齿顶圆直径 dₐ      66.0 mm
  齿根圆直径 d_f     52.5 mm
  公法线长度 Wₖ      22.987 mm  (跨3齿)

  ─────────────────── 强度校核 ─────────────────
  接触应力 σ_H       285 MPa  ≤  590 MPa  ✓  S_H = 2.07
  弯曲应力 σ_F1       37 MPa  ≤  720 MPa  ✓  S_F1 = 19.6
```

## 功能

| 模块 | 功能 |
|------|------|
| **几何引擎** | 直/斜齿圆柱齿轮 GB/T 1356 全参数 |
| **强度校核** | ISO 6336-2/3 接触 + 弯曲疲劳 (Method B) |
| **载荷系数** | K_A / K_V / K_Hβ / K_Fβ / K_Hα / K_Fα |
| **材料数据库** | GB/T 3480.5 共 10 种常用材料 |
| **设计合成** | 只知 P/n/u → 自动推荐模数齿数方案 |
| **NL 解析** | "中等冲击" "40Cr调质" 等中文自然语言 |
| **CAD 输出** | SolidWorks COM Python 脚本 + FreeCAD 脚本 |
| **报告** | HTML 设计报告 |
| **REST API** | FastAPI 接口，支持 JSON 调用 |

## 快速开始

```bash
pip install rich
python mech.py
```

```
mech> 直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质
mech> cad      ← 生成 SolidWorks 脚本
mech> report   ← 生成 HTML 报告
mech> help
```

## REST API

```bash
pip install "mech-engine[api]"
uvicorn app.api.main:app --reload
# 文档: http://localhost:8000/docs
```

**分析齿轮副:**

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "m_n": 3, "z1": 25, "z2": 75,
    "b": 75, "power_kw": 5.5, "rpm": 960,
    "material_key": "45钢-调质"
  }'
```

```json
{
  "pinion": {"d": 75.0, "da": 81.0, "df": 67.5},
  "pair":   {"center_distance": 150.0, "epsilon_alpha": 1.745},
  "strength": {
    "sigma_H": 285.11, "sigma_HP": 590.0, "S_H": 2.069, "contact_pass": true,
    "sigma_F1": 36.8,  "sigma_FP1": 720.0, "S_F1": 19.57, "passed": true
  }
}
```

**自然语言解析:**

```bash
curl -X POST http://localhost:8000/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质"}'
```

**设计合成 (只知功率转速):**

```bash
curl -X POST http://localhost:8000/synthesize \
  -H "Content-Type: application/json" \
  -d '{"power_kw": 5.5, "rpm": 960, "ratio": 3.2}'
```

## 项目结构

```
mech-engine/
├── mech.py              # CLI 入口
├── app/
│   ├── engine/
│   │   ├── gears.py         # 几何计算 (GB/T 1356)
│   │   ├── strength.py      # ISO 6336 强度校核
│   │   ├── load_factors.py  # K_A / K_V / K_Hβ …
│   │   ├── materials.py     # 材料数据库 (GB/T 3480.5)
│   │   └── synthesis.py     # 需求 → 设计方案
│   ├── ai/
│   │   ├── parser.py        # 自然语言解析
│   │   └── reporter.py      # 报告文本生成
│   ├── api/
│   │   └── main.py          # FastAPI REST 接口
│   └── output/
│       ├── cad_macro.py     # SolidWorks / FreeCAD 脚本
│       └── report.py        # HTML 报告
└── tests/
    ├── test_geometry.py     # 几何验证 (6 tests)
    ├── test_strength.py     # 强度验证 (12 tests)
    ├── test_parser.py       # 解析器 (8 tests)
    └── test_api.py          # API 端点 (8 tests)
```

## 验证状态

| 模块 | 状态 | 方法 |
|------|------|------|
| 几何计算 | ✓ 6/6 通过 | 手工公式推导对照 |
| 材料数据库 | 数据来源标注 | GB/T 3480.5 图表 |
| 载荷系数 K_A | ✓ 查表验证 | GB/T 3480.1 表1 |
| 载荷系数 K_V | GB/T 10063 方法 | 含 z₁ 和 F_t/b 影响 |
| 接触强度 σ_H | 公式结构正确 | 待课本例题交叉验证 |
| 弯曲强度 σ_F | 公式结构正确 | 待课本例题交叉验证 |
| REST API | ✓ 8/8 通过 | FastAPI TestClient |

## 开发

```bash
pip install -e ".[dev,api]"
pytest                         # 全部测试
pytest tests/test_strength.py  # 仅强度校核测试
```

## 标准依据

- **GB/T 1356** — 渐开线圆柱齿轮齿形
- **GB/T 1357** — 模数系列
- **ISO 6336-2** / **GB/T 3480.2** — 接触疲劳强度 (Method B)
- **ISO 6336-3** / **GB/T 3480.3** — 弯曲疲劳强度 (Method B)
- **GB/T 3480.5** — 材料疲劳极限数据
- **GB/T 10063** — 动载系数

## 免责声明

本工具计算结果仅供参考。工程应用须经专业人员审核。使用者应自行承担因使用本工具而产生的任何风险。

## License

[Apache 2.0](LICENSE)
