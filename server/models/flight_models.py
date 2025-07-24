from typing import Optional, List
from pydantic import BaseModel,Field

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

class FlightOption(BaseModel):
    airline: str
    price: Optional[float]
    currency: str
    departure_time: str
    arrival_time: str
    duration: str
    stops: int
    booking_link: Optional[str]
    id: Optional[str] = None  # Optional or remove if unused


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