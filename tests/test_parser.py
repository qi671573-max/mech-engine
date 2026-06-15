"""
自然语言解析器测试
"""

import pytest
from app.ai.parser import parse_gear_request


def test_parse_full_chinese():
    r = parse_gear_request("直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质")
    assert r.gear_type == "spur"
    assert r.m_n == pytest.approx(3.0)
    assert r.z1 == 20
    assert r.power_kw == pytest.approx(5.5)
    assert r.rpm == pytest.approx(960.0)
    assert r.material_key == "45钢-调质"


def test_parse_gear_pair_with_ratio():
    r = parse_gear_request("模数2.5，小齿轮20齿，传动比3.2，5.5kW，960rpm")
    assert r.z1 == 20
    assert r.z2 == pytest.approx(64, abs=2)  # 20 × 3.2 = 64
    assert r.m_n == pytest.approx(2.5)


def test_parse_helical():
    r = parse_gear_request("斜齿轮 螺旋角15° 模数3 25齿 75齿")
    assert r.gear_type == "helical"
    assert r.beta_deg == pytest.approx(15.0)
    assert r.z1 == 25
    assert r.z2 == 75


def test_parse_moderate_shock():
    r = parse_gear_request("5.5kW 960rpm 模数3 20齿 中等冲击")
    assert r.driven_type == "moderate_shock"


def test_parse_heavy_shock():
    r = parse_gear_request("破碎机传动 模数4 24齿 11kW 480rpm")
    assert r.driven_type == "heavy_shock"


def test_parse_40cr_material():
    r = parse_gear_request("40Cr调质 模数3 25齿 5.5kW 960rpm")
    assert r.material_key == "40Cr-调质"


def test_is_complete_with_module_and_z1():
    r = parse_gear_request("模数3 20齿")
    assert r.is_complete()


def test_is_incomplete_without_module():
    r = parse_gear_request("20齿 5.5kW")
    assert not r.is_complete()
