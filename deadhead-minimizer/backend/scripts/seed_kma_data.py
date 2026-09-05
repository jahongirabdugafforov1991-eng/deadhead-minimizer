"""
Seed script: populates `kma_heatmaps` with ~45 major US freight markets using
realistic, hand-curated load-to-truck ratios based on well-known lane patterns
(e.g. Northeast delivery-heavy metros run soft/dead for outbound vans; Southeast
manufacturing/distribution hubs run hot).

This lets you build and demo the heat map, deadhead endpoint, and (later)
triangulation loop builder with zero dependency on DAT access.

Usage:
    cd backend
    python -m scripts.seed_kma_data

Idempotent: re-running upserts on (kma_code, equipment_type) rather than
duplicating rows.
"""

import asyncio
from dataclasses import dataclass

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.models.enums import EquipmentType

EQUIPMENT_FOR_SEED = EquipmentType.VAN  # seed van lanes first; rerun with REEFER/FLATBED to extend


@dataclass
class SeedKma:
    kma_code: str
    kma_name: str
    zip3: str
    lat: float
    lon: float
    load_count: int
    truck_count: int
    avg_outbound_rpm: float
    avg_inbound_rpm: float


# Ratios and RPMs are illustrative approximations of typical van market behavior,
# not live rates — replace with real DAT/RateView numbers once ingestion is wired up.
SEED_KMAS: list[SeedKma] = [
    # --- Southeast: generally hot/balanced outbound (manufacturing + import distribution) ---
    SeedKma("ATL", "Atlanta, GA", "303", 33.7490, -84.3880, 620, 140, 2.35, 2.10),
    SeedKma("CHA", "Chattanooga, TN", "374", 35.0456, -85.3097, 210, 35, 2.55, 2.05),
    SeedKma("NSH", "Nashville, TN", "372", 36.1627, -86.7816, 380, 90, 2.30, 2.05),
    SeedKma("MEM", "Memphis, TN", "381", 35.1495, -90.0490, 540, 95, 2.60, 2.15,),
    SeedKma("BHM", "Birmingham, AL", "352", 33.5186, -86.8104, 260, 60, 2.20, 2.00),
    SeedKma("SAV", "Savannah, GA", "314", 32.0809, -81.0912, 470, 70, 2.75, 2.20),
    SeedKma("JAX", "Jacksonville, FL", "322", 30.3322, -81.6557, 400, 85, 2.40, 2.05),
    SeedKma("CLT", "Charlotte, NC", "282", 35.2271, -80.8431, 350, 90, 2.15, 2.00),
    SeedKma("RIC", "Richmond, VA", "232", 37.5407, -77.4360, 230, 65, 2.05, 1.95),

    # --- Midwest: hot/balanced, classic freight crossroads ---
    SeedKma("CHI", "Chicago, IL", "606", 41.8781, -87.6298, 890, 180, 2.45, 2.10),
    SeedKma("IND", "Indianapolis, IN", "462", 39.7684, -86.1581, 410, 95, 2.30, 2.05),
    SeedKma("CMH", "Columbus, OH", "432", 39.9612, -82.9988, 360, 90, 2.20, 2.00),
    SeedKma("CVG", "Cincinnati, OH", "452", 39.1031, -84.5120, 330, 80, 2.15, 1.95),
    SeedKma("CLE", "Cleveland, OH", "441", 41.4993, -81.6944, 240, 70, 2.00, 1.90),
    SeedKma("STL", "St. Louis, MO", "631", 38.6270, -90.1994, 400, 100, 2.25, 2.05),
    SeedKma("KC", "Kansas City, MO", "641", 39.0997, -94.5786, 380, 90, 2.20, 2.00),
    SeedKma("MSP", "Minneapolis, MN", "554", 44.9778, -93.2650, 260, 75, 2.05, 1.95),
    SeedKma("DET", "Detroit, MI", "482", 42.3314, -83.0458, 300, 85, 2.05, 1.90),
    SeedKma("LOU", "Louisville, KY", "402", 38.2527, -85.7585, 340, 75, 2.30, 2.05),

    # --- South Central / Texas: hot, high volume ---
    SeedKma("DAL", "Dallas, TX", "752", 32.7767, -96.7970, 760, 150, 2.40, 2.10),
    SeedKma("HOU", "Houston, TX", "770", 29.7604, -95.3698, 700, 145, 2.35, 2.10),
    SeedKma("SAT", "San Antonio, TX", "782", 29.4241, -98.4936, 320, 80, 2.10, 1.95),
    SeedKma("OKC", "Oklahoma City, OK", "731", 35.4676, -97.5164, 250, 65, 2.05, 1.90),
    SeedKma("ELP", "El Paso, TX", "799", 31.7619, -106.4850, 200, 55, 2.15, 1.95),
    SeedKma("MSY", "New Orleans, LA", "701", 29.9511, -90.0715, 220, 60, 2.10, 1.95),
    SeedKma("LIT", "Little Rock, AR", "722", 34.7465, -92.2896, 180, 45, 2.05, 1.90),

    # --- West: mixed — LA/Inland Empire hot, coastal delivery metros softer ---
    SeedKma("LAX", "Los Angeles, CA", "900", 34.0522, -118.2437, 780, 150, 2.55, 2.20),
    SeedKma("ONT", "Ontario/Inland Empire, CA", "917", 34.0633, -117.6509, 640, 120, 2.60, 2.15),
    SeedKma("SAC", "Sacramento, CA", "958", 38.5816, -121.4944, 180, 130, 1.55, 2.05),
    SeedKma("FAT", "Fresno, CA", "937", 36.7378, -119.7871, 190, 90, 1.85, 1.90),
    SeedKma("PHX", "Phoenix, AZ", "850", 33.4484, -112.0740, 420, 110, 2.10, 2.00),
    SeedKma("LAS", "Las Vegas, NV", "891", 36.1699, -115.1398, 210, 90, 1.90, 1.95),
    SeedKma("RNO", "Reno, NV", "895", 39.5296, -119.8138, 140, 75, 1.70, 1.85),
    SeedKma("SEA", "Seattle, WA", "981", 47.6062, -122.3321, 240, 110, 1.80, 2.00),
    SeedKma("PDX", "Portland, OR", "972", 45.5152, -122.6784, 190, 95, 1.75, 1.95),
    SeedKma("DEN", "Denver, CO", "802", 39.7392, -104.9903, 330, 100, 2.00, 1.95),
    SeedKma("SLC", "Salt Lake City, UT", "841", 40.7608, -111.8910, 260, 85, 1.95, 1.90),
    SeedKma("ABQ", "Albuquerque, NM", "871", 35.0844, -106.6504, 150, 55, 1.90, 1.85),

    # --- Northeast / Mid-Atlantic: classic dead zones — delivery-heavy, few outbound loads ---
    SeedKma("NJ", "New Jersey (Newark/Elizabeth)", "070", 40.7357, -74.1724, 160, 210, 1.45, 2.30),
    SeedKma("NYC", "New York, NY", "100", 40.7128, -74.0060, 120, 190, 1.35, 2.35),
    SeedKma("PHL", "Philadelphia, PA", "191", 39.9526, -75.1652, 200, 180, 1.55, 2.15),
    SeedKma("BOS", "Boston, MA", "021", 42.3601, -71.0589, 130, 150, 1.40, 2.10),
    SeedKma("BAL", "Baltimore, MD", "212", 39.2904, -76.6122, 190, 160, 1.60, 2.05),
    SeedKma("HAR", "Harrisburg, PA", "170", 40.2732, -76.8867, 220, 140, 1.80, 2.00),
    SeedKma("ALN", "Allentown/Lehigh Valley, PA", "181", 40.6023, -75.4714, 240, 150, 1.85, 2.05),
    SeedKma("BUF", "Buffalo, NY", "142", 42.8864, -78.8784, 150, 95, 1.70, 1.90),
    SeedKma("PIT", "Pittsburgh, PA", "152", 40.4406, -79.9959, 210, 110, 1.90, 1.95),

    # --- Florida: mixed — inbound-heavy tourist/consumer economy, softer outbound ---
    SeedKma("MIA", "Miami, FL", "331", 25.7617, -80.1918, 170, 140, 1.60, 2.10),
    SeedKma("ORL", "Orlando, FL", "328", 28.5383, -81.3792, 200, 130, 1.70, 2.00),
    SeedKma("TPA", "Tampa, FL", "336", 27.9506, -82.4572, 210, 125, 1.75, 2.00),
]


def classify(ratio: float) -> str:
    """Mirrors KmaHeatmap.classify() thresholds — keep these in sync."""
    if ratio > 4.0:
        return "hot"
    if ratio >= 2.0:
        return "balanced"
    if ratio >= 1.0:
        return "soft"
    return "dead"


UPSERT_SQL = text(
    """
    INSERT INTO kma_heatmaps (
        kma_code, kma_name, zip3, equipment_type, centroid,
        load_count, truck_count, load_to_truck_ratio,
        avg_outbound_rpm, avg_inbound_rpm, zone_classification, source
    )
    VALUES (
        :kma_code, :kma_name, :zip3, :equipment_type,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
        :load_count, :truck_count, :ratio,
        :avg_outbound_rpm, :avg_inbound_rpm, :zone_classification, 'seed_script'
    )
    ON CONFLICT (kma_code, equipment_type) DO UPDATE SET
        kma_name = EXCLUDED.kma_name,
        zip3 = EXCLUDED.zip3,
        centroid = EXCLUDED.centroid,
        load_count = EXCLUDED.load_count,
        truck_count = EXCLUDED.truck_count,
        load_to_truck_ratio = EXCLUDED.load_to_truck_ratio,
        avg_outbound_rpm = EXCLUDED.avg_outbound_rpm,
        avg_inbound_rpm = EXCLUDED.avg_inbound_rpm,
        zone_classification = EXCLUDED.zone_classification,
        source = 'seed_script',
        updated_at = now()
    """
)


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        for kma in SEED_KMAS:
            ratio = round(kma.load_count / kma.truck_count, 2)
            await session.execute(
                UPSERT_SQL,
                {
                    "kma_code": kma.kma_code,
                    "kma_name": kma.kma_name,
                    "zip3": kma.zip3,
                    "equipment_type": EQUIPMENT_FOR_SEED.value,
                    "lon": kma.lon,
                    "lat": kma.lat,
                    "load_count": kma.load_count,
                    "truck_count": kma.truck_count,
                    "ratio": ratio,
                    "avg_outbound_rpm": kma.avg_outbound_rpm,
                    "avg_inbound_rpm": kma.avg_inbound_rpm,
                    "zone_classification": classify(ratio),
                },
            )
        await session.commit()
        print(f"Seeded {len(SEED_KMAS)} KMAs for equipment_type='{EQUIPMENT_FOR_SEED.value}'.")


if __name__ == "__main__":
    asyncio.run(seed())
