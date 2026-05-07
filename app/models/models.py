from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, Index
from sqlalchemy.sql import func
from app.core.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String(17), unique=True, index=True, nullable=False)
    make = Column(String(50), nullable=False)
    model = Column(String(50), nullable=False)
    year = Column(Integer, nullable=False)
    trim = Column(String(100))
    body_style = Column(String(50))
    exterior_color = Column(String(50))
    interior_color = Column(String(50))
    fuel_type = Column(String(30))
    transmission = Column(String(30))
    drivetrain = Column(String(30))
    engine = Column(String(100))
    horsepower = Column(Integer)
    torque = Column(Integer)
    mileage = Column(Integer)
    dealer_id = Column(String(100), index=True)
    dealer_name = Column(String(200))
    dealer_location = Column(String(200))
    source_url = Column(String(500))
    source_name = Column(String(100))
    listing_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('ix_vehicle_make_model_year', 'make', 'model', 'year'),
        Index('ix_vehicle_price_mileage', 'mileage'),
    )


class ListingPrice(Base):
    __tablename__ = "listing_prices"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, nullable=False, index=True)
    vin = Column(String(17), nullable=False, index=True)
    price = Column(Float, nullable=False)
    price_type = Column(String(20), default="listing")
    currency = Column(String(3), default="USD")
    mileage = Column(Integer)
    condition = Column(String(50))
    source_name = Column(String(100))
    source_url = Column(String(500))
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_listing_vin_scraped', 'vin', 'scraped_at'),
    )


class PriceAnalysis(Base):
    __tablename__ = "price_analyses"

    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String(17), nullable=False, index=True)
    make = Column(String(50))
    model = Column(String(50))
    year = Column(Integer)
    avg_price = Column(Float)
    min_price = Column(Float)
    max_price = Column(Float)
    median_price = Column(Float)
    price_std_dev = Column(Float)
    sample_size = Column(Integer)
    mileage_adjustment = Column(Float)
    condition_adjustment = Column(Float)
    market_trend = Column(String(20))
    analysis_date = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(100), unique=True, nullable=False)
    source_name = Column(String(100))
    source_url = Column(String(500))
    status = Column(String(20), default="pending")
    vehicles_found = Column(Integer, default=0)
    prices_found = Column(Integer, default=0)
    errors = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Dealer(Base):
    __tablename__ = "dealers"

    id = Column(Integer, primary_key=True, index=True)
    dealer_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200))
    location = Column(String(300))
    city = Column(String(100))
    state = Column(String(50))
    zip_code = Column(String(20))
    phone = Column(String(20))
    website = Column(String(200))
    rating = Column(Float)
    review_count = Column(Integer)
    inventory_count = Column(Integer)
    source_name = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
