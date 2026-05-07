import asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from typing import List, Dict, Optional
from app.core.logging import logger
from app.core.config import get_settings
import re

settings = get_settings()


class ListingScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=settings.playwright_headless
        )
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def scrape_listing_page(self, url: str) -> List[Dict]:
        page = await self.context.new_page()
        vehicles = []

        try:
            logger.info(f"Scraping URL: {url}")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            listings = await page.query_selector_all("[data-vehicle-id], .vehicle-card, .listing-item")

            for listing in listings:
                try:
                    vehicle = await self._extract_vehicle_data(listing)
                    if vehicle:
                        vehicles.append(vehicle)
                except Exception as e:
                    logger.warning(f"Failed to extract listing: {e}")
                    continue

            logger.info(f"Extracted {len(vehicles)} vehicles from {url}")

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
        finally:
            await page.close()

        return vehicles

    async def _extract_vehicle_data(self, listing) -> Optional[Dict]:
        try:
            vin = await self._extract_vin(listing)
            make = await self._extract_make(listing)
            model = await self._extract_model(listing)
            year = await self._extract_year(listing)
            price = await self._extract_price(listing)
            mileage = await self._extract_mileage(listing)

            if not vin or not make or not model:
                return None

            return {
                "vin": vin,
                "make": make,
                "model": model,
                "year": year,
                "price": price,
                "mileage": mileage,
                "source_url": await listing.get_attribute("href") or "",
                "source_name": "listing_source"
            }
        except Exception as e:
            logger.warning(f"Failed to extract vehicle data: {e}")
            return None

    async def _extract_vin(self, listing) -> Optional[str]:
        vin_elem = await listing.query_selector("[data-vin], .vin, .vehicle-vin")
        if vin_elem:
            text = await vin_elem.inner_text()
            vin = re.search(r'[A-HJ-NPR-Z0-9]{17}', text.upper())
            if vin:
                return vin.group(0)
        return None

    async def _extract_make(self, listing) -> Optional[str]:
        make_elem = await listing.query_selector("[data-make], .make, .vehicle-make")
        if make_elem:
            return (await make_elem.inner_text()).strip()
        return None

    async def _extract_model(self, listing) -> Optional[str]:
        model_elem = await listing.query_selector("[data-model], .model, .vehicle-model")
        if model_elem:
            return (await model_elem.inner_text()).strip()
        return None

    async def _extract_year(self, listing) -> Optional[int]:
        year_elem = await listing.query_selector("[data-year], .year, .vehicle-year")
        if year_elem:
            text = await year_elem.inner_text()
            year_match = re.search(r'\b(19|20)\d{2}\b', text)
            if year_match:
                return int(year_match.group(0))
        return None

    async def _extract_price(self, listing) -> Optional[float]:
        price_elem = await listing.query_selector("[data-price], .price, .vehicle-price")
        if price_elem:
            text = await price_elem.inner_text()
            price_match = re.search(r'\$?([\d,]+)', text.replace(',', ''))
            if price_match:
                return float(price_match.group(1))
        return None

    async def _extract_mileage(self, listing) -> Optional[int]:
        mileage_elem = await listing.query_selector("[data-mileage], .mileage, .odometer")
        if mileage_elem:
            text = await mileage_elem.inner_text()
            mileage_match = re.search(r'([\d,]+)\s*(mi|miles|km)', text, re.IGNORECASE)
            if mileage_match:
                return int(mileage_match.group(1).replace(',', ''))
        return None


class RealTimeAggregator:
    def __init__(self):
        self.scraper = ListingScraper()
        self.scrape_interval = settings.scraper_interval

    async def run_scrape_cycle(self, sources: List[Dict]) -> List[Dict]:
        all_vehicles = []

        async with self.scraper as scraper:
            for source in sources:
                try:
                    vehicles = await scraper.scrape_listing_page(source["url"])
                    for v in vehicles:
                        v["source_name"] = source.get("name", "unknown")
                    all_vehicles.extend(vehicles)
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Failed to scrape {source['url']}: {e}")
                    continue

        return all_vehicles

    async def start_continuous_aggregation(self, sources: List[Dict]):
        while True:
            try:
                logger.info("Starting scrape cycle...")
                vehicles = await self.run_scrape_cycle(sources)
                logger.info(f"Collected {len(vehicles)} vehicles")
            except Exception as e:
                logger.error(f"Scrape cycle failed: {e}")

            await asyncio.sleep(self.scrape_interval)
