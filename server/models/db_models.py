from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON
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
    passenger_names = Column(JSON, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)

    airlines = Column(JSON, nullable=True)  # List of airline names

    total_price = Column(Float)
    currency = Column(String)
    booking_token = Column(String)

    is_multi_city = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    price_breakdown = Column(JSON, nullable=True)

    legs = relationship("FlightLegDB", back_populates="booking", cascade="all, delete-orphan")
    segments = relationship("FlightSegmentDB", back_populates="booking", cascade="all, delete-orphan")
    layovers = relationship("LayoverDB", back_populates="booking", cascade="all, delete-orphan")

class FlightLegDB(Base):
    __tablename__ = "flight_legs"

    id = Column(String, primary_key=True)  # UUID
    booking_id = Column(String, ForeignKey("flight_bookings.id"), nullable=False)

    departure_date_time = Column(String, nullable=False)
    arrival_date_time = Column(String, nullable=False)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    total_duration = Column(String, nullable=True)
    stops = Column(Integer, nullable=True)

    booking = relationship("FlightBooking", back_populates="legs")
    segments = relationship("FlightSegmentDB", back_populates="leg", cascade="all, delete-orphan")
    layovers = relationship("LayoverDB", back_populates="leg", cascade="all, delete-orphan")

class FlightSegmentDB(Base):
    __tablename__ = "flight_segments"

    id = Column(String, primary_key=True)  # UUID
    booking_id = Column(String, ForeignKey("flight_bookings.id"), nullable=False)
    leg_id = Column(String, ForeignKey("flight_legs.id"), nullable=False)

    segment_number = Column(Integer, nullable=False)
    departure_airport = Column(String, nullable=False)
    departure_datetime = Column(String, nullable=False)
    arrival_airport = Column(String, nullable=False)
    arrival_datetime = Column(String, nullable=False)
    duration = Column(String, nullable=False)
    cabin_class = Column(String, nullable=False)
    extension_info = Column(JSON, nullable=True)  # List of strings
    airline = Column(JSON, nullable=True)
    flight_number = Column(String, nullable=True)

    booking = relationship("FlightBooking", back_populates="segments")
    leg = relationship("FlightLegDB", back_populates="segments")

class LayoverDB(Base):
    __tablename__ = "layovers"

    id = Column(String, primary_key=True)  # UUID
    booking_id = Column(String, ForeignKey("flight_bookings.id"), nullable=False)
    leg_id = Column(String, ForeignKey("flight_legs.id"), nullable=False)

    layover_airport = Column(String, nullable=False)
    layover_duration = Column(String, nullable=False)

    booking = relationship("FlightBooking", back_populates="layovers")
    leg = relationship("FlightLegDB", back_populates="layovers")
