# models/db_models.py

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class FlightBooking(Base):
    __tablename__ = "flight_bookings"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=False)
    booking_reference = Column(String, nullable=False)

    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)

    airline = Column(String, nullable=False)
    price = Column(Float)
    currency = Column(String)
    booking_link = Column(String)

    is_multi_city = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # One booking can have multiple legs
    legs = relationship("FlightLegDB", back_populates="booking", cascade="all, delete-orphan")


class FlightLegDB(Base):
    __tablename__ = "flight_legs"

    id = Column(String, primary_key=True)  # UUID
    booking_id = Column(String, ForeignKey("flight_bookings.id"))

    departure_time = Column(String)
    arrival_time = Column(String)
    origin = Column(String)
    destination = Column(String)
    duration = Column(String)
    stops = Column(Integer)
    extensions = Column(JSON)

    booking = relationship("Booking", back_populates="legs")
