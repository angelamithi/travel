import os
import requests
import logging
import uuid
from typing import Optional
from models.flight_models import SearchFlightInput, SearchFlightOutput, FlightOption, FlightLeg,  FlightSegment, LayoverInfo
from in_memory_context import set_context
from agents import function_tool
from datetime import datetime
from dotenv import load_dotenv
import json

load_dotenv()

logger = logging.getLogger("chat_logger")
SERP_API_KEY = os.getenv("SERP_API_KEY")


def format_duration(minutes_str: str) -> str:
    try:
        minutes = int(minutes_str.strip().replace("min", "").strip())
        hours = minutes // 60
        mins = minutes % 60
        if hours and mins:
            return f"{hours}h {mins}m"
        elif hours:
            return f"{hours}h"
        else:
            return f"{mins}m"
    except:
        return minutes_str  # fallback to original if parsing fails


def parse_segments_and_layovers(flights):
    segments = []
    layovers = []

    for i, flight in enumerate(flights):
        segments.append(FlightSegment(
            segment_number=i + 1,
            departure_airport=flight.get("departure_airport", {}).get("id"),
            departure_datetime=flight.get("departure_airport", {}).get("time"),
            arrival_airport=flight.get("arrival_airport", {}).get("id"),
            arrival_datetime=flight.get("arrival_airport", {}).get("time"),
            duration=format_duration(str(flight.get('duration'))),
            cabin_class=flight.get("travel_class", "Economy"),
            extension_info=flight.get("extensions", [])
        ))

        if i > 0:
            prev_arrival_time = datetime.strptime(flights[i - 1]["arrival_airport"]["time"], "%Y-%m-%d %H:%M")
            next_departure_time = datetime.strptime(flight["departure_airport"]["time"], "%Y-%m-%d %H:%M")
            layover_duration = int((next_departure_time - prev_arrival_time).total_seconds() / 60)
            layovers.append(LayoverInfo(
                layover_airport=flight["departure_airport"]["id"],
                layover_duration=f"{layover_duration} min"
            ))

    return segments, layovers



def format_flight_option(option: FlightOption, index: int, trip_type: str) -> str:
    def format_layover(layover):
        return f"  • **Layover:** {format_duration(layover.layover_duration)} at {layover.layover_airport}"

    def get_segment_info(segments):
        if not segments:
            return {}, {}, "", ""
        first_seg = segments[0]
        last_seg = segments[-1]
        route = " → ".join([seg.departure_airport for seg in segments] + [segments[-1].arrival_airport])
        dep_time = datetime.strptime(first_seg.departure_datetime, "%Y-%m-%d %H:%M").strftime("%b %d, %Y %I:%M %p")
        arr_time = datetime.strptime(last_seg.arrival_datetime, "%Y-%m-%d %H:%M").strftime("%b %d, %Y %I:%M %p")
        dep = f"{first_seg.departure_airport} at {dep_time}"
        arr = f"{last_seg.arrival_airport} at {arr_time}"
        return first_seg, last_seg, route, (dep, arr)


    price = option.price_breakdown
    price_str = (
        f"\n💵 **Total Price:** ${price['total_price']:.2f}\n"
        f" **Adults:** ${price['adults']['total']:.2f}, "
        f"**Children:** ${price['children']['total']:.2f}, "
        f"**Infants:** ${price['infants']['total']:.2f}"
    )

    summary_lines = []

    if trip_type == "one-way":
        first_seg, last_seg, route, (dep_str, arr_str) = get_segment_info(option.segments)
        layover_str = format_layover(option.layovers[0]) if option.layovers else ""
        summary_lines = [
            f"✈️ **Option {index + 1}: {option.airline}** — Flight {option.outbound.flight_number if option.outbound else 'N/A'}\n",
            f"  • **Route:** {route}",
            f"  • **Departs:** {dep_str}",
            f"  • **Arrives:** {arr_str}",
            f"  • **Duration:** {option.total_duration}",
            f"  • **Cabin Class:** {first_seg.cabin_class}",
        ]
        if layover_str:
            summary_lines.append(layover_str)
        summary_lines.append(price_str)

    elif trip_type == "round-trip":
        outbound = option.outbound_segments
        return_seg = option.return_segments
        first_seg_out, last_seg_out, route_out, (dep_out, arr_out) = get_segment_info(outbound)
        first_seg_ret, last_seg_ret, route_ret, (dep_ret, arr_ret) = get_segment_info(return_seg)

        summary_lines = [
            f"✈️ **Option {index + 1}: {option.airline}** — Round-Trip\n🆔 ID: `{option.id}`",
            f"\n**Outbound Flight**",
            f"  • **Flight Number:** {first_seg_out.flight_number}",
            f"  • **Route:** {route_out}",
            f"  • **Departs:** {dep_out}",
            f"  • **Arrives:** {arr_out}",
            f"  • **Duration:** {format_duration(option.outbound_duration)}",
            f"  • **Cabin Class:** {first_seg_out.cabin_class}",
        ]
        if option.outbound_layovers:
            summary_lines.append(format_layover(option.outbound_layovers[0]))

        summary_lines += [
            f"\n**Return Flight**",
            f"  • **Flight Number:** {first_seg_ret.flight_number}",
            f"  • **Route:** {route_ret}",
            f"  • **Departs:** {dep_ret}",
            f"  • **Arrives:** {arr_ret}",
            f"  • **Duration:** {format_duration(option.return_duration)}",
            f"  • **Cabin Class:** {first_seg_ret.cabin_class}",
        ]
        if option.return_layovers:
            summary_lines.append(format_layover(option.return_layovers[0]))

        summary_lines.append(f"\n🕒 **Total Trip Duration:** {option.total_duration}")
        summary_lines.append(price_str)

    elif trip_type == "multi-city":
        f"✈️ **Option {index + 1}: {option.airline}** — Multi-City Itinerary\n🆔 ID: `{option.id}`"

        for i, segment in enumerate(option.multi_city_segments or [], start=1):
            first_seg, last_seg, route, (dep_str, arr_str) = get_segment_info([segment])
            layover_str = format_layover(segment.layover) if hasattr(segment, 'layover') and segment.layover else ""
            summary_lines += [
                f"\n**Leg {i}:** {route}",
                f"  • **Flight Number:** {first_seg.flight_number}",
                f"  • **Departs:** {dep_str}",
                f"  • **Arrives:** {arr_str}",
                f"  • **Duration:** {format_duration(segment.duration)}",
                f"  • **Cabin Class:** {segment.cabin_class}",
            ]
            if layover_str:
                summary_lines.append(layover_str)

        summary_lines.append(f"\n🕒 **Total Trip Duration:** {option.total_duration}")
        summary_lines.append(price_str)

    return "\n".join(summary_lines)



@function_tool
def search_flight(data: SearchFlightInput, user_id: Optional[str] = None, thread_id: Optional[str] = None) -> Optional[SearchFlightOutput]:
    try:
        is_multi_city = data.multi_city_legs is not None and len(data.multi_city_legs) > 0

        if is_multi_city:
            logger.info("Searching multi-city flight...")
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
                "multi_city_json": json.dumps(multi_city_payload),
                "hl": "en",
                "currency": "USD",
                "adults": 1,
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
                "adults": 1,
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

        for index, group in enumerate(all_flight_groups[:max_results]):
            flights = group.get("flights", [])
            if not flights:
                continue
            segments, layovers = parse_segments_and_layovers(flights)
            total_duration = f"{group.get('total_duration')} min"

            if is_multi_city:
                legs = [
                    FlightLeg(
                        departure_time=leg.get("departure_airport", {}).get("time", "Unknown"),
                        arrival_time=leg.get("arrival_airport", {}).get("time", "Unknown"),
                        origin=leg.get("departure_airport", {}).get("id"),
                        destination=leg.get("arrival_airport", {}).get("id"),
                        duration=leg.get("duration"),
                        stops=0,
                        extensions=leg.get("extensions", []),
                        flight_number=leg.get("flight_number", "Unknown")
                    ) for leg in flights
                ]

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
                    airline=flights[0].get("airline", "Unknown"),
                    currency="USD",
                    legs=legs,
                    booking_link=group.get("booking_link"),
                    id=str(uuid.uuid4()),
                    price=total_price,
                    segments=segments,
                    layovers=layovers
                )
                flight_option.price_breakdown = price_breakdown

            else:
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
                    flight_number=first_flight.get("flight_number", "Unknown")
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
                            "adults": 1,
                            "api_key": SERP_API_KEY
                        }

                        return_response = requests.get("https://serpapi.com/search.json", params=return_params)
                        if return_response.status_code == 200:
                            return_data = return_response.json()
                            return_flights = (
                                return_data.get("best_flights", []) or
                                return_data.get("other_flights", []) or
                                return_data.get("return_flights", [])
                            )

                            if return_flights:
                                return_group = return_flights[0]
                                return_legs = return_group.get("flights", [])
                                if return_legs:
                                    return_leg = FlightLeg(
                                        departure_time=return_legs[0].get("departure_airport", {}).get("time"),
                                        arrival_time=return_legs[-1].get("arrival_airport", {}).get("time"),
                                        origin=data.destination,
                                        destination=data.origin,
                                        duration=str(return_group.get("total_duration", "Unknown")),
                                        stops=len(return_legs) - 1,
                                        extensions=return_group.get("extensions", []),
                                        flight_number=return_legs[0].get("flight_number", "Unknown")
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
                    segments=segments,
                    layovers=layovers
                )
                flight_option.price_breakdown = price_breakdown

            trip_type_str = "multi-city" if is_multi_city else "round-trip" if data.return_date else "one-way"
            formatted_summary = format_flight_option(flight_option, index, trip_type_str)
            flight_option.formatted_summary = formatted_summary  # Add summary

            logger.info(f"Formatted Flight Option {index+1}:\n{formatted_summary}")
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
