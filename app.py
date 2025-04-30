import os
import io
import tempfile
import shutil
import logging
import gc
import uuid
import json
from flask import Flask, render_template, request, send_file, flash, jsonify, session
from werkzeug.utils import secure_filename
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from ocr_processor import process_receipt

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
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB max file size
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(image, max_size_mb=0.1):  # Reduced to 100KB target
    try:
        # Start with quality 60 and adjust based on file size
        quality = 60
        target_size = max_size_mb * 1024 * 1024  # Convert MB to bytes
        
        # Convert image to RGB if it's not
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize image if it's too large (max 1200px on longest side)
        max_size = 1200  # Reduced from 1500px
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Create a BytesIO object to check size
        while quality > 15:  # Lower minimum quality
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=quality, optimize=True)
            if buffer.tell() <= target_size:
                buffer.seek(0)
                compressed_img = Image.open(buffer)
                final_img = Image.new('RGB', compressed_img.size)
                final_img.paste(compressed_img)
                compressed_img.close()
                buffer.close()
                return final_img
            quality -= 10  # More aggressive quality reduction
            buffer.close()
            gc.collect()
        
        # If we get here, create one final attempt with lowest quality
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=15, optimize=True)
        buffer.seek(0)
        compressed_img = Image.open(buffer)
        final_img = Image.new('RGB', compressed_img.size)
        final_img.paste(compressed_img)
        compressed_img.close()
        buffer.close()
        return final_img
    except Exception as e:
        logger.error(f"Error in compress_image: {str(e)}")
        raise
    finally:
        gc.collect()

def process_single_image(img_path, c, page_width, page_height, margin):
    try:
        with Image.open(img_path) as img:
            compressed_img = compress_image(img)
            try:
                max_width = page_width - (2 * margin)
                max_height = page_height - (2 * margin)
                img_width, img_height = compressed_img.size
                
                width_ratio = max_width / img_width
                height_ratio = max_height / img_height
                scale_factor = min(width_ratio, height_ratio)
                
                new_width = img_width * scale_factor
                new_height = img_height * scale_factor
                
                x = (page_width - new_width) / 2
                y = (page_height - new_height) / 2
                
                c.drawImage(ImageReader(compressed_img), x, y, width=new_width, height=new_height)
                c.showPage()
                
                logger.info(f"Processed: {os.path.basename(img_path)}")
            finally:
                compressed_img.close()
                gc.collect()
    except Exception as e:
        logger.error(f"Error processing {os.path.basename(img_path)}: {str(e)}")
        raise

def merge_images_to_pdf(image_files):
    try:
        output = io.BytesIO(initial_bytes=b'')
        c = canvas.Canvas(output, pagesize=letter)
        c.setPageCompression(1)
        
        page_width, page_height = letter
        margin = 40
        
        for img_path in image_files:
            process_single_image(img_path, c, page_width, page_height, margin)
            gc.collect()
        
        c.save()
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"Error in merge_images_to_pdf: {str(e)}")
        raise
    finally:
        gc.collect()

@app.route('/')
def index():
    """Main page"""
    # Initialize session storage for files
    if 'files' not in session:
        session['files'] = []
    if 'upload_id' not in session:
        session['upload_id'] = str(uuid.uuid4())
    
    # Create a unique upload directory for this session
    upload_dir = os.path.join(UPLOAD_FOLDER, session['upload_id'])
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle single file upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    try:
        filename = secure_filename(file.filename)
        upload_dir = os.path.join(UPLOAD_FOLDER, session['upload_id'])
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        # Process receipt with OCR
        logger.info(f"Processing OCR for file: {filename}")
        with Image.open(filepath) as img:
            ocr_result = process_receipt(img)
        logger.info(f"OCR result for {filename}: {ocr_result}")
        
        # Add file and OCR result to session
        if 'files' not in session:
            session['files'] = []
        if 'ocr_results' not in session:
            session['ocr_results'] = {}
        
        session['files'].append(filepath)
        session['ocr_results'][filepath] = ocr_result
        session.modified = True
        
        response_data = {
            'success': True,
            'filename': filename,
            'ocr_result': ocr_result
        }
        logger.info(f"Sending response for {filename}: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/merge', methods=['POST'])
def merge_files():
    """Merge uploaded files into PDF"""
    try:
        if 'files' not in session or not session['files']:
            return jsonify({'error': 'No files uploaded'}), 400
        
        files = session['files']
        ocr_results = session.get('ocr_results', {})
        
        # Sort files by total amount if available
        def get_total(filepath):
            result = ocr_results.get(filepath, {})
            if result.get('success', False):
                return result.get('total', 0)
            return 0
        
        files = sorted(files, key=get_total, reverse=True)
        
        pdf_output = merge_images_to_pdf(files)
        
        # Clean up
        upload_dir = os.path.join(UPLOAD_FOLDER, session['upload_id'])
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)
        
        # Clear session
        session.pop('files', None)
        session.pop('ocr_results', None)
        session.pop('upload_id', None)
        
        return send_file(
            pdf_output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='merged_receipts.pdf'
        )
    except Exception as e:
        logger.error(f"Error merging files: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/clear', methods=['POST'])
def clear_files():
    """Clear uploaded files"""
    try:
        if 'upload_id' in session:
            upload_dir = os.path.join(UPLOAD_FOLDER, session['upload_id'])
            if os.path.exists(upload_dir):
                shutil.rmtree(upload_dir)
        session.pop('files', None)
        session.pop('upload_id', None)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error clearing files: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    logger.info(f"Starting application on port {port} with debug={debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode) 