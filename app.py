import os
import io
import tempfile
import shutil
import logging
import gc
from flask import Flask, render_template, request, send_file, flash
from werkzeug.utils import secure_filename
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Configure upload folder
UPLOAD_FOLDER = tempfile.mkdtemp()
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'bmp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # Reduce to 8MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(image, max_size_mb=0.3):
    try:
        # Start with quality 80 and adjust based on file size
        quality = 80
        target_size = max_size_mb * 1024 * 1024  # Convert MB to bytes
        
        # Convert image to RGB if it's not
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Create a BytesIO object to check size
        while quality > 15:  # Don't go below quality 15
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=quality, optimize=True)
            if buffer.tell() <= target_size:
                buffer.seek(0)
                return Image.open(buffer)
            quality -= 10
        
        # If we get here, return the last compressed version
        buffer.seek(0)
        return Image.open(buffer)
    except Exception as e:
        logger.error(f"Error in compress_image: {str(e)}")
        raise
    finally:
        # Force garbage collection
        gc.collect()

def process_single_image(img_path, c, page_width, page_height, margin):
    try:
        # Open and process one image
        with Image.open(img_path) as img:
            # Compress the image
            compressed_img = compress_image(img)
            
            # Calculate dimensions
            max_width = page_width - (2 * margin)
            max_height = page_height - (2 * margin)
            img_width, img_height = compressed_img.size
            
            # Calculate scaling factors
            width_ratio = max_width / img_width
            height_ratio = max_height / img_height
            scale_factor = min(width_ratio, height_ratio)
            
            new_width = img_width * scale_factor
            new_height = img_height * scale_factor
            
            # Center the image
            x = (page_width - new_width) / 2
            y = (page_height - new_height) / 2
            
            # Add to PDF
            c.drawImage(ImageReader(compressed_img), x, y, width=new_width, height=new_height)
            c.showPage()
            
            logger.info(f"Processed: {os.path.basename(img_path)}")
            
            # Force cleanup
            compressed_img.close()
            gc.collect()
            
    except Exception as e:
        logger.error(f"Error processing {os.path.basename(img_path)}: {str(e)}")
        raise

def merge_images_to_pdf(image_files):
    try:
        # Create PDF in memory
        output = io.BytesIO()
        
        # Create PDF with compression
        c = canvas.Canvas(output, pagesize=letter)
        c.setPageCompression(1)  # Enable PDF compression
        
        page_width, page_height = letter
        margin = 40
        
        # Process images one at a time
        for img_path in image_files:
            process_single_image(img_path, c, page_width, page_height, margin)
            gc.collect()  # Force garbage collection after each image
        
        # Save PDF
        c.save()
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"Error in merge_images_to_pdf: {str(e)}")
        raise
    finally:
        gc.collect()  # Final garbage collection

@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to verify application is running and configured correctly"""
    debug_info = {
        'app_root': app.root_path,
        'template_folder': app.template_folder,
        'templates_exist': os.path.exists(app.template_folder),
        'templates_contents': os.listdir(app.template_folder) if os.path.exists(app.template_folder) else [],
        'upload_folder': UPLOAD_FOLDER,
        'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
        'environment': os.environ.get('FLASK_ENV', 'not set'),
        'port': os.environ.get('PORT', 'not set')
    }
    logger.info(f"Debug info: {debug_info}")
    return debug_info

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint called")
    return {"status": "healthy", "message": "Application is running"}

@app.route('/', methods=['GET'])
def index():
    """Main page"""
    logger.info("Rendering index page")
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file upload and PDF generation"""
    logger.info("Upload endpoint called")
    
    if 'files[]' not in request.files:
        logger.warning("No files in request")
        flash('No files selected')
        return render_template('index.html')
    
    files = request.files.getlist('files[]')
    
    if not files or files[0].filename == '':
        logger.warning("Empty files list or no filename")
        flash('No files selected')
        return render_template('index.html')
    
    # Create temporary directory for this upload
    upload_dir = tempfile.mkdtemp()
    saved_files = []
    
    try:
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                saved_files.append(filepath)
                logger.info(f"Saved file: {filename}")
        
        if not saved_files:
            logger.warning("No valid image files uploaded")
            flash('No valid image files uploaded')
            return render_template('index.html')
        
        # Generate PDF
        logger.info("Generating PDF")
        pdf_output = merge_images_to_pdf(saved_files)
        
        # Clean up
        shutil.rmtree(upload_dir)
        
        logger.info("Sending PDF file")
        return send_file(
            pdf_output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='merged_receipts.pdf'
        )
        
    except Exception as e:
        logger.error(f"Error processing files: {str(e)}")
        flash(f'Error processing files: {str(e)}')
        return render_template('index.html')
    finally:
        # Ensure cleanup happens even if there's an error
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    logger.info(f"Starting application on port {port} with debug={debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode) 