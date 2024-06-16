from sqlalchemy import Column, ForeignKey, Integer, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class ForecastHour(Base):
    __tablename__ = 'forecast_hours'
    __table_args__ = (
        UniqueConstraint('hour', 'cycle_id'),
    )

    id = Column(Integer, primary_key=True)
    hour = Column(Integer, nullable=False)
    cycle_id = Column(Integer, ForeignKey('forecast_cycles.id', ondelete='CASCADE'), index=True, nullable=False)

    forecast_cycle = relationship('ForecastCycle', back_populates='hours')


class ForecastCycle(Base):
    __tablename__ = 'forecast_cycles'

    id = Column(Integer, primary_key=True)
    datetime = Column(DateTime, nullable=False, unique=True)
    is_complete = Column(Boolean, nullable=False, default=False)

    hours = relationship('ForecastHour', back_populates='forecast_cycle', cascade='all, delete-orphan')
