from typing import Optional
from pydantic import BaseModel
from in_memory_context import get_context
from agents import function_tool, RunContextWrapper
from models.flight_models import LastBookingOutput, RetrieveLastFlightBookingInput, FlightLeg
from models.context_models import UserInfo

@function_tool
def retrieve_last_booking_flight_details(
    wrapper: RunContextWrapper[UserInfo],
    input: RetrieveLastFlightBookingInput
) -> LastBookingOutput:
    user_id = wrapper.context.user_id
    thread_id = wrapper.context.thread_id

    print(f"[Retrieve] user_id: {user_id}, thread_id: {thread_id}")

    if not user_id or not thread_id:
        return LastBookingOutput(message="User ID and Thread ID are required to retrieve booking details.")

    ctx = {
        # Booking info
        "reference": get_context(user_id, thread_id, "last_booking_reference"),
        "name": get_context(user_id, thread_id, "last_passenger_name"),
        "email": get_context(user_id, thread_id, "last_email"),
        "phone": get_context(user_id, thread_id, "last_phone"),
        "flight_id": get_context(user_id, thread_id, "last_flight_id"),

        # Outbound leg
        "airline": get_context(user_id, thread_id, "last_flight_airline"),
        "outbound_departure": get_context(user_id, thread_id, "last_flight_outbound_departure_time"),
        "outbound_arrival": get_context(user_id, thread_id, "last_flight_outbound_arrival_time"),
        "outbound_origin": get_context(user_id, thread_id, "last_flight_outbound_origin"),
        "outbound_destination": get_context(user_id, thread_id, "last_flight_outbound_destination"),
        "outbound_duration": get_context(user_id, thread_id, "last_flight_outbound_duration"),
        "outbound_stops": get_context(user_id, thread_id, "last_flight_outbound_stops"),
        "outbound_extensions": get_context(user_id, thread_id, "last_flight_outbound_extensions"),

        # Return leg (optional)
        "return_departure": get_context(user_id, thread_id, "last_flight_return_departure_time"),
        "return_arrival": get_context(user_id, thread_id, "last_flight_return_arrival_time"),
        "return_origin": get_context(user_id, thread_id, "last_flight_return_origin"),
        "return_destination": get_context(user_id, thread_id, "last_flight_return_destination"),
        "return_duration": get_context(user_id, thread_id, "last_flight_return_duration"),
        "return_stops": get_context(user_id, thread_id, "last_flight_return_stops"),
        "return_extensions": get_context(user_id, thread_id, "last_flight_return_extensions"),

        # General
        "price": get_context(user_id, thread_id, "last_flight_price"),
        "currency": get_context(user_id, thread_id, "last_flight_currency"),
        "booking_link": get_context(user_id, thread_id, "last_flight_booking_link"),
    }

    print(f"[Retrieve] Context: {ctx}")

    if not ctx["reference"]:
        return LastBookingOutput(message="I couldn't find any recent flight bookings for you.")

    # Build message
    message = (
        f"📄 **Your Last Flight Booking Details**:\n"
        f"- **Booking Reference:** {ctx['reference']}\n"
        f"- **Passenger:** {ctx['name']}\n"
        f"- **Email:** {ctx['email']}\n"
        f"- **Phone:** {ctx['phone']}\n\n"
        f"✈️ **Outbound Flight**:\n"
        f"- **Airline:** {ctx['airline']}\n"
        f"- **From:** {ctx['outbound_origin']} → **To:** {ctx['outbound_destination']}\n"
        f"- **Departure:** {ctx['outbound_departure']}\n"
    )

    if ctx["outbound_arrival"]:
        message += f"- **Arrival:** {ctx['outbound_arrival']}\n"
    if ctx["outbound_duration"]:
        message += f"- **Duration:** {ctx['outbound_duration']}\n"
    if ctx["outbound_stops"] is not None:
        message += f"- **Stops:** {ctx['outbound_stops']}\n"
    if ctx["outbound_extensions"]:
        message += f"- **Extensions:** {ctx['outbound_extensions']}\n"

    if ctx["return_departure"]:
        message += (
            f"\n🔁 **Return Flight**:\n"
            f"- **From:** {ctx['return_origin']} → **To:** {ctx['return_destination']}\n"
            f"- **Departure:** {ctx['return_departure']}\n"
        )
        if ctx["return_arrival"]:
            message += f"- **Arrival:** {ctx['return_arrival']}\n"
        if ctx["return_duration"]:
            message += f"- **Duration:** {ctx['return_duration']}\n"
        if ctx["return_stops"] is not None:
            message += f"- **Stops:** {ctx['return_stops']}\n"
        if ctx["return_extensions"]:
            message += f"- **Extensions:** {ctx['return_extensions']}\n"

        message += f"\n💰 **Total Cost (Round Trip):** {ctx['currency']} {ctx['price']}\n"
    else:
        message += f"\n💰 **Cost (One-Way):** {ctx['currency']} {ctx['price']}\n"

    if ctx["booking_link"]:
        message += f"\n🔗 [View Booking Link]({ctx['booking_link']})\n"

    return LastBookingOutput(message=message)