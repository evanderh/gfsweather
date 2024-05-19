from sqlalchemy import TEXT, Column, ForeignKey, Index, Integer, collate
from sqlalchemy.orm import relationship, mapped_column
from geoalchemy2.types import Raster as GeoRaster
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Raster(Base):
    __tablename__ = 'rasters'

    rid = Column(Integer, primary_key=True)
    rast = Column(GeoRaster(spatial_index=True))
    forecast_hour = Column(TEXT, ForeignKey('raster_metadata.forecast_hour'), index=True)

    raster_metadata = relationship('RasterMetadata', back_populates='rasters')


class RasterMetadata(Base):
    __tablename__ = 'raster_metadata'

    id = Column(Integer, primary_key=True)
    forecast_hour = Column(TEXT, index=True, unique=True)

    rasters = relationship('Raster', back_populates='raster_metadata')