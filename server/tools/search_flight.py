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

load_dotenv()

logger = logging.getLogger("chat_logger")
SERP_API_KEY = os.getenv("SERP_API_KEY")


@function_tool
def search_flight(
    data: SearchFlightInput,
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None) -> Optional[SearchFlightOutput]:
    try:
        logger.info(f"Searching flight for {data.origin} → {data.destination} on {data.departure_date}")

        cabin_class_map = {
            "economy": 1,
            "premium_economy": 2,
            "business": 3,
            "first": 4
        }
        cabin_class_code = cabin_class_map.get(data.cabin_class.lower(), 1)

        trip_type = 1 if data.return_date else 2

        # Initial request for outbound flights
        params = {
            "engine": "google_flights",
            "departure_id": data.origin,
            "arrival_id": data.destination,
            "outbound_date": data.departure_date,
            "return_date": data.return_date,
            "type": trip_type,
            "hl": "en",
            "currency": "USD",
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

            first_flight = flights[0]
            departure_token = group.get("departure_token")

            # Create outbound leg
            outbound_leg = FlightLeg(
                departure_time=first_flight.get("departure_airport", {}).get("time", "Unknown"),
                arrival_time=first_flight.get("arrival_airport", {}).get("time", "Unknown"),
                origin=data.origin,
                destination=data.destination,
                duration=str(group.get("total_duration", "Unknown")),
                stops=len(flights) - 1,
                extensions=group.get("extensions")
            )

            return_leg = None
            if departure_token and data.return_date:
                try:
                    # Request for return flights needs to include all original parameters plus departure_token
                    return_params = {
                        "engine": "google_flights",
                        "departure_id": data.origin,
                        "arrival_id": data.destination,
                        "outbound_date": data.departure_date,
                        "return_date": data.return_date,
                        "departure_token": departure_token,
                        "hl": "en",
                        "currency": "USD",
                        "api_key": SERP_API_KEY
                    }
                    
                    logger.info(f"Calling SERP API for return with params: {return_params}")
                    return_response = requests.get("https://serpapi.com/search.json", params=return_params)
                    
                    if return_response.status_code == 200:
                        return_data = return_response.json()
                        logger.info(f"Return flight data: {return_data}")
                        
                        # Check different possible locations for return flights in response
                        return_flights = (
                            return_data.get("best_flights", []) or 
                            return_data.get("other_flights", []) or 
                            return_data.get("return_flights", [])
                        )
                        
                        if not return_flights:
                            logger.warning("No return flights found in any expected field")
                        else:
                            # Take the first return flight option
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
                                    extensions=return_flight_group.get("extensions", [])
                                )
                except Exception as err:
                    logger.error(f"Failed to fetch return flight: {str(err)}", exc_info=True)

            # Build full flight option
            flight_option = FlightOption(
                airline=first_flight.get("airline", "Unknown"),
                price=float(group.get("price", 0)) if group.get("price") else None,
                currency="USD",
                outbound=outbound_leg,
                return_leg=return_leg,
                booking_link=group.get("booking_link"),
                id=str(uuid.uuid4()),
                departure_token=departure_token
            )

            # ---- Filtering Logic ----
            if data.max_price and flight_option.price and flight_option.price > data.max_price:
                continue

            if data.nonstop_only and outbound_leg.stops and outbound_leg.stops > 0:
                continue

            if data.allowed_airlines and flight_option.airline not in data.allowed_airlines:
                continue

            if data.excluded_airlines and flight_option.airline in data.excluded_airlines:
                continue

            flight_results.append(flight_option)

            if user_id and thread_id:
                set_context(user_id, thread_id, f"flight_option_{flight_option.id}", flight_option.model_dump())

            print(f"### Option: {flight_option.airline}\n")

            print(f"🛫 Outbound Flight:")
            print(f"  - From: {outbound_leg.origin}")
            print(f"  - To: {outbound_leg.destination}")
            print(f"  - Departure: {outbound_leg.departure_time}")
            print(f"  - Arrival: {outbound_leg.arrival_time}")
            print(f"  - Duration: {outbound_leg.duration}")
            print(f"  - Stops: {outbound_leg.stops}")
            if outbound_leg.extensions:
                print(f"  - Extras: {', '.join(outbound_leg.extensions)}")

            if return_leg:
                print(f"\n🔁 Return Flight:")
                print(f"  - From: {return_leg.origin}")
                print(f"  - To: {return_leg.destination}")
                print(f"  - Departure: {return_leg.departure_time}")
                print(f"  - Arrival: {return_leg.arrival_time}")
                print(f"  - Duration: {return_leg.duration}")
                print(f"  - Stops: {return_leg.stops}")
                if return_leg.extensions:
                    print(f"  - Extras: {', '.join(return_leg.extensions)}")

            print(f"\n💰 Total Price (Round Trip): ${flight_option.price} {flight_option.currency}")
            print("-" * 50 + "\n")


            
        return SearchFlightOutput(
            origin=data.origin,
            destination=data.destination,
            flights=flight_results
        )

    except Exception as e:
        logger.error(f"search_flight error: {e}", exc_info=True)
        raise