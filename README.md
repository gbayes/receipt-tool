# Receipt Merger

A web application that allows users to upload multiple receipt images and merge them into a single PDF file. The application automatically scales and centers the images while maintaining quality and keeping the file size optimized.

## Features

- Drag-and-drop file upload interface
- Supports multiple image formats (PNG, JPG, JPEG, TIFF, BMP)
- Automatic image scaling and centering
- Image compression to optimize PDF size
- Mobile-friendly design
- Secure file handling with temporary storage

## Local Development Setup

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/receipt-merger.git
cd receipt-merger
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Docker Deployment

1. Build the Docker image:
```bash
docker build -t receipt-merger .
```

2. Run the container:
```bash
docker run -p 8080:8080 receipt-merger
```

The application will be available at `http://localhost:8080`

## Deployment to Render.com

1. Fork this repository or push it to your GitHub account
2. Create a new account on [Render.com](https://render.com) if you haven't already
3. Click "New +" and select "Web Service"
4. Connect your GitHub repository
5. Select "Docker" as the environment
6. Choose a name for your service
7. Select the free instance type
8. Click "Create Web Service"

Render will automatically build and deploy your application.

## Technical Details

- Built with Flask (Python web framework)
- Uses Pillow for image processing
- Uses ReportLab for PDF generation
- Implements secure file handling with `werkzeug`
- Containerized with Docker
- Uses Gunicorn as the WSGI HTTP Server

## Security Features

- Secure filename handling
- Temporary file storage
- File type validation
- Maximum file size limit (16MB)
- Automatic cleanup of temporary files

## License

MIT License 