from db.session import SessionLocal
from models.db_models import AccommodationBooking
from agents import function_tool, RunContextWrapper
from models.context_models import UserInfo
import uuid
import logging
from models.accommodation_models import BookAccommodationInput, BookAccommodationOutput
from in_memory_context import set_context, get_context
from datetime import datetime
import json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@function_tool
async def book_accommodation(wrapper: RunContextWrapper[UserInfo], input: BookAccommodationInput) -> BookAccommodationOutput:
    user_id = wrapper.context.user_id
    thread_id = wrapper.context.thread_id

    session = SessionLocal()

    existing_ref = get_context(user_id, thread_id, "last_booking_reference")
    if existing_ref:
        logger.warning(f"Duplicate booking attempt. Returning existing reference: {existing_ref}")
        return BookAccommodationOutput(
            booking_reference=existing_ref,
            message=f"✅ Your accommodation has already been booked.\n✈️ Booking Reference: {existing_ref}\nPlease check your email for confirmation."
        )

    # Get accommodation details
    accommodation = None
    if input.selected_accommodation_details:
        accommodation = input.selected_accommodation_details
    else:
        accommodation_data = get_context(user_id, thread_id, f"accommodation_option_{input.selected_accommodation_id}")
        if accommodation_data:
            try:
                if isinstance(accommodation_data, str):
                    accommodation_data = json.loads(accommodation_data)
                # Ensure it's a list
                if isinstance(accommodation_data, dict):
                    accommodation = [accommodation_data]
                else:
                    accommodation = accommodation_data
            except Exception as e:
                logger.error(f"Failed to parse accommodation data: {e}")
                raise ValueError("Invalid accommodation data format")
        else:
            raise ValueError("No accommodation data available to book. Cannot proceed.")

    if not accommodation or len(accommodation) == 0:
        raise ValueError("No valid accommodation data found")

    try:
        logger.info(f"Booking accommodation for user {user_id}. Accommodation details: {json.dumps(accommodation, default=str, indent=2)}")
    except Exception as log_err:
        logger.warning(f"Failed to serialize accommodation details for logging: {log_err}")

    # Calculate total price from price breakdown if available
    total_price = 0
    price_breakdown = None
    acc_data = accommodation[0]
    
    if isinstance(acc_data, dict):
        if 'price_breakdown' in acc_data and acc_data['price_breakdown']:
            price_breakdown = acc_data['price_breakdown']
            total_price = price_breakdown.get('total_price', 0)
        else:
            # Fallback calculation if no price breakdown
            total_price = acc_data.get('price_info', {}).get('extracted_price', 0)
    else:
        if hasattr(acc_data, 'price_breakdown') and acc_data.price_breakdown:
            price_breakdown = acc_data.price_breakdown.dict() if hasattr(acc_data.price_breakdown, 'dict') else acc_data.price_breakdown
            total_price = price_breakdown.get('total_price', 0)
        else:
            total_price = acc_data.price_info.extracted_price

    booking_reference = str(uuid.uuid4())[:8].upper()

    try:
        # Prepare common booking data
        booking_data = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'thread_id': thread_id,
            'booking_reference': booking_reference,
            'full_name': input.full_name,
            'guest_names': input.guest_names,
            'email': input.email,
            'phone': input.phone,
            'payment_method': "Not Provided",
            'total_price': total_price,
            'currency': acc_data.get('price_info', {}).get('currency', 'USD') if isinstance(acc_data, dict) else acc_data.price_info.currency,
            'property_token': acc_data.get('property_token', '') if isinstance(acc_data, dict) else acc_data.property_token,
            'price_breakdown': price_breakdown,
            'hotel_class': acc_data.get('hotel_class') if isinstance(acc_data, dict) else acc_data.hotel_class,
        
            # Accommodation details
            'accommodation_name': acc_data.get('name', '') if isinstance(acc_data, dict) else acc_data.name,
            'accommodation_type': acc_data.get('type', '') if isinstance(acc_data, dict) else acc_data.type,
            'accommodation_rating': acc_data.get('rating', 0) if isinstance(acc_data, dict) else acc_data.rating,
            'accommodation_reviews': acc_data.get('reviews', 0) if isinstance(acc_data, dict) else acc_data.reviews,
            'accommodation_amenities': acc_data.get('amenities', []) if isinstance(acc_data, dict) else acc_data.amenities,
            'accommodation_images': acc_data.get('images', []) if isinstance(acc_data, dict) else (acc_data.images if hasattr(acc_data, 'images') else []),
            'accommodation_formatted_images': acc_data.get('formatted_images', []) if isinstance(acc_data, dict) else (acc_data.formatted_images if hasattr(acc_data, 'formatted_images') else []),
            'accommodation_link': acc_data.get('link', '') if isinstance(acc_data, dict) else acc_data.link,
            'accommodation_formatted_link': acc_data.get('formatted_link') if isinstance(acc_data, dict) else (acc_data.formatted_link if hasattr(acc_data, 'formatted_link') else None),
            'accommodation_location': json.dumps(acc_data.get('location', {})) if isinstance(acc_data, dict) else (json.dumps(acc_data.location.dict()) if hasattr(acc_data, 'location') and acc_data.location else None)
        }

        booking = AccommodationBooking(**booking_data)
        session.add(booking)
        session.commit()

        set_context(user_id, thread_id, "last_booking_reference", booking_reference)
        set_context(user_id, thread_id, "last_passenger_name", input.full_name)
        set_context(user_id, thread_id, "last_email", input.email)
        set_context(user_id, thread_id, "last_phone", input.phone)
        set_context(user_id, thread_id, "last_accommodation_id", input.selected_accommodation_id)

        message = (
            f"✅ Your Accommodation has been booked successfully!\n"
            f"✈️ Booking Reference: {booking_reference}\n"
            f"🏨 Accommodation: {booking_data['accommodation_name']}\n"
            f"💰 Total Price: {total_price} {booking_data['currency']}\n"
            f"A confirmation has been sent to {input.email}. "
            "Thank you for choosing our service!"
        )

        logger.info(f"Accommodation booked successfully with reference: {booking_reference}")
        return BookAccommodationOutput(
            booking_reference=booking_reference,
            message=message
        )

    except Exception as e:
        session.rollback()
        logger.error(f"Error during accommodation booking: {e}")
        raise
    finally:
        session.close()