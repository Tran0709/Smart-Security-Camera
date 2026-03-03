# Smart Security Camera System

A real-time security camera system using YOLOv8 for object detection, unauthorized access detection, and automatic video segment recording.

## Features

- **Real-time Object Detection**: Uses YOLOv8 to detect and categorize objects (humans, vehicles, etc.) from video streams
- **Unauthorized Access Detection**: Identifies suspicious motion patterns based on detected objects
- **Automatic Recording**: Saves annotated video segments when unauthorized access is detected
- **RESTful API**: Backend API for web interface integration

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Using Webcam

```bash
python main.py --source 0 --display  # Use default webcam (0) with display window
```

### Using Video Files

```bash
# Process a video file
python main.py --source path/to/video.mp4 --display

# Process video file and loop it continuously
python main.py --source path/to/video.mp4 --display --loop-video
```

### Using Single Images

```bash
# Process a single image (saves annotated result to detected_images/ folder)
python main.py --source path/to/image.jpg --display

# Process without displaying window
python main.py --source path/to/image.jpg
```

### Using Image Directories

```bash
# Process all images in a directory
python main.py --source path/to/images/ --display

# Process directory without saving annotated images
python main.py --source path/to/images/ --save-images
```

### With Custom Configuration

```bash
python main.py --source 0 --config config.json --display
```

### Start API Server

```bash
python api_server.py
```

The API will be available at `http://localhost:8000`

### Supported File Formats

**Images**: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`, `.webp`, `.gif`

**Videos**: `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, `.webm`, `.m4v`

## Project Structure

```
.
├── main.py                 # Main application entry point
├── api_server.py          # FastAPI server for web interface
├── detector.py            # YOLOv8 object detection module
├── security_monitor.py    # Unauthorized access detection logic
├── video_recorder.py      # Video annotation and saving
├── config.json            # Configuration file
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Configuration

Edit `config.json` to customize:
- Detection confidence thresholds
- Unauthorized access rules
- Video recording settings
- Object categories to monitor

## Web Interface Integration

See `WEB_INTEGRATION.md` for detailed documentation on integrating the backend with a web interface.

## Design Specifications

This project includes comprehensive design documentation:

- **DESIGN_SPECIFICATIONS.md**: System architecture diagrams, component interactions, data flow diagrams, and process flowcharts
- **WIREFRAMES.md**: User interface wireframes, layout specifications, and UI component designs
- **ARCHITECTURE.md**: Detailed technical architecture documentation, API specifications, and deployment architecture

These documents provide complete design specifications including user interface wireframes and functional descriptions with architecture diagrams and flowcharts.


