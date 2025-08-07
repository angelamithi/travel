from typing import Optional, List, Dict
from pydantic import BaseModel, Field, HttpUrl, UUID4
from uuid import uuid4

class SearchAccommodationInput(BaseModel):
    location: str
    check_in_date: str
    check_out_date: str
    adults: int
    amenities: Optional[List[str]] = None  # Changed from str to List[str]
    max_price: Optional[float] = None  # Made optional

class Rate(BaseModel):
    lowest: Optional[str] = None
    extracted_lowest: Optional[float] = None
    before_taxes_fees: Optional[str] = None
    extracted_before_taxes_fees: Optional[float] = None

class GpsCoordinates(BaseModel):
    latitude: float
    longitude: float

class Image(BaseModel):
    thumbnail: Optional[HttpUrl] = None
    original_image: Optional[HttpUrl] = None

class PriceInfo(BaseModel):
    price: str  # Formatted price string ("$150")
    extracted_price: float  # Numeric value for calculations
    currency: str = "USD"  # Default currency

class AccommodationOption(BaseModel):
    id: UUID4 = Field(default_factory=uuid4)  
    name: str
    type: Optional[str] = "hotel"  
    price_info: PriceInfo
    rating: Optional[float] = None
    reviews: Optional[int] = None
    location: Optional[GpsCoordinates] = None
    amenities: Optional[List[str]] = None
    images: List[str] = None  
    link: str = None
    property_token: Optional[str] = None  
    source: Optional[str] = None  
    free_cancellation: Optional[bool] = None
    hotel_class: Optional[int] = Field(None, ge=1, le=5)  
    formatted_images: Optional[List[str]] = Field(default_factory=list)
    formatted_link: Optional[str] = None


class SearchAccommodationOutput(BaseModel):
    accommodation: List[AccommodationOption]
    search_metadata: Optional[Dict] = None
    formatted_message: Optional[str] = None  # Add this line