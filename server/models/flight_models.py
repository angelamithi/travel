from typing import Optional, List
from pydantic import BaseModel

# --- For search_flight ---
class SearchFlightInput(BaseModel):
    origin: str  # IATA
    destination: str  # IATA
    departure_date: str  # Format: YYYY-MM-DD
    return_date: Optional[str] = None
    adults: int
    children: Optional[int] = 0
    infants: Optional[int] = 0
    cabin_class: str  # economy, business, etc.

class FlightOption(BaseModel):
    id: str  # unique identifier of flight
    airline: str
    departure_time: str
    arrival_time: str
    duration: str
    stops: int
    price: float
    link: Optional[str] = None  # booking link

class SearchFlightOutput(BaseModel):
    flights: List[FlightOption]


# --- For booking flight ---
class BookFlightInput(BaseModel):
    selected_flight_id: str
    full_name: str
    email: str
    phone: str
    selected_flight_details: Optional[FlightOption]  # ✅ new field to hold full flight info

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