from typing import Optional
from pydantic import BaseModel
from in_memory_context import get_context
from agents import function_tool,RunContextWrapper
from models.flight_models import LastBookingOutput, RetrieveLastFlightBookingInput
from models.context_models import UserInfo

@function_tool
def retrieve_last_booking_flight_details(wrapper: RunContextWrapper[UserInfo],
    input: RetrieveLastFlightBookingInput
) -> LastBookingOutput:
    user_id = wrapper.context.user_id
    thread_id = wrapper.context.thread_id

    print(f"[Retrieve] user_id: {user_id}, thread_id: {thread_id}")  # <-- Add this

    if not user_id or not thread_id:
        return LastBookingOutput(message="User ID and Thread ID are required to retrieve booking details.")

    ctx = {
        "reference": get_context(user_id, thread_id, "last_booking_reference"),
        "name": get_context(user_id, thread_id, "last_passenger_name"),
        "email": get_context(user_id, thread_id, "last_email"),
        "phone": get_context(user_id, thread_id, "last_phone"),
        "flight_id": get_context(user_id, thread_id, "last_flight_id"),
        "airline": get_context(user_id, thread_id, "last_flight_airline"),
        "departure": get_context(user_id, thread_id, "last_flight_departure_time"),
        "arrival": get_context(user_id, thread_id, "last_flight_arrival_time"),
        "origin": get_context(user_id, thread_id, "last_flight_origin"),
        "destination": get_context(user_id, thread_id, "last_flight_destination"),
        "duration": get_context(user_id, thread_id, "last_flight_duration"),
        "stops": get_context(user_id, thread_id, "last_flight_stops"),
        "cost": get_context(user_id, thread_id, "last_flight_cost"),
        "currency": get_context(user_id, thread_id, "last_flight_currency"),
        "booking_link": get_context(user_id, thread_id, "last_flight_booking_link"),
    }

    print(f"[Retrieve] Context: {ctx}")  # <-- Add this

    if not ctx["reference"]:
        return LastBookingOutput(message="I couldn't find any recent flight bookings for you.")



    message = (
        f"📄 **Your Last Flight Booking Details**:\n"
        f"- **Booking Reference:** {ctx['reference']}\n"
        f"- **Passenger:** {ctx['name']}\n"
        f"- **Email:** {ctx['email']}\n"
        f"- **Phone:** {ctx['phone']}\n\n"
        f"✈️ **Flight Information**:\n"
        f"- **Airline:** {ctx['airline']}\n"
        f"- **From:** {ctx['origin']} → **To:** {ctx['destination']}\n"
        f"- **Departure:** {ctx['departure']}\n"
        f"- **Arrival:** {ctx['arrival']}\n"
        f"- **Duration:** {ctx['duration']}\n"
        f"- **Stops:** {ctx['stops']}\n"
        f"- **Cost:** {ctx['currency']} {ctx['cost']}\n"
    )

    if ctx["booking_link"]:
        message += f"- [🔗 View Booking Link]({ctx['booking_link']})\n"

    return LastBookingOutput(message=message)
