import os
import requests
import logging
from typing import Optional
from models.flight_models import SearchFlightInput, SearchFlightOutput, FlightOption
from context import set_context

logger = logging.getLogger("chat_logger")
SERP_API_KEY = os.getenv("SERP_API_KEY")

def search_flight(
    data: SearchFlightInput,
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None
) -> Optional[SearchFlightOutput]:
    try:
        logger.info(f"Searching flight for {data.origin} → {data.destination} on {data.departure_date}")

        total_passengers = data.adults + data.children + data.infants

        query = f"{data.origin} to {data.destination} flights {data.departure_date.strftime('%Y-%m-%d')}"
        if data.return_date:
            query += f" return {data.return_date.strftime('%Y-%m-%d')}"

        params = {
            "engine": "google_flights",
            "q": query,
            "hl": "en",
            "api_key": SERP_API_KEY
        }

        response = requests.get("https://serpapi.com/search", params=params)

        if response.status_code != 200:
            raise Exception(f"SERP API error: {response.status_code} - {response.text}")

        data_json = response.json()
        flight_results = []

        for flight in data_json.get("flights_results", []):
            price_amount = flight.get("price", {}).get("amount", None)
            currency = flight.get("price", {}).get("currency", "USD")

            flight_option = FlightOption(
                airline=flight.get("airline", "Unknown"),
                price=price_amount,
                currency=currency,
                departure_time=flight.get("departure_time", "Unknown"),
                arrival_time=flight.get("arrival_time", "Unknown"),
                duration=flight.get("duration", "Unknown"),
                stops=flight.get("stops", 0),
                booking_link=flight.get("booking_link")
            )
            flight_results.append(flight_option)

        output = SearchFlightOutput(
            origin=data.origin,
            destination=data.destination,
            results=flight_results
        )

        # Save context if available
        if user_id and thread_id and flight_results:
            set_context(user_id, thread_id, "last_flight_origin", data.origin)
            set_context(user_id, thread_id, "last_flight_destination", data.destination)
            set_context(user_id, thread_id, "last_number_of_travelers", total_passengers)

            first_price = flight_results[0].price
            if first_price and str(first_price).replace('.', '', 1).isdigit():
                set_context(user_id, thread_id, "last_flight_cost", float(first_price))

        return output

    except Exception as e:
        logger.error(f"search_flight error: {e}", exc_info=True)
        raise
