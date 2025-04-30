import re
import logging
import pytesseract
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

def preprocess_image(image):
    """Preprocess image for better OCR results"""
    # Convert to grayscale if not already
    if image.mode != 'L':
        image = image.convert('L')
    
    # Increase contrast
    image = image.point(lambda x: 0 if x < 128 else 255, '1')
    
    return image

def extract_amounts(text):
    """Extract all currency amounts from text"""
    # Pattern for currency amounts (handles different formats)
    # Examples: $123.45, $1,234.56, 123.45, 1,234.56
    amount_pattern = r'\$?\s*\d{1,3}(?:,\d{3})*\.\d{2}'
    
    # Find all matches
    amounts = re.findall(amount_pattern, text)
    
    # Convert to float values
    float_amounts = []
    for amount in amounts:
        # Remove $ and commas, then convert to float
        clean_amount = amount.replace('$', '').replace(',', '')
        try:
            float_amounts.append(float(clean_amount))
        except ValueError:
            logger.warning(f"Could not convert amount: {amount}")
            continue
    
    return float_amounts

def find_total_amount(text):
    """Find the total amount on the receipt"""
    # Common patterns for total labels
    total_patterns = [
        r'total\s*(?:amount|sum|due)?[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})',
        r'(?:sub)?total\s*(?:amount|sum|due)?[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})',
        r'amount\s*(?:total|due)[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})',
        r'grand\s*total[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})',
        r'balance\s*due[\s:]*(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2})'
    ]
    
    text = text.lower()
    
    # Try to find amounts with total-related labels
    for pattern in total_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Clean and convert the first match
            amount = matches[-1].replace('$', '').replace(',', '')
            try:
                return float(amount)
            except ValueError:
                continue
    
    # If no labeled total found, get all amounts and return the largest
    amounts = extract_amounts(text)
    if amounts:
        return max(amounts)
    
    return None

def process_receipt(image):
    """Process receipt image and extract total amount"""
    try:
        # Preprocess the image
        processed_image = preprocess_image(image)
        
        # Perform OCR
        text = pytesseract.image_to_string(processed_image)
        logger.debug(f"Extracted text: {text}")
        
        # Find total amount
        total = find_total_amount(text)
        
        if total is not None:
            return {
                'success': True,
                'total': total,
                'text': text
            }
        else:
            return {
                'success': False,
                'error': 'Could not find total amount',
                'text': text
            }
    
    except Exception as e:
        logger.error(f"Error processing receipt: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        } 