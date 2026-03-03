"""
Video Recorder Module
Handles annotation and saving of video segments upon unauthorized access detection.

This module manages video recording functionality for security events. It
implements a buffering system that captures frames before events occur,
records during events, and continues recording for a period after events end.
This ensures complete event coverage including context before and after.

Key Features:
- Pre-event buffering (captures frames before event starts)
- Post-event buffering (continues recording after event ends)
- Frame annotation with detections, timestamps, and alerts
- Event metadata storage (JSON files with event details)
- Automatic recording start/stop based on security events
"""

# Computer vision library for video writing and image operations
import cv2

# NumPy for array operations
import numpy as np

# Type hints for function parameters and return values
from typing import List, Dict, Optional

# Date/time formatting for filenames and timestamps
from datetime import datetime

# File system operations
import os

# Double-ended queue for efficient frame buffering
from collections import deque

# JSON file handling for metadata storage
import json


class VideoRecorder:
    """
    Records and annotates video segments when security events are detected.
    
    This class manages the complete video recording lifecycle:
    1. Continuously buffers frames (pre-event buffer)
    2. Starts recording when unauthorized access is detected
    3. Writes buffered pre-event frames to video
    4. Continues recording during the event
    5. Continues recording for post-event buffer period
    6. Stops recording and saves metadata
    
    The recorder uses OpenCV's VideoWriter to create MP4 video files with
    annotated frames showing detections, timestamps, and alert overlays.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the video recorder with configuration settings.
        
        This constructor extracts recording settings from the configuration
        dictionary and sets up the recording system, including creating the
        save directory and initializing frame buffers.
        
        Args:
            config: Configuration dictionary containing:
                   - 'recording': Recording settings section
                   
        Configuration Structure:
            config = {
                'recording': {
                    'save_directory': 'recordings',  # Directory to save videos
                    'pre_event_buffer': 5.0,  # Seconds before event to record
                    'post_event_buffer': 10.0,  # Seconds after event to record
                    'fps': 30,  # Frames per second for output video
                    'codec': 'mp4v',  # Video codec (mp4v, XVID, etc.)
                    'annotate': True,  # Whether to annotate frames
                    'include_timestamp': True  # Whether to add timestamp overlay
                }
            }
        """
        # Store full configuration for reference
        self.config = config
        
        # Extract recording configuration section
        recording_config = config.get('recording', {})
        
        # ====================================================================
        # Recording Configuration Parameters
        # ====================================================================
        
        # Directory where recorded videos will be saved
        # Default: 'recordings' in current directory
        self.save_directory = recording_config.get('save_directory', 'recordings')
        
        # Pre-event buffer duration: How many seconds before event to record
        # This captures context leading up to the event
        # Default: 5.0 seconds
        self.pre_event_buffer = recording_config.get('pre_event_buffer', 5.0)
        
        # Post-event buffer duration: How many seconds after event to record
        # This captures what happens after the event
        # Default: 10.0 seconds
        self.post_event_buffer = recording_config.get('post_event_buffer', 10.0)
        
        # Frames per second for output video
        # Should match or be close to input video FPS
        # Default: 30 FPS
        self.fps = recording_config.get('fps', 30)
        
        # Video codec for encoding
        # 'mp4v' is widely compatible, 'XVID' is another option
        # Default: 'mp4v'
        self.codec = recording_config.get('codec', 'mp4v')
        
        # Whether to annotate frames with detections and overlays
        # If False, raw frames are saved without annotations
        # Default: True
        self.annotate = recording_config.get('annotate', True)
        
        # Whether to include timestamp overlay on frames
        # Adds human-readable date/time to each frame
        # Default: True
        self.include_timestamp = recording_config.get('include_timestamp', True)
        
        # ====================================================================
        # Directory Setup
        # ====================================================================
        
        # Create save directory if it doesn't exist
        # exist_ok=True prevents error if directory already exists
        os.makedirs(self.save_directory, exist_ok=True)
        
        # ====================================================================
        # Frame Buffer for Pre-Event Recording
        # ====================================================================
        
        # Deque for storing frames before event occurs
        # maxlen limits buffer size to pre_event_buffer duration
        # Formula: maxlen = seconds * fps (e.g., 5.0 * 30 = 150 frames)
        self.frame_buffer = deque(maxlen=int(self.pre_event_buffer * self.fps))
        
        # Deque for storing timestamps corresponding to buffered frames
        # Used for metadata and timestamp overlay
        self.frame_buffer_timestamps = deque(maxlen=int(self.pre_event_buffer * self.fps))
        
        # ====================================================================
        # Current Recording State
        # ====================================================================
        
        # Boolean flag indicating if currently recording
        self.is_recording = False
        
        # OpenCV VideoWriter instance for current recording
        # None when not recording
        self.current_video_writer = None
        
        # Timestamp when current recording started
        # None when not recording
        self.recording_start_time = None
        
        # Timestamp when current recording should end
        # None if recording should continue indefinitely
        self.recording_end_time = None
        
        # Event information dictionary for current recording
        # Contains details about the unauthorized access event
        self.event_info = None
        
    def add_frame(self, frame: np.ndarray, detections: List[Dict], 
                  timestamp: float, event_info: Optional[Dict] = None):
        """
        Add a frame to the buffer and handle recording logic.
        
        This is the main method called for each frame. It:
        1. Adds frame to pre-event buffer (always)
        2. Starts recording if unauthorized access detected
        3. Records frame if recording is active
        4. Stops recording when event ends and post-event buffer expires
        
        The method manages the complete recording lifecycle automatically
        based on event_info from the security monitor.
        
        Args:
            frame: Input video frame as numpy array (BGR format)
            detections: List of detection dictionaries from ObjectDetector
                       Used for frame annotation
            timestamp: Current Unix timestamp (float)
                     Used for timing and metadata
            event_info: Optional dictionary from SecurityMonitor.check_unauthorized_access()
                       Contains 'is_unauthorized' flag and event details
                       None if no event information available
                       
        Note:
            Frames are always buffered, even when not recording, to enable
            pre-event recording when events occur.
        """
        # ====================================================================
        # Step 1: Always Add Frame to Pre-Event Buffer
        # ====================================================================
        
        # Store frame copy in buffer (copy prevents reference issues)
        # Buffer automatically maintains maxlen (oldest frames are discarded)
        self.frame_buffer.append(frame.copy())
        
        # Store corresponding timestamp for this frame
        self.frame_buffer_timestamps.append(timestamp)
        
        # ====================================================================
        # Step 2: Start Recording if Event Detected
        # ====================================================================
        
        # Check if unauthorized access event is detected and not already recording
        if event_info and event_info.get('is_unauthorized', False) and not self.is_recording:
            # Unauthorized access detected - start recording
            # This will write buffered pre-event frames and begin new recording
            self._start_recording(frame, detections, timestamp, event_info)
        
        # ====================================================================
        # Step 3: Continue Recording if Active
        # ====================================================================
        
        # If currently recording, add this frame to the video
        if self.is_recording:
            # Record the current frame (with annotations)
            self._record_frame(frame, detections, timestamp, event_info)
            
            # ====================================================================
            # Step 4: Check if Recording Should Stop
            # ====================================================================
            
            # Check if event has ended (unauthorized access no longer detected)
            if event_info and not event_info.get('is_unauthorized', False):
                # Event ended - start post-event buffer countdown
                if self.recording_end_time is None:
                    # Set end time to current time + post-event buffer duration
                    # This allows recording to continue for post_event_buffer seconds
                    self.recording_end_time = timestamp + self.post_event_buffer
                
                # Check if post-event buffer period has expired
                if timestamp >= self.recording_end_time:
                    # Post-event buffer complete - stop recording
                    self._stop_recording()
            elif self.recording_end_time and timestamp >= self.recording_end_time:
                # Recording end time reached (safety check)
                self._stop_recording()
    
    def _start_recording(self, frame: np.ndarray, detections: List[Dict], 
                        timestamp: float, event_info: Dict):
        """
        Start recording a new video segment for an unauthorized access event.
        
        This private method initializes a new video recording when an
        unauthorized access event is detected. It:
        1. Sets recording state flags
        2. Generates a unique filename based on timestamp
        3. Initializes OpenCV VideoWriter
        4. Writes all buffered pre-event frames to video
        5. Saves event metadata to JSON file
        
        Args:
            frame: Current video frame (used to determine dimensions)
            detections: List of current detections (not used for buffered frames)
            timestamp: Event timestamp (used for filename and metadata)
            event_info: Event information dictionary from SecurityMonitor
            
        Note:
            This is a private method called internally by add_frame()
            when unauthorized access is first detected.
        """
        # Set recording state flags
        self.is_recording = True
        self.recording_start_time = timestamp
        self.recording_end_time = None
        self.event_info = event_info
        
        # Generate unique filename based on event timestamp
        # Format: unauthorized_access_YYYYMMDD_HHMMSS.mp4
        timestamp_str = datetime.fromtimestamp(timestamp).strftime('%Y%m%d_%H%M%S')
        filename = f"unauthorized_access_{timestamp_str}.mp4"
        filepath = os.path.join(self.save_directory, filename)
        
        # Get frame dimensions for video writer initialization
        height, width = frame.shape[:2]
        
        # Initialize OpenCV VideoWriter with codec and settings
        fourcc = cv2.VideoWriter_fourcc(*self.codec)
        self.current_video_writer = cv2.VideoWriter(
            filepath, fourcc, self.fps, (width, height)
        )
        
        # Write all pre-event buffered frames to video
        # This captures context before the event occurred
        for buffered_frame, buffered_ts in zip(self.frame_buffer, self.frame_buffer_timestamps):
            annotated_frame = self._annotate_frame(
                buffered_frame, [], buffered_ts, None
            )
            self.current_video_writer.write(annotated_frame)
        
        # Save event metadata to JSON file
        self._save_event_metadata(filepath, event_info, timestamp)
        
        print(f"[RECORDING] Started recording: {filepath}")
    
    def _record_frame(self, frame: np.ndarray, detections: List[Dict], 
                     timestamp: float, event_info: Optional[Dict]):
        """
        Record a single frame to the current video recording.
        
        This private method adds a frame to the active video recording.
        The frame is annotated with detections, timestamps, and event
        information before being written to the video file.
        
        Args:
            frame: Video frame to record (numpy array, BGR format)
            detections: List of detection dictionaries for annotation
            timestamp: Frame timestamp for overlay
            event_info: Event information for alert overlays
            
        Note:
            This method does nothing if not currently recording.
            It's called internally by add_frame() during active recording.
        """
        if self.current_video_writer is None:
            return
        
        # Annotate frame and write to video
        annotated_frame = self._annotate_frame(frame, detections, timestamp, event_info)
        self.current_video_writer.write(annotated_frame)
    
    def _stop_recording(self):
        """
        Stop the current video recording and release resources.
        
        This private method finalizes the current video recording by:
        1. Releasing the VideoWriter (closes file and writes headers)
        2. Resetting recording state flags
        3. Printing confirmation message
        
        Note:
            This method is safe to call even if not recording.
            It's called internally when post-event buffer expires or
            when cleanup() is called.
        """
        if self.current_video_writer is not None:
            self.current_video_writer.release()
            self.current_video_writer = None
        
        self.is_recording = False
        self.recording_end_time = None
        print(f"[RECORDING] Stopped recording")
    
    def _annotate_frame(self, frame: np.ndarray, detections: List[Dict], 
                       timestamp: float, event_info: Optional[Dict]) -> np.ndarray:
        """
        Annotate frame with detections, timestamp, and event information.
        
        This private method adds visual annotations to a frame including:
        - Bounding boxes around detected objects
        - Class names and confidence scores
        - Timestamp overlay
        - Alert overlays for unauthorized access events
        
        The annotations use color coding:
        - Red boxes: Unauthorized objects
        - Green boxes: Other detected objects
        - Thicker boxes: During active unauthorized access events
        
        Args:
            frame: Input video frame (numpy array, BGR format)
            detections: List of detection dictionaries to annotate
            timestamp: Frame timestamp for overlay
            event_info: Optional event information for alert overlays
            
        Returns:
            Annotated frame (numpy array, same dimensions as input)
            Original frame if annotation is disabled
            
        Note:
            This is a private method called internally during recording.
            If self.annotate is False, returns original frame unchanged.
        """
        # Check if annotation is enabled
        if not self.annotate:
            return frame
        
        # Create copy of frame to avoid modifying original
        annotated = frame.copy()
        
        # ====================================================================
        # Draw Detection Bounding Boxes and Labels
        # ====================================================================
        
        for det in detections:
            # Extract bounding box coordinates (convert to integers)
            x1, y1, x2, y2 = map(int, det['bbox'])
            class_name = det['class']
            confidence = det['confidence']
            
            # Determine color based on whether object is unauthorized
            # Red (0, 0, 255) for unauthorized, Green (0, 255, 0) for others
            unauthorized_classes = self.config.get('detection', {}).get('unauthorized_classes', [])
            color = (0, 0, 255) if det['class'] in unauthorized_classes else (0, 255, 0)
            
            # Use thicker lines during active unauthorized access events
            thickness = 3 if event_info and event_info.get('is_unauthorized', False) else 2
            
            # Draw bounding box rectangle
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
            
            # Prepare label text with class name and confidence
            label = f"{class_name} {confidence:.2f}"
            
            # Calculate text size for background rectangle
            (label_width, label_height), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )
            
            # Draw filled rectangle as label background
            cv2.rectangle(
                annotated,
                (x1, y1 - label_height - 10),  # Top-left
                (x1 + label_width, y1),  # Bottom-right
                color,  # Same color as bounding box
                -1  # Filled rectangle
            )
            
            # Draw label text on background
            cv2.putText(
                annotated,
                label,
                (x1, y1 - 5),  # Position
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,  # Font scale
                (255, 255, 255),  # White text
                2  # Line thickness
            )
        
        # ====================================================================
        # Add Timestamp Overlay
        # ====================================================================
        
        if self.include_timestamp:
            # Format timestamp as human-readable date/time
            timestamp_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            # Draw timestamp at top-left of frame
            cv2.putText(
                annotated,
                timestamp_str,
                (10, 30),  # Position: 10px from left, 30px from top
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,  # Font scale
                (255, 255, 255),  # White text
                2  # Line thickness
            )
        
        # ====================================================================
        # Add Event Alert Overlay (if unauthorized access detected)
        # ====================================================================
        
        if event_info and event_info.get('is_unauthorized', False):
            alert_text = "UNAUTHORIZED ACCESS DETECTED"
            reason = event_info.get('reason', '')
            
            # Calculate text dimensions for background rectangle
            (text_width, text_height), _ = cv2.getTextSize(
                alert_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3
            )
            
            # Draw red background rectangle at bottom of frame
            cv2.rectangle(
                annotated,
                (10, annotated.shape[0] - 80),  # Top-left
                (text_width + 20, annotated.shape[0] - 10),  # Bottom-right
                (0, 0, 255),  # Red background
                -1  # Filled rectangle
            )
            
            # Draw main alert text
            cv2.putText(
                annotated,
                alert_text,
                (15, annotated.shape[0] - 45),  # Position
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,  # Large font
                (255, 255, 255),  # White text
                3  # Thick lines
            )
            
            # Draw event reason text (truncated if too long)
            cv2.putText(
                annotated,
                reason[:50],  # Truncate to 50 characters
                (15, annotated.shape[0] - 15),  # Position below main text
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,  # Smaller font
                (255, 255, 255),  # White text
                2  # Line thickness
            )
        
        return annotated
    
    def _save_event_metadata(self, video_path: str, event_info: Dict, timestamp: float):
        """
        Save metadata about the recorded event to a JSON file.
        
        This private method creates a JSON metadata file alongside each
        recorded video containing detailed information about the event.
        This metadata is useful for searching, filtering, and analyzing
        recorded events without having to process the video files.
        
        Args:
            video_path: Path to the recorded video file
            event_info: Event information dictionary from SecurityMonitor
            timestamp: Event timestamp
            
        Metadata File Format:
            The metadata file has the same name as the video but with
            '_metadata.json' extension instead of '.mp4'
            Example: unauthorized_access_20251209_143022_metadata.json
            
        Metadata Contents:
            - video_path: Path to associated video file
            - timestamp: Unix timestamp of event
            - datetime: ISO format date/time string
            - event_type: Type of event ('unauthorized_access')
            - reason: Human-readable reason for the event
            - duration: How long the event lasted (seconds)
            - detections: List of detected objects with details
            - zone_violations: List of restricted zones that were violated
        """
        # Build metadata dictionary with event information
        metadata = {
            'video_path': video_path,  # Path to video file
            'timestamp': timestamp,  # Unix timestamp
            'datetime': datetime.fromtimestamp(timestamp).isoformat(),  # ISO format date/time
            'event_type': 'unauthorized_access',  # Event type identifier
            'reason': event_info.get('reason', ''),  # Human-readable reason
            'duration': event_info.get('duration', 0.0),  # Event duration in seconds
            'detections': [  # List of detected objects
                {
                    'class': det['class'],  # Object class name
                    'confidence': det['confidence'],  # Detection confidence
                    'bbox': det['bbox'],  # Bounding box coordinates
                    'center': det['center']  # Center point coordinates
                }
                for det in event_info.get('detections', [])
            ],
            'zone_violations': event_info.get('zone_violations', [])  # Violated zones
        }
        
        # Generate metadata file path (replace .mp4 with _metadata.json)
        metadata_path = video_path.replace('.mp4', '_metadata.json')
        
        # Write metadata to JSON file with pretty formatting
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)  # indent=2 for readable formatting
    
    def cleanup(self):
        """
        Clean up resources and stop any active recordings.
        
        This method should be called when shutting down the system or
        when switching video sources. It ensures that any active recording
        is properly finalized (video file is closed and headers are written).
        
        Note:
            This method is safe to call multiple times.
            It's typically called in finally blocks or shutdown handlers.
        """
        # Stop recording if currently active
        if self.is_recording:
            self._stop_recording()


