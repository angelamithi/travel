from typing import Optional
from pydantic import BaseModel
import uuid
from in_memory_context import set_context
from models.flight_models import BookFlightInput, BookFlightOutput
from agents import Agent, Runner,function_tool,RunContextWrapper
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

        if input.selected_flight_details:
            flight = input.selected_flight_details
            set_context(user_id, thread_id, "last_flight_airline", flight.airline)
            set_context(user_id, thread_id, "last_flight_departure_time", flight.departure_time)
            set_context(user_id, thread_id, "last_flight_arrival_time", flight.arrival_time)
            set_context(user_id, thread_id, "last_flight_destination", flight.destination)
            set_context(user_id, thread_id, "last_flight_origin", flight.origin)
            set_context(user_id, thread_id, "last_flight_duration", flight.duration)
            set_context(user_id, thread_id, "last_flight_cost", flight.price)
            set_context(user_id, thread_id, "last_flight_currency", flight.currency)
            set_context(user_id, thread_id, "last_flight_stops", flight.stops)
            set_context(user_id, thread_id, "last_flight_booking_link", flight.booking_link)

    return BookFlightOutput(
        booking_reference=booking_reference,
        message=message
    )
