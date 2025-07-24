import os
import requests
import logging
from typing import Optional
from models.flight_models import SearchFlightInput, SearchFlightOutput, FlightOption
from context import set_context
from agents import Agent, Runner,function_tool
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("chat_logger")
SERP_API_KEY = os.getenv("SERP_API_KEY")



@function_tool
def search_flight(
    data: SearchFlightInput,
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None
) -> Optional[SearchFlightOutput]:
    try:
        logger.info(f"Searching flight for {data.origin} → {data.destination} on {data.departure_date}")

        # Validate and parse departure date
        departure_dt = datetime.strptime(data.departure_date, '%Y-%m-%d')

        # Map cabin class string
        cabin_class_map = {
            "economy": 1,
            "premium_economy": 2,
            "business": 3,
            "first": 4
        }
        cabin_class_code = cabin_class_map.get(data.cabin_class.lower(), 1)

        # Determine trip type
        trip_type = 1 if data.return_date else 2  # 1 = Round trip, 2 = One-way

        # Prepare SERP API query
        params = {
            "engine": "google_flights",
            "departure_id": data.origin,
            "arrival_id": data.destination,
            "outbound_date": data.departure_date,
            "return_date": data.return_date,
            "type": trip_type,
            "hl": "en",
            "api_key": SERP_API_KEY
        }
        params = {k: v for k, v in params.items() if v is not None}

        logger.info(f"Calling SERP API with params: {params}")
        response = requests.get("https://serpapi.com/search", params=params)

        if response.status_code != 200:
            raise Exception(f"SERP API error: {response.status_code} - {response.text}")

        data_json = response.json()
        logger.info(f"SERP response keys: {data_json.keys()}")

        flight_results = []

        # Prefer best_flights; fallback to other_flights
        all_flight_groups = data_json.get("best_flights", []) or data_json.get("other_flights", [])
        max_results = 3

        for group in all_flight_groups[:max_results]:
            flights = group.get("flights", [])
            if not flights:
                continue

            first_flight = flights[0]

            flight_option = FlightOption(
                airline=first_flight.get("airline", "Unknown"),
                price=float(group.get("price", 0)) if group.get("price") else None,
                currency="USD",  # You can improve this by checking actual currency field if available
                departure_time=first_flight.get("departure_airport", {}).get("time", "Unknown"),
                arrival_time=first_flight.get("arrival_airport", {}).get("time", "Unknown"),
                duration=str(group.get("total_duration", "Unknown")),
                stops=len(flights) - 1,
                booking_link=None,
                id=None  # Optional, based on your model
            )
            flight_results.append(flight_option)


        # Build output
        output = SearchFlightOutput(
            origin=data.origin,
            destination=data.destination,
            flights=flight_results
        )

        # Save context if available
        total_passengers = (data.adults or 0) + (data.children or 0) + (data.infants or 0)

        if user_id and thread_id and flight_results:
            set_context(user_id, thread_id, "last_flight_origin", data.origin)
            set_context(user_id, thread_id, "last_flight_destination", data.destination)
            set_context(user_id, thread_id, "last_number_of_travelers", total_passengers)
            set_context(user_id, thread_id, "last_cabin_class", data.cabin_class)

            first_price = flight_results[0].price
            if first_price and str(first_price).replace('.', '', 1).isdigit():
                set_context(user_id, thread_id, "last_flight_cost", float(first_price))

        return output

    except Exception as e:
        logger.error(f"search_flight error: {e}", exc_info=True)
        raise
