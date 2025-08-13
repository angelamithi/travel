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


def build_multi_city_flight_option(group, flights, data, segments, layovers_data) -> Optional[FlightOption]:
    from dateutil import parser

    # 1. --- Price Breakdown ---
    # Handle price extraction carefully
    price_info = group.get("price", {})
    if isinstance(price_info, dict):
        base_price = float(price_info.get("value", 0))
        currency = price_info.get("currency", "USD")
    elif isinstance(price_info, (int, float)):
        base_price = float(price_info)
        currency = "USD"
    else:
        base_price = 0
        currency = "USD"

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

    # Rest of the function remains the same...
    airline_set = set()
    segments_by_leg = {}
    layovers_by_leg = {}

    # Group segments by leg_index
    for seg in segments:
        leg_index = seg.get("leg_index", 0)  # default to 0 if missing
        segments_by_leg.setdefault(leg_index, []).append(seg)
        airline_set.add(seg.get("airline"))

    # Group layovers by leg_index
    for lay in layovers_data:
        leg_index = lay.get("leg_index", 0)
        layovers_by_leg.setdefault(leg_index, []).append(lay)

    # Build FlightLegs for all legs in the multi-city trip
    legs = []
    for leg_index in sorted(segments_by_leg.keys()):
        segs = segments_by_leg[leg_index]
        lyrs = layovers_by_leg.get(leg_index, [])

        if not segs:
            continue

        first_seg = segs[0]
        last_seg = segs[-1]

        departure_dt = parser.parse(first_seg["departure_date_time"])
        arrival_dt = parser.parse(last_seg["arrival_date_time"])
        duration = format_duration((arrival_dt - departure_dt).total_seconds() / 60)

        # Get the leg details from the corresponding multi_city_leg
        leg_data = data.multi_city_legs[leg_index] if leg_index < len(data.multi_city_legs) else None
        
        leg = FlightLeg(
            departure_date_time=first_seg["departure_date_time"],
            arrival_date_time=last_seg["arrival_date_time"],
            origin=leg_data.origin if leg_data else first_seg["departure_airport"],
            destination=leg_data.destination if leg_data else last_seg["arrival_airport"],
            total_duration=duration,
            stops=len(segs) - 1,
            segments=[FlightSegment(
                segment_number=idx + 1,
                departure_airport=seg["departure_airport"],
                departure_datetime=seg["departure_date_time"],
                arrival_airport=seg["arrival_airport"],
                arrival_datetime=seg["arrival_date_time"],
                duration=format_duration(seg.get("duration", "Unknown")),
                cabin_class=seg.get("travel_class", "Economy"),
                airline=[seg["airline"]] if isinstance(seg["airline"], str) else seg["airline"],
                flight_number=seg.get("flight_number", "Unknown"),
                extension_info=seg.get("extensions", [])
            ) for idx, seg in enumerate(segs)],
            layovers=[LayoverInfo(
                layover_airport=lay["name"],
                layover_duration=format_duration(lay.get("duration", "Unknown"))
            ) for lay in lyrs]
        )
        legs.append(leg)

    if not legs:
        return None

    # Get origin and destination from the first and last legs
    origin = legs[0].origin
    destination = legs[-1].destination
    
    # Get city names from the first segment of first leg and last segment of last leg
    origin_city = legs[0].segments[0].departure_airport if legs[0].segments else "Unknown"
    destination_city = legs[-1].segments[-1].arrival_airport if legs[-1].segments else "Unknown"

    return FlightOption(
        id=str(uuid.uuid4()),
        origin=origin,
        destination=destination,
        origin_city=origin_city,
        desination_city=destination_city,
        airline=list(airline_set),
        legs=legs,
        total_price=total_price,
        currency=currency,  # Use the extracted currency
        price_breakdown=[price_breakdown],
        booking_token=group.get("booking_token")
    )


    

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
                extension_info=seg.get("extensions", []) or []
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
                extension_info=seg.get("extensions", []) or []
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
            extension_info=seg.get("extensions", []) or []
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

        if is_multi_city:
            # For multi-city, we need to make separate API calls for each leg and combine them
            all_leg_options = []
            
            # First get options for each leg
            for leg in data.multi_city_legs:
                params = {
                    "engine": "google_flights",
                    "departure_id": leg.origin,
                    "arrival_id": leg.destination,
                    "outbound_date": leg.departure_date,
                    "type": 2,  # one-way
                    "hl": "en",
                    "currency": "USD",
                    "adults": data.adults,
                    "api_key": SERP_API_KEY
                }
                
                logger.info(f"Fetching leg {leg.origin}-{leg.destination} with params: {params}")
                response = requests.get("https://serpapi.com/search.json", params=params)
                if response.status_code != 200:
                    raise Exception(f"SERP API error for leg {leg.origin}-{leg.destination}: {response.status_code}")
                
                leg_data = response.json()
                logger.info(f"Leg API Response for {leg.origin}-{leg.destination}:\n{json.dumps(leg_data, indent=2)}")
                
                # Log the raw API response structure
                logger.info(f"Raw API response keys for leg {leg.origin}-{leg.destination}: {list(leg_data.keys())}")
                if 'best_flights' in leg_data:
                    logger.info(f"Best flights count: {len(leg_data['best_flights']) if leg_data['best_flights'] else 0}")
                if 'other_flights' in leg_data:
                    logger.info(f"Other flights count: {len(leg_data['other_flights']) if leg_data['other_flights'] else 0}")
                
                leg_groups = leg_data.get("best_flights") or leg_data.get("other_flights") or []
                all_leg_options.append(leg_groups[:3])  # Take top 3 options for each leg
                
                # Log details of each flight group in this leg
                for i, group in enumerate(leg_groups[:3]):
                    logger.info(f"Leg {leg.origin}-{leg.destination} option {i+1}:")
                    logger.info(f"  Price: {group.get('price')}")
                    logger.info(f"  Total duration: {group.get('total_duration')}")
                    logger.info(f"  Flights count: {len(group.get('flights', []))}")
                    logger.info(f"  Segments count: {len(group.get('segments', []))}")
                    logger.info(f"  Layovers count: {len(group.get('layovers', []))}")
            
            # Now combine the options to create complete itineraries
            combined_option = {
                "flights": [],
                "segments": [],
                "layovers": [],
                "price": {
                    "value": 0,
                    "currency": "USD"
                }
            }
            
            # Log the combination process
            logger.info(f"Combining {len(all_leg_options)} legs into multi-city itinerary")
            
            for i, leg_options in enumerate(all_leg_options):
                if not leg_options:
                    logger.warning(f"No options found for leg {i+1}")
                    continue
                    
                leg_group = leg_options[0]  # Take the first option for this leg
                leg_flights = leg_group.get("flights", [])
                leg_segments = leg_group.get("segments", [])
                leg_layovers = leg_group.get("layovers", [])
                
                # Handle price extraction more carefully
                leg_price = 0
                if isinstance(leg_group.get("price"), dict):
                    leg_price = float(leg_group["price"].get("value", 0))
                elif isinstance(leg_group.get("price"), (int, float)):
                    leg_price = float(leg_group["price"])
                
                logger.info(f"Adding leg {i+1}: {len(leg_flights)} flights, {len(leg_segments)} segments, price: {leg_price}")
                
                # Add leg index to segments and layovers
                for seg in leg_segments:
                    seg["leg_index"] = i
                for lay in leg_layovers:
                    lay["leg_index"] = i
                
                combined_option["flights"].extend(leg_flights)
                combined_option["segments"].extend(leg_segments)
                combined_option["layovers"].extend(leg_layovers)
                combined_option["price"]["value"] += leg_price
                
                # Log the segment details
                for seg in leg_segments:
                    logger.debug(f"Segment details - airline: {seg.get('airline')}, "
                                f"departure: {seg.get('departure_airport', {}).get('id')} "
                                f"at {seg.get('departure_airport', {}).get('time')}, "
                                f"arrival: {seg.get('arrival_airport', {}).get('id')} "
                                f"at {seg.get('arrival_airport', {}).get('time')}")
            
            # Log the combined option before building
            logger.info(f"Combined multi-city option details:")
            logger.info(f"  Total price: {combined_option['price']['value']}")
            logger.info(f"  Total flights: {len(combined_option['flights'])}")
            logger.info(f"  Total segments: {len(combined_option['segments'])}")
            logger.info(f"  Total layovers: {len(combined_option['layovers'])}")
            
            # Build the combined flight option
            flight_option = build_multi_city_flight_option(
                group=combined_option,
                flights=combined_option["flights"],
                data=data,
                segments=combined_option["segments"],
                layovers_data=combined_option["layovers"]
            )
            
            if flight_option:
                trip_type_str = "multi-city"
                formatted_summary = format_flight_option(flight_option, 0, trip_type_str)
                flight_option.formatted_summary = formatted_summary
                flight_results.append(flight_option)
                logger.info(f"Combined multi-city flight option:\n{formatted_summary}")
                logger.info(f"Flight option object structure:\n{json.dumps(json.loads(flight_option.json()), indent=2)}")
            else:
                logger.warning("Failed to build multi-city flight option from combined data")
        
        else:
            # Original single-leg or round-trip logic
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

            params = {k: v for k, v in params.items() if v is not None}

            logger.info(f"Calling SERP API with params: {params}")
            response = requests.get("https://serpapi.com/search.json", params=params)
            if response.status_code != 200:
                raise Exception(f"SERP API error: {response.status_code} - {response.text}")

            data_json = response.json()
            logger.info(f"Complete SERP API Response:\n{json.dumps(data_json, indent=2)}")
            
            all_flight_groups = data_json.get("best_flights") or data_json.get("other_flights") or []
            max_results = 3

            for index, group in enumerate(all_flight_groups[:max_results]):
                flights = group.get("flights", [])
                if not flights:
                    continue

                segments = group.get("segments", []) or []
                layovers = group.get("layovers", []) or []

                if trip_type == 1:  # Round-trip
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

        # Store context if needed
        if user_id and thread_id:
            for flight_option in flight_results:
                set_context(user_id, thread_id, f"flight_option_{flight_option.id}", json.loads(flight_option.json()))

        return SearchFlightOutput(flights=flight_results)

    except Exception as e:
        logger.error(f"search_flight error: {e}", exc_info=True)
        raise