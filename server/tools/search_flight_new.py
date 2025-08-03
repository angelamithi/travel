import os
import requests
import logging
import uuid
from typing import Optional
from in_memory_context import set_context
from agents import function_tool
from datetime import datetime
from dotenv import load_dotenv
import json
from typing import List
from models.flight_models import (
    FlightOption,
    FlightLeg,
    FlightSegment,
    LayoverInfo,
    PriceBreakdown,
    PriceBreakdownEntry,
    SearchFlightInput,
    SearchFlightOutput,
)



load_dotenv()

logger = logging.getLogger("chat_logger")
SERP_API_KEY = os.getenv("SERP_API_KEY")

def format_duration(value) -> str:
    try:
        if isinstance(value, int):
            minutes = value
        elif isinstance(value, str):
            minutes = int(value.strip().replace("min", "").strip())
        else:
            return str(value)

        hours = minutes // 60
        mins = minutes % 60

        if hours and mins:
            return f"{hours}h {mins}m"
        elif hours:
            return f"{hours}h"
        else:
            return f"{mins}m"
    except:
        return str(value)  # fallback to original if parsing fails

def format_datetime(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime('%B %d, %Y at %H:%M')  # Example: August 10, 2025 at 10:00
    except Exception:
        return dt_str  # Fallback if parsing fails

def format_flight_option(option: FlightOption, index: int, trip_type: str) -> str:
    summary_lines = [
        f"[Option {index + 1}] {trip_type.title()} flight:",
        f"From {option.origin_city} ({option.origin}) to {option.desination_city} ({option.destination})",
        f"Airline(s): {', '.join(option.airline)}"
,
        f"Departs: {option.legs[0].origin} at {format_datetime(option.legs[0].departure_date_time)}",
        f"Arrives: {option.legs[-1].destination} at {format_datetime(option.legs[-1].arrival_date_time)}",
    ]

    # Include each segment's flight number and airline (if available in extension_info)
    flight_numbers = []
    for leg in option.legs:
        for segment in leg.segments:
            flight_num = None
            airline = option.airline  # fallback
            # Try to extract flight number from extension info
            for ext in segment:
                if isinstance(ext, dict) and "flight_number" in ext:
                    flight_num = ext.get("flight_number")
                if isinstance(ext, dict) and "airline" in ext:
                    airline = ext.get("airline")
            if flight_num:
                if isinstance(airline, list):
                    airline_str = "/".join(airline)
                else:
                    airline_str = airline
                flight_numbers.append(f"{airline_str} {flight_num}")

    
    if flight_numbers:
        summary_lines.append("Flight(s): " + ", ".join(flight_numbers))

    summary_lines.append(f"Total Price: {option.total_price:.2f} {option.currency}")
    return "\n".join(summary_lines)



def build_multi_city_flight_option(group, flights, data, segments_data, layovers_data) -> FlightOption:
    segments_data = flights  # SerpAPI returns each segment as a full "flight"

    # 1. --- Price Breakdown ---
    base_price = float(group.get("price", 0)) if group.get("price") else 0
    adults = data.adults
    children = data.children
    infants = data.infants

    total_adults = base_price * adults
    total_children = base_price * 0.75 * children
    total_infants = base_price * 0.10 * infants
    total_price = total_adults + total_children + total_infants

    price_breakdown = PriceBreakdown(
        base_fare_per_person=base_price,
        adults=PriceBreakdownEntry(count=adults, total=total_adults),
        children=PriceBreakdownEntry(count=children, total=total_children) if children else None,
        infants=PriceBreakdownEntry(count=infants, total=total_infants) if infants else None,
        total_price=total_price
    )

    # 2. --- Build Segments per leg ---
    segments_by_leg = {}
    airline_set = set()  # To collect unique airline names

    for i, seg in enumerate(segments_data):
        leg_index = seg.get("leg_index", 0)
        raw_airline = seg.get("airline", "Unknown")
        airline = [raw_airline] if isinstance(raw_airline, str) else raw_airline or ["Unknown"]
        airline_set.update(airline)

        flight_number = seg.get("flight_number", "Unknown")

        segment = FlightSegment(
            segment_number=i + 1,
            departure_airport=seg.get("departure_airport", {}).get("id", "Unknown"),
            departure_datetime=seg.get("departure_airport", {}).get("time", "Unknown"),
            arrival_airport=seg.get("arrival_airport", {}).get("id", "Unknown"),
            arrival_datetime=seg.get("arrival_airport", {}).get("time", "Unknown"),
            duration=format_duration(seg.get("duration", "Unknown")),
            cabin_class=seg.get("travel_class", "Economy"),
            airline=airline,
            flight_number=flight_number,
            extension_info=[flight_number, *(seg.get("extensions", []))]
        )

        segments_by_leg.setdefault(leg_index, []).append(segment)

    # 3. --- Build Layovers per leg ---
    layovers_by_leg = {}
    for lay in layovers_data:
        leg_index = lay.get("leg_index", 0)
        layover = LayoverInfo(
            layover_airport=lay.get("name", "Unknown"),
            layover_duration=format_duration(lay.get("duration", "Unknown"))
        )
        layovers_by_leg.setdefault(leg_index, []).append(layover)

    # 4. --- Build Flight Legs ---
    legs: List[FlightLeg] = []
    for i, leg in enumerate(flights):
        formatted_duration = format_duration(leg.get("duration", "Unknown"))
        flight_leg = FlightLeg(
            departure_date_time=leg.get("departure_airport", {}).get("time", "Unknown"),
            arrival_date_time=leg.get("arrival_airport", {}).get("time", "Unknown"),
            origin=leg.get("departure_airport", {}).get("id", "Unknown"),
            destination=leg.get("arrival_airport", {}).get("id", "Unknown"),
            total_duration=formatted_duration,
            stops=leg.get("stops", 0),
            segments=segments_by_leg.get(i, []),
            layovers=layovers_by_leg.get(i, [])
        )
        legs.append(flight_leg)

    # 5. --- Final Flight Option ---
    first_leg = flights[0]
    last_leg = flights[-1]

    return FlightOption(
        id=str(uuid.uuid4()),
        origin=first_leg.get("departure_airport", {}).get("id", "Unknown"),
        destination=last_leg.get("arrival_airport", {}).get("id", "Unknown"),
        origin_city=first_leg.get("departure_airport", {}).get("name", "Unknown"),
        desination_city=last_leg.get("arrival_airport", {}).get("name", "Unknown"),
        airline=sorted(airline_set) if airline_set else "Unknown",  # Joined airline list
        legs=legs,
        total_price=total_price,
        currency="USD",
        price_breakdown=[price_breakdown],
        booking_token=group.get("booking_token")
    )



def build_one_way_flight_option(group, flights, data, segments_data, layovers_data) -> FlightOption:
    import uuid
    from typing import List

    first_flight = flights[0]
    segments_data = flights

    # 1. --- Price Breakdown ---
    base_price = float(group.get("price", 0)) if group.get("price") else 0
    adults = data.adults
    children = data.children
    infants = data.infants

    total_adults = base_price * adults
    total_children = base_price * 0.75 * children
    total_infants = base_price * 0.10 * infants
    total_price = total_adults + total_children + total_infants

    price_breakdown = PriceBreakdown(
        base_fare_per_person=base_price,
        adults=PriceBreakdownEntry(count=adults, total=total_adults),
        children=PriceBreakdownEntry(count=children, total=total_children) if children else None,
        infants=PriceBreakdownEntry(count=infants, total=total_infants) if infants else None,
        total_price=total_price
    )

    # 2. --- Flight Segments ---
    flight_segments: List[FlightSegment] = []
    airline_set = set()  # <-- To store unique airlines
    for i, seg in enumerate(segments_data):
        raw_airline = seg.get("airline", "Unknown")
        airline = [raw_airline] if isinstance(raw_airline, str) else raw_airline or ["Unknown"]
        airline_set.update(airline)

        flight_number = seg.get("flight_number", "Unknown")


        flight_segments.append(FlightSegment(
            segment_number=i + 1,
            departure_airport=seg.get("departure_airport", {}).get("id", "Unknown"),
            departure_datetime=seg.get("departure_airport", {}).get("time", "Unknown"),
            arrival_airport=seg.get("arrival_airport", {}).get("id", "Unknown"),
            arrival_datetime=seg.get("arrival_airport", {}).get("time", "Unknown"),
            duration=format_duration(seg.get("duration", "Unknown")),
            cabin_class=seg.get("travel_class", "Economy"),
            airline=airline,
            flight_number=flight_number,
            extension_info=[flight_number, *(seg.get("extensions", []))]
        ))

    # 3. --- Layovers ---
    layovers: List[LayoverInfo] = []
    for lay in layovers_data:
        layovers.append(LayoverInfo(
            layover_airport=lay.get("name", "Unknown"),
            layover_duration=format_duration(lay.get("duration", "Unknown"))
        ))

    # 4. --- Flight Leg ---
    formatted_total_duration = format_duration(group.get("total_duration", "Unknown"))
    flight_leg = FlightLeg(
        departure_date_time=first_flight.get("departure_airport", {}).get("time", "Unknown"),
        arrival_date_time=first_flight.get("arrival_airport", {}).get("time", "Unknown"),
        origin=data.origin,
        destination=data.destination,
        total_duration=formatted_total_duration,
        stops=len(flights) - 1,
        segments=flight_segments,
        layovers=layovers
    )

    # 5. --- Final Flight Option ---
    return FlightOption(
        id=str(uuid.uuid4()),
        origin=data.origin,
        destination=data.destination,
        origin_city=first_flight.get("departure_airport", {}).get("name", "Unknown"),
        desination_city=first_flight.get("arrival_airport", {}).get("name", "Unknown"),
        airline=sorted(airline_set),
        legs=[flight_leg],
        total_price=total_price,
        currency="USD",
        price_breakdown=[price_breakdown],
        booking_token=group.get("booking_token")
    )


def build_round_trip_flight_option(group, outbound_flights, data, outbound_segments, outbound_layovers) -> FlightOption:
    import uuid
    import requests

    outbound_segments = outbound_flights

    # --- Collect unique airlines ---
    airline_set = set()

    # 1. --- Price Breakdown ---
    base_price = float(group.get("price", 0)) if group.get("price") else 0
    adults = data.adults
    children = data.children
    infants = data.infants

    total_adults = base_price * adults
    total_children = base_price * 0.75 * children
    total_infants = base_price * 0.10 * infants
    total_price = total_adults + total_children + total_infants

    price_breakdown = PriceBreakdown(
        base_fare_per_person=base_price,
        adults=PriceBreakdownEntry(count=adults, total=total_adults),
        children=PriceBreakdownEntry(count=children, total=total_children) if children else None,
        infants=PriceBreakdownEntry(count=infants, total=total_infants) if infants else None,
        total_price=total_price
    )

    # 2. --- Outbound Segments ---
    outbound_segment_objs: List[FlightSegment] = []
    for seg in outbound_segments:
        raw_airline = seg.get("airline", "Unknown")
        airline = [raw_airline] if isinstance(raw_airline, str) else raw_airline or ["Unknown"]
        airline_set.update(airline)

        flight_number = seg.get("flight_number", "Unknown")


        outbound_segment_objs.append(FlightSegment(
            segment_number=seg.get("segment_number", 1),
            departure_airport=seg.get("departure_airport", {}).get("id", "Unknown"),
            departure_datetime=seg.get("departure_airport", {}).get("time", "Unknown"),
            arrival_airport=seg.get("arrival_airport", {}).get("id", "Unknown"),
            arrival_datetime=seg.get("arrival_airport", {}).get("time", "Unknown"),
            duration=format_duration(seg.get("duration", "Unknown")),
            cabin_class=seg.get("cabin_class", "Economy"),
            airline=airline,
            flight_number=flight_number,
            extension_info=[flight_number, *(seg.get("extensions", []))]
        ))

    # 3. --- Outbound Layovers ---
    outbound_layover_objs: List[LayoverInfo] = [
        LayoverInfo(
            layover_airport=lay.get("name", "Unknown"),
            layover_duration=format_duration(lay.get("duration", "Unknown"))
        ) for lay in outbound_layovers
    ]

    # 4. --- Outbound Leg ---
    first_outbound = outbound_flights[0]
    last_outbound = outbound_flights[-1]
    outbound_leg = FlightLeg(
        departure_date_time=first_outbound.get("departure_airport", {}).get("time", "Unknown"),
        arrival_date_time=last_outbound.get("arrival_airport", {}).get("time", "Unknown"),
        origin=data.origin,
        destination=data.destination,
        total_duration=format_duration(group.get("total_duration", "Unknown")),
        stops=len(outbound_flights) - 1,
        segments=outbound_segment_objs,
        layovers=outbound_layover_objs
    )

    # 5. --- Return Leg ---
    return_leg = None
    departure_token = group.get("departure_token")

    if departure_token:
        try:
            return_params = {
                "engine": "google_flights",
                "departure_id": data.destination,
                "arrival_id": data.origin,
                "outbound_date": data.departure_date,
                "return_date": data.return_date,
                "departure_token": departure_token,
                "hl": "en",
                "currency": "USD",
                "adults": data.adults,
                "api_key": SERP_API_KEY
            }

            return_response = requests.get("https://serpapi.com/search.json", params=return_params)
            if return_response.status_code == 200:
                return_data = return_response.json()
                return_flights = return_data.get("best_flights") or return_data.get("other_flights") or []
                if return_flights:
                    return_group = return_flights[0]
                    return_legs = return_group.get("flights", [])

                    # --- Parse Return Segments ---
                    return_segment_objs: List[FlightSegment] = []
                    for seg in return_legs:
                        raw_airline = seg.get("airline", "Unknown")
                        airline = [raw_airline] if isinstance(raw_airline, str) else raw_airline or ["Unknown"]
                        airline_set.update(airline)

                        flight_number = seg.get("flight_number", "Unknown")
                   

                        return_segment_objs.append(FlightSegment(
                            segment_number=seg.get("segment_number", 1),
                            departure_airport=seg.get("departure_airport", {}).get("id", "Unknown"),
                            departure_datetime=seg.get("departure_airport", {}).get("time", "Unknown"),
                            arrival_airport=seg.get("arrival_airport", {}).get("id", "Unknown"),
                            arrival_datetime=seg.get("arrival_airport", {}).get("time", "Unknown"),
                            duration=format_duration(seg.get("duration", "Unknown")),
                            cabin_class=seg.get("cabin_class", "Economy"),
                            airline=airline,
                            flight_number=flight_number,
                            extension_info=[flight_number, *(seg.get("extensions", []))]
                        ))

                    # --- Return Layovers ---
                    return_layover_objs: List[LayoverInfo] = []
                    for i in range(len(return_legs) - 1):
                        layover_airport = return_legs[i].get("arrival_airport", {}).get("id", "Unknown")
                        layover_duration = format_duration(return_legs[i + 1].get("duration", "Unknown"))
                        return_layover_objs.append(LayoverInfo(
                            layover_airport=layover_airport,
                            layover_duration=layover_duration
                        ))

                    return_leg = FlightLeg(
                        departure_date_time=return_legs[0].get("departure_airport", {}).get("time", "Unknown"),
                        arrival_date_time=return_legs[-1].get("arrival_airport", {}).get("time", "Unknown"),
                        origin=data.destination,
                        destination=data.origin,
                        total_duration=format_duration(return_group.get("total_duration", "Unknown")),
                        stops=len(return_legs) - 1,
                        segments=return_segment_objs,
                        layovers=return_layover_objs
                    )
        except Exception as err:
            logger.error(f"Failed to fetch return flight: {str(err)}", exc_info=True)

    # 6. --- Final Flight Option ---
    return FlightOption(
        id=str(uuid.uuid4()),
        origin=data.origin,
        destination=data.destination,
        origin_city=first_outbound.get("departure_airport", {}).get("name", "Unknown"),
        desination_city=last_outbound.get("arrival_airport", {}).get("name", "Unknown"),
        airline=sorted(airline_set),  # <-- Multi-airline support
        legs=[outbound_leg] + ([return_leg] if return_leg else []),
        total_price=total_price,
        currency="USD",
        price_breakdown=[price_breakdown],
        booking_token=group.get("booking_token")
    )


@function_tool
def search_flight(data: SearchFlightInput, user_id: Optional[str] = None, thread_id: Optional[str] = None) -> Optional[SearchFlightOutput]:
    try:
        is_multi_city = data.multi_city_legs is not None and len(data.multi_city_legs) > 0
        flight_results = []

        # --- Determine Trip Type ---
        trip_type = 3 if is_multi_city else (2 if data.return_date is None else 1)
        logger.info(f"Trip type: {'multi-city' if trip_type == 3 else 'round-trip' if trip_type == 1 else 'one-way'}")

        # --- Build Parameters ---
        if is_multi_city:
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
                "type": 3,
                "multi_city_json": json.dumps(multi_city_payload),
                "hl": "en",
                "currency": "USD",
                "adults": data.adults,
                "api_key": SERP_API_KEY
            }
        else:
            params = {
                "engine": "google_flights",
                "departure_id": data.origin,
                "arrival_id": data.destination,
                "outbound_date": data.departure_date,
                "return_date": data.return_date if trip_type == 1 else None,
                "type": trip_type,
                "hl": "en",
                "currency": "USD",
                "adults": data.adults,
                "api_key": SERP_API_KEY
            }

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        logger.info(f"Calling SERP API with params: {params}")
        response = requests.get("https://serpapi.com/search.json", params=params)
        if response.status_code != 200:
            raise Exception(f"SERP API error: {response.status_code} - {response.text}")

        data_json = response.json()
        all_flight_groups = data_json.get("best_flights") or data_json.get("other_flights") or []
        max_results = 3

        for index, group in enumerate(all_flight_groups[:max_results]):
            flights = group.get("flights", [])
            if not flights:
                continue

            # --- Segments and Layovers ---
            segments = group.get("segments", []) or []
            layovers = group.get("layovers", []) or []

            if is_multi_city:
                flight_option = build_multi_city_flight_option(group, flights, data, segments, layovers)
                trip_type_str = "multi-city"
            elif trip_type == 1:
                flight_option = build_round_trip_flight_option(group, flights, data, segments, layovers)
                trip_type_str = "round-trip"
            else:
                flight_option = build_one_way_flight_option(group, flights, data, segments, layovers)
                trip_type_str = "one-way"

            formatted_summary = format_flight_option(flight_option, index, trip_type_str)
            flight_option.formatted_summary = formatted_summary
            
            logger.debug(f"Full FlightOption JSON {index+1}: {flight_option.model_dump_json(indent=2)}")


            # logger.info(f"Formatted Flight Option {index+1}:\n{formatted_summary}")
            flight_results.append(flight_option)

            if user_id and thread_id:
                set_context(user_id, thread_id, f"flight_option_{flight_option.id}", flight_option.model_dump())

        return SearchFlightOutput(flights=flight_results)

    except Exception as e:
        logger.error(f"search_flight error: {e}", exc_info=True)
        raise