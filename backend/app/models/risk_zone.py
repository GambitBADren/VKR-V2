from sqlalchemy import Column, Integer, Float, DateTime
from geoalchemy2 import Geography
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RiskZone(Base):
    __tablename__ = "risk_zones"

    id = Column(Integer, primary_key=True)
    center = Column(Geography("POINT", srid=4326), nullable=False)
    radius_km = Column(Float, nullable=False)
    avg_risk_score = Column(Float, nullable=False)
    points_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())