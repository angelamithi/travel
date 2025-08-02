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

    print(f"Retrieving last flight booking details for user_id: {user_id}")

    if not user_id:
        return LastBookingOutput(message="User ID is required to retrieve booking details.")

    db = SessionLocal()
    booking = (
        db.query(FlightBooking)
        .filter(FlightBooking.user_id == user_id)
        .order_by(FlightBooking.created_at.desc())
        .options(
            joinedload(FlightBooking.legs)
            .joinedload(FlightLegDB.segments),
            joinedload(FlightBooking.legs)
            .joinedload(FlightLegDB.layovers),
        )
        .first()
    )
    db.close()

    if not booking:
        return LastBookingOutput(message="I couldn't find any recent flight bookings for you.")

    message = (
        f"## 📄 Your Last Flight Booking Details *(from database)*\n"
        f"- **Booking Reference:** {booking.booking_reference}\n"
        f"- **Passenger:** {booking.full_name}\n"
        f"- **Email:** {booking.email}\n"
        f"- **Phone:** {booking.phone}\n"
        f"- **Airline:** {booking.airline}\n"
    )

    for idx, leg in enumerate(booking.legs):
        leg_label = f"### 🛫 Leg {idx + 1}"
        message += (
            f"\n{leg_label}\n"
            f"- **From:** {leg.origin} → **To:** {leg.destination}\n"
            f"- **Departure:** {leg.departure_date_time}\n"
            f"- **Arrival:** {leg.arrival_date_time}\n"
        )
        if leg.total_duration:
            message += f"- **Duration:** {leg.total_duration}\n"
        if leg.stops is not None:
            message += f"- **Stops:** {leg.stops}\n"

        if leg.segments:
            message += "\n#### 🧩 Flight Segments\n"
            for segment in leg.segments:
                message += (
                    f"- **Segment {segment.segment_number}**\n"
                    f"  - **Airline:** {segment.airline_name}\n"
                    f"  - **Flight Number:** {segment.flight_number}\n"
                    f"  - **From:** {segment.departure_airport} at {segment.departure_datetime}\n"
                    f"  - **To:** {segment.arrival_airport} at {segment.arrival_datetime}\n"
                    f"  - **Duration:** {segment.duration}\n"
                    f"  - **Cabin Class:** {segment.cabin_class}\n"
                )
                if segment.extension_info:
                    message += f"  - **Extra Info:** {segment.extension_info}\n"

        if leg.layovers:
            message += "\n#### ⏸️ Layovers\n"
            for layover in leg.layovers:
                message += f"- At **{layover.layover_airport}** for **{layover.layover_duration}**\n"

    if booking.booking_token:
        message += f"\n🔗 [View Booking Link]({booking.booking_token})\n"

    if isinstance(booking.price_breakdown, list) and len(booking.price_breakdown) > 0:
        pb = booking.price_breakdown[0]

        message += "\n## 📊 Price Breakdown\n"
        if pb.get("base_fare_per_person"):
            message += f"- Base Fare per Person: {booking.currency} {pb['base_fare_per_person']}\n"

        for group in ["adults", "children", "infants"]:
            group_data = pb.get(group)
            if isinstance(group_data, dict) and group_data.get("count", 0) > 0:
                message += (
                    f"- {group.capitalize()}: {group_data['count']} × base → "
                    f"{booking.currency} {group_data['total']}\n"
                )

        if pb.get("total_price"):
            message += f"\n💰 **Total Cost:** {booking.currency} {booking.total_price}\n"
    else:
        message += "\n⚠️ **Price Breakdown format is invalid or missing.**\n"

    return LastBookingOutput(message=message)
