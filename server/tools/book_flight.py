from db.session import SessionLocal
from models.db_models import FlightBooking, FlightLegDB, LayoverDB, FlightSegmentDB
from agents import function_tool, RunContextWrapper
from models.context_models import UserInfo
import uuid
import logging
from models.flight_models import BookFlightInput, BookFlightOutput, FlightOption
from in_memory_context import set_context, get_context
from datetime import datetime
import json

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@function_tool
async def book_flight(wrapper: RunContextWrapper[UserInfo], input: BookFlightInput) -> BookFlightOutput:
    user_id = wrapper.context.user_id
    thread_id = wrapper.context.thread_id

    session = SessionLocal()

    existing_ref = get_context(user_id, thread_id, "last_booking_reference")
    if existing_ref:
        logger.warning(f"Duplicate booking attempt. Returning existing reference: {existing_ref}")
        return BookFlightOutput(
            booking_reference=existing_ref,
            message=f"✅ Your flight has already been booked.\n✈️ Booking Reference: {existing_ref}\nPlease check your email for confirmation."
        )

    # Get all flight details (not just the first one)
    if input.selected_flight_details:
        flights = input.selected_flight_details
        is_multi_city = len(input.selected_flight_details) > 1
    else:
        flight_data = get_context(user_id, thread_id, f"flight_option_{input.selected_flight_id}")
        if flight_data:
            try:
                # Ensure flight_data is properly deserialized
                if isinstance(flight_data, str):
                    flight_data = json.loads(flight_data)
                flights = [FlightOption(**flight_data)]
                is_multi_city = False
            except Exception as e:
                logger.error(f"Failed to parse flight data: {e}")
                raise ValueError("Invalid flight data format")
        else:
            raise ValueError("No flight data available to book. Cannot proceed.")

    try:
        logger.info(f"Booking flight for user {user_id}. Flight details: {json.dumps([f.dict() for f in flights], default=str, indent=2)}")
    except Exception as log_err:
        logger.warning(f"Failed to serialize flight details for logging: {log_err}")

    

    email = get_context(user_id, thread_id, "booking_email")
    full_name = get_context(user_id, thread_id, "full_name")
    phone = get_context(user_id, thread_id, "booking_phone")
    passenger_count = input.passenger_count

    # 🔁 Gather passenger names
    passenger_names = [
        get_context(user_id, thread_id, f"passenger_name_{i}")
        for i in range(1, passenger_count + 1)
    ]





    booking_reference = str(uuid.uuid4())[:8].upper()

    try:
        # Accumulate total price and collect all airlines across all flights
        total_price = 0.0
        all_airlines = set()
        price_breakdown = []

        for flight in flights:
            total_price += flight.total_price or 0.0
            
            # Collect airlines from all segments in all legs
            if hasattr(flight, 'legs') and flight.legs:
                for leg in flight.legs:
                    if leg.segments:
                        for seg in leg.segments:
                            if seg.airline:
                                if isinstance(seg.airline, list):
                                    all_airlines.update(seg.airline)
                                else:
                                    all_airlines.add(seg.airline)
            elif hasattr(flight, 'airline') and flight.airline:
                all_airlines.add(flight.airline)

            # Combine price breakdowns
            if hasattr(flight, 'price_breakdown') and flight.price_breakdown:
                price_breakdown.extend([pb.dict() for pb in flight.price_breakdown])

        # Create booking
        booking = FlightBooking(
            id=str(uuid.uuid4()),
            user_id=user_id,
            thread_id=thread_id,
            booking_reference=booking_reference,
            full_name=input.full_name,
            passenger_names=input.passenger_names,
            email=input.email,
            phone=input.phone,
            payment_method="Not Provided",
            airlines=list(all_airlines),
            total_price=total_price,
            currency=flights[0].currency,  # Assuming same currency for all flights
            booking_token=flights[0].booking_token if hasattr(flights[0], 'booking_token') else None,
            is_multi_city=is_multi_city,
            price_breakdown=price_breakdown or None
        )
        session.add(booking)
        session.flush()

        # Save all legs from all flights
        for flight in flights:
            if hasattr(flight, 'legs') and flight.legs:
                for leg in flight.legs:
                    leg_id = str(uuid.uuid4())
                    flight_leg = FlightLegDB(
                        id=leg_id,
                        booking_id=booking.id,
                        departure_date_time=leg.departure_date_time,
                        arrival_date_time=leg.arrival_date_time,
                        origin=leg.origin,
                        destination=leg.destination,
                        total_duration=leg.total_duration,
                        stops=leg.stops or 0
                    )
                    session.add(flight_leg)

                    # Save all segments
                    if leg.segments:
                        for seg in leg.segments:
                            segment = FlightSegmentDB(
                                id=str(uuid.uuid4()),
                                booking_id=booking.id,
                                leg_id=leg_id,
                                segment_number=seg.segment_number,
                                departure_airport=seg.departure_airport,
                                departure_datetime=seg.departure_datetime,
                                arrival_airport=seg.arrival_airport,
                                arrival_datetime=seg.arrival_datetime,
                                airline=seg.airline,
                                flight_number=seg.flight_number,
                                duration=seg.duration,
                                cabin_class=seg.cabin_class,
                                extension_info=seg.extension_info if seg.extension_info else None
                            )
                            session.add(segment)

                    # Save all layovers
                    if leg.layovers:
                        for lay in leg.layovers:
                            layover = LayoverDB(
                                id=str(uuid.uuid4()),
                                booking_id=booking.id,
                                leg_id=leg_id,
                                layover_airport=lay.layover_airport,
                                layover_duration=lay.layover_duration
                            )
                            session.add(layover)

        session.commit()

        set_context(user_id, thread_id, "last_booking_reference", booking_reference)
        set_context(user_id, thread_id, "last_passenger_name", input.full_name)
        set_context(user_id, thread_id, "last_email", input.email)
        set_context(user_id, thread_id, "last_phone", input.phone)
        set_context(user_id, thread_id, "last_flight_id", input.selected_flight_id)

        message = (
            f"✅ Your flight has been booked successfully!\n"
            f"✈️ Booking Reference: {booking_reference}\n"
            f"A confirmation has been sent to {input.email}. "
            "Thank you for choosing our service!"
        )

        logger.info(f"Flight booked successfully with reference: {booking_reference}")
        return BookFlightOutput(
            booking_reference=booking_reference,
            message=message
        )

    except Exception as e:
        session.rollback()
        logger.error(f"Error during booking: {e}")
        raise
    finally:
        session.close()