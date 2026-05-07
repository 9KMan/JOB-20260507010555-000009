from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services import VehicleService, PriceService
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/v1", tags=["vehicles"])


class VehicleCreate(BaseModel):
    vin: str
    make: str
    model: str
    year: int
    trim: Optional[str] = None
    body_style: Optional[str] = None
    exterior_color: Optional[str] = None
    interior_color: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    drivetrain: Optional[str] = None
    engine: Optional[str] = None
    horsepower: Optional[int] = None
    torque: Optional[int] = None
    mileage: Optional[int] = None
    dealer_id: Optional[str] = None
    dealer_name: Optional[str] = None
    dealer_location: Optional[str] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None


class VehicleResponse(VehicleCreate):
    id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PriceRecord(BaseModel):
    vehicle_id: int
    vin: str
    price: float
    price_type: str = "listing"
    currency: str = "USD"
    mileage: Optional[int] = None
    condition: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None


class MarketPricingRequest(BaseModel):
    make: str
    model: str
    year: int
    mileage: int


class MarketPricingResponse(BaseModel):
    sample_size: int
    pricing: Optional[dict]
    mileage_adjustment: float


@router.post("/vehicles", response_model=VehicleResponse, status_code=201)
async def create_vehicle(
    vehicle: VehicleCreate,
    db: AsyncSession = Depends(get_db)
):
    service = VehicleService(db)
    existing = await service.get_vehicle_by_vin(vehicle.vin)
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle with this VIN already exists")

    db_vehicle = await service.create_vehicle(vehicle.model_dump())
    return db_vehicle


@router.get("/vehicles", response_model=List[VehicleResponse])
async def list_vehicles(
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    year_min: Optional[int] = Query(None),
    year_max: Optional[int] = Query(None),
    mileage_max: Optional[int] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    service = VehicleService(db)
    vehicles = await service.get_vehicles(
        make=make,
        model=model,
        year_min=year_min,
        year_max=year_max,
        mileage_max=mileage_max,
        limit=limit,
        offset=offset
    )
    return vehicles


@router.get("/vehicles/{vin}", response_model=VehicleResponse)
async def get_vehicle(vin: str, db: AsyncSession = Depends(get_db)):
    service = VehicleService(db)
    vehicle = await service.get_vehicle_by_vin(vin)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.put("/vehicles/{vin}", response_model=VehicleResponse)
async def update_vehicle(
    vin: str,
    vehicle: VehicleCreate,
    db: AsyncSession = Depends(get_db)
):
    service = VehicleService(db)
    updated = await service.update_vehicle(vin, vehicle.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return updated


@router.post("/prices", status_code=201)
async def record_price(
    price: PriceRecord,
    db: AsyncSession = Depends(get_db)
):
    service = PriceService(db)
    db_price = await service.record_price(price.model_dump())
    return {"id": db_price.id, "status": "recorded"}


@router.get("/prices/{vin}/history")
async def get_price_history(
    vin: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    service = PriceService(db)
    history = await service.get_price_history(vin, days)
    return {"vin": vin, "history": history}


@router.post("/prices/analyze")
async def analyze_prices(
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    service = PriceService(db)
    analysis = await service.analyze_prices(make=make, model=model, year=year, days=days)
    if not analysis:
        raise HTTPException(status_code=404, detail="No price data found for analysis")
    return analysis


@router.post("/pricing/market", response_model=MarketPricingResponse)
async def get_market_pricing(
    request: MarketPricingRequest,
    db: AsyncSession = Depends(get_db)
):
    service = PriceService(db)
    pricing = await service.get_market_pricing(
        make=request.make,
        model=request.model,
        year=request.year,
        mileage=request.mileage
    )
    return pricing
