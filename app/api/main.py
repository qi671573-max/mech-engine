"""
MechEngine REST API

Run:  uvicorn app.api.main:app --reload
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.engine.gears import GearDesignInput, compute_geometry
from app.engine.strength import compute_strength
from app.engine.materials import list_materials, resolve_material
from app.engine.synthesis import synthesize
from app.ai.parser import parse_gear_request

app = FastAPI(
    title="MechEngine API",
    description="AI-powered gear design and ISO 6336 strength analysis",
    version="0.2.0",
    license_info={"name": "Apache 2.0"},
)


# ─── Request / Response models ───────────────────────────────────────────────


class GearRequest(BaseModel):
    gear_type: str = Field("spur", description="'spur' or 'helical'")
    m_n: float = Field(..., gt=0, description="Normal module (mm)")
    z1: int = Field(..., ge=5, description="Pinion tooth count")
    z2: int | None = Field(None, ge=5, description="Wheel tooth count (optional)")
    beta_deg: float = Field(0.0, ge=0, lt=45, description="Helix angle (°)")
    x1: float = Field(0.0, description="Pinion profile shift coefficient")
    x2: float = Field(0.0, description="Wheel profile shift coefficient")
    b: float | None = Field(None, gt=0, description="Face width (mm)")
    power_kw: float | None = Field(None, gt=0, description="Transmitted power (kW)")
    rpm: float | None = Field(None, gt=0, description="Pinion speed (rpm)")
    material_key: str = Field("45钢-调质", description="Material identifier")
    accuracy_grade: int = Field(8, ge=5, le=12, description="ISO accuracy grade")
    driver_type: str = Field("uniform", description="Prime mover shock type")
    driven_type: str = Field("uniform", description="Driven machine shock type")


class GearGeometryResponse(BaseModel):
    z: int
    m_n: float
    beta_deg: float
    d: float
    da: float
    df: float
    db: float
    h: float
    s: float
    k_span: int
    base_tangent_length: float
    z_v: float


class PairGeometryResponse(BaseModel):
    u: float
    center_distance: float
    epsilon_alpha: float


class StrengthResponse(BaseModel):
    sigma_H: float
    sigma_HP: float
    S_H: float
    contact_pass: bool
    sigma_F1: float
    sigma_FP1: float
    S_F1: float
    sigma_F2: float
    sigma_FP2: float
    S_F2: float
    bending_pass: bool
    passed: bool
    K_A: float
    K_V: float
    K_Hbeta: float
    K_Halpha: float


class GearAnalysisResponse(BaseModel):
    pinion: GearGeometryResponse
    wheel: GearGeometryResponse | None
    pair: PairGeometryResponse | None
    strength: StrengthResponse | None
    material_label: str


class NLRequest(BaseModel):
    text: str = Field(..., min_length=3, description="Natural language gear requirement (Chinese/English)")


class SynthesisRequest(BaseModel):
    power_kw: float = Field(..., gt=0)
    rpm: float = Field(..., gt=0)
    ratio: float = Field(3.0, gt=1, description="Gear ratio u")
    material_key: str = "45钢-调质"
    gear_type: str = "spur"


class SynthesisProposal(BaseModel):
    z1: int
    z2: int
    m_n: float
    u_actual: float
    d1: float
    center_distance: float
    reason: str


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _gear_to_response(g) -> GearGeometryResponse:
    return GearGeometryResponse(
        z=g.z, m_n=g.m_n, beta_deg=g.beta_deg,
        d=round(g.d, 4), da=round(g.da, 4), df=round(g.df, 4),
        db=round(g.db, 4), h=round(g.h, 4), s=round(g.s, 4),
        k_span=g.k_span, base_tangent_length=round(g.base_tangent_length, 4),
        z_v=round(g.z_v, 4),
    )


# ─── Routes ──────────────────────────────────────────────────────────────────


@app.get("/", tags=["meta"])
def root():
    return {"project": "MechEngine", "version": "0.2.0", "docs": "/docs"}


@app.get("/materials", tags=["meta"])
def get_materials():
    """List all available gear materials."""
    return {"materials": list_materials()}


@app.post("/analyze", response_model=GearAnalysisResponse, tags=["design"])
def analyze(req: GearRequest):
    """
    Compute gear geometry and optional ISO 6336 strength check.

    Strength check runs automatically when `power_kw` and `rpm` are provided
    and `z2` is specified (gear pair required for strength analysis).
    """
    mat = resolve_material(req.material_key)
    if mat is None:
        raise HTTPException(400, f"Unknown material: {req.material_key}")

    inp = GearDesignInput(
        gear_type=req.gear_type,
        m_n=req.m_n,
        z1=req.z1,
        z2=req.z2,
        beta_deg=req.beta_deg,
        x1=req.x1,
        x2=req.x2,
        b=req.b,
        power_kw=req.power_kw,
        rpm=req.rpm,
        material_key=req.material_key,
    )

    result = compute_geometry(inp)
    if result.pair:
        result.pinion.b = req.b
        result.wheel.b = req.b  # type: ignore[union-attr]

    pair_resp = None
    if result.pair:
        pair_resp = PairGeometryResponse(
            u=round(result.pair.u, 4),
            center_distance=round(result.pair.a, 4),
            epsilon_alpha=round(result.pair.epsilon_alpha, 4),
        )

    strength_resp = None
    if result.pair and req.power_kw and req.rpm:
        sr = compute_strength(
            pinion=result.pinion,
            wheel=result.wheel,  # type: ignore[arg-type]
            pair=result.pair,
            power_kw=req.power_kw,
            rpm=req.rpm,
            material_key=req.material_key,
            accuracy_grade=req.accuracy_grade,
            driver_type=req.driver_type,
            driven_type=req.driven_type,
        )
        strength_resp = StrengthResponse(
            sigma_H=sr.sigma_H, sigma_HP=sr.sigma_HP, S_H=sr.S_H,
            contact_pass=sr.contact_pass,
            sigma_F1=sr.sigma_F1, sigma_FP1=sr.sigma_FP1, S_F1=sr.S_F1,
            sigma_F2=sr.sigma_F2, sigma_FP2=sr.sigma_FP2, S_F2=sr.S_F2,
            bending_pass=sr.bending_pass, passed=sr.passed,
            K_A=sr.K_A, K_V=sr.K_V, K_Hbeta=sr.K_Hbeta, K_Halpha=sr.K_Halpha,
        )

    return GearAnalysisResponse(
        pinion=_gear_to_response(result.pinion),
        wheel=_gear_to_response(result.wheel) if result.wheel else None,
        pair=pair_resp,
        strength=strength_resp,
        material_label=mat.label,
    )


@app.post("/parse", response_model=GearRequest, tags=["nlp"])
def parse_nl(req: NLRequest):
    """
    Parse a natural-language gear requirement into structured parameters.

    Example input: "直齿轮，模数3，20齿，5.5kW，960rpm，45钢调质"
    """
    parsed = parse_gear_request(req.text)
    if not parsed.is_complete():
        raise HTTPException(
            422,
            "Could not extract minimum required parameters (module + tooth count). "
            "Try: '模数3，20齿' or 'module=3, z1=20'."
        )
    return GearRequest(
        gear_type=parsed.gear_type,
        m_n=parsed.m_n,  # type: ignore[arg-type]
        z1=parsed.z1,  # type: ignore[arg-type]
        z2=parsed.z2,
        beta_deg=parsed.beta_deg,
        power_kw=parsed.power_kw,
        rpm=parsed.rpm,
        material_key=parsed.material_key,
        driver_type=parsed.driver_type,
        driven_type=parsed.driven_type,
    )


@app.post("/synthesize", response_model=list[SynthesisProposal], tags=["design"])
def synthesize_design(req: SynthesisRequest):
    """
    Generate candidate gear pair designs from power / speed / ratio requirements.

    Returns 2-3 proposals ranked by conservatism. Useful when module and tooth
    count are not yet known.
    """
    mat = resolve_material(req.material_key)
    if mat is None:
        raise HTTPException(400, f"Unknown material: {req.material_key}")

    proposals = synthesize(
        power_kw=req.power_kw,
        rpm=req.rpm,
        u=req.ratio,
        material_key=req.material_key,
        gear_type=req.gear_type,
    )

    return [
        SynthesisProposal(
            z1=p.z1, z2=p.z2, m_n=p.m_n, u_actual=round(p.u_actual, 3),
            d1=round(p.d1, 2), center_distance=round(p.a, 2), reason=p.reason,
        )
        for p in proposals
    ]
