import os
import requests
import logging
import uuid
from typing import Optional
from models.flight_models import SearchFlightInput, SearchFlightOutput, FlightOption, FlightLeg
from in_memory_context import set_context
from agents import function_tool
from datetime import datetime
from dotenv import load_dotenv
import json

load_dotenv()

logger = logging.getLogger("chat_logger")
SERP_API_KEY = os.getenv("SERP_API_KEY")


@function_tool
def search_flight(
    data: SearchFlightInput,
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None) -> Optional[SearchFlightOutput]:
    try:
        is_multi_city = data.multi_city_legs is not None and len(data.multi_city_legs) > 0

        if is_multi_city:
            logger.info("Searching multi-city flight...")

            # Prepare multi-city request
            trip_type = 3  # Multi-city
         

            multi_city_payload = [
                {
                    "departure_id": leg.origin,
                    "arrival_id": leg.destination,
                    "date": leg.departure_date,
                    **({"times": leg.times} if leg.times else {})
                }
                for leg in data.multi_city_legs
            ]

            params = {
                "engine": "google_flights",
                "type": trip_type,
                "multi_city_json": json.dumps(multi_city_payload),  # Proper JSON format
                "hl": "en",
                "currency": "USD",
                "adults":1,
                "api_key": SERP_API_KEY
            }


        else:
            logger.info(f"Searching flight for {data.origin} → {data.destination} on {data.departure_date}")
            trip_type = 2 if data.return_date is None else 1


            params = {
                "engine": "google_flights",
                "departure_id": data.origin,
                "arrival_id": data.destination,
                "outbound_date": data.departure_date,
                "return_date": data.return_date,
                "type": trip_type,
                "hl": "en",
                "currency": "USD",
                "adults":1,
                "api_key": SERP_API_KEY
            }

        params = {k: v for k, v in params.items() if v is not None}

        logger.info(f"Calling SERP API with params: {params}")
        response = requests.get("https://serpapi.com/search.json", params=params)

        if response.status_code != 200:
            raise Exception(f"SERP API error: {response.status_code} - {response.text}")

        data_json = response.json()
        logger.info(f"SERP response keys: {data_json.keys()}")

        flight_results = []
        all_flight_groups = data_json.get("best_flights", []) or data_json.get("other_flights", [])
        max_results = 3

        for group in all_flight_groups[:max_results]:
            flights = group.get("flights", [])
            if not flights:
                continue

            if is_multi_city:
                # Handle multiple legs
                legs = [
                    FlightLeg(
                        departure_time=leg.get("departure_airport", {}).get("time", "Unknown"),
                        arrival_time=leg.get("arrival_airport", {}).get("time", "Unknown"),
                        origin=leg.get("departure_airport", {}).get("id"),
                        destination=leg.get("arrival_airport", {}).get("id"),
                        duration=leg.get("duration"),
                        stops=0,
                        extensions=leg.get("extensions", []),
                        flight_number=first_flight.get("flight_number", "Unknown")  # New line
                    ) for leg in flights
                ]

                base_price = float(group.get("price", 0)) if group.get("price") else 0
                adults = data.adults
                children = data.children
                infants = data.infants


                total_price =base_price * adults + base_price * 0.75 * children + base_price * 0.10 * infants

                price_breakdown = {
                        "base_fare_per_person": base_price,
                        "adults": {"count": adults, "total": base_price * adults},
                        "children": {"count": children, "total": base_price * 0.75 * children},
                        "infants": {"count": infants, "total": base_price * 0.10 * infants},
                        "total_price": total_price
                    }

                flight_option = FlightOption(
                    airline=flights[0].get("airline", "Unknown"),                    
                    currency="USD",
                    legs=legs,
                    booking_link=group.get("booking_link"),
                    id=str(uuid.uuid4()),
                    price=total_price,    

                                    )
                flight_option.price_breakdown = price_breakdown                   

            else:
                # One-way or return trip
                first_flight = flights[0]
                departure_token = group.get("departure_token")

                outbound_leg = FlightLeg(
                    
                    departure_time=first_flight.get("departure_airport", {}).get("time", "Unknown"),
                    arrival_time=first_flight.get("arrival_airport", {}).get("time", "Unknown"),
                    origin=data.origin,
                    destination=data.destination,
                    duration=str(group.get("total_duration", "Unknown")),
                    stops=len(flights) - 1,
                    extensions=group.get("extensions"),
                    flight_number=first_flight.get("flight_number", "Unknown")  # New line
                )

                return_leg = None
                if departure_token and data.return_date:
                    try:
                        return_params = {
                            "engine": "google_flights",
                            "departure_id": data.origin,
                            "arrival_id": data.destination,
                            "outbound_date": data.departure_date,
                            "return_date": data.return_date,
                            "departure_token": departure_token,
                            "hl": "en",
                            "currency": "USD",
                            "adults":1,
                            "api_key": SERP_API_KEY
                        }

                        logger.info(f"Calling SERP API for return with params: {return_params}")
                        return_response = requests.get("https://serpapi.com/search.json", params=return_params)

                        if return_response.status_code == 200:
                            return_data = return_response.json()
                            return_flights = (
                                return_data.get("best_flights", []) or 
                                return_data.get("other_flights", []) or 
                                return_data.get("return_flights", [])
                            )

                            if return_flights:
                                return_flight_group = return_flights[0]
                                return_legs = return_flight_group.get("flights", [])
                                if return_legs:
                                    return_leg = FlightLeg(
                                        departure_time=return_legs[0].get("departure_airport", {}).get("time"),
                                        arrival_time=return_legs[-1].get("arrival_airport", {}).get("time"),
                                        origin=data.destination,
                                        destination=data.origin,
                                        duration=str(return_flight_group.get("total_duration", "Unknown")),
                                        stops=len(return_legs) - 1,
                                        extensions=return_flight_group.get("extensions", []),
                                        flight_number=first_flight.get("flight_number", "Unknown")  # New line
                                    )
                    except Exception as err:
                        logger.error(f"Failed to fetch return flight: {str(err)}", exc_info=True)

                base_price = float(group.get("price", 0)) if group.get("price") else 0
                adults = data.adults
                children = data.children
                infants = data.infants

                total_price = base_price * adults + base_price * 0.75 * children + base_price * 0.10 * infants

                price_breakdown = {
                        "base_fare_per_person": base_price,
                        "adults": {"count": adults, "total": base_price * adults},
                        "children": {"count": children, "total": base_price * 0.75 * children},
                        "infants": {"count": infants, "total": base_price * 0.10 * infants},
                        "total_price": total_price
                    }

                flight_option = FlightOption(
                    airline=first_flight.get("airline", "Unknown"),                    
                    currency="USD",
                    outbound=outbound_leg,
                    return_leg=return_leg,
                    booking_link=group.get("booking_link"),
                    id=str(uuid.uuid4()),
                    departure_token=departure_token,
                    price=total_price,
                    

                )
                flight_option.price_breakdown = price_breakdown

            flight_results.append(flight_option)

            if user_id and thread_id:
                set_context(user_id, thread_id, f"flight_option_{flight_option.id}", flight_option.model_dump())

        return SearchFlightOutput(
            origin=data.origin,
            destination=data.destination,
            flights=flight_results
        )

    except Exception as e:
        logger.error(f"search_flight error: {e}", exc_info=True)
        raise