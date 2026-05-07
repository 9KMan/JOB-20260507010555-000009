import pytest
from app.services.vehicle_service import VehicleService, PriceService
from app.models import Vehicle


@pytest.mark.asyncio
async def test_create_vehicle(db_session):
    from app.core.database import async_session_maker

    async with async_session_maker() as session:
        service = VehicleService(session)
        vehicle_data = {
            "vin": "1HGBH41JXMN109186",
            "make": "Honda",
            "model": "Civic",
            "year": 2022,
            "mileage": 15000
        }
        vehicle = await service.create_vehicle(vehicle_data)
        assert vehicle.id is not None
        assert vehicle.vin == "1HGBH41JXMN109186"


@pytest.mark.asyncio
async def test_get_vehicle_by_vin(db_session):
    from app.core.database import async_session_maker

    async with async_session_maker() as session:
        service = VehicleService(session)
        vehicle_data = {
            "vin": "1HGBH41JXMN109186",
            "make": "Honda",
            "model": "Civic",
            "year": 2022,
            "mileage": 15000
        }
        await service.create_vehicle(vehicle_data)

        vehicle = await service.get_vehicle_by_vin("1HGBH41JXMN109186")
        assert vehicle is not None
        assert vehicle.make == "Honda"


@pytest.mark.asyncio
async def test_update_vehicle(db_session):
    from app.core.database import async_session_maker

    async with async_session_maker() as session:
        service = VehicleService(session)
        vehicle_data = {
            "vin": "1HGBH41JXMN109186",
            "make": "Honda",
            "model": "Civic",
            "year": 2022,
            "mileage": 15000
        }
        await service.create_vehicle(vehicle_data)

        updated = await service.update_vehicle("1HGBH41JXMN109186", {"mileage": 20000})
        assert updated is not None
        assert updated.mileage == 20000


@pytest.mark.asyncio
async def test_record_price(db_session):
    from app.core.database import async_session_maker

    async with async_session_maker() as session:
        vehicle_service = VehicleService(session)
        price_service = PriceService(session)

        vehicle_data = {
            "vin": "1HGBH41JXMN109186",
            "make": "Honda",
            "model": "Civic",
            "year": 2022,
            "mileage": 15000
        }
        vehicle = await vehicle_service.create_vehicle(vehicle_data)

        price_data = {
            "vehicle_id": vehicle.id,
            "vin": "1HGBH41JXMN109186",
            "price": 28500.00,
            "mileage": 15000
        }
        price = await price_service.record_price(price_data)
        assert price.id is not None
        assert price.price == 28500.00
