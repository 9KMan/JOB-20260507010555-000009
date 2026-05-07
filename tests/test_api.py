import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import Base, engine


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_vehicle(client, db_session):
    vehicle_data = {
        "vin": "1HGBH41JXMN109186",
        "make": "Honda",
        "model": "Civic",
        "year": 2022,
        "trim": "EX",
        "mileage": 15000
    }

    response = await client.post("/api/v1/vehicles", json=vehicle_data)
    assert response.status_code == 201
    data = response.json()
    assert data["vin"] == vehicle_data["vin"]
    assert data["make"] == "Honda"


@pytest.mark.asyncio
async def test_list_vehicles(client, db_session):
    vehicle_data = {
        "vin": "1HGBH41JXMN109186",
        "make": "Honda",
        "model": "Civic",
        "year": 2022,
        "mileage": 15000
    }
    await client.post("/api/v1/vehicles", json=vehicle_data)

    response = await client.get("/api/v1/vehicles")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_get_vehicle_by_vin(client, db_session):
    vehicle_data = {
        "vin": "1HGBH41JXMN109186",
        "make": "Honda",
        "model": "Civic",
        "year": 2022,
        "mileage": 15000
    }
    await client.post("/api/v1/vehicles", json=vehicle_data)

    response = await client.get("/api/v1/vehicles/1HGBH41JXMN109186")
    assert response.status_code == 200
    data = response.json()
    assert data["vin"] == "1HGBH41JXMN109186"


@pytest.mark.asyncio
async def test_get_nonexistent_vehicle(client, db_session):
    response = await client.get("/api/v1/vehicles/NONEXISTENT")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_filter_vehicles_by_make(client, db_session):
    vehicles = [
        {"vin": "1HGBH41JXMN109186", "make": "Honda", "model": "Civic", "year": 2022, "mileage": 15000},
        {"vin": "2HGBH41JXMN109187", "make": "Toyota", "model": "Camry", "year": 2023, "mileage": 5000},
    ]

    for v in vehicles:
        await client.post("/api/v1/vehicles", json=v)

    response = await client.get("/api/v1/vehicles?make=Honda")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["make"] == "Honda"


@pytest.mark.asyncio
async def test_record_price(client, db_session):
    vehicle_data = {
        "vin": "1HGBH41JXMN109186",
        "make": "Honda",
        "model": "Civic",
        "year": 2022,
        "mileage": 15000
    }
    await client.post("/api/v1/vehicles", json=vehicle_data)

    price_data = {
        "vehicle_id": 1,
        "vin": "1HGBH41JXMN109186",
        "price": 28500.00,
        "mileage": 15000,
        "source_name": "test_source"
    }

    response = await client.post("/api/v1/prices", json=price_data)
    assert response.status_code == 201
    assert response.json()["status"] == "recorded"
