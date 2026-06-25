from sqlalchemy import Column, BigInteger, Float, String, ForeignKey, DateTime
from geoalchemy2 import Geography
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AISRecord(Base):
    __tablename__ = "ais_records"

    id = Column(BigInteger, primary_key=True)
    mmsi = Column(BigInteger, ForeignKey("vessels.mmsi"), index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    location = Column(Geography("POINT", srid=4326), nullable=False)
    sog = Column(Float)
    cog = Column(Float)
    heading = Column(Float)
    risk_score = Column(Float, index=True)
    wind_speed = Column(Float)
    wave_height = Column(Float)
    current_speed = Column(Float)
    season = Column(String(10))