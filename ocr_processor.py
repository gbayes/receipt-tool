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
    """Extract all currency amounts from text"""
    logger.info("Extracting amounts from text")
    logger.debug(f"Input text: {text}")
    
    # Pattern for currency amounts (handles different formats)
    # Examples: $123.45, $1,234.56, 123.45, 1,234.56
    amount_pattern = r'\$?\s*\d{1,3}(?:,\d{3})*\.\d{2}'
    
    # Find all matches
    amounts = re.findall(amount_pattern, text)
    logger.debug(f"Found amounts: {amounts}")
    
    # Convert to float values
    float_amounts = []
    for amount in amounts:
        # Remove $ and commas, then convert to float
        clean_amount = amount.replace('$', '').replace(',', '')
        try:
            float_amounts.append(float(clean_amount))
            logger.debug(f"Converted amount {amount} to {float(clean_amount}")
        except ValueError:
            logger.warning(f"Could not convert amount: {amount}")
            continue
    
    logger.info(f"Extracted {len(float_amounts)} valid amounts")
    return float_amounts

def find_total_amount(text):
    """Find the total amount on the receipt"""
    logger.info("Finding total amount in text")
    
    # Common patterns for total labels
    total_patterns = [
        r'total\s*(?:amount|sum|due)?[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})',
        r'(?:sub)?total\s*(?:amount|sum|due)?[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})',
        r'amount\s*(?:total|due)[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})',
        r'grand\s*total[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})',
        r'balance\s*due[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})'
    ]
    
    text = text.lower()
    logger.debug(f"Normalized text: {text}")
    
    # Try to find amounts with total-related labels
    for pattern in total_patterns:
        logger.debug(f"Trying pattern: {pattern}")
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            logger.debug(f"Found matches: {matches}")
            # Clean and convert the first match
            amount = matches[-1].replace('$', '').replace(',', '')
            try:
                result = float(amount)
                logger.info(f"Found total amount with pattern: ${result:.2f}")
                return result
            except ValueError:
                logger.warning(f"Could not convert matched amount: {amount}")
                continue
    
    logger.info("No labeled total found, looking for largest amount")
    # If no labeled total found, get all amounts and return the largest
    amounts = extract_amounts(text)
    if amounts:
        max_amount = max(amounts)
        logger.info(f"Using largest amount as total: ${max_amount:.2f}")
        return max_amount
    
    logger.warning("No amounts found in text")
    return None

def process_receipt(image):
    """Process receipt image and extract total amount"""
    logger.info("Starting receipt processing")
    try:
        # Preprocess the image
        processed_image = preprocess_image(image)
        
        # Perform OCR
        logger.info("Performing OCR")
        text = pytesseract.image_to_string(processed_image)
        logger.debug(f"Extracted text: {text}")
        
        # Find total amount
        total = find_total_amount(text)
        
        if total is not None:
            logger.info(f"Successfully found total amount: ${total:.2f}")
            return {
                'success': True,
                'total': total,
                'text': text
            }
        else:
            logger.warning("Could not find total amount")
            return {
                'success': False,
                'error': 'Could not find total amount',
                'text': text
            }
    
    except Exception as e:
        logger.error(f"Error processing receipt: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        } 