from typing import Optional
from pydantic import BaseModel
from in_memory_context import get_context
from agents import function_tool, RunContextWrapper
from models.flight_models import LastBookingOutput, RetrieveLastFlightBookingInput, FlightLeg
from models.context_models import UserInfo
from db.session import SessionLocal
from models.db_models import FlightBooking,FlightLegDB

from sqlalchemy.orm import joinedload

@function_tool
def retrieve_last_booking_flight_details(
    wrapper: RunContextWrapper[UserInfo],
    input: RetrieveLastFlightBookingInput
) -> LastBookingOutput:
    user_id = wrapper.context.user_id
    thread_id = wrapper.context.thread_id

    if not user_id or not thread_id:
        return LastBookingOutput(message="User ID and Thread ID are required to retrieve booking details.")

    # --- Try context first ---
    ctx = {
        "reference": get_context(user_id, thread_id, "last_booking_reference"),
        "name": get_context(user_id, thread_id, "last_passenger_name"),
        "email": get_context(user_id, thread_id, "last_email"),
        "phone": get_context(user_id, thread_id, "last_phone"),
        "flight_id": get_context(user_id, thread_id, "last_flight_id"),
        "airline": get_context(user_id, thread_id, "last_flight_airline"),
        "outbound_departure": get_context(user_id, thread_id, "last_flight_outbound_departure_time"),
        "outbound_arrival": get_context(user_id, thread_id, "last_flight_outbound_arrival_time"),
        "outbound_origin": get_context(user_id, thread_id, "last_flight_outbound_origin"),
        "outbound_destination": get_context(user_id, thread_id, "last_flight_outbound_destination"),
        "outbound_duration": get_context(user_id, thread_id, "last_flight_outbound_duration"),
        "outbound_stops": get_context(user_id, thread_id, "last_flight_outbound_stops"),
        "outbound_extensions": get_context(user_id, thread_id, "last_flight_outbound_extensions"),
        "outbound_flight_number": get_context(user_id, thread_id, "last_flight_outbound_flight_number"),
        "return_departure": get_context(user_id, thread_id, "last_flight_return_departure_time"),
        "return_arrival": get_context(user_id, thread_id, "last_flight_return_arrival_time"),
        "return_origin": get_context(user_id, thread_id, "last_flight_return_origin"),
        "return_destination": get_context(user_id, thread_id, "last_flight_return_destination"),
        "return_duration": get_context(user_id, thread_id, "last_flight_return_duration"),
        "return_stops": get_context(user_id, thread_id, "last_flight_return_stops"),
        "return_extensions": get_context(user_id, thread_id, "last_flight_return_extensions"),
        "return_flight_number": get_context(user_id, thread_id, "last_flight_return_flight_number"),
        "price": get_context(user_id, thread_id, "last_flight_price"),
        "currency": get_context(user_id, thread_id, "last_flight_currency"),
        "booking_link": get_context(user_id, thread_id, "last_flight_booking_link"),
        "price_breakdown": get_context(user_id, thread_id, "last_flight_price_breakdown"),

    }

    # If context is empty, fallback to database
    if not ctx["reference"]:
        db = SessionLocal()
        booking = (
            db.query(FlightBooking)
            .filter(FlightBooking.user_id == user_id)
            .order_by(FlightBooking.created_at.desc())
            .options(joinedload(FlightBooking.legs))
            .first()
        )
        db.close()

        if not booking:
            return LastBookingOutput(message="I couldn't find any recent flight bookings for you.")

        outbound_leg = booking.legs[0] if booking.legs else None
        return_leg = booking.legs[1] if len(booking.legs) > 1 else None

        ctx = {
            "reference": booking.booking_reference,
            "name": booking.full_name,
            "email": booking.email,
            "phone": booking.phone,
            "flight_id": booking.id,
            "airline": booking.airline,
            "outbound_departure": outbound_leg.departure_time if outbound_leg else None,
            "outbound_arrival": outbound_leg.arrival_time if outbound_leg else None,
            "outbound_origin": outbound_leg.origin if outbound_leg else None,
            "outbound_destination": outbound_leg.destination if outbound_leg else None,
            "outbound_duration": outbound_leg.duration if outbound_leg else None,
            "outbound_stops": outbound_leg.stops if outbound_leg else None,
            "outbound_extensions": outbound_leg.extensions if outbound_leg else None,
            "outbound_flight_number": outbound_leg.flight_number if outbound_leg else None,
            "return_departure": return_leg.departure_time if return_leg else None,
            "return_arrival": return_leg.arrival_time if return_leg else None,
            "return_origin": return_leg.origin if return_leg else None,
            "return_destination": return_leg.destination if return_leg else None,
            "return_duration": return_leg.duration if return_leg else None,
            "return_stops": return_leg.stops if return_leg else None,
            "return_extensions": return_leg.extensions if return_leg else None,
            "return_flight_number": return_leg.flight_number if return_leg else None,
            "price": booking.total_price,
            "price_breakdown": booking.price_breakdown,
            "currency": booking.currency,
            "booking_link": booking.booking_link,
          
        }

        source = "database"
    else:
        source = "context"

    # --- Build response message ---
    message = (
        f"📄 **Your Last Flight Booking Details** *(from {source})*:\n"
        f"- **Booking Reference:** {ctx['reference']}\n"
        f"- **Passenger:** {ctx['name']}\n"
        f"- **Email:** {ctx['email']}\n"
        f"- **Phone:** {ctx['phone']}\n\n"
        f"✈️ **Outbound Flight**:\n"
        f"- **Airline:** {ctx['airline']}\n"
        f"- **From:** {ctx['outbound_origin']} → **To:** {ctx['outbound_destination']}\n"
        f"- **Departure:** {ctx['outbound_departure']}\n"
    )

    if ctx.get("outbound_arrival"):
        message += f"- **Arrival:** {ctx['outbound_arrival']}\n"
    if ctx.get("outbound_duration"):
        message += f"- **Duration:** {ctx['outbound_duration']}\n"
    if ctx.get("outbound_stops") is not None:
        message += f"- **Stops:** {ctx['outbound_stops']}\n"
    if ctx.get("outbound_extensions"):
        message += f"- **Extensions:** {ctx['outbound_extensions']}\n"
    if ctx.get("outbound_flight_number"):
        message += f"- **Flight Number:** {ctx['outbound_flight_number']}\n"

    if ctx.get("return_departure"):
        message += (
            f"\n🔁 **Return Flight**:\n"
            f"- **From:** {ctx['return_origin']} → **To:** {ctx['return_destination']}\n"
            f"- **Departure:** {ctx['return_departure']}\n"
        )
        if ctx.get("return_arrival"):
            message += f"- **Arrival:** {ctx['return_arrival']}\n"
        if ctx.get("return_duration"):
            message += f"- **Duration:** {ctx['return_duration']}\n"
        if ctx.get("return_stops") is not None:
            message += f"- **Stops:** {ctx['return_stops']}\n"
        if ctx.get("return_extensions"):
            message += f"- **Extensions:** {ctx['return_extensions']}\n"
        if ctx.get("return_flight_number"):
            message += f"- **Flight Number:** {ctx['return_flight_number']}\n"

        message += f"\n💰 **Total Cost (Round Trip):** {ctx['currency']} {ctx['price']}\n"
    else:
        message += f"\n💰 **Cost (One-Way):** {ctx['currency']} {ctx['price']}\n"

    if ctx.get("booking_link"):
        message += f"\n🔗 [View Booking Link]({ctx['booking_link']})\n"

    price_breakdown = ctx.get("price_breakdown")
    if price_breakdown:
        message += "\n📊 **Price Breakdown:**\n"
        base = price_breakdown.get("base_fare_per_person")
        if base:
            message += f"- Base Fare per Person: {ctx['currency']} {base}\n"

        for group in ["adults", "children", "infants"]:
            group_data = price_breakdown.get(group)
            if group_data and group_data.get("count", 0) > 0:
                message += (
                    f"- {group.capitalize()}: {group_data['count']} × base → "
                    f"{ctx['currency']} {group_data['total']}\n"
                )

        total = price_breakdown.get("total_price")
        if total:
            message += f"- **Total:** {ctx['currency']} {total}\n"


    return LastBookingOutput(message=message)
