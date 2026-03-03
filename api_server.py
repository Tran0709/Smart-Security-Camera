"""
FastAPI Server for Web Interface Integration
Provides RESTful API endpoints for the security camera system.

This module implements a FastAPI-based REST API server that allows web interfaces
and other clients to interact with the security camera system. It provides endpoints
for starting/stopping monitoring, viewing live streams, managing recordings, and
receiving real-time status updates via WebSocket.

Key Features:
- RESTful API endpoints for system control
- MJPEG video streaming for live feed viewing
- WebSocket support for real-time status updates
- Configuration management via API
- Recording management and metadata access
"""

# FastAPI and web framework imports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Standard library imports
from typing import List, Optional, Dict
import cv2  # OpenCV for video capture and frame processing
import json  # JSON file handling for configuration
import asyncio  # Asynchronous operations for WebSocket
import time  # Timestamp generation
import os  # File system operations
from pathlib import Path  # Path manipulation
from datetime import datetime  # Date/time formatting
from collections import deque  # Efficient queue for FPS tracking
import psutil  # System and process monitoring

# Local module imports - core system components
from detector import ObjectDetector  # Object detection using YOLOv8
from security_monitor import SecurityMonitor  # Security event monitoring
from video_recorder import VideoRecorder  # Video recording management

# Initialize FastAPI application instance
# This creates the main web server application
app = FastAPI(title="Smart Security Camera API")

# Enable CORS (Cross-Origin Resource Sharing) for web interface
# This allows web browsers to make requests from different origins
# WARNING: allow_origins=["*"] is permissive - configure appropriately for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production - restrict to specific domains
    allow_credentials=True,  # Allow cookies and authentication headers
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all request headers
)

# ============================================================================
# Global State Variables
# ============================================================================
# These variables maintain the system state across API requests
# They are initialized on server startup and updated during runtime

config = {}  # System configuration dictionary loaded from config.json
detector = None  # ObjectDetector instance for YOLOv8 object detection
security_monitor = None  # SecurityMonitor instance for unauthorized access detection
video_recorder = None  # VideoRecorder instance for event recording
video_capture = None  # OpenCV VideoCapture object for video source
is_running = False  # Boolean flag indicating if monitoring is currently active
active_connections = set()  # Set of active WebSocket connections for status updates

# Performance metrics tracking
performance_metrics = {
    "resolution": {"width": 0, "height": 0},
    "fps_history": deque(maxlen=100),  # Store last 100 FPS measurements
    "detection_latencies": deque(maxlen=100),  # Store last 100 detection latencies
    "start_time": None,
    "frame_count": 0,
    "last_fps_update": None
}


# ============================================================================
# Pydantic Models for Request/Response Validation
# ============================================================================

class ConfigUpdate(BaseModel):
    """
    Pydantic model for configuration update requests.
    
    This model validates incoming configuration updates from API clients.
    Each field is optional, allowing partial configuration updates.
    
    Attributes:
        detection: Optional dictionary containing detection settings
                  (model path, confidence threshold, monitored classes, etc.)
        security: Optional dictionary containing security monitoring settings
                 (unauthorized access rules, alert cooldown, etc.)
        recording: Optional dictionary containing recording settings
                  (save directory, buffer times, codec, etc.)
        video: Optional dictionary containing video source settings
              (source index/path, resolution, etc.)
    """
    detection: Optional[Dict] = None
    security: Optional[Dict] = None
    recording: Optional[Dict] = None
    video: Optional[Dict] = None


# ============================================================================
# Configuration Management Functions
# ============================================================================

def load_config(config_path: str = "config.json") -> dict:
    """
    Load system configuration from a JSON file.
    
    This function reads the configuration file and parses it as JSON.
    If the file doesn't exist, it returns an empty dictionary to allow
    the system to use default values.
    
    Args:
        config_path: Path to the configuration JSON file (default: "config.json")
        
    Returns:
        Dictionary containing configuration settings, or empty dict if file not found
    """
    try:
        # Open and read the configuration file
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return empty dict if config file doesn't exist
        # System will use default values from individual components
        return {}


def initialize_system():
    """
    Initialize all security camera system components.
    
    This function loads the configuration and creates instances of:
    - ObjectDetector: For YOLOv8-based object detection
    - SecurityMonitor: For unauthorized access detection and alerting
    - VideoRecorder: For recording video segments when events occur
    
    The function uses global variables to store these instances so they
    can be accessed by API endpoints throughout the application lifecycle.
    """
    global config, detector, security_monitor, video_recorder
    
    # Load configuration from file
    config = load_config()
    
    # Extract detection configuration section
    detection_config = config.get('detection', {})
    
    # Initialize object detector with YOLOv8 model
    # Uses model path and confidence threshold from config, or defaults
    detector = ObjectDetector(
        model_path=detection_config.get('model', 'yolov8n.pt'),  # Default to nano model
        confidence_threshold=detection_config.get('confidence_threshold', 0.5)  # Default 50% confidence
    )
    
    # Initialize security monitor with full config for rule evaluation
    security_monitor = SecurityMonitor(config)
    
    # Initialize video recorder with full config for recording settings
    video_recorder = VideoRecorder(config)


# ============================================================================
# FastAPI Lifecycle Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event handler.
    
    This function is automatically called when the FastAPI server starts.
    It initializes all system components (detector, monitor, recorder)
    by loading configuration and creating component instances.
    """
    initialize_system()


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Root endpoint - serves the dashboard HTML page.
    
    Returns:
        HTML content of the dashboard
    """
    try:
        with open('dashboard.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return """
        <html>
            <head><title>API Information</title></head>
            <body>
                <h1>Smart Security Camera API</h1>
                <p>Dashboard not found. API endpoints available:</p>
                <ul>
                    <li><a href="/api/status">GET /api/status</a> - Get system status</li>
                    <li>POST /api/start - Start video monitoring</li>
                    <li>POST /api/stop - Stop video monitoring</li>
                    <li>GET /api/config - Get configuration</li>
                    <li>PUT /api/config - Update configuration</li>
                    <li>GET /api/recordings - List recordings</li>
                    <li>GET /api/stream - MJPEG video stream</li>
                    <li>WS /ws - WebSocket for real-time updates</li>
                </ul>
            </body>
        </html>
        """


def get_performance_metrics():
    """
    Calculate and return current performance metrics.
    
    Returns:
        Dictionary containing:
        - resolution: Current video resolution (width x height)
        - fps_range: Min and max FPS from recent history
        - fps_current: Current average FPS
        - cpu_load: Current CPU usage percentage
        - detection_latency: Average detection latency in milliseconds
    """
    global performance_metrics
    
    # Calculate FPS metrics
    fps_history = list(performance_metrics["fps_history"])
    if fps_history:
        fps_min = min(fps_history)
        fps_max = max(fps_history)
        fps_current = sum(fps_history) / len(fps_history) if fps_history else 0
    else:
        fps_min = fps_max = fps_current = 0
    
    # Calculate detection latency
    latencies = list(performance_metrics["detection_latencies"])
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    
    # Get CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    
    return {
        "resolution": {
            "width": performance_metrics["resolution"]["width"],
            "height": performance_metrics["resolution"]["height"],
            "display": f"{performance_metrics['resolution']['width']}x{performance_metrics['resolution']['height']}"
        },
        "fps_range": {
            "min": round(fps_min, 1),
            "max": round(fps_max, 1),
            "current": round(fps_current, 1),
            "display": f"{fps_min:.1f} - {fps_max:.1f}"
        },
        "cpu_load": round(cpu_percent, 1),
        "detection_latency": round(avg_latency, 1)
    }


@app.get("/api/status")
async def get_status():
    """
    Get current system status and monitoring information.
    
    This endpoint provides real-time status of the security camera system,
    including whether monitoring is active, current monitoring state,
    recording status, number of active WebSocket connections, and performance metrics.
    
    Returns:
        Dictionary containing:
        - status: "not_initialized", "running", or "stopped"
        - monitoring: Detailed monitoring status from SecurityMonitor
        - recording: Boolean indicating if currently recording
        - active_connections: Number of active WebSocket connections
        - performance: Performance metrics (resolution, FPS range, CPU load, detection latency)
    """
    # Check if system has been initialized
    if not detector:
        return {"status": "not_initialized"}
    
    # Get detailed monitoring status if monitor is available
    monitor_status = security_monitor.get_status() if security_monitor else {}
    
    # Get performance metrics
    perf_metrics = get_performance_metrics() if is_running else {}
    
    # Return comprehensive status information
    return {
        "status": "running" if is_running else "stopped",  # Overall system state
        "monitoring": monitor_status,  # Security monitoring details
        "recording": video_recorder.is_recording if video_recorder else False,  # Recording state
        "active_connections": len(active_connections),  # WebSocket connection count
        "performance": perf_metrics  # Performance metrics
    }


@app.post("/api/start")
async def start_monitoring():
    """
    Start video monitoring and begin processing video stream.
    
    This endpoint initializes the video capture source (camera or video file)
    and begins the monitoring process. The video source is determined from
    the configuration file. Once started, the system will begin detecting
    objects and monitoring for unauthorized access.
    
    Returns:
        Dictionary with success message and status
        
    Raises:
        HTTPException: If video source cannot be opened (status 500)
    """
    global is_running, video_capture
    
    # Check if monitoring is already running
    if is_running:
        return {"message": "Already running", "status": "running"}
    
    # Get video source configuration
    config_video = config.get('video', {})
    source = config_video.get('source', 0)  # Default to camera index 0
    
    # Try to parse source as integer (camera index), otherwise use as string (file path)
    try:
        video_source = int(source)
    except ValueError:
        # Source is a string (likely a file path)
        video_source = source
    
    # Initialize OpenCV VideoCapture with the specified source
    video_capture = cv2.VideoCapture(video_source)
    
    # Verify that the video source was successfully opened
    if not video_capture.isOpened():
        raise HTTPException(
            status_code=500,
            detail=f"Could not open video source {video_source}"
        )
    
    # Set running flag to indicate monitoring is active
    is_running = True
    
    return {"message": "Monitoring started", "status": "running"}


@app.post("/api/stop")
async def stop_monitoring():
    """
    Stop video monitoring and release resources.
    
    This endpoint stops the monitoring process, releases the video capture
    resource, and cleans up any active recordings. This should be called
    before shutting down the system or switching video sources.
    
    Returns:
        Dictionary with success message and status
    """
    global is_running, video_capture, performance_metrics
    
    # Check if monitoring is currently running
    if not is_running:
        return {"message": "Not running", "status": "stopped"}
    
    # Release video capture resource if it exists
    if video_capture:
        video_capture.release()  # Free the camera/file handle
        video_capture = None
    
    # Clean up video recorder (stop any active recordings)
    if video_recorder:
        video_recorder.cleanup()
    
    # Reset performance metrics
    performance_metrics["fps_history"].clear()
    performance_metrics["detection_latencies"].clear()
    performance_metrics["frame_count"] = 0
    performance_metrics["start_time"] = None
    performance_metrics["resolution"]["width"] = 0
    performance_metrics["resolution"]["height"] = 0
    
    # Set running flag to indicate monitoring is stopped
    is_running = False
    
    return {"message": "Monitoring stopped", "status": "stopped"}


@app.get("/api/config")
async def get_config():
    """
    Get the current system configuration.
    
    This endpoint returns the complete configuration dictionary that is
    currently being used by the system. This includes all settings for
    detection, security monitoring, recording, and video sources.
    
    Returns:
        Dictionary containing the complete system configuration
    """
    return config


@app.put("/api/config")
async def update_config(config_update: ConfigUpdate):
    """
    Update system configuration and reinitialize components.
    
    This endpoint allows clients to update the system configuration.
    The update can be partial (only specific sections) or complete.
    After updating, the system components are reinitialized with the
    new configuration, and the changes are saved to the config file.
    
    Args:
        config_update: ConfigUpdate model containing configuration changes
        
    Returns:
        Dictionary with success message and updated configuration
        
    Note:
        Reinitializing the system will reset detector, monitor, and recorder
        instances. Any active monitoring should be stopped before updating config.
    """
    global config
    
    # Update detection configuration if provided
    if config_update.detection:
        # setdefault ensures the section exists, then update merges new values
        config.setdefault('detection', {}).update(config_update.detection)
    
    # Update security configuration if provided
    if config_update.security:
        config.setdefault('security', {}).update(config_update.security)
    
    # Update recording configuration if provided
    if config_update.recording:
        config.setdefault('recording', {}).update(config_update.recording)
    
    # Update video configuration if provided
    if config_update.video:
        config.setdefault('video', {}).update(config_update.video)
    
    # Reinitialize system components with new configuration
    # This creates new detector, monitor, and recorder instances
    initialize_system()
    
    # Persist configuration changes to file
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)  # Pretty-print with 2-space indentation
    
    return {"message": "Configuration updated", "config": config}


@app.get("/api/recordings")
async def list_recordings():
    """
    List all recorded video segments with metadata.
    
    This endpoint scans the recordings directory and returns information
    about all available video recordings, including file size, creation
    time, and modification time. Recordings are sorted by creation time
    (newest first).
    
    Returns:
        Dictionary containing a list of recording metadata dictionaries,
        each with filename, path, size, created timestamp, and modified timestamp
    """
    # Get recording directory from configuration
    recording_config = config.get('recording', {})
    save_directory = recording_config.get('save_directory', 'recordings')
    
    recordings = []
    
    # Check if recordings directory exists
    if os.path.exists(save_directory):
        # Iterate through all files in the directory
        for file in os.listdir(save_directory):
            # Only process MP4 video files
            if file.endswith('.mp4'):
                filepath = os.path.join(save_directory, file)
                
                # Get file statistics (size, timestamps)
                stat = os.stat(filepath)
                
                # Add recording metadata to list
                recordings.append({
                    "filename": file,  # Just the filename
                    "path": filepath,  # Full file path
                    "size": stat.st_size,  # File size in bytes
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),  # Creation time (ISO format)
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()  # Last modification time (ISO format)
                })
    
    # Sort recordings by creation time, newest first
    return {"recordings": sorted(recordings, key=lambda x: x['created'], reverse=True)}


@app.get("/api/recordings/{filename}")
async def get_recording(filename: str):
    """
    Download a specific recorded video segment.
    
    This endpoint serves a video file for download or streaming.
    The filename should match a file in the recordings directory.
    
    Args:
        filename: Name of the video file to download (e.g., "unauthorized_access_20251209_101206.mp4")
        
    Returns:
        FileResponse object containing the video file
        
    Raises:
        HTTPException: If the recording file is not found (status 404)
    """
    # Get recording directory from configuration
    recording_config = config.get('recording', {})
    save_directory = recording_config.get('save_directory', 'recordings')
    
    # Construct full file path
    filepath = os.path.join(save_directory, filename)
    
    # Verify file exists
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Recording not found")
    
    # Return file as HTTP response with appropriate media type
    return FileResponse(filepath, media_type="video/mp4")


@app.get("/api/recordings/{filename}/metadata")
async def get_recording_metadata(filename: str):
    """
    Get metadata for a specific recorded video segment.
    
    Each recorded video has an associated JSON metadata file containing
    information about the event that triggered the recording, including
    detection details, timestamps, and event reasons.
    
    Args:
        filename: Name of the video file (metadata filename is derived from this)
        
    Returns:
        Dictionary containing event metadata (timestamp, detections, reason, etc.)
        
    Raises:
        HTTPException: If the metadata file is not found (status 404)
    """
    # Get recording directory from configuration
    recording_config = config.get('recording', {})
    save_directory = recording_config.get('save_directory', 'recordings')
    
    # Metadata files use the same name as video but with _metadata.json extension
    metadata_path = os.path.join(save_directory, filename.replace('.mp4', '_metadata.json'))
    
    # Verify metadata file exists
    if not os.path.exists(metadata_path):
        raise HTTPException(status_code=404, detail="Metadata not found")
    
    # Read and parse JSON metadata file
    with open(metadata_path, 'r') as f:
        return json.load(f)


# ============================================================================
# Video Streaming Functions
# ============================================================================

def generate_frames():
    """
    Generator function for MJPEG video streaming.
    
    This generator function continuously reads frames from the video source,
    processes them through object detection and security monitoring, and
    yields JPEG-encoded frames in MJPEG format for HTTP streaming.
    
    The function performs the following for each frame:
    1. Read frame from video source
    2. Detect objects using YOLOv8
    3. Filter detections by monitored classes
    4. Check for unauthorized access events
    5. Add frame to video recorder (for event recording)
    6. Annotate frame with detection boxes and alerts
    7. Encode frame as JPEG
    8. Yield frame in MJPEG format
    
    Yields:
        Bytes in MJPEG format (multipart/x-mixed-replace with boundary markers)
        
    Note:
        This generator runs in a loop while is_running is True. It stops
        automatically when monitoring is stopped or video source ends.
    """
    global video_capture, detector, security_monitor, video_recorder, performance_metrics
    
    # Verify video capture is initialized and opened
    if not video_capture or not video_capture.isOpened():
        return
    
    # Initialize performance tracking
    performance_metrics["start_time"] = time.time()
    performance_metrics["frame_count"] = 0
    performance_metrics["last_fps_update"] = time.time()
    
    # Get resolution from video capture
    width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    performance_metrics["resolution"]["width"] = width
    performance_metrics["resolution"]["height"] = height
    
    # Get list of classes to monitor from configuration
    monitored_classes = config.get('detection', {}).get('monitored_classes', [])
    
    # Main processing loop - continues while monitoring is active
    while is_running:
        frame_start_time = time.time()
        
        # Read next frame from video source
        ret, frame = video_capture.read()
        if not ret:
            # Failed to read frame (end of video or error)
            break
        
        # Get current timestamp for event tracking
        timestamp = time.time()
        
        # Step 1: Detect all objects in the frame using YOLOv8
        # Track detection latency
        detection_start = time.time()
        detections = detector.detect(frame)
        detection_latency = (time.time() - detection_start) * 1000  # Convert to milliseconds
        performance_metrics["detection_latencies"].append(detection_latency)
        
        # Step 2: Filter detections to only include monitored classes
        # This reduces processing and focuses on relevant objects
        filtered_detections = detector.filter_by_classes(detections, monitored_classes)
        
        # Step 3: Check if current detections indicate unauthorized access
        # This evaluates security rules and determines if alert should trigger
        event_info = security_monitor.check_unauthorized_access(
            filtered_detections, timestamp
        )
        
        # Step 4: Add frame to video recorder
        # Recorder handles buffering and saving video segments when events occur
        video_recorder.add_frame(
            frame, filtered_detections, timestamp, event_info
        )
        
        # Step 5: Annotate frame with detection boxes and labels
        # This draws bounding boxes and class names on the frame
        annotated_frame = detector.annotate_frame(frame, filtered_detections)
        
        # Step 6: Add alert overlay if unauthorized access detected
        if event_info.get('is_unauthorized', False):
            # Draw red alert text on frame
            cv2.putText(
                annotated_frame,
                "ALERT: Unauthorized Access!",
                (10, 60),  # Position: 10 pixels from left, 60 from top
                cv2.FONT_HERSHEY_SIMPLEX,  # Font type
                0.7,  # Font scale
                (0, 0, 255),  # Color: Red in BGR format
                2  # Line thickness
            )
        
        # Step 7: Encode frame as JPEG for streaming
        # imencode converts OpenCV image to JPEG bytes
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        if not ret:
            # Encoding failed, skip this frame
            continue
        
        # Convert numpy array to bytes
        frame_bytes = buffer.tobytes()
        
        # Update performance metrics
        performance_metrics["frame_count"] += 1
        frame_time = time.time() - frame_start_time
        if frame_time > 0:
            current_fps = 1.0 / frame_time
            performance_metrics["fps_history"].append(current_fps)
        
        # Step 8: Yield frame in MJPEG format
        # MJPEG uses multipart/x-mixed-replace with boundary markers
        # Each frame is preceded by boundary and content-type headers
        yield (b'--frame\r\n'  # MJPEG boundary marker
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.get("/api/stream")
async def video_stream():
    """
    Video streaming endpoint for MJPEG live feed.
    
    This endpoint provides a continuous MJPEG (Motion JPEG) stream of the
    video feed with object detection annotations and security alerts overlaid.
    The stream can be viewed in web browsers or video players that support MJPEG.
    
    The stream format is multipart/x-mixed-replace, which allows continuous
    frame updates without requiring WebSocket or other complex protocols.
    
    Returns:
        StreamingResponse with MJPEG video stream
        
    Raises:
        HTTPException: If monitoring is not started (status 400)
        
    Usage:
        Open the URL in a browser or video player:
        http://localhost:8000/api/stream
    """
    # Verify monitoring is active before streaming
    if not is_running:
        raise HTTPException(
            status_code=400,
            detail="Monitoring not started. Call /api/start first."
        )
    
    # Return streaming response with generator function
    # media_type specifies MJPEG format with frame boundary
    return StreamingResponse(
        generate_frames(),  # Generator function that yields frames
        media_type="multipart/x-mixed-replace; boundary=frame"  # MJPEG format
    )


# ============================================================================
# WebSocket Endpoint for Real-Time Updates
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time system status updates.
    
    This endpoint establishes a WebSocket connection that sends periodic
    status updates to connected clients. This is useful for web interfaces
    that need real-time monitoring information without polling the REST API.
    
    The connection sends updates every second with:
    - System status (running/stopped)
    - Current timestamp
    - Detailed monitoring status
    - Recording status
    
    The connection remains open until the client disconnects or an error occurs.
    
    Args:
        websocket: WebSocket connection object from FastAPI
        
    Note:
        Multiple clients can connect simultaneously. Each connection is
        tracked in the active_connections set.
    """
    # Accept the WebSocket connection from client
    await websocket.accept()
    
    # Add this connection to the active connections set
    active_connections.add(websocket)
    
    try:
        # Main update loop - runs until connection is closed
        while True:
            # Build status dictionary with current system state
            status = {
                "status": "running" if is_running else "stopped",  # Overall system state
                "timestamp": time.time(),  # Current Unix timestamp
                "monitoring": security_monitor.get_status() if security_monitor else {},  # Detailed monitoring info
                "recording": video_recorder.is_recording if video_recorder else False,  # Recording state
                "performance": get_performance_metrics() if is_running else {}  # Performance metrics
            }
            
            # Send status update as JSON to client
            await websocket.send_json(status)
            
            # Wait 1 second before sending next update
            await asyncio.sleep(1)
    
    except WebSocketDisconnect:
        # Client disconnected normally - remove from active connections
        active_connections.remove(websocket)


# ============================================================================
# FastAPI Shutdown Event
# ============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """
    FastAPI shutdown event handler.
    
    This function is automatically called when the FastAPI server is shutting down.
    It performs cleanup operations to release resources properly:
    - Releases video capture (camera/file handle)
    - Stops any active video recordings
    
    This ensures resources are freed and files are properly closed.
    """
    global video_capture, video_recorder
    
    # Release video capture resource if it exists
    if video_capture:
        video_capture.release()
    
    # Clean up video recorder (stop any active recordings)
    if video_recorder:
        video_recorder.cleanup()


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    """
    Run the FastAPI server when script is executed directly.
    
    This starts the Uvicorn ASGI server to serve the FastAPI application.
    The server listens on all network interfaces (0.0.0.0) on port 8000.
    
    To run the server:
        python api_server.py
        
    Or use uvicorn directly:
        uvicorn api_server:app --host 0.0.0.0 --port 8000
    """
    import uvicorn
    
    # Start Uvicorn ASGI server
    # host="0.0.0.0" makes server accessible from any network interface
    # port=8000 is the default port for the API
    uvicorn.run(app, host="0.0.0.0", port=8000)


