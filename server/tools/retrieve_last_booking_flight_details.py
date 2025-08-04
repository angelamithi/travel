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
    try:
        # Query with all relationships loaded
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

        if not booking:
            return LastBookingOutput(message="I couldn't find any recent flight bookings for you.")

        # Build the message
        message_parts = [
            f"## 📄 Your Last Flight Booking Details *(from database)*",
            f"- **Booking Reference:** {booking.booking_reference}",
            f"- **Passenger:** {booking.full_name}",
            f"- **Email:** {booking.email}",
            f"- **Phone:** {booking.phone}",
            f"- **Airline(s):** {', '.join(booking.airlines) if booking.airlines else 'N/A'}",
            f"- **Total Price:** {booking.currency} {booking.total_price}",
            f"- **Booking Date:** {booking.created_at.strftime('%Y-%m-%d %H:%M')}",
        ]

        # Handle multi-city flights
        if booking.is_multi_city:
            message_parts.append("\n### ✈️ Multi-City Itinerary")

        # Process each leg
        for idx, leg in enumerate(booking.legs):
            leg_label = f"### 🛫 {'Leg' if booking.is_multi_city else 'Flight'} {idx + 1}"
            message_parts.extend([
                f"\n{leg_label}",
                f"- **From:** {leg.origin} → **To:** {leg.destination}",
                f"- **Departure:** {leg.departure_date_time}",
                f"- **Arrival:** {leg.arrival_date_time}",
            ])
            
            if leg.total_duration:
                message_parts.append(f"- **Duration:** {leg.total_duration}")
            if leg.stops is not None:
                message_parts.append(f"- **Stops:** {leg.stops}")

            # Flight segments
            if leg.segments:
                message_parts.append("\n#### 🧩 Flight Segments")
                for segment in leg.segments:
                    segment_parts = [
                        f"- **Segment {segment.segment_number}**",
                        f"  - **Airline:** {', '.join(segment.airline) if segment.airline else 'N/A'}",
                        f"  - **Flight Number:** {segment.flight_number or 'N/A'}",
                        f"  - **From:** {segment.departure_airport} at {segment.departure_datetime}",
                        f"  - **To:** {segment.arrival_airport} at {segment.arrival_datetime}",
                        f"  - **Duration:** {segment.duration}",
                        f"  - **Cabin Class:** {segment.cabin_class}",
                    ]
                    if segment.extension_info:
                        segment_parts.append(f"  - **Extra Info:** {segment.extension_info}")
                    message_parts.extend(segment_parts)

            # Layovers
            if leg.layovers:
                message_parts.append("\n#### ⏸️ Layovers")
                for layover in leg.layovers:
                    message_parts.append(f"- At **{layover.layover_airport}** for **{layover.layover_duration}**")

        # Booking link
        if booking.booking_token:
            message_parts.append(f"\n🔗 [View Booking Link]({booking.booking_token})")

        # Price breakdown
        if isinstance(booking.price_breakdown, list) and len(booking.price_breakdown) > 0:
            pb = booking.price_breakdown[0]
            message_parts.append("\n## 📊 Price Breakdown")
            
            if pb.get("base_fare_per_person"):
                message_parts.append(f"- Base Fare per Person: {booking.currency} {pb['base_fare_per_person']}")

            for group in ["adults", "children", "infants"]:
                group_data = pb.get(group)
                if isinstance(group_data, dict) and group_data.get("count", 0) > 0:
                    message_parts.append(
                        f"- {group.capitalize()}: {group_data['count']} × base → "
                        f"{booking.currency} {group_data['total']}"
                    )

            if pb.get("total_price"):
                message_parts.append(f"\n💰 **Total Cost:** {booking.currency} {booking.total_price}")
        else:
            message_parts.append("\n⚠️ **Price Breakdown format is invalid or missing.**")

        return LastBookingOutput(message="\n".join(message_parts))

    finally:
        db.close()