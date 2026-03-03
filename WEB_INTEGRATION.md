# Web Interface Integration Guide

This document describes how to integrate the Smart Security Camera System backend with a web interface.

## Architecture Overview

The system consists of:
- **Backend API Server** (`api_server.py`): FastAPI-based RESTful API and WebSocket server
- **Core Components**: Object detection, security monitoring, and video recording
- **Web Interface**: Frontend application (to be implemented)

## API Endpoints

### REST API Endpoints

#### 1. System Status
```
GET /api/status
```
Returns current system status including monitoring state, recording status, and active connections.

**Response:**
```json
{
  "status": "running",
  "monitoring": {
    "monitoring": true,
    "unauthorized_classes": ["person", "car"],
    "detection_duration_threshold": 2.0,
    "min_objects": 1
  },
  "recording": false,
  "active_connections": 2
}
```

#### 2. Start/Stop Monitoring
```
POST /api/start
POST /api/stop
```
Start or stop the video monitoring system.

**Response:**
```json
{
  "message": "Monitoring started",
  "status": "running"
}
```

#### 3. Configuration Management
```
GET /api/config
PUT /api/config
```
Get or update system configuration.

**Update Request Body:**
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

#### 4. Video Recordings
```
GET /api/recordings
GET /api/recordings/{filename}
GET /api/recordings/{filename}/metadata
```
List all recordings, download a recording, or get metadata for a recording.

**List Response:**
```json
{
  "recordings": [
    {
      "filename": "unauthorized_access_20240101_120000.mp4",
      "path": "recordings/unauthorized_access_20240101_120000.mp4",
      "size": 1048576,
      "created": "2024-01-01T12:00:00",
      "modified": "2024-01-01T12:00:00"
    }
  ]
}
```

#### 5. Video Stream
```
GET /api/stream
```
MJPEG video stream endpoint for displaying live video feed in the browser.

**Usage in HTML:**
```html
<img src="http://localhost:8000/api/stream" alt="Live Stream" />
```

### WebSocket Endpoint

#### Real-time Updates
```
WS /ws
```
WebSocket connection for real-time status updates.

**Message Format:**
```json
{
  "status": "running",
  "timestamp": 1704110400.0,
  "monitoring": {
    "monitoring": true,
    "current_detections": 2
  },
  "recording": false
}
```

## Frontend Integration Examples

### 1. React Component Example

```jsx
import React, { useEffect, useState } from 'react';

function SecurityCameraDashboard() {
  const [status, setStatus] = useState(null);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [recordings, setRecordings] = useState([]);

  // Fetch system status
  useEffect(() => {
    fetch('http://localhost:8000/api/status')
      .then(res => res.json())
      .then(data => {
        setStatus(data);
        setIsMonitoring(data.status === 'running');
      });
  }, []);

  // WebSocket connection for real-time updates
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data);
    };

    return () => ws.close();
  }, []);

  // Start/Stop monitoring
  const toggleMonitoring = async () => {
    const endpoint = isMonitoring ? '/api/stop' : '/api/start';
    const response = await fetch(`http://localhost:8000${endpoint}`, {
      method: 'POST'
    });
    const data = await response.json();
    setIsMonitoring(data.status === 'running');
  };

  // Fetch recordings
  useEffect(() => {
    fetch('http://localhost:8000/api/recordings')
      .then(res => res.json())
      .then(data => setRecordings(data.recordings));
  }, []);

  return (
    <div className="dashboard">
      <h1>Security Camera Dashboard</h1>
      
      <div className="controls">
        <button onClick={toggleMonitoring}>
          {isMonitoring ? 'Stop' : 'Start'} Monitoring
        </button>
      </div>

      <div className="video-stream">
        <img 
          src="http://localhost:8000/api/stream" 
          alt="Live Stream"
          style={{ maxWidth: '100%' }}
        />
      </div>

      <div className="status">
        <h2>Status</h2>
        <pre>{JSON.stringify(status, null, 2)}</pre>
      </div>

      <div className="recordings">
        <h2>Recordings</h2>
        <ul>
          {recordings.map(rec => (
            <li key={rec.filename}>
              <a href={`http://localhost:8000/api/recordings/${rec.filename}`}>
                {rec.filename} - {rec.created}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default SecurityCameraDashboard;
```

### 2. HTML/JavaScript Example

```html
<!DOCTYPE html>
<html>
<head>
    <title>Security Camera Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .video-stream { margin: 20px 0; }
        .controls { margin: 20px 0; }
        button { padding: 10px 20px; font-size: 16px; }
        .status { background: #f5f5f5; padding: 15px; border-radius: 5px; }
        .recordings { margin-top: 20px; }
        .recording-item { margin: 10px 0; padding: 10px; background: #fff; border: 1px solid #ddd; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Security Camera Dashboard</h1>
        
        <div class="controls">
            <button id="toggleBtn" onclick="toggleMonitoring()">Start Monitoring</button>
        </div>

        <div class="video-stream">
            <img id="stream" src="http://localhost:8000/api/stream" alt="Live Stream" />
        </div>

        <div class="status" id="status">
            <h2>Status</h2>
            <pre id="statusText">Loading...</pre>
        </div>

        <div class="recordings">
            <h2>Recordings</h2>
            <div id="recordingsList">Loading...</div>
        </div>
    </div>

    <script>
        let isMonitoring = false;

        // WebSocket connection
        const ws = new WebSocket('ws://localhost:8000/ws');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            updateStatus(data);
            isMonitoring = data.status === 'running';
            updateButton();
        };

        // Fetch initial status
        fetch('http://localhost:8000/api/status')
            .then(res => res.json())
            .then(data => {
                updateStatus(data);
                isMonitoring = data.status === 'running';
                updateButton();
            });

        // Fetch recordings
        function loadRecordings() {
            fetch('http://localhost:8000/api/recordings')
                .then(res => res.json())
                .then(data => {
                    const list = document.getElementById('recordingsList');
                    list.innerHTML = data.recordings.map(rec => `
                        <div class="recording-item">
                            <a href="http://localhost:8000/api/recordings/${rec.filename}">
                                ${rec.filename}
                            </a>
                            <span> - ${rec.created}</span>
                        </div>
                    `).join('');
                });
        }

        function updateStatus(data) {
            document.getElementById('statusText').textContent = JSON.stringify(data, null, 2);
        }

        function updateButton() {
            const btn = document.getElementById('toggleBtn');
            btn.textContent = isMonitoring ? 'Stop Monitoring' : 'Start Monitoring';
        }

        async function toggleMonitoring() {
            const endpoint = isMonitoring ? '/api/stop' : '/api/start';
            const response = await fetch(`http://localhost:8000${endpoint}`, {
                method: 'POST'
            });
            const data = await response.json();
            isMonitoring = data.status === 'running';
            updateButton();
        }

        // Load recordings on page load
        loadRecordings();
        setInterval(loadRecordings, 30000); // Refresh every 30 seconds
    </script>
</body>
</html>
```

### 3. Vue.js Component Example

```vue
<template>
  <div class="dashboard">
    <h1>Security Camera Dashboard</h1>
    
    <div class="controls">
      <button @click="toggleMonitoring">
        {{ isMonitoring ? 'Stop' : 'Start' }} Monitoring
      </button>
    </div>

    <div class="video-stream">
      <img :src="streamUrl" alt="Live Stream" />
    </div>

    <div class="status">
      <h2>Status</h2>
      <pre>{{ JSON.stringify(status, null, 2) }}</pre>
    </div>

    <div class="recordings">
      <h2>Recordings</h2>
      <div v-for="rec in recordings" :key="rec.filename" class="recording-item">
        <a :href="`${apiUrl}/api/recordings/${rec.filename}`">
          {{ rec.filename }} - {{ rec.created }}
        </a>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      apiUrl: 'http://localhost:8000',
      streamUrl: 'http://localhost:8000/api/stream',
      status: null,
      isMonitoring: false,
      recordings: [],
      ws: null
    };
  },
  mounted() {
    this.fetchStatus();
    this.fetchRecordings();
    this.connectWebSocket();
    setInterval(this.fetchRecordings, 30000);
  },
  beforeUnmount() {
    if (this.ws) {
      this.ws.close();
    }
  },
  methods: {
    async fetchStatus() {
      const response = await fetch(`${this.apiUrl}/api/status`);
      const data = await response.json();
      this.status = data;
      this.isMonitoring = data.status === 'running';
    },
    async fetchRecordings() {
      const response = await fetch(`${this.apiUrl}/api/recordings`);
      const data = await response.json();
      this.recordings = data.recordings;
    },
    connectWebSocket() {
      this.ws = new WebSocket(`ws://localhost:8000/ws`);
      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        this.status = data;
        this.isMonitoring = data.status === 'running';
      };
    },
    async toggleMonitoring() {
      const endpoint = this.isMonitoring ? '/api/stop' : '/api/start';
      const response = await fetch(`${this.apiUrl}${endpoint}`, {
        method: 'POST'
      });
      const data = await response.json();
      this.isMonitoring = data.status === 'running';
    }
  }
};
</script>
```

## Integration Points

### 1. Live Video Stream
- Use the `/api/stream` endpoint to display live video feed
- Supports MJPEG format, can be embedded in `<img>` tag
- Updates automatically in real-time

### 2. Real-time Status Updates
- Connect to WebSocket endpoint `/ws` for live status updates
- Receives periodic updates about system state, detections, and alerts
- Can trigger UI notifications when unauthorized access is detected

### 3. Configuration Management
- Use `GET /api/config` to load current settings
- Use `PUT /api/config` to update settings (e.g., confidence thresholds, detection rules)
- Changes take effect immediately after update

### 4. Recording Management
- List all recordings with `GET /api/recordings`
- Download recordings via `GET /api/recordings/{filename}`
- Access metadata (detections, timestamps, etc.) via `GET /api/recordings/{filename}/metadata`
- Display recordings in a gallery or timeline view

### 5. Alert Notifications
- Monitor WebSocket messages for `recording: true` status
- Display alerts when unauthorized access is detected
- Link alerts to corresponding video recordings

## Security Considerations

1. **CORS Configuration**: Update CORS settings in `api_server.py` for production:
   ```python
   allow_origins=["https://yourdomain.com"]  # Instead of ["*"]
   ```

2. **Authentication**: Add authentication middleware for production use:
   ```python
   from fastapi import Depends, HTTPException, status
   from fastapi.security import HTTPBearer
   
   security = HTTPBearer()
   
   @app.get("/api/status")
   async def get_status(token: str = Depends(security)):
       # Verify token
       pass
   ```

3. **HTTPS**: Use HTTPS in production for secure communication

4. **Rate Limiting**: Implement rate limiting to prevent abuse

## Deployment

### Backend Deployment
```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn api_server:app --host 0.0.0.0 --port 8000

# Or with gunicorn for production
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api_server:app
```

### Frontend Deployment
- Build your frontend application
- Serve static files with nginx or similar
- Configure reverse proxy to backend API
- Enable WebSocket support in nginx configuration

### Docker Deployment (Optional)
Create a `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Testing

Test the API endpoints using curl or Postman:

```bash
# Get status
curl http://localhost:8000/api/status

# Start monitoring
curl -X POST http://localhost:8000/api/start

# Get recordings
curl http://localhost:8000/api/recordings

# Update config
curl -X PUT http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"detection": {"confidence_threshold": 0.6}}'
```

## Next Steps

1. Implement frontend UI with your preferred framework
2. Add user authentication and authorization
3. Implement notification system (email, SMS, push notifications)
4. Add analytics dashboard for detection statistics
5. Implement mobile app for remote monitoring
6. Add cloud storage integration for recordings
7. Implement multi-camera support


