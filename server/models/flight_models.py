from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict

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



class LayoverInfo(BaseModel):
    layover_airport: str
    layover_duration: str

 
class FlightSegment(BaseModel):
    segment_number: int
    departure_airport: str
    departure_datetime: str
    arrival_airport: str
    arrival_datetime: str
    duration: str
    cabin_class: str
    extension_info: List[str]
    airline: Optional[List[str]] = None  # <-- Change this line
    flight_number:str
    # --- Leg of a Flight ---

class FlightLeg(BaseModel):
    departure_date_time: str
    arrival_date_time: str
    origin: str
    destination: str
    total_duration: str = None
    stops: Optional[int] = None
    segments: List[FlightSegment]
    layovers: Optional[List[LayoverInfo]] = None



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

class BreakdownDetail(BaseModel):
    flight_cost: Optional[float] = None
    accommodation_cost: Optional[float] = None
    taxes_and_fees: Optional[float] = None
    currency: str = "USD"

class PriceCalculationOutput(BaseModel):
    total_cost: float
    breakdown: BreakdownDetail
    formatted_output: Optional[str] = None  # Make this optional
    
    model_config = ConfigDict(extra='forbid')
# --- Last Booking Details ---
class LastBookingOutput(BaseModel):
    message: str

class RetrieveLastFlightBookingInput(BaseModel):
    user_id: str
    thread_id: str

# --- Full Flight Option ---
class FlightOption(BaseModel):
    id: str
    origin:str
    destination:str
    origin_city:str
    desination_city:str
    airline: List[str]  # Changed from single `airline` to list
    legs: List[FlightLeg]
    total_price: float
    currency: str
    price_breakdown: List[PriceBreakdown] = None
    booking_token: Optional[str] = None
    formatted_summary: Optional[str] = None


# --- Output for Searching Flights ---
class SearchFlightOutput(BaseModel):
    flights: List[FlightOption]

# --- Input/Output for Booking a Flight ---
class BookFlightInput(BaseModel):
    selected_flight_id:str
    selected_flight_details: Optional[List[FlightOption]] = None 
    email: Optional[str] = None
    phone: Optional[str] = None
    passenger_count: Optional[int] = None
    passenger_names: List[str] = []
    full_name:str
    current_step: str = "email"  # email → phone → passenger_count → names → payment → confirm

    def is_complete(self):
        return all([
            self.email,
            self.phone,
            self.passenger_count is not None,
            len(self.passenger_names) == self.passenger_count,
            self.payment_method
        ])
  