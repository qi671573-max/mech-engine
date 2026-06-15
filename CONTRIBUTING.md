# Contributing to MechEngine

## 开发环境

```bash
git clone https://github.com/qi671573-max/mech-engine
cd mech-engine
pip install -e ".[dev,api]"
```

## 运行测试

```bash
pytest              # 所有测试
pytest -v --cov=app # 带覆盖率
```

## 代码规范

- Python 3.10+，类型注解
- 使用 `ruff check` 检查风格
- 新功能必须附带测试
- 计算系数请标注数据来源（标准号 + 图表编号）

## 增加材料

在 `app/engine/materials.py` 的 `MATERIALS` 字典中添加 `GearMaterial` 条目，数据来源请标注至 GB/T 3480.5 或机械设计手册具体页面。

## 增加计算标准

强度计算在 `app/engine/strength.py`。新增系数请在函数 docstring 中引用标准来源，并在 `tests/test_strength.py` 中添加回归测试。

## Pull Request

1. Fork → 新建分支 → 修改 → 测试通过 → PR
2. PR 描述中说明修改内容和标准依据
3. CI 通过后等待 review
