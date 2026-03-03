"""
YOLOv8 Object Detection Module
Handles real-time object detection and categorization from video streams.

This module provides a wrapper around the Ultralytics YOLOv8 model for detecting
objects in video frames. It processes frames, filters detections by class and
confidence, and provides annotation capabilities for visualization.

Key Features:
- Real-time object detection using YOLOv8
- Configurable confidence threshold
- Class-based filtering
- Frame annotation with bounding boxes and labels
- Consistent color coding for object classes
"""

# Computer vision and image processing
import cv2  # OpenCV for image operations and drawing
import numpy as np  # NumPy for array operations

# YOLOv8 model from Ultralytics
from ultralytics import YOLO

# Type hints for better code documentation and IDE support
from typing import List, Dict, Tuple, Optional
import json  # JSON handling (currently unused but available for future use)


class ObjectDetector:
    """
    YOLOv8-based object detector for real-time video processing.
    
    This class encapsulates the YOLOv8 object detection model and provides
    convenient methods for detecting objects in frames, filtering results,
    and annotating frames with detection visualizations.
    
    The detector uses a pre-trained YOLOv8 model (default: yolov8n.pt - nano version)
    which can detect 80 different object classes from the COCO dataset.
    """
    
    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.5):
        """
        Initialize the object detector with YOLOv8 model.
        
        This constructor loads the YOLOv8 model from the specified path and
        sets up the detector with the given confidence threshold. The model
        is loaded once and reused for all subsequent detections.
        
        Args:
            model_path: Path to YOLOv8 model file (.pt format)
                      Default: "yolov8n.pt" (YOLOv8 nano - fastest, smallest)
                      Other options: yolov8s.pt, yolov8m.pt, yolov8l.pt, yolov8x.pt
            confidence_threshold: Minimum confidence score (0.0-1.0) for detections
                                 Detections below this threshold are discarded
                                 Default: 0.5 (50% confidence)
                                 
        Note:
            First model load may take a few seconds. Subsequent detections are fast.
            Lower confidence threshold = more detections (including false positives)
            Higher confidence threshold = fewer detections (more accurate)
        """
        # Load YOLOv8 model from file
        # This initializes the neural network with pre-trained weights
        self.model = YOLO(model_path)
        
        # Store confidence threshold for filtering detections
        # Only detections with confidence >= this value will be returned
        self.confidence_threshold = confidence_threshold
        
        # Get class name mapping from model
        # This is a dictionary mapping class IDs (0-79) to class names (e.g., "person", "car")
        self.class_names = self.model.names
        
    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect objects in a video frame using YOLOv8 model.
        
        This method processes a single frame through the YOLOv8 neural network
        and returns a list of detected objects with their properties. Each
        detection includes the object class, confidence score, bounding box
        coordinates, and center point.
        
        Args:
            frame: Input video frame as numpy array in BGR format (OpenCV standard)
                  Shape: (height, width, 3) where 3 represents BGR channels
                  
        Returns:
            List of detection dictionaries, each containing:
            - 'class': Class name as string (e.g., "person", "car", "bicycle")
            - 'class_id': Numeric class ID (0-79 for COCO dataset)
            - 'confidence': Confidence score as float (0.0-1.0)
            - 'bbox': Bounding box coordinates as list [x1, y1, x2, y2]
                     (x1,y1) = top-left corner, (x2,y2) = bottom-right corner
            - 'center': Center point of bounding box as tuple (x, y)
            
        Example:
            detections = detector.detect(frame)
            for det in detections:
                print(f"Found {det['class']} with {det['confidence']:.2%} confidence")
        """
        # Run YOLOv8 inference on the frame
        # conf parameter filters detections below threshold
        # verbose=False suppresses model output messages
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)
        
        # List to store formatted detection results
        detections = []
        
        # Process each result (YOLOv8 can return multiple results for batch processing)
        for result in results:
            # Get bounding boxes from result
            boxes = result.boxes
            
            # Process each detected box
            for box in boxes:
                # Extract class ID from box tensor
                # box.cls[0] is a tensor, convert to Python int
                class_id = int(box.cls[0])
                
                # Extract confidence score from box tensor
                # box.conf[0] is a tensor, convert to Python float
                confidence = float(box.conf[0])
                
                # Get human-readable class name from class ID
                class_name = self.class_names[class_id]
                
                # Extract bounding box coordinates
                # box.xyxy[0] contains [x1, y1, x2, y2] as tensor
                # .cpu().numpy() converts from GPU tensor to CPU numpy array
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                
                # Convert to Python float list for JSON serialization
                bbox = [float(x1), float(y1), float(x2), float(y2)]
                
                # Calculate center point of bounding box
                # Center is useful for zone checking and tracking
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                center = (float(center_x), float(center_y))
                
                # Create detection dictionary with all information
                detections.append({
                    'class': class_name,  # Human-readable class name
                    'class_id': class_id,  # Numeric class ID
                    'confidence': confidence,  # Detection confidence (0.0-1.0)
                    'bbox': bbox,  # Bounding box coordinates
                    'center': center  # Center point for spatial analysis
                })
        
        return detections
    
    def filter_by_classes(self, detections: List[Dict], monitored_classes: List[str]) -> List[Dict]:
        """
        Filter detections to only include specified object classes.
        
        This method filters the detection list to keep only objects whose
        class names are in the monitored_classes list. This is useful for
        focusing on specific object types (e.g., only "person" and "car")
        and ignoring other detected objects.
        
        Args:
            detections: List of detection dictionaries from detect() method
            monitored_classes: List of class names to keep (e.g., ["person", "car"])
                             Class names must match exactly (case-sensitive)
                             
        Returns:
            Filtered list of detection dictionaries containing only monitored classes
            
        Example:
            all_detections = detector.detect(frame)
            # Only keep person and car detections
            filtered = detector.filter_by_classes(all_detections, ["person", "car"])
        """
        # List comprehension filters detections where class is in monitored_classes
        # This creates a new list with only matching detections
        return [det for det in detections if det['class'] in monitored_classes]
    
    def annotate_frame(self, frame: np.ndarray, detections: List[Dict], 
                      show_confidence: bool = True) -> np.ndarray:
        """
        Annotate frame with detection bounding boxes and labels.
        
        This method draws visual annotations on the frame to highlight detected
        objects. For each detection, it draws:
        - A colored bounding box around the object
        - A label with the class name (and optionally confidence score)
        - A colored background behind the label for better visibility
        
        Args:
            frame: Input video frame as numpy array in BGR format
            detections: List of detection dictionaries from detect() method
            show_confidence: If True, include confidence score in label
                           If False, show only class name
                           Default: True
                           
        Returns:
            Annotated frame as numpy array (same dimensions as input)
            The original frame is not modified - a copy is returned
            
        Example:
            detections = detector.detect(frame)
            annotated = detector.annotate_frame(frame, detections, show_confidence=True)
            cv2.imshow("Detections", annotated)
        """
        # Create a copy of the frame to avoid modifying the original
        # This allows the original frame to be used elsewhere if needed
        annotated_frame = frame.copy()
        
        # Process each detection and draw annotations
        for det in detections:
            # Extract bounding box coordinates and convert to integers
            # OpenCV drawing functions require integer coordinates
            x1, y1, x2, y2 = map(int, det['bbox'])
            
            # Get class name and confidence for label
            class_name = det['class']
            confidence = det['confidence']
            
            # Get a consistent color for this class
            # Same class will always have the same color across frames
            color = self._get_class_color(class_name)
            
            # Draw bounding box rectangle around detected object
            # Parameters: (image, top-left, bottom-right, color, thickness)
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            
            # Prepare label text
            label = class_name  # Start with class name
            if show_confidence:
                # Append confidence score formatted to 2 decimal places
                label += f" {confidence:.2f}"
            
            # Calculate text size to determine background rectangle dimensions
            # This ensures the background fits the text properly
            (label_width, label_height), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            
            # Draw filled rectangle as label background
            # Positioned above the bounding box for visibility
            # Parameters: (image, top-left, bottom-right, color, -1 for filled)
            cv2.rectangle(
                annotated_frame,
                (x1, y1 - label_height - 10),  # Top-left of label background
                (x1 + label_width, y1),  # Bottom-right of label background
                color,  # Same color as bounding box
                -1  # -1 means filled rectangle
            )
            
            # Draw label text on top of the background
            # Parameters: (image, text, position, font, scale, color, thickness)
            cv2.putText(
                annotated_frame,
                label,
                (x1, y1 - 5),  # Position: slightly above bounding box
                cv2.FONT_HERSHEY_SIMPLEX,  # Font type
                0.5,  # Font scale (size)
                (255, 255, 255),  # Color: White in BGR format
                1  # Line thickness
            )
        
        return annotated_frame
    
    def _get_class_color(self, class_name: str) -> Tuple[int, int, int]:
        """
        Generate a consistent color for an object class based on its name.
        
        This private method uses the hash of the class name to generate a
        deterministic color. The same class name will always produce the
        same color, making it easier to visually identify object types
        across multiple frames.
        
        The color is generated by:
        1. Computing hash of class name
        2. Extracting RGB components from hash bits
        3. Converting to BGR format (OpenCV standard)
        
        Args:
            class_name: Name of the object class (e.g., "person", "car")
            
        Returns:
            Tuple of (B, G, R) color values in BGR format
            Each value is 0-255 (8-bit color channel)
            
        Note:
            This is a private method (indicated by leading underscore)
            It's used internally by annotate_frame() method
        """
        # Compute hash value of class name
        # Hash provides deterministic pseudo-random number based on string
        hash_value = hash(class_name)
        
        # Extract red component (bits 16-23)
        # 0xFF0000 is bitmask for red channel, >> 16 shifts to get value 0-255
        r = (hash_value & 0xFF0000) >> 16
        
        # Extract green component (bits 8-15)
        # 0xFF00 is bitmask for green channel, >> 8 shifts to get value 0-255
        g = (hash_value & 0xFF00) >> 8
        
        # Extract blue component (bits 0-7)
        # 0xFF is bitmask for blue channel, no shift needed
        b = hash_value & 0xFF
        
        # Return in BGR format (OpenCV standard, opposite of RGB)
        # Convert to int to ensure proper type
        return (int(b), int(g), int(r))
    
    def get_class_names(self) -> Dict[int, str]:
        """
        Get the mapping of class IDs to class names.
        
        This method returns the dictionary that maps numeric class IDs
        (0-79 for COCO dataset) to their human-readable class names.
        This is useful for understanding what classes the model can detect
        and for building class selection interfaces.
        
        Returns:
            Dictionary mapping class IDs (int) to class names (str)
            Example: {0: "person", 1: "bicycle", 2: "car", ...}
            
        Example:
            class_names = detector.get_class_names()
            print(f"Model can detect {len(class_names)} classes")
            print(f"Class 0 is: {class_names[0]}")  # "person"
        """
        return self.class_names
