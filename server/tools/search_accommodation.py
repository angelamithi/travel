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
from models.accommodation_models import SearchAccommodationInput, SearchAccommodationOutput

load_dotenv()

logger = logging.getLogger("chat_logger")
SERP_API_KEY = os.getenv("SERP_API_KEY")


def calculate_nights(check_in_date, check_out_date):
    """Calculate the number of nights between check-in and check-out dates."""
    if isinstance(check_in_date, str):
        check_in_date = datetime.strptime(check_in_date, "%Y-%m-%d").date()
    elif isinstance(check_in_date, datetime):
        check_in_date = check_in_date.date()
    
    if isinstance(check_out_date, str):
        check_out_date = datetime.strptime(check_out_date, "%Y-%m-%d").date()
    elif isinstance(check_out_date, datetime):
        check_out_date = check_out_date.date()
    
    return (check_out_date - check_in_date).days

def format_accommodation_message(accommodations, check_in_date, check_out_date, adults=1, children=0):
    message_lines = []
    nights = calculate_nights(check_in_date, check_out_date)
    
    for idx, acc in enumerate(accommodations, 1):
        message_lines.append(f"<h3>{idx}. {acc['name']}</h3>")
        message_lines.append(f"<p><strong>Type:</strong> {acc['type'].title()}</p>")
        
        # Calculate prices based on adults and children
        base_price = acc['price_info'].get('extracted_price', 0)
        
        if 'price_breakdown' in acc:
            # Use price breakdown if available
            price_breakdown = acc['price_breakdown']
            total_adults = price_breakdown['adults']['total'] * nights
            total_children = price_breakdown['children']['total'] * nights if price_breakdown['children'] else 0
            total_price = total_adults + total_children
        else:
            # Calculate manually if no breakdown
            total_adults = base_price * adults * nights
            total_children = base_price * 0.75 * children * nights if children else 0
            total_price = total_adults + total_children
        
        message_lines.append(f"<p><strong>Base Rate Per Night:</strong> ${base_price:.2f}</p>")
        message_lines.append(f"<p><strong>Total Rate:</strong> ${total_price:.2f} (for {nights} nights, {adults} adults, {children} children)</p>")
        
        if 'price_breakdown' in acc:
            message_lines.append("<p><strong>Price Breakdown:</strong></p>")
            message_lines.append("<ul>")
            message_lines.append(f"<li>Adults: {price_breakdown['adults']['count']} x ${price_breakdown['base_rate_per_person']:.2f} = ${price_breakdown['adults']['total']:.2f} per night</li>")
            if price_breakdown['children']:
                message_lines.append(f"<li>Children: {price_breakdown['children']['count']} x ${price_breakdown['base_rate_per_person'] * 0.75:.2f} = ${price_breakdown['children']['total']:.2f} per night</li>")
            message_lines.append("</ul>")
        
        message_lines.append(f"<p><strong>Overall Rating:</strong> {acc['rating']} ({acc['reviews']} reviews)</p>")
        message_lines.append(f"<p><strong>Amenities:</strong> {', '.join(acc['amenities'])}</p>")
        
        # Add images section
        if acc['images']:
            message_lines.append('<div style="margin: 10px 0;">')
            for img_url in acc['images']:
                message_lines.append(
                    f'<img src="{img_url}" alt="{acc["name"]}" style="max-width: 200px; height: auto; border: 1px solid #ddd; border-radius: 4px; padding: 5px; margin-right: 10px;"/>'
                )
            message_lines.append('</div>')
        
        # Add separate "View More Details" link
        if acc['link']:
            message_lines.append(
                f'<a href="{acc["link"]}" target="_blank" rel="noopener noreferrer" style="display: inline-block; margin: 10px 0; color: #0066cc; text-decoration: underline;">View More Details</a>'
            )
        
        message_lines.append("<hr style='margin: 20px 0;'/>")
    
    return "".join(message_lines)
    
@function_tool
def search_accommodation(data: SearchAccommodationInput, user_id: Optional[str] = None, thread_id: Optional[str] = None) -> Optional[SearchAccommodationOutput]:
    params = {
        "engine": "google_hotels",
        "q": data.location,
        "check_in_date": data.check_in_date.strftime("%Y-%m-%d") if isinstance(data.check_in_date, datetime) else data.check_in_date,
        "check_out_date": data.check_out_date.strftime("%Y-%m-%d") if isinstance(data.check_out_date, datetime) else data.check_out_date,
        "adults": data.adults,
        "children":data.children,
        "children_ages":data.children_ages,
        "hl": "en",
        "currency": "USD",
        "api_key": SERP_API_KEY
    }
    
    # Add optional parameters if they exist
    if hasattr(data, 'max_price') and data.max_price:
        params['price_max'] = data.max_price
    if hasattr(data, 'children') and data.children:
        params['children'] = data.children
    
    logger.info(f"Fetching accommodation in {data.location} with params: {params}")
    
    try:
        response = requests.get("https://serpapi.com/search.json", params=params)
        response.raise_for_status()
        api_data = response.json()
        logger.info(f"API Response for {data.location}:\n{json.dumps(api_data, indent=2)}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise Exception(f"Failed to fetch accommodations: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse API response: {e}")
        raise Exception("Invalid response from accommodation service")
    
    accommodation_results = []
    adults = data.adults
    children = getattr(data, 'children', 0)
    
    if 'properties' in api_data:
        for prop in api_data['properties'][:3]:
            link = prop.get('link', '')
            image_urls = [img['thumbnail'] for img in prop.get('images', [])[:3] if 'thumbnail' in img]
            
            base_price = prop.get('rate_per_night', {}).get('extracted_lowest', 0)
            
            # Create price breakdown if possible
            price_breakdown = None
            if base_price > 0:
                total_adults = base_price * adults
                total_children = base_price * 0.75 * children if children else 0
                total_price = total_adults + total_children
                
                price_breakdown = {
                    'base_rate_per_person': base_price,
                    'adults': {
                        'count': adults,
                        'total': total_adults
                    },
                    'children': {
                        'count': children,
                        'total': total_children
                    } if children else None,
                    'total_price': total_price
                }
            
            accommodation_results.append({
                'id': str(uuid.uuid4()),
                'name': prop.get('name', 'Unknown'),
                'type': prop.get('type', 'hotel'),
                'price_info': {
                    'price': prop.get('rate_per_night', {}).get('lowest', 'Price not available'),
                    'extracted_price': base_price,
                    'currency': 'USD'
                },
                'rating': prop.get('overall_rating', 0),
                'reviews': prop.get('reviews', 0),
                'location': prop.get('gps_coordinates', {}),
                'amenities': prop.get('amenities', []),
                'images': image_urls,
                'link': link,
                'property_token': prop.get('property_token', ''),
                'price_breakdown': price_breakdown
            })

    if len(accommodation_results) < 3 and 'ads' in api_data:
        remaining_slots = 3 - len(accommodation_results)
        for ad in api_data['ads'][:remaining_slots]:
            link = ad.get('link', '')
            image_urls = [ad['thumbnail']] if ad.get('thumbnail') else []
            
            base_price = ad.get('extracted_price', 0)
            
            # Create price breakdown if possible
            price_breakdown = None
            if base_price > 0:
                total_adults = base_price * adults
                total_children = base_price * 0.75 * children if children else 0
                total_price = total_adults + total_children
                
                price_breakdown = {
                    'base_rate_per_person': base_price,
                    'adults': {
                        'count': adults,
                        'total': total_adults
                    },
                    'children': {
                        'count': children,
                        'total': total_children
                    } if children else None,
                    'total_price': total_price
                }
            
            accommodation_results.append({
                'id': str(uuid.uuid4()),
                'name': ad.get('name', 'Unknown'),
                'type': 'hotel',
                'price_info': {
                    'price': ad.get('price', 'Price not available'),
                    'extracted_price': base_price,
                    'currency': 'USD'
                },
                'rating': ad.get('overall_rating', 0),
                'reviews': ad.get('reviews', 0),
                'location': ad.get('gps_coordinates', {}),
                'amenities': ad.get('amenities', []),
                'images': image_urls,
                'link': link,
                'property_token': ad.get('property_token', ''),
                'price_breakdown': price_breakdown
            })
            
    if user_id and thread_id:
        # Store all options together
        set_context(user_id, thread_id, "accommodation_options", accommodation_results)
        # Also store individual options
        for accommodation_option in accommodation_results:
            set_context(user_id, thread_id, f"accommodation_option_{accommodation_option['id']}", accommodation_option)

    output_message = format_accommodation_message(
        accommodation_results, 
        data.check_in_date,
        data.check_out_date,
        adults, 
        children
    )
    return SearchAccommodationOutput(
        accommodation=accommodation_results,
        formatted_message=output_message
    )