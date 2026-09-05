import uuid
from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EquipmentType, TruckStatus


class Truck(Base):
    """Active driver/asset position and status."""

    __tablename__ = "trucks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_name: Mapped[str] = mapped_column(String(120), nullable=False)
    truck_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    equipment_type: Mapped[EquipmentType] = mapped_column(Enum(EquipmentType, name="equipment_type_enum"), nullable=False)

    current_geom: Mapped[str] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    current_city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    current_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    current_kma_code: Mapped[str | None] = mapped_column(String(10), ForeignKey("kma_heatmaps.kma_code"), nullable=True)

    status: Mapped[TruckStatus] = mapped_column(Enum(TruckStatus, name="truck_status_enum"), nullable=False, default=TruckStatus.AVAILABLE)
    target_destination_city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_destination_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    available_from_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    assigned_load_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("loads.id", ondelete="SET NULL"), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
