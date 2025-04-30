import re
import logging
import easyocr
import numpy as np
import cv2
from PIL import Image

logger = logging.getLogger(__name__)
# Initialize EasyOCR reader (this will be done once and cached)
reader = easyocr.Reader(['en'])

def preprocess_image(image):
    """Preprocess image for better OCR results"""
    logger.info("Starting image preprocessing")
    try:
        # Convert PIL Image to OpenCV format
        if isinstance(image, Image.Image):
            image = np.array(image)
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 21, 11
        )
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh)
        
        # Deskew if needed
        angle = get_skew_angle(denoised)
        if abs(angle) > 0.5:
            logger.info(f"Deskewing image by {angle:.2f} degrees")
            denoised = rotate_image(denoised, angle)
        
        logger.info("Image preprocessing completed")
        return denoised
    except Exception as e:
        logger.error(f"Error in image preprocessing: {str(e)}")
        raise

def get_skew_angle(image):
    """Detect the skew angle of the image"""
    try:
        # Find all non-zero points in the image
        coords = np.column_stack(np.where(image > 0))
        angle = cv2.minAreaRect(coords)[-1]
        
        # The angle is between -90 and 0
        if angle < -45:
            angle = 90 + angle
            
        return angle
    except Exception as e:
        logger.warning(f"Could not determine skew angle: {str(e)}")
        return 0

def rotate_image(image, angle):
    """Rotate the image by the given angle"""
    try:
        # Get image dimensions
        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        
        # Create rotation matrix
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Perform rotation
        rotated = cv2.warpAffine(
            image, rotation_matrix, (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        return rotated
    except Exception as e:
        logger.error(f"Error rotating image: {str(e)}")
        return image

def extract_amounts(text_results):
    """Extract all dollar amounts from OCR results"""
    logger.info("Extracting dollar amounts from text")
    
    # Pattern for dollar amounts (must have $ sign)
    # Handles various formats: $123.45, $1,234.56, $ 123.45
    amount_pattern = r'\$\s*\d{1,3}(?:,\d{3})*\.\d{2}'
    
    float_amounts = []
    
    # EasyOCR returns list of (bbox, text, conf) tuples
    for detection in text_results:
        text = detection[1]  # Get the text part
        logger.debug(f"Processing text: {text}")
        
        # Find all matches in this text segment
        amounts = re.findall(amount_pattern, text)
        
        for amount in amounts:
            # Remove $ and commas, then convert to float
            clean_amount = amount.replace('$', '').replace(',', '').strip()
            try:
                float_amount = float(clean_amount)
                float_amounts.append(float_amount)
                logger.debug(f"Found amount: ${float_amount:.2f}")
            except ValueError:
                logger.warning(f"Could not convert amount: {amount}")
                continue
    
    logger.info(f"Extracted {len(float_amounts)} valid dollar amounts")
    return float_amounts

def find_total_amount(text_results):
    """Find the largest dollar amount in the OCR results"""
    logger.info("Finding largest dollar amount")
    
    amounts = extract_amounts(text_results)
    
    if amounts:
        max_amount = max(amounts)
        logger.info(f"Largest dollar amount found: ${max_amount:.2f}")
        return max_amount
    
    logger.warning("No dollar amounts found in text")
    return None

def process_receipt(image):
    """Process receipt image and extract largest dollar amount using EasyOCR"""
    logger.info("Starting receipt processing")
    try:
        # Preprocess the image
        processed_image = preprocess_image(image)
        
        # Perform OCR with EasyOCR
        logger.info("Performing OCR with EasyOCR")
        text_results = reader.readtext(processed_image)
        logger.debug(f"Raw OCR results: {text_results}")
        
        # Find largest dollar amount
        total = find_total_amount(text_results)
        
        if total is not None:
            logger.info(f"Successfully found largest amount: ${total:.2f}")
            return {
                'success': True,
                'total': float(total),
                'text': ' '.join(t[1] for t in text_results)  # Join all detected text
            }
        else:
            logger.warning("No dollar amounts found")
            return {
                'success': False,
                'error': 'No dollar amounts found on receipt',
                'text': ' '.join(t[1] for t in text_results)
            }
    
    except Exception as e:
        logger.error(f"Error processing receipt: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f"Failed to process receipt: {str(e)}"
        } 