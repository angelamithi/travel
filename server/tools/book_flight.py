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

def log_flight_details(input: BookFlightInput, flight_data: dict):
    """Helper function to log flight details in a readable format"""
    try:
        logger.info("=== BOOKING REQUEST DETAILS ===")
        logger.info(f"Selected Flight ID: {input.selected_flight_id}")
        logger.info(f"Passenger: {input.full_name}")
        logger.info(f"Email: {input.email}")
        logger.info(f"Phone: {input.phone}")
        logger.info(f"Passengers: {input.passenger_names}")
        logger.info(f"Payment Method: {input.payment_method}")
        
        logger.info("\n=== FLIGHT DETAILS ===")
        if flight_data:
            flight = FlightOption(**flight_data)
            logger.info(f"Airline: {flight.airline}")
            logger.info(f"Total Price: {flight.price} {flight.currency}")
            logger.info(f"Booking Link: {flight.booking_link}")
            
            if flight.segments:
                logger.info("\nFlight Segments:")
                for i, seg in enumerate(flight.segments, 1):
                    logger.info(f"  Segment {i}:")
                    logger.info(f"    From: {seg.departure_airport} at {seg.departure_datetime}")
                    logger.info(f"    To: {seg.arrival_airport} at {seg.arrival_datetime}")
                    logger.info(f"    Duration: {seg.duration}")
            
            if flight.price_breakdown:
                logger.info("\nPrice Breakdown:")
                logger.info(f"  Base Fare: ${flight.price_breakdown['base_fare_per_person']}")
                logger.info(f"  Adults: {flight.price_breakdown['adults']['count']} x ${flight.price_breakdown['adults']['total']}")
                if flight.price_breakdown.get('children'):
                    logger.info(f"  Children: {flight.price_breakdown['children']['count']} x ${flight.price_breakdown['children']['total']}")
                if flight.price_breakdown.get('infants'):
                    logger.info(f"  Infants: {flight.price_breakdown['infants']['count']} x ${flight.price_breakdown['infants']['total']}")
                logger.info(f"  Total: ${flight.price_breakdown['total_price']}")
        
        logger.info("="*40)
    except Exception as e:
        logger.error(f"Error logging flight details: {str(e)}")

@function_tool
async def book_flight(wrapper: RunContextWrapper[UserInfo], input: BookFlightInput) -> BookFlightOutput:
    user_id = wrapper.context.user_id
    thread_id = wrapper.context.thread_id

    existing_ref = get_context(user_id, thread_id, "last_booking_reference")
    if existing_ref:
        logger.warning(f"Duplicate booking attempt. Returning existing reference: {existing_ref}")
        return BookFlightOutput(
            booking_reference=existing_ref,
            message=f"✅ Your flight has already been booked.\n✈️ Booking Reference: {existing_ref}\nPlease check your email for confirmation."
        )
    session = SessionLocal()

   
    booking_reference = str(uuid.uuid4())[:8].upper()

    message = (
        f"✅ Your flight has been booked successfully!\n"
        f"✈️ Booking Reference: {booking_reference}\n"
        f"A confirmation has been sent to {input.email}. "
        "Thank you for choosing our service!"
    )

    # 🧠 STEP 1: Retrieve full flight data
    flight_data = None
    if user_id and thread_id and input.selected_flight_id:
        # Try to retrieve from memory
        flight_data = get_context(user_id, thread_id, f"flight_option_{input.selected_flight_id}")

    # If not in memory, fallback to what the user might have passed
    if flight_data:
        flight = FlightOption(**flight_data)
    elif input.selected_flight_details:
        logger.warning("Flight details loaded from fallback input. Segments may be missing.")
        flight = input.selected_flight_details[0]  # It's a list!

    else:
        raise ValueError("No flight data available to book. Cannot proceed.")
    

    # 🧠 STEP 2: Store context for recent booking
    if user_id and thread_id:
        set_context(user_id, thread_id, "last_booking_reference", booking_reference)
        set_context(user_id, thread_id, "last_passenger_name", input.full_name)
        set_context(user_id, thread_id, "last_email", input.email)
        set_context(user_id, thread_id, "last_phone", input.phone)
        set_context(user_id, thread_id, "last_flight_id", input.selected_flight_id)

        is_multi_city = flight.legs is not None and len(flight.legs) > 0

        # Store booking metadata
        booking = FlightBooking(
            id=str(uuid.uuid4()),
            user_id=user_id,
            thread_id=thread_id,
            booking_reference=booking_reference,
            full_name=input.full_name,
            email=input.email,
            passenger_names=input.passenger_names or [input.full_name],
            phone=input.phone,
            payment_method=input.payment_method or "Not provided",
            airline=flight.airline,
            total_price=flight.price,
            currency=flight.currency,
            booking_link=flight.booking_link,
            is_multi_city=is_multi_city,
            price_breakdown=flight.price_breakdown.dict() if flight.price_breakdown else None,
        )

        session.add(booking)
        session.flush()

        # Save segments
        if flight.segments:
            for seg in flight.segments:
                segment_db = FlightSegmentDB(
                    id=str(uuid.uuid4()),
                    booking_id=booking.id,
                    segment_number=seg.segment_number,
                    departure_airport=seg.departure_airport,
                    departure_datetime=seg.departure_datetime,
                    arrival_airport=seg.arrival_airport,
                    arrival_datetime=seg.arrival_datetime,
                    duration=seg.duration,
                    cabin_class=seg.cabin_class,
                    extension_info=seg.extension_info.dict() if seg.extension_info else None
                )
                session.add(segment_db)
                logger.debug(f"Added segment: {seg.departure_airport} → {seg.arrival_airport}")

        # Save layovers
        if flight.layovers:
            for lay in flight.layovers:
                layover_db = LayoverDB(
                    id=str(uuid.uuid4()),
                    booking_id=booking.id,
                    layover_airport=lay.layover_airport,
                    layover_duration=lay.layover_duration,
                )
                session.add(layover_db)
                logger.debug(f"Added layover at {lay.layover_airport} for {lay.layover_duration}")

        # Save flight legs
        if is_multi_city:
            for leg in flight.legs:
                flight_leg = FlightLegDB(
                    id=str(uuid.uuid4()),
                    booking_id=booking.id,
                    departure_time=datetime.fromisoformat(leg.departure_time),
                    arrival_time=datetime.fromisoformat(leg.arrival_time),
                    origin=leg.origin,
                    destination=leg.destination,
                    duration=leg.duration,
                    stops=leg.stops or 0,
                    extensions=leg.extensions.dict() if leg.extensions else None,
                    flight_number=leg.flight_number,
                )
                session.add(flight_leg)
                logger.debug(f"Added multi-city leg: {leg.origin} → {leg.destination}")
        else:
           # Handle outbound_legs (if provided)
            if flight.outbound_legs:
                for leg in flight.outbound_legs:
                    leg_db = FlightLegDB(
                        id=str(uuid.uuid4()),
                        booking_id=booking.id,
                        departure_time=datetime.fromisoformat(leg.departure_time),
                        arrival_time=datetime.fromisoformat(leg.arrival_time),
                        origin=leg.origin,
                        destination=leg.destination,
                        duration=leg.duration,
                        stops=leg.stops or 0,
                        extensions=leg.extensions.dict() if leg.extensions else None,
                        flight_number=leg.flight_number,
                    )
                    session.add(leg_db)

            # Handle return_legs (if provided)
            if flight.return_legs:
                for leg in flight.return_legs:
                    leg_db = FlightLegDB(
                        id=str(uuid.uuid4()),
                        booking_id=booking.id,
                        departure_time=datetime.fromisoformat(leg.departure_time),
                        arrival_time=datetime.fromisoformat(leg.arrival_time),
                        origin=leg.origin,
                        destination=leg.destination,
                        duration=leg.duration,
                        stops=leg.stops or 0,
                        extensions=leg.extensions.dict() if leg.extensions else None,
                        flight_number=leg.flight_number,
                    )
                    session.add(leg_db)

                
        session.commit()
        logger.info(f"Successfully booked flight with reference: {booking_reference}")

        return BookFlightOutput(
            booking_reference=booking_reference,
            message=message
        )

   