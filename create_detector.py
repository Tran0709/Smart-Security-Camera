"""
File Generator Script: create_detector.py
Creates the detector.py module file programmatically.

This script generates the detector.py file containing the ObjectDetector class.
It's a utility script used during project setup to create the detector module
with all necessary code and documentation.

Usage:
    python create_detector.py
    
This will create detector.py in the current directory.
"""

# File system operations
import os

# ============================================================================
# Detector Module Code Template
# ============================================================================

# Multi-line string containing the complete detector.py source code
# This is the code that will be written to detector.py
detector_code = """\"\"\"
YOLOv8 Object Detection Module
Handles real-time object detection and categorization from video streams.
\"\"\"

import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Tuple, Optional
import json


class ObjectDetector:
    \"\"\"YOLOv8-based object detector for real-time video processing.\"\"\"
    
    def __init__(self, model_path: str = \"yolov8n.pt\", confidence_threshold: float = 0.5):
        \"\"\"
        Initialize the object detector.
        
        Args:
            model_path: Path to YOLOv8 model file
            confidence_threshold: Minimum confidence for detections
        \"\"\"
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.class_names = self.model.names
        
    def detect(self, frame: np.ndarray) -> List[Dict]:
        \"\"\"
        Detect objects in a frame.
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            List of detection dictionaries with keys:
            - 'class': class name (str)
            - 'class_id': class ID (int)
            - 'confidence': confidence score (float)
            - 'bbox': bounding box [x1, y1, x2, y2] (list)
            - 'center': center point (x, y) (tuple)
        \"\"\"
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)
        detections = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Extract detection information
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                class_name = self.class_names[class_id]
                
                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                bbox = [float(x1), float(y1), float(x2), float(y2)]
                
                # Calculate center point
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                center = (float(center_x), float(center_y))
                
                detections.append({
                    'class': class_name,
                    'class_id': class_id,
                    'confidence': confidence,
                    'bbox': bbox,
                    'center': center
                })
        
        return detections
    
    def filter_by_classes(self, detections: List[Dict], monitored_classes: List[str]) -> List[Dict]:
        \"\"\"
        Filter detections to only include monitored classes.
        
        Args:
            detections: List of detection dictionaries
            monitored_classes: List of class names to monitor
            
        Returns:
            Filtered list of detections
        \"\"\"
        return [det for det in detections if det['class'] in monitored_classes]
    
    def annotate_frame(self, frame: np.ndarray, detections: List[Dict], 
                      show_confidence: bool = True) -> np.ndarray:
        \"\"\"
        Annotate frame with detection boxes and labels.
        
        Args:
            frame: Input frame (BGR format)
            detections: List of detection dictionaries
            show_confidence: Whether to show confidence scores
            
        Returns:
            Annotated frame
        \"\"\"
        annotated_frame = frame.copy()
        
        for det in detections:
            x1, y1, x2, y2 = map(int, det['bbox'])
            class_name = det['class']
            confidence = det['confidence']
            
            # Draw bounding box
            color = self._get_class_color(class_name)
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            
            # Prepare label
            label = class_name
            if show_confidence:
                label += f\" {confidence:.2f}\"
            
            # Draw label background
            (label_width, label_height), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(
                annotated_frame,
                (x1, y1 - label_height - 10),
                (x1 + label_width, y1),
                color,
                -1
            )
            
            # Draw label text
            cv2.putText(
                annotated_frame,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
        
        return annotated_frame
    
    def _get_class_color(self, class_name: str) -> Tuple[int, int, int]:
        \"\"\"Get a consistent color for a class.\"\"\"
        # Generate a color based on class name hash
        hash_value = hash(class_name)
        r = (hash_value & 0xFF0000) >> 16
        g = (hash_value & 0xFF00) >> 8
        b = hash_value & 0xFF
        return (int(b), int(g), int(r))  # BGR format
    
    def get_class_names(self) -> Dict[int, str]:
        \"\"\"Get mapping of class IDs to class names.\"\"\"
        return self.class_names
"""

# ============================================================================
# File Creation
# ============================================================================

# Write the detector code to detector.py file
# encoding='utf-8' ensures proper handling of special characters
with open('detector.py', 'w', encoding='utf-8') as f:
    f.write(detector_code)

# Print confirmation message
print('Created detector.py')
