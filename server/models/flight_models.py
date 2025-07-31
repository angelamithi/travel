from typing import Optional, List, Dict
from pydantic import BaseModel, Field

# --- Models for Multi-City Flights ---
class MultiCityLeg(BaseModel):
    origin: str
    destination: str
    departure_date: str  # Format: YYYY-MM-DD
    times: Optional[str] = None

# --- Price Breakdown Structure ---
class PriceBreakdownEntry(BaseModel):
    count: int
    total: float

class PriceBreakdown(BaseModel):
    base_fare_per_person: float
    adults: PriceBreakdownEntry
    children: Optional[PriceBreakdownEntry] = None
    infants: Optional[PriceBreakdownEntry] = None
    total_price: float

# --- Input for Searching Flights ---
class SearchFlightInput(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    cabin_class: str = "economy"
    adults: int = Field(default=1, ge=0)
    children: int = Field(default=0, ge=0)
    infants: int = Field(default=0, ge=0)
    max_price: Optional[float] = None
    nonstop_only: Optional[bool] = False
    allowed_airlines: Optional[List[str]] = None
    excluded_airlines: Optional[List[str]] = None
    multi_city_legs: Optional[List[MultiCityLeg]] = None

# --- Segment Details (for complex itineraries) ---
class FlightSegment(BaseModel):
    segment_number: int
    departure_airport: str
    departure_datetime: str
    arrival_airport: str
    arrival_datetime: str
    duration: str
    cabin_class: str
    extension_info: List[str]

class LayoverInfo(BaseModel):
    layover_airport: str
    layover_duration: str

# --- Leg of a Flight ---
class FlightLeg(BaseModel):
    departure_time: str
    arrival_time: str
    origin: Optional[str] = None
    destination: Optional[str] = None
    duration: Optional[str] = None
    stops: Optional[int] = None
    extensions: Optional[List[str]] = None
    flight_number: Optional[str] = None

# --- Full Flight Option ---
class FlightOption(BaseModel):
    id: str
    airline: str
    flight_number: Optional[str] = None
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None
    outbound: Optional[FlightLeg] = None
    return_leg: Optional[FlightLeg] = None
    outbound_legs: Optional[List[FlightLeg]] = None
    return_legs: Optional[List[FlightLeg]] = None
    legs: Optional[List[FlightLeg]] = None
    segments: List[FlightSegment] = None
    layovers: Optional[List[LayoverInfo]] = None
    total_duration: Optional[str] = None
    price: Optional[float] = None
    currency: str
    price_breakdown: Optional[PriceBreakdown] = None
    booking_link: Optional[str] = None
    departure_token: Optional[str] = None
    formatted_summary: Optional[str] = None

# --- Output for Searching Flights ---
class SearchFlightOutput(BaseModel):
    origin: str
    destination: str
    flights: List[FlightOption]

  

# --- Input/Output for Booking a Flight ---
class BookFlightInput(BaseModel):
    selected_flight_id: str
    full_name: str
    email: str
    phone: str
    selected_flight_details: List[FlightOption]
    passenger_names: Optional[List[str]] = None
    payment_method: Optional[str] = None

class BookFlightOutput(BaseModel):
    booking_reference: str
    message: str

# --- Travel Cost Estimation ---
class PriceCalculationInput(BaseModel):
    flight_cost: Optional[float] = None
    accommodation_cost: Optional[float] = None
    number_of_travelers: Optional[int] = None
    number_of_nights: Optional[int] = None
    destination: Optional[str] = None
    include_flight: Optional[bool] = True
    include_accommodation: Optional[bool] = True

class PriceCalculationOutput(BaseModel):
    total_cost: float
    breakdown: dict

# --- Last Booking Details ---
class LastBookingOutput(BaseModel):
    message: str

class RetrieveLastFlightBookingInput(BaseModel):
    user_id: str
    thread_id: str