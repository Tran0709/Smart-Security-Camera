# Quick Start Guide
## Smart Security Camera System

This guide will help you get the platform running quickly.

---

## Prerequisites

✅ Python 3.8 or higher (You have Python 3.10.3)
✅ All dependencies installed (Already installed)

---

## Running the Platform

You have two options to run the system:

### Option 1: Command-Line Interface (CLI)

This runs the system directly with a display window.

#### Using Webcam (Recommended for first test)

```bash
python main.py --source 0 --display
```

This will:
- Use your default webcam (camera index 0)
- Display the video feed with detections
- Record videos when unauthorized access is detected
- Save recordings to the `recordings/` folder

#### Using a Video File

```bash
python main.py --source sample.mp4 --display
```

#### Using a Test Image

```bash
python main.py --source sample.png --display
```

#### Command-Line Options

- `--source`: Video source (0 for webcam, or path to file)
- `--display`: Show video window with detections
- `--config`: Path to config file (default: config.json)
- `--loop-video`: Loop video file continuously
- `--save-images`: Save annotated images

---

### Option 2: Web API Server

This runs the system as a web server that you can access via browser or API.

#### Start the API Server

```bash
python api_server.py
```

The server will start at: `http://localhost:8000`

#### Access the API

- **API Documentation**: http://localhost:8000/docs (Interactive Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc
- **Status Endpoint**: http://localhost:8000/api/status
- **Live Stream**: http://localhost:8000/api/stream (MJPEG stream)

#### API Usage

1. **Start Monitoring**:
   ```bash
   curl -X POST http://localhost:8000/api/start
   ```

2. **Check Status**:
   ```bash
   curl http://localhost:8000/api/status
   ```

3. **View Live Stream**:
   Open in browser: http://localhost:8000/api/stream

4. **List Recordings**:
   ```bash
   curl http://localhost:8000/api/recordings
   ```

5. **Stop Monitoring**:
   ```bash
   curl -X POST http://localhost:8000/api/stop
   ```

---

## First Run Checklist

1. ✅ **Check Python version**: `python --version` (You have 3.10.3)
2. ✅ **Dependencies installed**: Already installed
3. ✅ **Model file exists**: `yolov8n.pt` is present
4. ✅ **Config file exists**: `config.json` is present

---

## Troubleshooting

### Issue: "No module named 'ultralytics'"
**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

### Issue: "Cannot open camera"
**Solution**: 
- Check if webcam is connected
- Try different camera index: `python main.py --source 1 --display`
- Use a video file instead: `python main.py --source sample.mp4 --display`

### Issue: "Model file not found"
**Solution**: The YOLOv8 model will be downloaded automatically on first run. Make sure you have internet connection.

### Issue: "Port 8000 already in use" (API Server)
**Solution**: 
- Stop the other application using port 8000
- Or modify the port in `api_server.py`

### Issue: Low FPS / Slow Performance
**Solution**:
- Reduce video resolution in `config.json`
- Use GPU acceleration (if available)
- Lower confidence threshold in `config.json`

---

## Configuration

Edit `config.json` to customize:

- **Detection Settings**: Confidence threshold, monitored classes
- **Security Rules**: Detection duration, minimum objects
- **Recording Settings**: Buffer times, FPS, codec
- **Video Source**: Camera index, resolution

---

## Next Steps

1. **Run the CLI version** to test with your webcam
2. **Run the API server** to access via web interface
3. **Check recordings** in the `recordings/` folder
4. **Review design docs**: See `DESIGN_SPECIFICATIONS.md`, `WIREFRAMES.md`, `ARCHITECTURE.md`

---

## Need Help?

- Check the main `README.md` for detailed usage
- Review `WEB_INTEGRATION.md` for API integration
- See design documents for system architecture

---

Happy monitoring! 🎥













