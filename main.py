"""
Main Application Entry Point
Smart Security Camera System with YOLOv8 object detection.

This is the main command-line interface for the security camera system.
It supports multiple input sources:
- Live camera feeds (USB/webcam)
- Video files (MP4, AVI, etc.)
- Single image files
- Directories of images

The application processes video frames in real-time, detects objects using
YOLOv8, monitors for unauthorized access, and records video segments when
security events are detected.

Usage Examples:
    # Process live camera feed
    python main.py --source 0 --display
    
    # Process video file
    python main.py --source sample.mp4 --display
    
    # Process single image
    python main.py --source sample.png
    
    # Process directory of images
    python main.py --source ./images/
"""

# Computer vision library for video/image processing
import cv2

# Command-line argument parsing
import argparse

# JSON configuration file handling
import json

# Time tracking for FPS calculation and timestamps
import time

# File system operations
import os

# File pattern matching for directory processing
import glob

# Path manipulation utilities
from pathlib import Path

# Local module imports - core system components
from detector import ObjectDetector  # Object detection using YOLOv8
from security_monitor import SecurityMonitor  # Security event monitoring
from video_recorder import VideoRecorder  # Video recording management


# ============================================================================
# Configuration Management
# ============================================================================

def load_config(config_path: str = "config.json") -> dict:
    """
    Load system configuration from a JSON file.
    
    This function reads the configuration file containing all system settings
    including detection parameters, security rules, recording settings, and
    video source configuration. If the file doesn't exist, the system will
    use default values from individual components.
    
    Args:
        config_path: Path to the configuration JSON file
                    Default: "config.json" in current directory
                    
    Returns:
        Dictionary containing configuration settings, or empty dict if file not found
        
    Note:
        An empty dictionary is returned if the file doesn't exist, allowing
        the system to use default values. A warning message is printed.
    """
    try:
        # Open and parse JSON configuration file
        # Using 'r' mode explicitly for clarity (text mode, read-only)
        # The 'with' statement ensures the file is properly closed even if an error occurs
        with open(config_path, 'r') as f:
            # json.load() parses the entire JSON structure into a Python dictionary
            # This includes nested dictionaries and lists from the config file
            return json.load(f)
    except FileNotFoundError:
        # File doesn't exist - print warning and return empty dict
        # This graceful degradation allows the system to run with sensible defaults
        # rather than crashing immediately. Each component will check for its config
        # and use built-in defaults if not found in the dictionary.
        # System components will use their default values
        print(f"Config file {config_path} not found. Using defaults.")
        return {}
    # Note: We don't catch JSONDecodeError here because if the file exists but is
    # malformed, it's better to let the exception propagate so the user knows
    # there's a problem with their configuration file


# ============================================================================
# File Type Detection Utilities
# ============================================================================

def is_image_file(filepath: str) -> bool:
    """
    Check if a file path points to an image file based on its extension.
    
    This function examines the file extension to determine if it's a
    supported image format. The check is case-insensitive.
    
    Args:
        filepath: Path to the file to check
        
    Returns:
        True if the file has an image extension, False otherwise
        
    Supported Formats:
        JPG, JPEG, PNG, BMP, TIFF, TIF, WEBP, GIF
    """
    # Set of supported image file extensions (lowercase for comparison)
    # Using a set for O(1) lookup performance instead of O(n) list search
    # This is more efficient when checking many files in batch processing
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.gif'}
    
    # Get file extension using Path.suffix which extracts the last extension
    # (handles cases like "file.tar.gz" correctly - returns ".gz")
    # Convert to lowercase for case-insensitive comparison
    # Check membership in the set (fast lookup)
    # Note: This doesn't verify the file actually exists or is a valid image,
    # it only checks the extension. Actual validation happens when cv2.imread() is called
    return Path(filepath).suffix.lower() in image_extensions


def is_video_file(filepath: str) -> bool:
    """
    Check if a file path points to a video file based on its extension.
    
    This function examines the file extension to determine if it's a
    supported video format. The check is case-insensitive.
    
    Args:
        filepath: Path to the file to check
        
    Returns:
        True if the file has a video extension, False otherwise
        
    Supported Formats:
        MP4, AVI, MOV, MKV, FLV, WMV, WEBM, M4V
    """
    # Set of supported video file extensions (lowercase for comparison)
    # These formats are commonly supported by OpenCV's VideoCapture
    # Note: Codec support depends on system-installed codecs, not just extension
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
    
    # Get file extension, convert to lowercase, and check if in supported set
    # Similar to is_image_file(), this is a fast extension-based check
    # Actual codec validation happens when cv2.VideoCapture() attempts to open the file
    return Path(filepath).suffix.lower() in video_extensions


# ============================================================================
# Image Processing Functions
# ============================================================================

def process_image(image_path: str, detector: ObjectDetector, config: dict, save_output: bool = True):
    """
    Process a single image file for object detection.
    
    This function loads an image, runs object detection on it, annotates
    the image with detection boxes and labels, and optionally saves the
    annotated result. It's useful for batch processing or testing detection
    on specific images.
    
    Args:
        image_path: Path to the image file to process
        detector: ObjectDetector instance for object detection
        config: Configuration dictionary containing detection settings
        save_output: If True, save annotated image to detected_images/ directory
                    Default: True
                    
    Returns:
        Tuple of (annotated_frame, filtered_detections):
        - annotated_frame: Image with detection annotations drawn
        - filtered_detections: List of detection dictionaries
        
    Note:
        If the image cannot be read, the function returns early without
        processing. Detection results are printed to console.
    """
    print(f"Processing image: {image_path}")
    
    # Read image file using OpenCV
    # cv2.imread returns None if file cannot be read (corrupted, wrong format, missing file)
    # OpenCV reads images in BGR format (Blue-Green-Red) by default, which is different
    # from the standard RGB format used by most image libraries
    frame = cv2.imread(image_path)
    if frame is None:
        # Early return pattern: exit immediately if image can't be loaded
        # This prevents downstream errors and provides clear feedback to the user
        print(f"Error: Could not read image {image_path}")
        print("  Possible reasons: file doesn't exist, corrupted file, or unsupported format")
        return
    
    # Get list of classes to monitor from configuration
    # Using nested .get() calls with default empty list to safely access nested dict
    # This prevents KeyError if 'detection' or 'monitored_classes' keys don't exist
    # Only these classes will be included in results - all other detections are filtered out
    monitored_classes = config.get('detection', {}).get('monitored_classes', [])
    
    # Step 1: Detect all objects in the image using YOLOv8
    # This runs the neural network inference on the entire frame
    # Returns a list of all detected objects with their bounding boxes, classes, and confidence scores
    # Note: This may detect objects not in monitored_classes - filtering happens next
    detections = detector.detect(frame)
    
    # Step 2: Filter detections to only include monitored classes
    # This removes unwanted detections (e.g., if only monitoring "person" and "car")
    # Filtering happens after detection to allow flexibility - you can change monitored
    # classes without re-running the expensive detection step
    filtered_detections = detector.filter_by_classes(detections, monitored_classes)
    
    # Step 3: Annotate frame with detection boxes and labels
    # This draws bounding boxes and class names on the image
    # The annotation creates a COPY of the frame, so the original is preserved
    # This is important if you need the original frame for other processing
    annotated_frame = detector.annotate_frame(frame, filtered_detections)
    
    # Print detection results to console
    # Provides immediate feedback about what was found in the image
    print(f"\nDetections found: {len(filtered_detections)}")
    for det in filtered_detections:
        # Print each detection with class name and confidence score
        # Confidence is formatted to 2 decimal places for readability
        # This helps users understand detection quality (higher = more confident)
        print(f"  - {det['class']}: {det['confidence']:.2f}")
    
    # Step 4: Save annotated image if requested
    # This allows users to review detection results later without re-running detection
    if save_output:
        # Create output directory if it doesn't exist
        # exist_ok=True prevents errors if directory already exists
        # Using Path object for cross-platform path handling (Windows/Unix compatible)
        output_dir = Path("detected_images")
        output_dir.mkdir(exist_ok=True)
        
        # Generate output filename based on input filename
        # .stem extracts filename without extension (e.g., "photo.jpg" -> "photo")
        # We append "_detected" to distinguish from original and save as .jpg
        # e.g., "photo.jpg" -> "photo_detected.jpg"
        input_name = Path(image_path).stem  # Get filename without extension
        output_path = output_dir / f"{input_name}_detected.jpg"
        
        # Save annotated image to file
        # cv2.imwrite requires string path, so we convert Path object to string
        # Returns True on success, False on failure (but we don't check here for simplicity)
        cv2.imwrite(str(output_path), annotated_frame)
        print(f"Saved annotated image to: {output_path}")
    
    return annotated_frame, filtered_detections


def process_images_directory(directory: str, detector: ObjectDetector, config: dict):
    """
    Process all image files in a directory.
    
    This function scans a directory for image files and processes each one
    using the process_image() function. It supports both lowercase and
    uppercase file extensions. Useful for batch processing multiple images.
    
    Args:
        directory: Path to directory containing image files
        detector: ObjectDetector instance for object detection
        config: Configuration dictionary containing detection settings
        
    Note:
        The function searches for common image formats and processes them
        sequentially. If no images are found, a message is printed and
        the function returns early.
    """
    # List of image file extensions to search for (with wildcard)
    # The '*' wildcard matches any filename, so '*.jpg' matches all .jpg files
    # Note: We don't include .gif here because animated GIFs need special handling
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.tif', '*.webp']
    image_files = []  # Accumulator list to collect all found image files
    
    # Search for images with both lowercase and uppercase extensions
    # This ensures we find files regardless of case (e.g., .JPG and .jpg)
    # Some file systems (like Windows) are case-insensitive, but others (like Linux) are not
    # This approach works on all systems and handles both cases gracefully
    for ext in image_extensions:
        # Search for lowercase extension using glob pattern matching
        # glob.glob() returns a list of matching file paths
        # os.path.join() ensures proper path separator for the current OS
        image_files.extend(glob.glob(os.path.join(directory, ext)))
        # Search for uppercase extension to catch files like "IMAGE.JPG"
        # .upper() converts the entire pattern, so '*.jpg' becomes '*.JPG'
        image_files.extend(glob.glob(os.path.join(directory, ext.upper())))
    
    # Check if any images were found
    # Early return pattern: if no images, inform user and exit gracefully
    # This prevents unnecessary processing and provides clear feedback
    if not image_files:
        print(f"No image files found in {directory}")
        print(f"  Searched for: {', '.join(image_extensions)}")
        return
    
    # Print summary of files to process
    # This gives users an idea of how long batch processing might take
    # The count helps verify that all expected images were found
    print(f"Found {len(image_files)} image(s) to process")
    
    # Process each image file sequentially
    # Sequential processing is simpler and uses less memory than parallel processing
    # For large batches, this could be optimized with multiprocessing, but for most
    # use cases, sequential is fine and easier to debug
    for image_path in image_files:
        # Process each image through the detection pipeline
        # Errors in one image don't stop processing of remaining images
        process_image(image_path, detector, config)
        print()  # Empty line between images for readability in console output


def main():
    """
    Main application entry point.
    
    This function sets up the command-line interface, initializes system
    components, and processes the specified video/image source. It handles
    different input types (camera, video file, image, directory) and runs
    the appropriate processing pipeline.
    
    The function supports:
    - Live camera feeds with real-time detection and monitoring
    - Video file processing with optional looping
    - Single image processing
    - Batch image directory processing
    
    Command-line Arguments:
        --source: Video/image source (camera index, file path, or directory)
        --config: Path to configuration file
        --display: Show video feed in window (for video/camera sources)
        --save-images: Save annotated images when processing images
        --loop-video: Loop video file when it ends
    """
    # ========================================================================
    # Command-Line Argument Parsing
    # ========================================================================
    
    # Create argument parser with program description
    # argparse provides automatic help generation and type checking
    # The description appears when users run: python main.py --help
    parser = argparse.ArgumentParser(description='Smart Security Camera System')
    
    # Define command-line arguments
    # --source: Flexible input handling - can be camera index, file, or directory
    # Default '0' means first available camera, which is the most common use case
    # Type is str to allow both numeric strings ("0") and file paths
    parser.add_argument('--source', type=str, default='0',
                       help='Video source: camera index (0, 1, etc.), video file path, image file path, or directory path')
    
    # --config: Allows users to specify different config files for different scenarios
    # Useful for testing, different environments, or multiple camera setups
    parser.add_argument('--config', type=str, default='config.json',
                       help='Path to configuration file')
    
    # --display: Optional flag to show video feed in a window
    # action='store_true' means the flag is False by default, True if present
    # Useful for headless servers or when you only want to save recordings
    parser.add_argument('--display', action='store_true',
                       help='Display video feed in window')
    
    # --save-images: Controls whether annotated images are saved to disk
    # default=True means images are saved by default (most users want this)
    # Can be disabled with --no-save-images if using argparse's store_false
    parser.add_argument('--save-images', action='store_true', default=True,
                       help='Save annotated images when processing images (default: True)')
    
    # --loop-video: Makes video files restart from beginning when they end
    # Useful for continuous monitoring or testing with the same video repeatedly
    parser.add_argument('--loop-video', action='store_true',
                       help='Loop video file when it ends')
    
    # Parse command-line arguments
    # This reads sys.argv automatically and populates the args object
    # Raises SystemExit with error message if invalid arguments are provided
    args = parser.parse_args()
    
    # ========================================================================
    # System Initialization
    # ========================================================================
    
    # Load system configuration from file
    # This happens early so all components can access configuration
    # If config file is missing, returns empty dict and components use defaults
    config = load_config(args.config)
    
    # Extract detection configuration section
    # Using .get() with default empty dict prevents KeyError if section is missing
    # This makes the system more resilient to incomplete configuration files
    detection_config = config.get('detection', {})
    
    # Initialize object detector with YOLOv8 model
    # This is the most expensive initialization step - loads the neural network weights
    # Model loading can take a few seconds, especially on first run (downloads model if needed)
    # Uses model path and confidence threshold from config, or sensible defaults
    # The nano model (yolov8n.pt) is the smallest and fastest, good for real-time processing
    detector = ObjectDetector(
        model_path=detection_config.get('model', 'yolov8n.pt'),  # Default to nano model (fastest)
        confidence_threshold=detection_config.get('confidence_threshold', 0.5)  # Default 50% confidence
    )
    
    # Get list of object classes to monitor from configuration
    # This is a whitelist approach - only these classes will be included in results
    # Empty list means all detected classes are included (no filtering)
    # This filtering happens after detection to maintain flexibility
    monitored_classes = detection_config.get('monitored_classes', [])
    
    # Store source path for processing
    # We keep the original string to check if it's a file/directory later
    # The source will be parsed differently depending on its type
    source_path = args.source
    
    # ========================================================================
    # Input Source Type Detection and Routing
    # ========================================================================
    # The system supports multiple input types, so we need to detect which one
    # the user provided and route to the appropriate processing pipeline.
    # Order matters: check image file before directory (a file path could
    # theoretically match a directory name, but os.path.isfile() is more specific)
    
    # Check if source is a single image file
    # os.path.isfile() checks if path exists AND is a file (not directory)
    # is_image_file() checks if the extension is a supported image format
    # Both checks are needed: a file might exist but not be an image
    if os.path.isfile(source_path) and is_image_file(source_path):
        # Process single image file
        # This is a one-shot operation - no loop needed, just process and exit
        print("=" * 60)
        print("Processing Single Image")
        print("=" * 60)
        process_image(source_path, detector, config, args.save_images)
        
        # If display flag is set, show annotated image in window
        # This is separate from process_image() because we want to show the
        # annotated version, not the original
        if args.display:
            # Reload image for display (process_image may have modified it)
            # Actually, process_image returns annotated frame, but we reload for clarity
            frame = cv2.imread(source_path)
            # Detect objects (re-running detection for display)
            # Could optimize by reusing results from process_image(), but this is simpler
            detections = detector.detect(frame)
            # Filter to monitored classes (same filtering as in process_image)
            filtered_detections = detector.filter_by_classes(detections, monitored_classes)
            # Annotate frame with detections (draws boxes and labels)
            annotated_frame = detector.annotate_frame(frame, filtered_detections)
            # Display in window with a descriptive title
            cv2.imshow('Detected Objects', annotated_frame)
            print("Press any key to close...")
            # Wait for key press (0 = wait indefinitely until key is pressed)
            # This keeps the window open so user can examine the results
            cv2.waitKey(0)
            # Close all OpenCV windows to free resources
            # Important on systems with limited window handles
            cv2.destroyAllWindows()
        return  # Early return - image processing is complete
    
    # Check if source is a directory of images
    # os.path.isdir() checks if path exists AND is a directory
    # This handles batch processing of multiple images in a folder
    if os.path.isdir(source_path):
        # Process all images in directory
        # This is useful for processing security camera snapshots or batch analysis
        print("=" * 60)
        print("Processing Image Directory")
        print("=" * 60)
        process_images_directory(source_path, detector, config)
        return  # Early return - directory processing is complete
    
    # ========================================================================
    # Video Source Processing (Camera or Video File)
    # ========================================================================
    # If we reach here, the source is either a camera index or a video file
    # (image files and directories were handled above with early returns)
    
    # Parse video source - try to interpret as camera index (integer)
    # This is a "try-except" pattern for type detection
    # If conversion to int succeeds, it's a camera index (0, 1, 2, etc.)
    # If it fails with ValueError, it's a file path (string)
    # This approach is simpler than regex or other string parsing methods
    try:
        video_source = int(source_path)  # Camera index (0, 1, 2, etc.)
        # Camera index 0 is typically the default/built-in camera
        # Higher indices (1, 2, etc.) are USB cameras or additional devices
    except ValueError:
        video_source = source_path  # File path (string)
        # Could be absolute path (C:\videos\test.mp4) or relative (./test.mp4)
    
    # Initialize security monitoring components (only needed for video)
    # These components track events over time, which doesn't make sense for static images
    # SecurityMonitor: Tracks detection duration, applies rules, determines alerts
    # VideoRecorder: Manages video buffering and saves recordings when events occur
    # These are initialized here (not earlier) to avoid unnecessary overhead for image processing
    security_monitor = SecurityMonitor(config)  # Monitors for unauthorized access
    video_recorder = VideoRecorder(config)  # Records video segments on events
    
    # Initialize video capture from source
    # OpenCV VideoCapture is polymorphic - it accepts both:
    #   - Integer: Camera device index (0, 1, 2, etc.)
    #   - String: File path to video file
    # This single interface handles both cases elegantly
    cap = cv2.VideoCapture(video_source)
    
    # Verify video source was successfully opened
    # cap.isOpened() returns False if:
    #   - Camera index doesn't exist (e.g., --source 99 when only 0 cameras available)
    #   - Video file doesn't exist or is corrupted
    #   - Video codec is not supported
    #   - Insufficient permissions to access camera
    if not cap.isOpened():
        print(f"Error: Could not open video source {video_source}")
        print("\nTips:")
        print("  - For camera: use --source 0 (or 1, 2, etc. for different cameras)")
        print("  - For video file: use --source path/to/video.mp4")
        print("  - For image: use --source path/to/image.jpg")
        print("  - For image directory: use --source path/to/images/")
        return  # Can't proceed without a valid video source
    
    # Configure camera properties (only for live cameras, not video files)
    # Video files have fixed resolution, but cameras can be configured
    # isinstance() check ensures we only try to configure actual camera devices
    if isinstance(video_source, int):
        # Get video resolution from configuration
        # These settings only apply to live cameras, not video files
        video_config = config.get('video', {})
        width = video_config.get('width', 640)   # Default width: 640 pixels (VGA)
        height = video_config.get('height', 480)  # Default height: 480 pixels (VGA)
        
        # Set camera resolution
        # Note: Actual resolution depends on camera capabilities
        # The camera may not support the requested resolution and will use closest match
        # Some cameras have fixed resolutions and ignore these settings
        # Lower resolution = faster processing but less detail
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    # Get source frame rate (from video file or camera)
    # This is the native frame rate of the source, not the processing FPS
    # For video files, this is the frame rate at which the video was recorded
    # For cameras, this is the camera's capture frame rate capability
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    # OpenCV may return 0.0 if frame rate cannot be determined
    # This is common for some cameras or video files without proper metadata
    if source_fps <= 0:
        source_fps = None  # Mark as unknown
    
    # Get actual resolution from source (may differ from requested for cameras)
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # ========================================================================
    # Display System Information
    # ========================================================================
    
    # Print system configuration and status
    print("=" * 60)
    print("Smart Security Camera System")
    print("=" * 60)
    print(f"Video Source: {video_source}")
    print(f"Resolution: {actual_width}x{actual_height}")
    if source_fps is not None:
        print(f"Source Frame Rate: {source_fps:.2f} FPS")
    else:
        print("Source Frame Rate: Unknown (will be measured during processing)")
    print(f"Model: {detection_config.get('model', 'yolov8n.pt')}")
    print(f"Monitored Classes: {len(monitored_classes)} classes")
    print(f"Unauthorized Classes: {len(detection_config.get('unauthorized_classes', []))} classes")
    if isinstance(video_source, str):
        print(f"Video File: {os.path.basename(video_source)}")
    print("=" * 60)
    print("Press 'q' to quit")
    print("Processing FPS will be displayed on screen and in console")
    print()
    
    # ========================================================================
    # Main Processing Loop
    # ========================================================================
    # This is the core real-time processing loop that runs continuously
    # until the video ends, user presses 'q', or an error occurs.
    # Each iteration processes one frame through the complete pipeline:
    #   1. Read frame from source
    #   2. Detect objects
    #   3. Filter by monitored classes
    #   4. Check security rules
    #   5. Record video if needed
    #   6. Display annotated frame (optional)
    
    # Initialize frame counter and timing for FPS calculation
    # frame_count: Tracks total frames processed (useful for statistics and debugging)
    # start_time: Used to calculate elapsed time for FPS (frames per second) calculation
    # FPS is important for performance monitoring - low FPS means the system is struggling
    frame_count = 0
    start_time = time.time()  # Unix timestamp when processing started
    
    try:
        # Main video processing loop - continues until interrupted or video ends
        # This is an infinite loop that breaks on specific conditions:
        #   - Video file ends (if not looping)
        #   - User presses 'q' key (if display enabled)
        #   - Camera read error
        #   - Keyboard interrupt (Ctrl+C)
        while True:
            # Read next frame from video source
            # cap.read() returns a tuple: (success_flag, frame_array)
            #   - ret (return value): True if frame was read successfully, False otherwise
            #   - frame: numpy array containing the image data in BGR format
            #     Shape is (height, width, 3) where 3 = Blue, Green, Red channels
            ret, frame = cap.read()
            
            # Check if frame was successfully read
            # ret is False when:
            #   - Video file has reached the end
            #   - Camera is disconnected or has an error
            #   - Video file is corrupted or codec issue
            if not ret:
                # Handle end of video file with optional looping
                # Different behavior for video files vs cameras
                if isinstance(video_source, str) and args.loop_video:
                    # Video file ended - restart from beginning
                    # This creates a continuous loop for testing or monitoring
                    print("Video ended. Looping...")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to frame 0 (beginning)
                    continue  # Skip to next iteration, read frame 0 again
                elif isinstance(video_source, str):
                    # Video file ended - exit normally
                    # This is expected behavior - video finished playing
                    print("Video ended.")
                    break  # Exit the loop gracefully
                else:
                    # Camera error - exit with error message
                    # Cameras shouldn't "end" - if read fails, something is wrong
                    print("Error: Could not read frame")
                    print("  Camera may be disconnected or in use by another application")
                    break  # Exit the loop with error
            
            # Increment frame counter and get current timestamp
            # frame_count is used for FPS calculation and periodic status updates
            frame_count += 1
            current_time = time.time()  # Current Unix timestamp (seconds since epoch)
            timestamp = current_time  # Use current time as frame timestamp
            # Timestamp is critical for:
            #   - Security monitoring (tracks detection duration)
            #   - Video recording (synchronizes frames)
            #   - Event logging (when did the event occur?)
            
            # Step 1: Detect objects in the frame using YOLOv8
            # This is the most computationally expensive step - runs neural network inference
            # YOLOv8 processes the entire frame and returns all detected objects with:
            #   - Bounding box coordinates (x1, y1, x2, y2)
            #   - Class ID and name (e.g., "person", "car")
            #   - Confidence score (0.0 to 1.0)
            # Processing time depends on frame size and model size (nano vs large)
            detections = detector.detect(frame)
            
            # Step 2: Filter detections to only include monitored classes
            # This removes unwanted detections based on configuration
            # For example, if config only monitors ["person", "car"], all other
            # detections (like "dog", "bicycle") are filtered out here
            # This filtering happens AFTER detection to maintain flexibility
            filtered_detections = detector.filter_by_classes(detections, monitored_classes)
            
            # Step 3: Check for unauthorized access events
            # This evaluates security rules and determines if alert should trigger
            # SecurityMonitor tracks:
            #   - Detection duration (how long objects have been detected)
            #   - Number of objects
            #   - Class types (unauthorized vs authorized)
            # Returns event_info dict with 'is_unauthorized', 'duration', 'reason', etc.
            event_info = security_monitor.check_unauthorized_access(
                filtered_detections, timestamp
            )
            
            # Step 4: Add frame to video recorder
            # Recorder handles buffering and saving video segments when events occur
            # VideoRecorder maintains a circular buffer of recent frames
            # When an event is detected, it saves frames from before, during, and after
            # This ensures we capture the complete event, not just the moment of detection
            video_recorder.add_frame(
                frame, filtered_detections, timestamp, event_info
            )
            
            # Step 5: Annotate and display frame (if display flag is set)
            # Display is optional because:
            #   - Headless servers don't have displays
            #   - Display adds overhead (drawing operations)
            #   - Some users only want recordings, not live view
            if args.display:
                # Annotate frame with detection boxes and labels
                # This draws bounding boxes, class names, and confidence scores on the frame
                # The annotation creates a copy, so original frame is preserved for recording
                annotated_frame = detector.annotate_frame(frame, filtered_detections)
                
                # Calculate and display FPS (frames per second)
                # FPS = total frames / elapsed time
                # This is a running average FPS, not instantaneous
                # Division by zero check: if start_time equals current_time (unlikely but possible)
                # FPS is important for performance monitoring - should be >= 15 for smooth video
                fps = frame_count / (current_time - start_time) if (current_time - start_time) > 0 else 0
                # Build status text with processing FPS and source FPS if available
                if source_fps is not None:
                    status_text = f"Frame: {frame_count} | Processing FPS: {fps:.1f} | Source FPS: {source_fps:.1f}"
                else:
                    status_text = f"Frame: {frame_count} | Processing FPS: {fps:.1f}"
                
                # Draw FPS and frame count at bottom of frame
                # Position calculation: annotated_frame.shape[0] is the height in pixels
                # We subtract 10 pixels from bottom to leave margin
                # (10, height-10) places text in bottom-left corner with padding
                cv2.putText(
                    annotated_frame,
                    status_text,
                    (10, annotated_frame.shape[0] - 10),  # Position: bottom-left with 10px margin
                    cv2.FONT_HERSHEY_SIMPLEX,  # Font type (simple, readable)
                    0.5,  # Font scale (size multiplier)
                    (0, 255, 0),  # Color: Green in BGR format (B=0, G=255, R=0)
                    1  # Line thickness (1 pixel)
                )
                
                # Add event status overlay based on security monitoring
                # This provides visual feedback about the current security state
                # Color coding: Red = Alert, Orange = Monitoring, Green = Normal (FPS text)
                if event_info.get('is_unauthorized', False):
                    # Unauthorized access detected - show red alert
                    # This is the highest priority status - security breach detected
                    # Positioned at top-left (10, 60) to be highly visible
                    cv2.putText(
                        annotated_frame,
                        "ALERT: Unauthorized Access!",
                        (10, 60),  # Position: top-left, below any other text
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,  # Font scale (larger for visibility)
                        (0, 0, 255),  # Color: Red in BGR format (B=0, G=0, R=255)
                        2  # Line thickness (thicker for emphasis)
                    )
                elif event_info.get('duration', 0) > 0:
                    # Monitoring in progress - show orange status
                    # This indicates objects are detected but haven't triggered alert yet
                    # Duration shows how long the monitoring has been active
                    # Useful for understanding if detection is transient or sustained
                    cv2.putText(
                        annotated_frame,
                        f"Monitoring: {event_info.get('duration', 0):.1f}s",
                        (10, 60),  # Position: top-left, same as alert
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,  # Font scale (medium size)
                        (0, 165, 255),  # Color: Orange in BGR format (B=0, G=165, R=255)
                        2  # Line thickness
                    )
                # If neither condition is true, no status overlay is shown (normal operation)
                
                # Display annotated frame in window
                # cv2.imshow() creates/updates a window with the given name
                # If window doesn't exist, it's created; if it exists, it's updated
                # Window name 'Security Camera' appears in the title bar
                cv2.imshow('Security Camera', annotated_frame)
                
                # Check for 'q' key press to quit
                # waitKey(1) waits 1 millisecond for a key press, then returns
                # This is non-blocking - allows the loop to continue processing frames
                # Returns -1 if no key was pressed, or the key code if a key was pressed
                # 0xFF masks to get only the last 8 bits (key code)
                # This handles different platforms that may return different key code formats
                # ord('q') converts 'q' character to its ASCII code (113)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\nQuit requested by user (pressed 'q')")
                    break  # Exit the loop when 'q' is pressed
            
            # Print status information to console every 30 frames
            # This provides periodic updates without flooding the console
            # Printing every frame would slow down processing and clutter output
            # 30 frames at 30 FPS = 1 update per second (good balance)
            # Using modulo operator (%) to check if frame_count is divisible by 30
            if frame_count % 30 == 0:
                # Calculate current FPS (same calculation as display overlay)
                # This is a running average, not instantaneous frame time
                fps = frame_count / (current_time - start_time)
                # Count number of detections in current frame
                # This helps understand detection activity (0 = no objects, >0 = objects found)
                det_count = len(filtered_detections)
                # Determine status (ALERT or MONITORING)
                # ALERT means security breach detected, MONITORING means normal operation
                status = "ALERT" if event_info.get('is_unauthorized', False) else "MONITORING"
                # Print status line with FPS, detection count, and event reason
                # This provides a concise summary of system state
                # event_info.get('reason', '') explains why alert/monitoring state exists
                print(f"[{status}] FPS: {fps:.1f} | Detections: {det_count} | {event_info.get('reason', '')}")
    
    # Handle keyboard interrupt (Ctrl+C)
    # This allows users to gracefully stop the program mid-execution
    # Without this, Ctrl+C would show an ugly traceback
    except KeyboardInterrupt:
        print("\nShutting down...")
        # KeyboardInterrupt is caught here, but cleanup still happens in finally block
    
    # ========================================================================
    # Cleanup and Resource Release
    # ========================================================================
    # The finally block ALWAYS executes, regardless of how the loop exits:
    #   - Normal completion (video ended)
    #   - User pressed 'q'
    #   - Keyboard interrupt (Ctrl+C)
    #   - Error/exception occurred
    # This ensures resources are always properly released, preventing:
    #   - Camera staying locked (can't be used by other programs)
    #   - File handles staying open (can't delete/move files)
    #   - Windows staying open (clutters screen)
    #   - Video files not being finalized (corrupted recordings)
    
    finally:
        # Always execute cleanup, even if interrupted
        # This is critical for production systems that run continuously
        
        # Stop any active video recordings and release resources
        # VideoRecorder.cleanup() ensures:
        #   - Any buffered frames are saved (if event was in progress)
        #   - Video files are properly closed and finalized
        #   - File handles are released
        #   - Temporary buffers are freed
        video_recorder.cleanup()
        
        # Release video capture resource (camera or file handle)
        # cap.release() is critical because:
        #   - Cameras: Releases exclusive access (other programs can use it)
        #   - Video files: Closes file handles (can delete/move file)
        #   - Frees memory used by VideoCapture object
        # Without this, camera might stay locked until program restart
        cap.release()
        
        # Close all OpenCV windows if display was enabled
        # cv2.destroyAllWindows() closes all windows created by cv2.imshow()
        # This is important because:
        #   - Windows consume system resources
        #   - On some systems, windows stay open after program exits
        #   - Clean shutdown looks more professional
        if args.display:
            cv2.destroyAllWindows()
        
        # Print shutdown confirmation
        # Provides user feedback that cleanup completed successfully
        # Helps distinguish between normal shutdown and crash
        print("System stopped.")


if __name__ == "__main__":
    main()


