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
        # Updated format to match example: "August 4, 2025, at 22:25"
        return dt.strftime('%B %d, %Y, at %H:%M')
    except Exception:
        return dt_str  # Fallback if parsing fails

def format_flight_option(option: FlightOption, index: int, trip_type: str) -> str:
    def clean_leg_info(title: str, leg: FlightLeg) -> str:
        airline_names = ", ".join(set(
            seg.airline[0] if isinstance(seg.airline, list) else seg.airline
            for seg in leg.segments
        ))
        flight_nums = ", ".join(seg.flight_number for seg in leg.segments)
        cabin_class = leg.segments[0].cabin_class if leg.segments else "Economy"
        stops = "Non-stop" if leg.stops == 0 else f"{leg.stops} stop(s)"

        layover_lines = ""
        if leg.layovers:
            layover_lines = "\n".join(
                f"   ⏸️ Layover at {lay.layover_airport} for {lay.layover_duration}"
                for lay in leg.layovers
            )
            layover_lines = f"\n- 🛑 Layovers:\n{layover_lines}"

        return (
            f"**{title}**\n"
            f"- {leg.origin} → {leg.destination}\n"
            f"- 🛫 {format_datetime(leg.departure_date_time)} → 🛬 {format_datetime(leg.arrival_date_time)}\n"
            f"- ⏱️ Duration: {leg.total_duration}, ✈️ {stops}\n"
            f"- 👨‍✈️ Airline: {airline_names}\n"
            f"- 🪪 Flight(s): {flight_nums}\n"
            f"- 🛋️ Cabin: {cabin_class}"
            f"{layover_lines}\n"
        )

    formatted = f"### ✈️ Option {index + 1}: {trip_type.title()}\n\n"

    if trip_type == "round-trip" and len(option.legs) >= 2:
        outbound_leg = option.legs[0]
        return_leg = option.legs[1]
        formatted += clean_leg_info("🟢 Outbound Flight", outbound_leg) + "\n"
        formatted += clean_leg_info("🔁 Return Flight", return_leg) + "\n"
    else:
        for i, leg in enumerate(option.legs):
            label = f"🛫 Leg {i + 1}" if trip_type == "multi-city" else "🟢 Flight"
            formatted += clean_leg_info(label, leg) + "\n"

    formatted += f"💰 **Total Price:** {option.total_price:.2f} {option.currency}\n"
    formatted += "---\n"
    return formatted


def build_round_trip_flight_option(group, outbound_flights, data, outbound_segments, outbound_layovers) -> Optional[FlightOption]:
    # First, process the outbound flight data
    outbound_segments = outbound_flights
    airline_set = set()

    # Get the departure token from the outbound flight
    departure_token = group.get("departure_token")
    if not departure_token:
        logger.warning("Skipping option - missing departure_token")
        return None

    # --- First try to find return flights ---
    try:
        # Derive outbound_date from actual outbound flight data
        first_outbound = outbound_flights[0]
        outbound_date_iso = first_outbound.get("departure_airport", {}).get("time", "")
        outbound_date_parsed = datetime.fromisoformat(outbound_date_iso) if outbound_date_iso else None
        outbound_date_str = outbound_date_parsed.strftime("%Y-%m-%d") if outbound_date_parsed else data.departure_date

        return_params = {
            "engine": "google_flights",
            "departure_id": data.origin,    # reverse of outbound
            "arrival_id": data.destination,  # reverse of outbound
            "departure_token": departure_token, # from outbound leg
            "outbound_date": outbound_date_str, # parsed from outbound actual time
            "return_date": data.return_date,    # from input
            "hl": "en",
            "currency": "USD",
            "adults": data.adults,
            "api_key": SERP_API_KEY
        }

        logger.info(f"Fetching return flight with params: {return_params}")
        return_response = requests.get("https://serpapi.com/search.json", params=return_params, timeout=30)
        
        if return_response.status_code != 200:
            logger.error(f"Failed to fetch return flights: {return_response.status_code}")
            return None

        return_data = return_response.json()
        logger.info(f"Return Flight API Response:\n{json.dumps(return_data, indent=2)}")
        
        # Check if we actually got return flights
        return_flights = return_data.get("best_flights") or return_data.get("other_flights") or []
        if not return_flights:
            logger.warning("No return flights found for this option")
            return None

        return_group = return_flights[0]  # Take the best return option
        return_flights_data = return_group.get("flights", [])
        if not return_flights_data:
            logger.warning("No flight segments in return group")
            return None

        # --- Now that we have both legs, build the complete option ---
        
        # Process outbound segments
        outbound_segment_objs = []
        for seg in outbound_segments:
            raw_airline = seg.get("airline", "Unknown")
            airline = [raw_airline] if isinstance(raw_airline, str) else raw_airline or ["Unknown"]
            airline_set.update(airline)

            outbound_segment_objs.append(FlightSegment(
                segment_number=seg.get("segment_number", 1),
                departure_airport=seg.get("departure_airport", {}).get("id", "Unknown"),
                departure_datetime=seg.get("departure_airport", {}).get("time", "Unknown"),
                arrival_airport=seg.get("arrival_airport", {}).get("id", "Unknown"),
                arrival_datetime=seg.get("arrival_airport", {}).get("time", "Unknown"),
                duration=format_duration(seg.get("duration", "Unknown")),
                cabin_class=seg.get("travel_class", "Economy"),
                airline=airline,
                flight_number=seg.get("flight_number", "Unknown"),
                extension_info=[seg.get("flight_number", "Unknown"), *(seg.get("extensions", []))]
            ))

        # Process return segments
        return_segment_objs = []
        for seg in return_flights_data:
            raw_airline = seg.get("airline", "Unknown")
            airline = [raw_airline] if isinstance(raw_airline, str) else raw_airline or ["Unknown"]
            airline_set.update(airline)

            return_segment_objs.append(FlightSegment(
                segment_number=seg.get("segment_number", 1),
                departure_airport=seg.get("departure_airport", {}).get("id", "Unknown"),
                departure_datetime=seg.get("departure_airport", {}).get("time", "Unknown"),
                arrival_airport=seg.get("arrival_airport", {}).get("id", "Unknown"),
                arrival_datetime=seg.get("arrival_airport", {}).get("time", "Unknown"),
                duration=format_duration(seg.get("duration", "Unknown")),
                cabin_class=seg.get("travel_class", "Economy"),
                airline=airline,
                flight_number=seg.get("flight_number", "Unknown"),
                extension_info=[seg.get("flight_number", "Unknown"), *(seg.get("extensions", []))]
            ))

        # --- Price Calculation ---
        outbound_price = float(group.get("price", 0)) if group.get("price") else 0
        return_price = float(return_group.get("price", 0)) if return_group.get("price") else 0
        base_price = outbound_price + return_price
        
        adults = data.adults
        children = data.children
        infants = data.infants

        total_price = base_price * (adults + 0.75 * children + 0.10 * infants)
        price_breakdown = PriceBreakdown(
            base_fare_per_person=base_price,
            adults=PriceBreakdownEntry(count=adults, total=outbound_price * adults + return_price * adults),
            children=PriceBreakdownEntry(
                count=children, 
                total=outbound_price * 0.75 * children + return_price * 0.75 * children
            ) if children else None,
            infants=PriceBreakdownEntry(
                count=infants, 
                total=outbound_price * 0.10 * infants + return_price * 0.10 * infants
            ) if infants else None,
            total_price=total_price
        )

        # --- Build Flight Legs ---
        last_outbound = outbound_flights[-1]
        outbound_leg = FlightLeg(
            departure_date_time=first_outbound.get("departure_airport", {}).get("time", "Unknown"),
            arrival_date_time=last_outbound.get("arrival_airport", {}).get("time", "Unknown"),
            origin=data.origin,
            destination=data.destination,
            total_duration=format_duration(group.get("total_duration", "Unknown")),
            stops=len(outbound_flights) - 1,
            segments=outbound_segment_objs,
            layovers=[
                LayoverInfo(
                    layover_airport=lay.get("name", "Unknown"),
                    layover_duration=format_duration(lay.get("duration", "Unknown"))
                ) for lay in outbound_layovers
            ]
        )

        return_leg = FlightLeg(
            departure_date_time=return_flights_data[0].get("departure_airport", {}).get("time", "Unknown"),
            arrival_date_time=return_flights_data[-1].get("arrival_airport", {}).get("time", "Unknown"),
            origin=data.destination,
            destination=data.origin,
            total_duration=format_duration(return_group.get("total_duration", "Unknown")),
            stops=len(return_flights_data) - 1,
            segments=return_segment_objs,
            layovers=[
                LayoverInfo(
                    layover_airport=lay.get("name", "Unknown"),
                    layover_duration=format_duration(lay.get("duration", "Unknown"))
                ) for lay in return_group.get("layovers", [])
            ]
        )

        # --- Final Flight Option ---
        return FlightOption(
            id=str(uuid.uuid4()),
            origin=data.origin,
            destination=data.destination,
            origin_city=first_outbound.get("departure_airport", {}).get("name", "Unknown"),
            desination_city=last_outbound.get("arrival_airport", {}).get("name", "Unknown"),
            airline=sorted(airline_set),
            legs=[outbound_leg, return_leg],
            total_price=total_price,
            currency="USD",
            price_breakdown=[price_breakdown],
            booking_token=group.get("booking_token"),
            departure_token=departure_token
        )

    except Exception as err:
        logger.error(f"Error building round trip option: {str(err)}", exc_info=True)
        return None
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
                "adults": 1,
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
                "adults": 1,
                "api_key": SERP_API_KEY
            }

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        logger.info(f"Calling SERP API with params: {params}")
        response = requests.get("https://serpapi.com/search.json", params=params)
        if response.status_code != 200:
            raise Exception(f"SERP API error: {response.status_code} - {response.text}")

        data_json = response.json()
        
        # Log the complete API response
        logger.info(f"Complete SERP API Response:\n{json.dumps(data_json, indent=2)}")
        
        all_flight_groups = data_json.get("best_flights") or data_json.get("other_flights") or []
        max_results = 1

        for index, group in enumerate(all_flight_groups[:max_results]):
            flights = group.get("flights", [])
            if not flights:
                continue

            segments = group.get("segments", []) or []
            layovers = group.get("layovers", []) or []

            if is_multi_city:
                flight_option = build_multi_city_flight_option(group, flights, data, segments, layovers)
                trip_type_str = "multi-city"
            elif trip_type == 1:  # Round-trip
                flight_option = build_round_trip_flight_option(group, flights, data, segments, layovers)
                trip_type_str = "round-trip"
                
                if not flight_option:
                    logger.warning(f"Skipping incomplete round-trip option {index + 1}")
                    continue
            else:
                flight_option = build_one_way_flight_option(group, flights, data, segments, layovers)
                trip_type_str = "one-way"

            formatted_summary = format_flight_option(flight_option, index, trip_type_str)
            flight_option.formatted_summary = formatted_summary
            
            logger.info(f"Formatted flight option {index + 1}:\n{formatted_summary}")
            flight_results.append(flight_option)

        return SearchFlightOutput(flights=flight_results)

    except Exception as e:
        logger.error(f"search_flight error: {e}", exc_info=True)
        raise