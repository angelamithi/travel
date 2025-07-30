from typing import Optional, List, Dict 
from pydantic import BaseModel,Field


class MultiCityLeg(BaseModel):
    origin: str
    destination: str
    departure_date: str  # Should be in YYYY-MM-DD format
    times: Optional[str] = None  # Optional times string for the API

class PriceBreakdownEntry(BaseModel):
    count: int
    total: float

class PriceBreakdown(BaseModel):
    base_fare_per_person: float
    adults: PriceBreakdownEntry
    children: Optional[PriceBreakdownEntry] = None
    infants: Optional[PriceBreakdownEntry] = None
    total_price: float

# --- For search_flight ---
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
    allowed_airlines: Optional[List[str]] = None  # e.g., ["Kenya Airways", "Emirates"]
    excluded_airlines: Optional[List[str]] = None
    multi_city_legs: Optional[List[MultiCityLeg]] = None

class FlightLeg(BaseModel):
    departure_time: str
    arrival_time: str
    origin: Optional[str] = None
    destination: Optional[str] = None
    duration: Optional[str] = None
    stops: Optional[int] = None
    extensions: Optional[List[str]] = None
    flight_number: Optional[str] = None  # Add this field


class FlightOption(BaseModel):
    airline: str
    price: Optional[float]
    currency: str
    outbound: FlightLeg  # ✅ Existing field (keep)
    return_leg: Optional[FlightLeg] = None  # ✅ Existing field (keep)
    booking_link: Optional[str]
    id: Optional[str] = None
    departure_token: Optional[str] = None
    outbound_legs: Optional[List[FlightLeg]] = None
    return_legs: Optional[List[FlightLeg]] = None
    legs: Optional[List[FlightLeg]] = None  # ✅ Unified access for all legs
    price_breakdown: Optional[PriceBreakdown] = None
 
    


class SearchFlightOutput(BaseModel):
    origin: str
    destination: str
    flights: List[FlightOption]


# --- For booking flight ---
class BookFlightInput(BaseModel):
    selected_flight_id: str
    full_name: str
    email: str
    phone: str
    selected_flight_details: Optional[FlightOption]  # ✅ new field to hold full flight info
    passenger_names: Optional[List[str]] = None
    payment_method: Optional[str] = None

class BookFlightOutput(BaseModel):
    booking_reference: str
    message: str


class PriceCalculationInput(BaseModel):
    flight_cost: Optional[float] = None
    accommodation_cost: Optional[float] = None
    number_of_travelers: Optional[int] = None
    number_of_nights: Optional[int] = None  # <- Use this consistently
    destination: Optional[str] = None
    include_flight: Optional[bool] = True
    include_accommodation: Optional[bool] = True


class PriceCalculationOutput(BaseModel):
    total_cost: float
    breakdown: dict

class LastBookingOutput(BaseModel):
    message: str

class RetrieveLastFlightBookingInput(BaseModel):
    user_id: str
    thread_id: str