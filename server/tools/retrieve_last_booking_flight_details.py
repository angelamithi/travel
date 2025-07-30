from typing import Optional
from pydantic import BaseModel
from agents import function_tool, RunContextWrapper
from models.flight_models import LastBookingOutput, RetrieveLastFlightBookingInput
from models.context_models import UserInfo
from db.session import SessionLocal
from models.db_models import FlightBooking, FlightLegDB
from sqlalchemy.orm import joinedload


@function_tool
def retrieve_last_booking_flight_details(
    wrapper: RunContextWrapper[UserInfo],
    input: RetrieveLastFlightBookingInput
) -> LastBookingOutput:
    user_id = wrapper.context.user_id

    # Log the user ID
    print(f"Retrieving last flight booking details for user_id: {user_id}")
   

    if not user_id :
        return LastBookingOutput(message="User ID are required to retrieve booking details.")
    

    # Query the most recent booking from the database
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

    # Build response message
    message = (
        f"📄 **Your Last Flight Booking Details** *(from database)*:\n"
        f"- **Booking Reference:** {booking.booking_reference}\n"
        f"- **Passenger:** {booking.full_name}\n"
        f"- **Email:** {booking.email}\n"
        f"- **Phone:** {booking.phone}\n\n"
        f"✈️ **Outbound Flight**:\n"
        f"- **Airline:** {booking.airline}\n"
        f"- **From:** {outbound_leg.origin} → **To:** {outbound_leg.destination}\n"
        f"- **Departure:** {outbound_leg.departure_time}\n"
    )

    if outbound_leg.arrival_time:
        message += f"- **Arrival:** {outbound_leg.arrival_time}\n"
    if outbound_leg.duration:
        message += f"- **Duration:** {outbound_leg.duration}\n"
    if outbound_leg.stops is not None:
        message += f"- **Stops:** {outbound_leg.stops}\n"
    if outbound_leg.extensions:
        message += f"- **Extensions:** {outbound_leg.extensions}\n"
    if outbound_leg.flight_number:
        message += f"- **Flight Number:** {outbound_leg.flight_number}\n"

    if return_leg:
        message += (
            f"\n🔁 **Return Flight**:\n"
            f"- **From:** {return_leg.origin} → **To:** {return_leg.destination}\n"
            f"- **Departure:** {return_leg.departure_time}\n"
        )
        if return_leg.arrival_time:
            message += f"- **Arrival:** {return_leg.arrival_time}\n"
        if return_leg.duration:
            message += f"- **Duration:** {return_leg.duration}\n"
        if return_leg.stops is not None:
            message += f"- **Stops:** {return_leg.stops}\n"
        if return_leg.extensions:
            message += f"- **Extensions:** {return_leg.extensions}\n"
        if return_leg.flight_number:
            message += f"- **Flight Number:** {return_leg.flight_number}\n"

        message += f"\n💰 **Total Cost (Round Trip):** {booking.currency} {booking.total_price}\n"
    else:
        message += f"\n💰 **Cost (One-Way):** {booking.currency} {booking.total_price}\n"

    if booking.booking_link:
        message += f"\n🔗 [View Booking Link]({booking.booking_link})\n"

    if booking.price_breakdown:
        pb = booking.price_breakdown
        message += "\n📊 **Price Breakdown:**\n"
        if pb.get("base_fare_per_person"):
            message += f"- Base Fare per Person: {booking.currency} {pb['base_fare_per_person']}\n"

        for group in ["adults", "children", "infants"]:
            group_data = pb.get(group)
            if group_data and group_data.get("count", 0) > 0:
                message += (
                    f"- {group.capitalize()}: {group_data['count']} × base → "
                    f"{booking.currency} {group_data['total']}\n"
                )

        if pb.get("total_price"):
            message += f"- **Total:** {booking.currency} {pb['total_price']}\n"

    return LastBookingOutput(message=message)
