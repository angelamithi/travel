from context import get_context
from models.flight_models import PriceCalculationInput, PriceCalculationOutput

def price_calculator_tool(input: PriceCalculationInput, user_id: str, thread_id: str) -> PriceCalculationOutput:
    # Try pulling from context if not provided in input
    flight_cost = input.flight_cost or get_context(user_id, thread_id, "last_flight_cost")
    accommodation_cost = input.accommodation_cost or get_context(user_id, thread_id, "last_accommodation_cost")
    number_of_nights = input.number_of_nights or get_context(user_id, thread_id, "last_number_of_nights")
    number_of_travelers = input.number_of_travelers or get_context(user_id, thread_id, "last_number_of_travelers")
    
    total = 0
    breakdown = {}

    if input.include_flight and flight_cost:
        total += flight_cost
        breakdown["Flight"] = flight_cost

    if input.include_accommodation and accommodation_cost and number_of_nights:
        acc_total = accommodation_cost * number_of_nights
        total += acc_total
        breakdown["Accommodation"] = acc_total

    return PriceCalculationOutput(total_cost=total, breakdown=breakdown)
