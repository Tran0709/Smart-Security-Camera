# System Architecture Documentation
## Smart Security Camera System

This document provides detailed technical architecture documentation for the Smart Security Camera System, including component details, data structures, API specifications, and system design decisions.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Patterns](#architecture-patterns)
3. [Component Details](#component-details)
4. [Data Structures](#data-structures)
5. [API Specifications](#api-specifications)
6. [Configuration Management](#configuration-management)
7. [Error Handling](#error-handling)
8. [Performance Considerations](#performance-considerations)
9. [Security Architecture](#security-architecture)
10. [Deployment Architecture](#deployment-architecture)

---

## System Overview

### Purpose
The Smart Security Camera System is designed to provide real-time object detection, unauthorized access monitoring, and automatic video recording capabilities for security applications.

### Key Requirements
- Real-time video processing
- Object detection using YOLOv8
- Unauthorized access detection
- Automatic video recording
- Web API for remote access
- Scalable architecture

### Technology Stack
- **Language**: Python 3.8+
- **ML Framework**: Ultralytics YOLOv8
- **Computer Vision**: OpenCV
- **Web Framework**: FastAPI
- **Data Processing**: NumPy
- **Configuration**: JSON

---

## Architecture Patterns

### Layered Architecture

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  (Web UI, CLI, API Endpoints)          │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Application Layer               │
│  (Business Logic, Orchestration)        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Domain Layer                    │
│  (Core Components, Domain Logic)        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Infrastructure Layer            │
│  (File I/O, Network, Hardware)          │
└─────────────────────────────────────────┘
```

### Component-Based Architecture

The system follows a component-based architecture where each major functionality is encapsulated in a separate module:

- **ObjectDetector**: Handles object detection
- **SecurityMonitor**: Implements security rules
- **VideoRecorder**: Manages video recording
- **API Server**: Provides web interface

### Event-Driven Processing

The system uses an event-driven approach for processing video frames:

```
Frame Capture → Detection → Security Evaluation → Recording Trigger
```

---

## Component Details

### ObjectDetector Component

#### Responsibilities
- Load and manage YOLOv8 model
- Process video frames for object detection
- Filter detections by confidence and class
- Annotate frames with detection results

#### Class Structure
```python
class ObjectDetector:
    - model: YOLO model instance
    - confidence_threshold: float
    - class_names: List[str]
    
    Methods:
    - __init__(model_path, confidence_threshold)
    - detect(frame) -> List[Detection]
    - filter_detections(detections) -> List[Detection]
    - annotate_frame(frame, detections) -> annotated_frame
```

#### Detection Data Structure
```python
Detection = {
    'class': str,           # Object class name
    'confidence': float,     # Confidence score (0-1)
    'bbox': [x1, y1, x2, y2], # Bounding box coordinates
    'center': (x, y)        # Center point
}
```

#### Processing Flow
1. Receive frame from video source
2. Preprocess frame (resize if needed)
3. Run YOLOv8 inference
4. Parse detection results
5. Filter by confidence threshold
6. Filter by monitored classes
7. Return list of detections

### SecurityMonitor Component

#### Responsibilities
- Evaluate detections against security rules
- Track detection duration
- Manage alert cooldown periods
- Enforce time-based and zone-based rules

#### Class Structure
```python
class SecurityMonitor:
    - config: Dict
    - detection_history: deque
    - last_alert_time: float
    - alert_cooldown: float
    
    Methods:
    - __init__(config)
    - check_unauthorized_access(detections) -> bool
    - update_detection_history(detections)
    - is_within_restricted_hours() -> bool
    - is_in_restricted_zone(detection) -> bool
```

#### Security Rules
- **Duration Threshold**: Minimum time unauthorized objects must be present
- **Minimum Objects**: Minimum count of unauthorized objects
- **Restricted Zones**: Geographic areas where access is prohibited
- **Time-Based Rules**: Time periods when access is restricted
- **Alert Cooldown**: Minimum time between alerts

#### Evaluation Logic
```
1. Filter detections by unauthorized classes
2. Check minimum object count
3. Update detection history
4. Calculate detection duration
5. Check duration threshold
6. Check time-based rules
7. Check restricted zones
8. Check alert cooldown
9. Return true if all conditions met
```

### VideoRecorder Component

#### Responsibilities
- Buffer pre-event frames
- Record video segments during events
- Annotate frames with detections
- Save video files and metadata

#### Class Structure
```python
class VideoRecorder:
    - config: Dict
    - pre_event_buffer: deque
    - video_writer: VideoWriter
    - is_recording: bool
    - recording_start_time: float
    
    Methods:
    - __init__(config)
    - add_frame(frame, detections)
    - start_recording()
    - stop_recording() -> (video_path, metadata_path)
    - annotate_frame(frame, detections) -> annotated_frame
```

#### Recording Process
1. Continuously buffer frames (pre-event)
2. On event trigger: initialize VideoWriter
3. Write buffered pre-event frames
4. Record current event frames (annotated)
5. Continue recording for post-event period
6. Stop recording and finalize video
7. Generate and save metadata

#### Metadata Structure
```json
{
    "filename": "unauthorized_access_20241221_103015.mp4",
    "timestamp": "2024-12-21T10:30:15",
    "duration": 45.0,
    "detections": [
        {
            "class": "person",
            "confidence": 0.85,
            "bbox": [100, 200, 300, 400],
            "timestamp": 10.5
        }
    ],
    "event_type": "unauthorized_access",
    "video_settings": {
        "fps": 30,
        "resolution": [1920, 1080],
        "codec": "mp4v"
    }
}
```

### API Server Component

#### Responsibilities
- Provide RESTful API endpoints
- Stream MJPEG video feed
- Manage WebSocket connections
- Handle configuration updates
- Serve recordings and metadata

#### FastAPI Application Structure
```python
app = FastAPI()

# Global state
config = {}
detector = None
security_monitor = None
video_recorder = None
is_running = False
active_connections = set()

# Endpoints
@app.get("/api/status")
@app.post("/api/start")
@app.post("/api/stop")
@app.get("/api/config")
@app.put("/api/config")
@app.get("/api/recordings")
@app.get("/api/stream")
@app.websocket("/ws")
```

#### Request/Response Flow
```
Client Request → FastAPI Router → Endpoint Handler → Core Component → Response
```

---

## Data Structures

### Configuration Structure

```json
{
    "detection": {
        "model": "yolov8n.pt",
        "confidence_threshold": 0.3,
        "monitored_classes": ["person", "car", ...],
        "unauthorized_classes": ["person", "car", ...]
    },
    "security": {
        "unauthorized_access_rules": {
            "detection_duration": 2.0,
            "min_objects": 1,
            "restricted_zones": [],
            "time_based_rules": {
                "enabled": false,
                "restricted_hours": []
            }
        },
        "alert_cooldown": 30.0
    },
    "recording": {
        "save_directory": "recordings",
        "pre_event_buffer": 5.0,
        "post_event_buffer": 10.0,
        "fps": 30,
        "codec": "mp4v",
        "annotate": true,
        "include_timestamp": true
    },
    "video": {
        "source": 0,
        "width": 640,
        "height": 480
    }
}
```

### Detection Result Structure

```python
{
    "class": str,              # Object class name
    "confidence": float,       # Confidence score (0-1)
    "bbox": [x1, y1, x2, y2],  # Bounding box [left, top, right, bottom]
    "center": (x, y)           # Center coordinates
}
```

### System Status Structure

```json
{
    "status": "running" | "stopped" | "error",
    "monitoring": {
        "monitoring": true,
        "unauthorized_classes": ["person", "car"],
        "detection_duration_threshold": 2.0,
        "min_objects": 1,
        "current_detections": 3
    },
    "recording": {
        "is_recording": false,
        "total_recordings": 24,
        "last_recording": "2024-12-21T10:30:15"
    },
    "active_connections": 2,
    "timestamp": 1704110400.0
}
```

---

## API Specifications

### REST API Endpoints

#### GET /api/status
Returns current system status.

**Response:**
```json
{
    "status": "running",
    "monitoring": {...},
    "recording": {...},
    "active_connections": 2
}
```

#### POST /api/start
Starts the monitoring system.

**Response:**
```json
{
    "message": "Monitoring started",
    "status": "running"
}
```

#### POST /api/stop
Stops the monitoring system.

**Response:**
```json
{
    "message": "Monitoring stopped",
    "status": "stopped"
}
```

#### GET /api/config
Returns current configuration.

**Response:**
```json
{
    "detection": {...},
    "security": {...},
    "recording": {...},
    "video": {...}
}
```

#### PUT /api/config
Updates system configuration.

**Request Body:**
```json
{
    "detection": {
        "confidence_threshold": 0.6
    },
    "security": {
        "unauthorized_access_rules": {
            "detection_duration": 3.0
        }
    }
}
```

**Response:**
```json
{
    "message": "Configuration updated",
    "config": {...}
}
```

#### GET /api/recordings
Lists all recordings.

**Response:**
```json
{
    "recordings": [
        {
            "filename": "unauthorized_access_20241221_103015.mp4",
            "path": "recordings/unauthorized_access_20241221_103015.mp4",
            "size": 13107200,
            "created": "2024-12-21T10:30:15",
            "modified": "2024-12-21T10:30:15"
        }
    ]
}
```

#### GET /api/recordings/{filename}
Downloads a recording file.

**Response:** Video file (binary)

#### GET /api/recordings/{filename}/metadata
Returns metadata for a recording.

**Response:**
```json
{
    "filename": "unauthorized_access_20241221_103015.mp4",
    "timestamp": "2024-12-21T10:30:15",
    "duration": 45.0,
    "detections": [...],
    "event_type": "unauthorized_access"
}
```

#### GET /api/stream
Streams MJPEG video feed.

**Response:** MJPEG stream (multipart/x-mixed-replace)

### WebSocket API

#### WS /ws
WebSocket connection for real-time updates.

**Message Format:**
```json
{
    "status": "running",
    "timestamp": 1704110400.0,
    "monitoring": {
        "monitoring": true,
        "current_detections": 2
    },
    "recording": {
        "is_recording": false
    }
}
```

**Connection Flow:**
1. Client connects to `/ws`
2. Server sends initial status
3. Server sends periodic updates (every 1 second)
4. Client can send ping messages
5. Server responds with pong

---

## Configuration Management

### Configuration Loading

```python
def load_config(config_path: str = "config.json") -> dict:
    """
    Load configuration from JSON file.
    Returns empty dict if file not found.
    """
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
```

### Configuration Validation

Configuration is validated at component initialization:
- Required fields checked
- Value ranges validated
- Type checking performed
- Default values applied if missing

### Configuration Updates

Configuration can be updated via:
1. **File Update**: Edit `config.json` directly
2. **API Update**: Use `PUT /api/config` endpoint
3. **Runtime Update**: Changes take effect immediately (if supported)

---

## Error Handling

### Error Types

1. **Configuration Errors**: Invalid or missing configuration
2. **Video Source Errors**: Cannot open video source
3. **Model Errors**: Cannot load YOLOv8 model
4. **Recording Errors**: Cannot write video file
5. **API Errors**: Invalid requests or server errors

### Error Handling Strategy

```python
try:
    # Operation
except SpecificError as e:
    # Handle specific error
    log_error(e)
    return error_response
except Exception as e:
    # Handle general error
    log_error(e)
    return generic_error_response
```

### Error Response Format

```json
{
    "error": true,
    "error_type": "ConfigurationError",
    "message": "Invalid confidence threshold",
    "details": {...}
}
```

### Logging

- **Info**: Normal operations
- **Warning**: Non-critical issues
- **Error**: Critical errors
- **Debug**: Detailed debugging information

---

## Performance Considerations

### Processing Pipeline Performance

| Stage | Time (ms) | Notes |
|-------|-----------|-------|
| Frame Capture | 33 | 30 FPS source |
| Object Detection | 50-100 | YOLOv8n on CPU |
| Security Evaluation | 1-5 | Rule checking |
| Frame Annotation | 5-10 | Drawing operations |
| Video Writing | 10-20 | File I/O |
| **Total** | **100-150** | **6-10 FPS effective** |

### Optimization Strategies

1. **GPU Acceleration**: Use GPU for YOLOv8 inference
2. **Frame Skipping**: Process every Nth frame
3. **Multi-threading**: Parallel processing
4. **Batch Processing**: Process multiple frames together
5. **Hardware Encoding**: Use hardware video encoder

### Memory Management

- **Frame Buffers**: Limited size (pre-event buffer)
- **Detection History**: Time-limited (sliding window)
- **Video Writer**: Flush periodically
- **Model Loading**: Load once, reuse

### Scalability

- **Horizontal**: Multiple API instances
- **Vertical**: More CPU/GPU resources
- **Distributed**: Separate processing nodes
- **Caching**: Cache detection results

---

## Security Architecture

### API Security

#### Authentication (To be implemented)
- JWT tokens
- API keys
- OAuth 2.0

#### Authorization (To be implemented)
- Role-based access control
- Permission checks
- Resource-level authorization

#### Input Validation
- Request validation using Pydantic
- Type checking
- Range validation
- Sanitization

#### CORS Configuration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Data Security

#### Storage Security
- Secure file permissions
- Encrypted storage (optional)
- Access control lists

#### Network Security
- HTTPS/TLS encryption
- Secure WebSocket (WSS)
- Rate limiting

#### Configuration Security
- Sensitive data encryption
- Secure configuration storage
- Access control

---

## Deployment Architecture

### Development Environment

```
Developer Machine
├── Python 3.8+
├── YOLOv8 Model
├── Video Source (Webcam/File)
└── Application Code
```

### Production Environment

```
┌─────────────────────────────────────────┐
│         Load Balancer (Nginx)           │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
┌───────▼──────┐   ┌────────▼────────┐
│  API Server  │   │  API Server    │
│  Instance 1  │   │  Instance 2     │
└───────┬──────┘   └────────┬────────┘
        │                   │
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │  Processing Cluster │
        │  (Shared State)     │
        └─────────┬───────────┘
                  │
        ┌─────────▼─────────┐
        │  Shared Storage    │
        │  (Recordings)      │
        └────────────────────┘
```

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

- `CONFIG_PATH`: Path to configuration file
- `MODEL_PATH`: Path to YOLOv8 model
- `RECORDINGS_DIR`: Directory for recordings
- `LOG_LEVEL`: Logging level
- `API_HOST`: API server host
- `API_PORT`: API server port

---

## Monitoring and Observability

### Metrics to Track

1. **Performance Metrics**
   - Processing FPS
   - Detection latency
   - Memory usage
   - CPU usage
   - GPU usage (if available)

2. **System Metrics**
   - Uptime
   - Active connections
   - Total recordings
   - Storage usage
   - Error rate

3. **Business Metrics**
   - Unauthorized access events
   - Detection accuracy
   - False positive rate
   - Alert frequency

### Logging Strategy

- **Structured Logging**: JSON format
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Log Rotation**: Daily rotation
- **Centralized Logging**: Optional (ELK, Splunk)

### Health Checks

- **Liveness Probe**: `/api/health`
- **Readiness Probe**: `/api/ready`
- **Startup Probe**: Check initialization

---

## Future Enhancements

### Planned Features

1. **Multi-Camera Support**
   - Multiple video sources
   - Camera management
   - Synchronized recording

2. **Cloud Integration**
   - Cloud storage for recordings
   - Cloud-based processing
   - Remote access

3. **Advanced Analytics**
   - Detection statistics
   - Trend analysis
   - Anomaly detection

4. **Machine Learning Improvements**
   - Custom model training
   - Transfer learning
   - Model optimization

5. **Notification System**
   - Email notifications
   - SMS alerts
   - Push notifications

6. **User Management**
   - Multi-user support
   - Role-based access
   - User authentication

---

## Document Version

- **Version**: 1.0
- **Last Updated**: 2024-12-21
- **Author**: Architecture Team













