import re
import logging
import pytesseract
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

def preprocess_image(image):
    """Preprocess image for better OCR results"""
    logger.info("Starting image preprocessing")
    try:
        # Convert to grayscale if not already
        if image.mode != 'L':
            logger.debug("Converting image to grayscale")
            image = image.convert('L')
        
        # Increase contrast
        logger.debug("Increasing image contrast")
        image = image.point(lambda x: 0 if x < 128 else 255, '1')
        
        logger.info("Image preprocessing completed")
        return image
    except Exception as e:
        logger.error(f"Error in image preprocessing: {str(e)}")
        raise

def extract_amounts(text):
    """Extract all dollar amounts from text"""
    logger.info("Extracting dollar amounts from text")
    logger.debug(f"Input text: {text}")
    
    # Pattern specifically for dollar amounts (must have $ sign)
    # Examples: $123.45, $1,234.56
    amount_pattern = r'\$\s*\d{1,3}(?:,\d{3})*\.\d{2}'
    
    # Find all matches
    amounts = re.findall(amount_pattern, text)
    logger.debug(f"Found dollar amounts: {amounts}")
    
    # Convert to float values
    float_amounts = []
    for amount in amounts:
        # Remove $ and commas, then convert to float
        clean_amount = amount.replace('$', '').replace(',', '')
        try:
            float_amount = float(clean_amount)
            float_amounts.append(float_amount)
            logger.debug(f"Converted amount {amount} to {float_amount}")
        except ValueError:
            logger.warning(f"Could not convert amount: {amount}")
            continue
    
    logger.info(f"Extracted {len(float_amounts)} valid dollar amounts")
    return float_amounts

def find_total_amount(text):
    """Find the largest dollar amount on the receipt"""
    logger.info("Finding largest dollar amount")
    
    # Get all dollar amounts
    amounts = extract_amounts(text)
    
    if amounts:
        max_amount = max(amounts)
        logger.info(f"Largest dollar amount found: ${max_amount:.2f}")
        return max_amount
    
    logger.warning("No dollar amounts found in text")
    return None

def process_receipt(image):
    """Process receipt image and extract largest dollar amount"""
    logger.info("Starting receipt processing")
    try:
        # Preprocess the image
        processed_image = preprocess_image(image)
        
        # Perform OCR
        logger.info("Performing OCR")
        text = pytesseract.image_to_string(processed_image)
        logger.debug(f"Extracted text: {text}")
        
        # Find largest dollar amount
        total = find_total_amount(text)
        
        if total is not None:
            logger.info(f"Successfully found largest amount: ${total:.2f}")
            return {
                'success': True,
                'total': float(total),
                'text': text
            }
        else:
            logger.warning("No dollar amounts found")
            return {
                'success': False,
                'error': 'No dollar amounts found on receipt',
                'text': text
            }
    
    except Exception as e:
        logger.error(f"Error processing receipt: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f"Failed to process receipt: {str(e)}"
        } 