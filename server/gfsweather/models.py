from sqlalchemy import TEXT, Column, ForeignKey, Integer, DateTime, Boolean
from sqlalchemy.orm import relationship, mapped_column
from geoalchemy2.types import Raster as GeoRaster
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Raster(Base):
    __tablename__ = 'rasters'
    __table_args__ = { 'schema': 'gfs' }

    rid = Column(Integer, primary_key=True)
    rast = Column(GeoRaster(spatial_index=True))
    cycle_hour_key = Column(TEXT, ForeignKey('gfs.cycle_hours.key', ondelete='CASCADE'), index=True)

    cycle_hour = relationship('CycleHour', back_populates='rasters')


class CycleHour(Base):
    __tablename__ = 'cycle_hours'
    __table_args__ = { 'schema': 'gfs' }

    key = Column(TEXT, primary_key=True)
    hour = Column(Integer, nullable=False)
    cycle_id = Column(Integer, ForeignKey('gfs.forecast_cycles.id', ondelete='CASCADE'), index=True, nullable=False)

    rasters = relationship('Raster', back_populates='cycle_hour', cascade='all, delete-orphan')
    forecast_cycle = relationship('ForecastCycle', back_populates='cycle_hours')


class ForecastCycle(Base):
    __tablename__ = 'forecast_cycles'
    __table_args__ = { 'schema': 'gfs' }

    id = Column(Integer, primary_key=True)
    datetime = Column(DateTime, nullable=False, unique=True)
    is_complete = Column(Boolean, nullable=False, default=False)
    cycle_hours = relationship('CycleHour', back_populates='forecast_cycle', cascade='all, delete-orphan')
