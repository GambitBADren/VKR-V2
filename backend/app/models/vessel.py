from sqlalchemy import Column, Integer, String, Float, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class VesselType(Base):
    __tablename__ = "vessel_types"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name_ru = Column(String(100), nullable=False)
    base_speed_knots = Column(Float, nullable=False)

class Vessel(Base):
    __tablename__ = "vessels"

    mmsi = Column(BigInteger, primary_key=True)
    vessel_type_id = Column(Integer, ForeignKey("vessel_types.id"))
    name = Column(String(255))
    length_m = Column(Float)
    width_m = Column(Float)