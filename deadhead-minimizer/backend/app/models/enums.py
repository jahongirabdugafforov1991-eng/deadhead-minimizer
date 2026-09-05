import enum


class EquipmentType(str, enum.Enum):
    VAN = "van"
    REEFER = "reefer"
    FLATBED = "flatbed"
    STEPDECK = "stepdeck"
    POWER_ONLY = "power_only"


class TruckStatus(str, enum.Enum):
    AVAILABLE = "available"
    IN_TRANSIT = "in_transit"
    BOOKED = "booked"
    OFF_DUTY = "off_duty"


class LoadStatus(str, enum.Enum):
    POSTED = "posted"
    NEGOTIATING = "negotiating"
    BOOKED = "booked"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ZoneClassification(str, enum.Enum):
    HOT = "hot"          # ratio > 4.0
    BALANCED = "balanced"  # 2.0 <= ratio <= 4.0
    SOFT = "soft"         # 1.0 <= ratio < 2.0
    DEAD = "dead"         # ratio < 1.0
