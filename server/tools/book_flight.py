from typing import Optional
from pydantic import BaseModel
import uuid
from in_memory_context import set_context, get_context  # ✅ added get_context
from models.flight_models import BookFlightInput, BookFlightOutput, FlightOption,FlightLeg
from agents import Agent, Runner, function_tool, RunContextWrapper
from models.context_models import UserInfo

@function_tool
async def book_flight(wrapper: RunContextWrapper[UserInfo], input: BookFlightInput) -> BookFlightOutput:
    user_id = wrapper.context.user_id
    thread_id = wrapper.context.thread_id

    print(f"[BOOK FLIGHT] user_id={user_id}, thread_id={thread_id}")
    booking_reference = str(uuid.uuid4())[:8].upper()

    message = (
        f"✅ Your flight has been booked successfully!\n"
        f"✈️ Booking Reference: {booking_reference}\n"
        f"A confirmation has been sent to {input.email}. "
        "Thank you for choosing our service!"
    )

    if user_id and thread_id:
        set_context(user_id, thread_id, "last_booking_reference", booking_reference)
        set_context(user_id, thread_id, "last_passenger_name", input.full_name)
        set_context(user_id, thread_id, "last_email", input.email)
        set_context(user_id, thread_id, "last_phone", input.phone)
        set_context(user_id, thread_id, "last_flight_id", input.selected_flight_id)

        # 🔁 Retrieve full flight data
        flight_data = get_context(user_id, thread_id, f"flight_option_{input.selected_flight_id}")
        if flight_data:
            flight = FlightOption(**flight_data)
        elif input.selected_flight_details:
            flight = input.selected_flight_details
        else:
            raise ValueError("No flight data available to book.")

        # ✅ Set outbound leg info
        outbound = flight.outbound
        set_context(user_id, thread_id, "last_flight_outbound_departure_time", outbound.departure_time)
        set_context(user_id, thread_id, "last_flight_outbound_arrival_time", outbound.arrival_time)
        set_context(user_id, thread_id, "last_flight_outbound_origin", outbound.origin)
        set_context(user_id, thread_id, "last_flight_outbound_destination", outbound.destination)
        set_context(user_id, thread_id, "last_flight_outbound_duration", outbound.duration)
        set_context(user_id, thread_id, "last_flight_outbound_stops", outbound.stops)
        set_context(user_id, thread_id, "last_flight_outbound_extensions", outbound.extensions)

        # ✅ Set return leg info (if any)
        if flight.return_leg:
            return_leg = flight.return_leg
            set_context(user_id, thread_id, "last_flight_return_departure_time", return_leg.departure_time)
            set_context(user_id, thread_id, "last_flight_return_arrival_time", return_leg.arrival_time)
            set_context(user_id, thread_id, "last_flight_return_origin", return_leg.origin)
            set_context(user_id, thread_id, "last_flight_return_destination", return_leg.destination)
            set_context(user_id, thread_id, "last_flight_return_duration", return_leg.duration)
            set_context(user_id, thread_id, "last_flight_return_stops", return_leg.stops)
            set_context(user_id, thread_id, "last_flight_return_extensions", return_leg.extensions)

        # ✅ General flight info
        set_context(user_id, thread_id, "last_flight_airline", flight.airline)
        set_context(user_id, thread_id, "last_flight_price", flight.price)
        set_context(user_id, thread_id, "last_flight_currency", flight.currency)
        set_context(user_id, thread_id, "last_flight_booking_link", flight.booking_link)

    return BookFlightOutput(
        booking_reference=booking_reference,
        message=message
    )
