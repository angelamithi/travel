from db.session import SessionLocal
from models.db_models import AccommodationBooking
from agents import function_tool, RunContextWrapper
from models.context_models import UserInfo
from in_memory_context import get_context
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

@function_tool
async def get_last_accommodation_booking(wrapper: RunContextWrapper[UserInfo]) -> dict:
    """
    Retrieves the last accommodation booking details for the current user from the database.
    Returns the booking information in a formatted message similar to search results.
    """
    user_id = wrapper.context.user_id
    thread_id = wrapper.context.thread_id
    print(f"Retrieving last accommodation booking details for user_id: {user_id}")

    if not user_id:
        return "User ID is required to retrieve booking details."
    # First try to get from context
    
    
    session = SessionLocal()
    try:
        # Get the booking from database
        booking = session.query(AccommodationBooking).filter(
            AccommodationBooking.user_id == user_id,
         
        
        ).order_by(AccommodationBooking.created_at.desc()).first()
        
        if not booking:
            return {"message": "No accommodation booking found with the provided reference."}
        
        # Convert booking to dict if it's an object
        if not isinstance(booking, dict):
            booking = booking.__dict__
        
        # Format the booking details similar to search results
        message_lines = []
        message_lines.append("<h2>Your Last Accommodation Booking</h2>")
        message_lines.append(f"<h3>{booking['accommodation_name']}</h3>")
        message_lines.append(f"<p><strong>Booking Reference:</strong> {booking['booking_reference']}</p>")
        message_lines.append(f"<p><strong>Status:</strong> Confirmed</p>")
        message_lines.append(f"<p><strong>Type:</strong> {booking['accommodation_type'].title() if booking['accommodation_type'] else 'Not specified'}</p>")
        
        # Guest information
        message_lines.append(f"<p><strong>Primary Guest:</strong> {booking['full_name']}</p>")
        if booking['guest_names']:
            if isinstance(booking['guest_names'], str):
                guest_names = json.loads(booking['guest_names'])
            else:
                guest_names = booking['guest_names']
            message_lines.append(f"<p><strong>All Guests:</strong> {', '.join(guest_names)}</p>")
        
        # Price information
        message_lines.append(f"<p><strong>Total Price:</strong> {booking['total_price']} {booking['currency']}</p>")
        if booking['price_breakdown']:
            if isinstance(booking['price_breakdown'], str):
                price_breakdown = json.loads(booking['price_breakdown'])
            else:
                price_breakdown = booking['price_breakdown']
            
            message_lines.append("<p><strong>Price Breakdown:</strong></p>")
            message_lines.append("<ul>")
            message_lines.append(f"<li>Adults: {price_breakdown['adults']['count']} x ${price_breakdown['base_rate_per_person']:.2f} = ${price_breakdown['adults']['total']:.2f} per night</li>")
            if price_breakdown.get('children'):
                message_lines.append(f"<li>Children: {price_breakdown['children']['count']} x ${price_breakdown['base_rate_per_person'] * 0.75:.2f} = ${price_breakdown['children']['total']:.2f} per night</li>")
            message_lines.append("</ul>")
        
        # Accommodation details
        message_lines.append(f"<p><strong>Overall Rating:</strong> {booking.get('accommodation_rating', 'Not rated')} ({booking.get('accommodation_reviews', 0)} reviews)</p>")
        
        if booking.get('accommodation_amenities'):
            amenities = booking['accommodation_amenities']
            if isinstance(amenities, str):
                amenities = json.loads(amenities)
            message_lines.append(f"<p><strong>Amenities:</strong> {', '.join(amenities)}</p>")
        
        # Contact information
        message_lines.append("<h3>Contact Information</h3>")
        message_lines.append(f"<p><strong>Email:</strong> {booking['email']}</p>")
        message_lines.append(f"<p><strong>Phone:</strong> {booking['phone']}</p>")
        
        # Add images if available
        if booking.get('accommodation_images'):
            images = booking['accommodation_images']
            if isinstance(images, str):
                images = json.loads(images)
            
            message_lines.append('<div style="margin: 10px 0;">')
            for img_url in images[:3]:  # Show max 3 images
                message_lines.append(
                    f'<img src="{img_url}" alt="{booking["accommodation_name"]}" style="max-width: 200px; height: auto; border: 1px solid #ddd; border-radius: 4px; padding: 5px; margin-right: 10px;"/>'
                )
            message_lines.append('</div>')
        
        # Add link to property if available
        if booking.get('accommodation_link'):
            message_lines.append(
                f'<a href="{booking["accommodation_link"]}" target="_blank" rel="noopener noreferrer" style="display: inline-block; margin: 10px 0; color: #0066cc; text-decoration: underline;">View Property Details</a>'
            )
        
        formatted_message = "".join(message_lines)
        
        return {
            "booking_reference": booking['booking_reference'],
            "accommodation_name": booking['accommodation_name'],
            "formatted_message": formatted_message,
            "booking_details": booking
        }
        
    except Exception as e:
        logger.error(f"Error retrieving booking details: {e}")
        return {"message": "An error occurred while retrieving your booking details."}
    finally:
        session.close()