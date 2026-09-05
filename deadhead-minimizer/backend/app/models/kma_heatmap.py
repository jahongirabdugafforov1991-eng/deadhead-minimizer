import uuid
from datetime import datetime

from geoalchemy2 import Geography, Geometry
from sqlalchemy import DateTime, Enum, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EquipmentType, ZoneClassification


class KmaHeatmap(Base):
    """
    One row per Key Market Area + equipment type combination.
    Populated/refreshed by the DAT ingestion pipeline on a polling cadence.
    """

    __tablename__ = "kma_heatmaps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    kma_code: Mapped[str] = mapped_column(String(10), nullable=False)
    kma_name: Mapped[str] = mapped_column(String(120), nullable=False)
    zip3: Mapped[str] = mapped_column(String(3), nullable=False)
    equipment_type: Mapped[EquipmentType] = mapped_column(Enum(EquipmentType, name="equipment_type_enum"), nullable=False)

    # `geography` for correct great-circle ST_DWithin radius math in the deadhead query
    centroid: Mapped[str] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    # `geometry` polygon purely for map rendering — not used in distance filters
    geom: Mapped[str | None] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)

    load_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truck_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    load_to_truck_ratio: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)

    avg_outbound_rpm: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    avg_inbound_rpm: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    zone_classification: Mapped[ZoneClassification] = mapped_column(
        Enum(ZoneClassification, name="zone_classification_enum"), nullable=False, default=ZoneClassification.BALANCED
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="dat_api")

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @staticmethod
    def classify(ratio: float) -> ZoneClassification:
        """
        Shared classification thresholds — keep this the single source of truth
        so the ingestion pipeline and any ad-hoc scripts agree with the map legend.
        """
        if ratio > 4.0:
            return ZoneClassification.HOT
        if ratio >= 2.0:
            return ZoneClassification.BALANCED
        if ratio >= 1.0:
            return ZoneClassification.SOFT
        return ZoneClassification.DEAD
