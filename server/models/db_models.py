# models/db_models.py

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON  # Use JSONB if you're using Postgres

Base = declarative_base()

class FlightBooking(Base):
    __tablename__ = "flight_bookings"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=False)
    booking_reference = Column(String, nullable=False)

    full_name = Column(String, nullable=False)
    passenger_names = Column(JSON, nullable=False)  # ✅ NEW
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)  # ✅ NEW

    airline = Column(String, nullable=False)
    total_price = Column(Float)
    currency = Column(String)
    booking_link = Column(String)

    is_multi_city = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    price_breakdown = Column(JSON, nullable=True)  # Add this line

    # One booking can have multiple legs
    legs = relationship("FlightLegDB", back_populates="booking", cascade="all, delete-orphan")
    segments = relationship("FlightSegmentDB", back_populates="booking", cascade="all, delete-orphan")
    layovers = relationship("LayoverDB", back_populates="booking", cascade="all, delete-orphan")



  
    
 

class FlightLegDB(Base):
    __tablename__ = "flight_legs"

    id = Column(String, primary_key=True)  # UUID
    booking_id = Column(String, ForeignKey("flight_bookings.id"))

    departure_time = Column(DateTime)
    arrival_time = Column(DateTime)

    origin = Column(String)
    destination = Column(String)
    duration = Column(String)
    stops = Column(Integer)
    extensions = Column(JSON)
    flight_number = Column(String)  # ✅ Add this line


    booking = relationship("FlightBooking", back_populates="legs")
  
class FlightSegmentDB(Base):
    __tablename__ = "flight_segments"

    id = Column(String, primary_key=True)
    booking_id = Column(String, ForeignKey("flight_bookings.id"))

    segment_number = Column(Integer)
    departure_airport = Column(String)
    departure_datetime = Column(String)
    arrival_airport = Column(String)
    arrival_datetime = Column(String)
    duration = Column(String)
    cabin_class = Column(String)
    extension_info = Column(JSON)

    booking = relationship("FlightBooking", back_populates="segments")

class LayoverDB(Base):
    __tablename__ = "layovers"

    id = Column(String, primary_key=True)
    booking_id = Column(String, ForeignKey("flight_bookings.id"))

    layover_airport = Column(String)
    layover_duration = Column(String)

    booking = relationship("FlightBooking", back_populates="layovers")
