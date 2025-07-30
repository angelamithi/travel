from db.session import SessionLocal
from models.db_models import FlightBooking, FlightLegDB
from agents import function_tool,RunContextWrapper
from models.context_models import UserInfo
import uuid
import os
import requests
import logging
import uuid
from typing import Optional
from models.flight_models import SearchFlightInput, SearchFlightOutput, FlightOption, FlightLeg,BookFlightInput,BookFlightOutput
from in_memory_context import set_context,get_context
from datetime import datetime
from dotenv import load_dotenv
import json

@function_tool
async def book_flight(wrapper: RunContextWrapper[UserInfo], input: BookFlightInput) -> BookFlightOutput:
    user_id = wrapper.context.user_id
    thread_id = wrapper.context.thread_id
    session = SessionLocal()

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

        flight_data = get_context(user_id, thread_id, f"flight_option_{input.selected_flight_id}")
        if flight_data:
            flight = FlightOption(**flight_data)
        elif input.selected_flight_details:
            flight = input.selected_flight_details
        else:
            raise ValueError("No flight data available to book.")

        is_multi_city = flight.legs is not None and len(flight.legs) > 0

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
            is_multi_city=is_multi_city
        )


                # Add booking and flush to get the ID
        session.add(booking)
        session.flush()

        # Save legs
        if is_multi_city:
            for leg in flight.legs:
                flight_leg = FlightLegDB(
                    id=str(uuid.uuid4()),
                    booking_id=booking.id,
                    departure_time=leg.departure_time,
                    arrival_time=leg.arrival_time,
                    origin=leg.origin,
                    destination=leg.destination,
                    duration=leg.duration,
                    stops=leg.stops or 0,
                    extensions=leg.extensions or [],
                )
                session.add(flight_leg)
        else:
            # Save outbound leg
            outbound = flight.outbound
            outbound_leg = FlightLegDB(
                id=str(uuid.uuid4()),
                booking_id=booking.id,
                departure_time=outbound.departure_time,
                arrival_time=outbound.arrival_time,
                origin=outbound.origin,
                destination=outbound.destination,
                duration=outbound.duration,
                stops=outbound.stops or 0,
                extensions=outbound.extensions or [],
            )
            session.add(outbound_leg)

            # Save return leg (if any)
            if flight.return_leg:
                return_leg = flight.return_leg
                return_flight_leg = FlightLegDB(
                    id=str(uuid.uuid4()),
                    booking_id=booking.id,
                    departure_time=return_leg.departure_time,
                    arrival_time=return_leg.arrival_time,
                    origin=return_leg.origin,
                    destination=return_leg.destination,
                    duration=return_leg.duration,
                    stops=return_leg.stops or 0,
                    extensions=return_leg.extensions or [],
                )
                session.add(return_flight_leg)


        session.add(booking)
        session.commit()
        session.close()

    return BookFlightOutput(
        booking_reference=booking_reference,
        message=message
    )