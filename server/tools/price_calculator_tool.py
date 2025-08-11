# price_calculator_tool.py
from typing import Dict
from models.flight_models import PriceCalculationInput, PriceCalculationOutput,BreakdownDetail
from agents import function_tool

def format_price_output(data: dict) -> str:
    """Formats the price output in a user-friendly way."""
    total = data.get('total_cost', 0)
    breakdown = data.get('breakdown', {})
    
    flight_cost = breakdown.get('flight_cost', 0)
    accommodation_cost = breakdown.get('accommodation_cost', 0)
    currency = breakdown.get('currency', 'USD')
    
    formatted_total = f"{total:,.2f}"
    formatted_flight = f"{flight_cost:,.2f}" if flight_cost else "0.00"
    formatted_accommodation = f"{accommodation_cost:,.2f}" if accommodation_cost else "0.00"
    
    # Get additional context from the input
    flight_details = data.get('flight_details', {})
    accommodation_details = data.get('accommodation_details', {})
    
    # Build flight info section
    flight_info = f"✈️ FLIGHTS: {currency}{formatted_flight}"
    if flight_details:
        airline = flight_details.get('airline', ['Unknown'])[0]
        flight_numbers = ", ".join(flight_details.get('flight_numbers', []))
        origin = flight_details.get('origin', 'Unknown')
        destination = flight_details.get('destination', 'Unknown')
        dates = flight_details.get('dates', 'Unknown')
        
        flight_info += f"\n   • {airline} ({flight_numbers})\n   • {origin} → {destination}\n   • {dates}"
    
    # Build accommodation info section
    accommodation_info = f"🏨 ACCOMMODATION: {currency}{formatted_accommodation}"
    if accommodation_details:
        hotel_name = accommodation_details.get('hotel_name', 'Unknown')
        room_type = accommodation_details.get('room_type', 'Unknown')
        check_in = accommodation_details.get('check_in', 'Unknown')
        check_out = accommodation_details.get('check_out', 'Unknown')
        nights = accommodation_details.get('nights', 'Unknown')
        
        accommodation_info += f"\n   • {hotel_name}\n   • {room_type}\n   • {check_in} to {check_out} ({nights} nights)"
    
    return f"""
✨ TOTAL TRIP COST BREAKDOWN ✨
--------------------------------------------------
{flight_info}
--------------------------------------------------
{accommodation_info}
--------------------------------------------------
💰 TOTAL: {currency}{formatted_total}
--------------------------------------------------
"""

@function_tool()
def price_calculator_tool(input: PriceCalculationInput) -> PriceCalculationOutput:
    """Calculates and formats trip prices (flights + accommodation)"""
    total = (input.flight_cost or 0) + (input.accommodation_cost or 0)
    
    # Create the breakdown detail
    breakdown = BreakdownDetail(
        flight_cost=input.flight_cost,
        accommodation_cost=input.accommodation_cost,
        taxes_and_fees=0,
        currency="USD"
    )
    
    # Format the output
    formatted_output = format_price_output({
        "total_cost": total,
        "breakdown": breakdown.model_dump(),
        "flight_details": {},  # Add these if available
        "accommodation_details": {}
    })
    
    # Return only the formatted output
    return formatted_output