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

# After creating the accommodation_results, format the output message
def format_accommodation_message(accommodations):
    message_lines = []
    for idx, acc in enumerate(accommodations, 1):
        message_lines.append(f"<h3>{idx}. {acc['name']}</h3>")
        message_lines.append(f"<p><strong>Type:</strong> {acc['type'].title()}</p>")
        message_lines.append(f"<p><strong>Rate Per Night:</strong> ${acc['price_info']['price']}</p>")
        message_lines.append(f"<p><strong>Total Rate:</strong> ${acc['price_info']['extracted_price'] * 6:.0f} (for 6 nights)</p>")
        message_lines.append(f"<p><strong>Overall Rating:</strong> {acc['rating']} ({acc['reviews']} reviews)</p>")
        message_lines.append(f"<p><strong>Amenities:</strong> {', '.join(acc['amenities'])}</p>")
        
        # Add images and link
        if acc['link'] and acc['images']:
            for img_url in acc['images']:
                message_lines.append(
                    f'<div style="margin: 10px 0;">'
                    f'<a href="{acc["link"]}" target="_blank" rel="noopener noreferrer">'
                    f'<img src="{img_url}" alt="{acc["name"]}" style="max-width: 200px; height: auto; border: 1px solid #ddd; border-radius: 4px; padding: 5px;"/>'
                    f'</a><br/>'
                    f'<a href="{acc["link"]}" target="_blank" rel="noopener noreferrer" style="color: #0066cc; text-decoration: underline;">View More Details</a>'
                    f'</div>'
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
        "hl": "en",
        "currency": "USD",
        "api_key": SERP_API_KEY
    }
    
    # Add optional parameters if they exist
    if hasattr(data, 'max_price') and data.max_price:
        params['price_max'] = data.max_price
   
    
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
    
    # Extract accommodation options from the API response
    accommodation_results = []
    
    # Check if 'properties' exists in the response and take first 3
   # In your search_accommodation function, modify how you create accommodation results:

    if 'properties' in api_data:
        for prop in api_data['properties'][:3]:
            link = prop.get('link', '')
            image_urls = [img['thumbnail'] for img in prop.get('images', [])[:3] if 'thumbnail' in img]
            
            # Create formatted HTML
            formatted_link = f'<a href="{link}" target="_blank">View More Details</a>' if link else ''
            formatted_images = [
                f'<img src="{url}" alt="{prop.get("name", "Hotel image")}" style="max-width: 200px; margin: 5px;"/>'
                for url in image_urls
            ]
            
            accommodation_results.append({
                'id': str(uuid.uuid4()),
                'name': prop.get('name', 'Unknown'),
                'type': prop.get('type', 'hotel'),
                'price_info': {
                    'price': prop.get('rate_per_night', {}).get('lowest', 'Price not available'),
                    'extracted_price': prop.get('rate_per_night', {}).get('extracted_lowest', 0),
                    'currency': 'USD'
                },
                'rating': prop.get('overall_rating', 0),
                'reviews': prop.get('reviews', 0),
                'location': prop.get('gps_coordinates', {}),
                'amenities': prop.get('amenities', []),
                'images': image_urls,  # Original URLs
                'link': link,  # Original URL
                'property_token': prop.get('property_token', ''),
                'formatted_images': formatted_images,
                'formatted_link': formatted_link
            })

    # Similarly modify the ads section
    if len(accommodation_results) < 3 and 'ads' in api_data:
        remaining_slots = 3 - len(accommodation_results)
        for ad in api_data['ads'][:remaining_slots]:
            link = ad.get('link', '')
            image_urls = [ad['thumbnail']] if ad.get('thumbnail') else []
            
            formatted_link = f'<a href="{link}" target="_blank">View More Details</a>' if link else ''
            formatted_images = [
                f'<img src="{url}" alt="{ad.get("name", "Hotel image")}" style="max-width: 200px; margin: 5px;"/>'
                for url in image_urls
            ]
            
            accommodation_results.append({
                'id': str(uuid.uuid4()),
                'name': ad.get('name', 'Unknown'),
                'type': 'hotel',
                'price_info': {
                    'price': ad.get('price', 'Price not available'),
                    'extracted_price': ad.get('extracted_price', 0),
                    'currency': 'USD'
                },
                'rating': ad.get('overall_rating', 0),
                'reviews': ad.get('reviews', 0),
                'location': ad.get('gps_coordinates', {}),
                'amenities': ad.get('amenities', []),
                'images': image_urls,
                'link': link,
                'property_token': ad.get('property_token', ''),
                'formatted_images': formatted_images,
                'formatted_link': formatted_link
            })
            
    # Store context if needed
    if user_id and thread_id:
        for accommodation_option in accommodation_results:
            set_context(user_id, thread_id, f"accommodation_option_{accommodation_option['id']}", accommodation_option)

    output_message = format_accommodation_message(accommodation_results)
    return SearchAccommodationOutput(
        accommodation=accommodation_results,
        formatted_message=output_message  # Add this to your model
    )