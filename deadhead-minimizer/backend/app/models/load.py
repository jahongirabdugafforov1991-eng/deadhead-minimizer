import uuid
from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EquipmentType, LoadStatus


class Load(Base):
    """DAT load board posting (or extension-bridge scraped equivalent)."""

    __tablename__ = "loads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dat_reference_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    origin_city: Mapped[str] = mapped_column(String(80), nullable=False)
    origin_state: Mapped[str] = mapped_column(String(2), nullable=False)
    origin_zip3: Mapped[str] = mapped_column(String(3), nullable=False)
    origin_geom: Mapped[str] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    origin_kma_code: Mapped[str | None] = mapped_column(String(10), ForeignKey("kma_heatmaps.kma_code"), nullable=True)

    dest_city: Mapped[str] = mapped_column(String(80), nullable=False)
    dest_state: Mapped[str] = mapped_column(String(2), nullable=False)
    dest_zip3: Mapped[str] = mapped_column(String(3), nullable=False)
    dest_geom: Mapped[str] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    dest_kma_code: Mapped[str | None] = mapped_column(String(10), ForeignKey("kma_heatmaps.kma_code"), nullable=True)

    equipment_type: Mapped[EquipmentType] = mapped_column(Enum(EquipmentType, name="equipment_type_enum"), nullable=False)
    miles: Mapped[float] = mapped_column(Numeric(7, 1), nullable=False)
    rate_total_usd: Mapped[float | None] = mapped_column(Numeric(9, 2), nullable=True)
    rpm_usd: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    weight_lbs: Mapped[int | None] = mapped_column(Integer, nullable=True)

    broker_company: Mapped[str | None] = mapped_column(String(120), nullable=True)
    broker_contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    broker_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    broker_mc_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    broker_email: Mapped[str | None] = mapped_column(String(120), nullable=True)

    pickup_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[LoadStatus] = mapped_column(Enum(LoadStatus, name="load_status_enum"), nullable=False, default=LoadStatus.POSTED)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
