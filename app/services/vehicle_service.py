from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from app.models import Vehicle, ListingPrice, PriceAnalysis, ScrapeJob, Dealer
from datetime import datetime, timedelta
from typing import List, Optional
import statistics


class VehicleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_vehicle(self, vehicle_data: dict) -> Vehicle:
        vehicle = Vehicle(**vehicle_data)
        self.db.add(vehicle)
        await self.db.commit()
        await self.db.refresh(vehicle)
        return vehicle

    async def get_vehicle_by_vin(self, vin: str) -> Optional[Vehicle]:
        result = await self.db.execute(
            select(Vehicle).where(Vehicle.vin == vin)
        )
        return result.scalar_one_or_none()

    async def get_vehicles(
        self,
        make: Optional[str] = None,
        model: Optional[str] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        mileage_max: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Vehicle]:
        query = select(Vehicle)

        filters = []
        if make:
            filters.append(Vehicle.make.ilike(f"%{make}%"))
        if model:
            filters.append(Vehicle.model.ilike(f"%{model}%"))
        if year_min:
            filters.append(Vehicle.year >= year_min)
        if year_max:
            filters.append(Vehicle.year <= year_max)
        if mileage_max:
            filters.append(Vehicle.mileage <= mileage_max)

        if filters:
            query = query.where(and_(*filters))

        query = query.limit(limit).offset(offset).order_by(Vehicle.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_vehicle(self, vin: str, update_data: dict) -> Optional[Vehicle]:
        vehicle = await self.get_vehicle_by_vin(vin)
        if not vehicle:
            return None

        for key, value in update_data.items():
            if hasattr(vehicle, key):
                setattr(vehicle, key, value)

        vehicle.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(vehicle)
        return vehicle

    async def get_dealer_inventory(self, dealer_id: str) -> List[Vehicle]:
        result = await self.db.execute(
            select(Vehicle)
            .where(Vehicle.dealer_id == dealer_id)
            .order_by(Vehicle.created_at.desc())
        )
        return result.scalars().all()


class PriceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_price(self, price_data: dict) -> ListingPrice:
        price = ListingPrice(**price_data)
        self.db.add(price)
        await self.db.commit()
        await self.db.refresh(price)
        return price

    async def get_price_history(self, vin: str, days: int = 30) -> List[ListingPrice]:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        result = await self.db.execute(
            select(ListingPrice)
            .where(
                and_(
                    ListingPrice.vin == vin,
                    ListingPrice.scraped_at >= cutoff_date
                )
            )
            .order_by(ListingPrice.scraped_at.desc())
        )
        return result.scalars().all()

    async def analyze_prices(
        self,
        make: Optional[str] = None,
        model: Optional[str] = None,
        year: Optional[int] = None,
        days: int = 30
    ) -> Optional[PriceAnalysis]:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = select(ListingPrice).where(ListingPrice.scraped_at >= cutoff_date)

        filters = []
        if make:
            vehicle_subquery = select(Vehicle.id).where(
                and_(Vehicle.make.ilike(f"%{make}%"))
            )
            if model:
                vehicle_subquery = vehicle_subquery.where(
                    Vehicle.model.ilike(f"%{model}%")
                )
            if year:
                vehicle_subquery = vehicle_subquery.where(Vehicle.year == year)
            filters.append(ListingPrice.vehicle_id.in_(vehicle_subquery))

        if filters:
            query = query.where(and_(*filters))

        result = await self.db.execute(query)
        prices = result.scalars().all()

        if not prices:
            return None

        price_values = [p.price for p in prices]
        avg_price = statistics.mean(price_values)
        min_price = min(price_values)
        max_price = max(price_values)
        median_price = statistics.median(price_values)
        std_dev = statistics.stdev(price_values) if len(price_values) > 1 else 0

        analysis = PriceAnalysis(
            make=make,
            model=model,
            year=year,
            avg_price=avg_price,
            min_price=min_price,
            max_price=max_price,
            median_price=median_price,
            price_std_dev=std_dev,
            sample_size=len(prices),
            analysis_date=datetime.utcnow()
        )

        self.db.add(analysis)
        await self.db.commit()
        await self.db.refresh(analysis)
        return analysis

    async def get_market_pricing(
        self,
        make: str,
        model: str,
        year: int,
        mileage: int,
        limit: int = 20
    ) -> dict:
        vehicles_result = await self.db.execute(
            select(Vehicle).where(
                and_(
                    Vehicle.make.ilike(f"%{make}%"),
                    Vehicle.model.ilike(f"%{model}%"),
                    Vehicle.year == year
                )
            ).limit(limit)
        )
        vehicles = vehicles_result.scalars().all()

        if not vehicles:
            return {"sample_size": 0, "pricing": None}

        vin_list = [v.vin for v in vehicles]
        prices_result = await self.db.execute(
            select(ListingPrice).where(
                and_(
                    ListingPrice.vin.in_(vin_list),
                    ListingPrice.scraped_at >= datetime.utcnow() - timedelta(days=7)
                )
            )
        )
        prices = prices_result.scalars().all()

        if not prices:
            return {"sample_size": len(vehicles), "pricing": None}

        price_values = [p.price for p in prices]
        return {
            "sample_size": len(vehicles),
            "pricing": {
                "avg_price": statistics.mean(price_values),
                "min_price": min(price_values),
                "max_price": max(price_values),
                "median_price": statistics.median(price_values),
                "std_dev": statistics.stdev(price_values) if len(price_values) > 1 else 0
            },
            "mileage_adjustment": self._calculate_mileage_adjustment(mileage, vehicles)
        }

    def _calculate_mileage_adjustment(self, target_mileage: int, vehicles: List[Vehicle]) -> float:
        if not vehicles:
            return 0.0

        avg_mileage = statistics.mean([v.mileage for v in vehicles if v.mileage])
        if avg_mileage == 0:
            return 0.0

        mileage_diff_pct = ((avg_mileage - target_mileage) / avg_mileage) * 100
        return round(mileage_diff_pct, 2)


class ScrapeJobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, job_data: dict) -> ScrapeJob:
        job = ScrapeJob(**job_data)
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def update_job(self, job_id: str, update_data: dict) -> Optional[ScrapeJob]:
        result = await self.db.execute(
            select(ScrapeJob).where(ScrapeJob.job_id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return None

        for key, value in update_data.items():
            if hasattr(job, key):
                setattr(job, key, value)

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_active_jobs(self) -> List[ScrapeJob]:
        result = await self.db.execute(
            select(ScrapeJob).where(ScrapeJob.status.in_(["pending", "running"]))
        )
        return result.scalars().all()

    async def complete_job(
        self,
        job_id: str,
        vehicles_found: int = 0,
        prices_found: int = 0,
        errors: Optional[str] = None
    ) -> Optional[ScrapeJob]:
        return await self.update_job(job_id, {
            "status": "completed" if not errors else "failed",
            "vehicles_found": vehicles_found,
            "prices_found": prices_found,
            "errors": errors,
            "completed_at": datetime.utcnow()
        })
