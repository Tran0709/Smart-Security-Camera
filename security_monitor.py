"""
Security Monitor Module
Defines and identifies unauthorized access based on detected objects.

This module implements the security monitoring logic that evaluates detected
objects against configured security rules to determine if unauthorized access
has occurred. It tracks detection duration, enforces time-based rules,
checks restricted zones, and manages alert cooldown periods.

Key Features:
- Duration-based detection (requires sustained presence)
- Minimum object count thresholds
- Restricted zone monitoring
- Time-based access rules (e.g., no access during certain hours)
- Alert cooldown to prevent spam
"""

# Type hints for function parameters and return values
from typing import List, Dict, Optional

# Date/time utilities for time-based rules
from datetime import datetime, timedelta

# Double-ended queue for efficient history tracking
from collections import deque

# Timestamp generation
import time


class SecurityMonitor:
    """
    Monitors video stream for unauthorized access patterns.
    
    This class evaluates object detections against security rules to determine
    if unauthorized access events have occurred. It implements various security
    policies including duration thresholds, minimum object counts, restricted
    zones, and time-based access rules.
    
    The monitor uses a stateful approach, tracking detection duration over time
    to avoid false positives from brief appearances of unauthorized objects.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the security monitor with configuration settings.
        
        This constructor extracts security rules from the configuration
        dictionary and sets up the monitoring system with appropriate
        thresholds and rules. It initializes state tracking variables
        for detection history and current monitoring state.
        
        Args:
            config: Configuration dictionary containing:
                   - 'security': Security monitoring settings
                   - 'detection': Detection settings (unauthorized classes)
                   
        Configuration Structure:
            config = {
                'security': {
                    'unauthorized_access_rules': {
                        'detection_duration': 2.0,  # seconds
                        'min_objects': 1,
                        'restricted_zones': [...],
                        'time_based_rules': {...}
                    },
                    'alert_cooldown': 30.0  # seconds
                },
                'detection': {
                    'unauthorized_classes': ['person', 'car', ...]
                }
            }
        """
        # Store full configuration for reference
        self.config = config
        
        # Extract security configuration section
        security_config = config.get('security', {})
        
        # Extract unauthorized access rules
        rules = security_config.get('unauthorized_access_rules', {})
        
        # Duration threshold: How long unauthorized objects must be detected
        # before triggering an alert (in seconds)
        # Default: 2.0 seconds - prevents false positives from brief appearances
        self.detection_duration = rules.get('detection_duration', 2.0)
        
        # Minimum number of unauthorized objects required to trigger alert
        # Default: 1 - any unauthorized object triggers monitoring
        self.min_objects = rules.get('min_objects', 1)
        
        # List of restricted zones (areas where unauthorized access is prohibited)
        # Each zone has: {'name': str, 'bbox': [x1, y1, x2, y2]}
        self.restricted_zones = rules.get('restricted_zones', [])
        
        # Time-based access rules (e.g., no access during certain hours)
        # Structure: {'enabled': bool, 'restricted_hours': [list of hours]}
        self.time_based_rules = rules.get('time_based_rules', {})
        
        # Alert cooldown period: Minimum time between alerts (in seconds)
        # Prevents alert spam when objects remain detected
        # Default: 30.0 seconds
        self.alert_cooldown = security_config.get('alert_cooldown', 30.0)
        
        # ====================================================================
        # Detection History Tracking
        # ====================================================================
        
        # Deque for storing recent detection history
        # maxlen=100 limits memory usage while keeping recent history
        # Useful for analysis and debugging
        self.detection_history = deque(maxlen=100)
        
        # List of object class names that are considered unauthorized
        # These are the classes that trigger security monitoring
        # Example: ['person', 'car', 'bicycle']
        self.unauthorized_objects = config.get('detection', {}).get('unauthorized_classes', [])
        
        # Timestamp of the last alert (for cooldown management)
        # Initialized to 0 (epoch) so first alert is always allowed
        self.last_alert_time = 0
        
        # ====================================================================
        # Current Monitoring State
        # ====================================================================
        
        # List of currently detected unauthorized objects
        # Updated each frame with current detections
        self.current_unauthorized_detections = []
        
        # Timestamp when current unauthorized detection period started
        # None if no unauthorized objects are currently detected
        self.detection_start_time = None
        
    def check_unauthorized_access(self, detections: List[Dict], timestamp: float) -> Dict:
        """
        Check if current detections indicate unauthorized access.
        
        This is the main method that evaluates object detections against
        security rules. It performs multiple checks:
        1. Filters for unauthorized object classes
        2. Validates minimum object count
        3. Checks time-based restrictions
        4. Checks restricted zones
        5. Tracks detection duration
        6. Enforces alert cooldown
        
        The method uses stateful tracking to determine if unauthorized
        objects have been detected for a sustained period (exceeding
        the detection_duration threshold).
        
        Args:
            detections: List of detection dictionaries from ObjectDetector
                      Each dict contains: 'class', 'confidence', 'bbox', 'center'
            timestamp: Current Unix timestamp (float)
                     Used for duration calculation and cooldown management
                     
        Returns:
            Dictionary containing:
            - 'is_unauthorized': bool - True if unauthorized access is confirmed
            - 'reason': str - Human-readable explanation of the decision
            - 'detections': List - Unauthorized detections in current frame
            - 'duration': float - How long unauthorized access has been detected (seconds)
            - 'zone_violations': List[str] - Names of violated restricted zones (if any)
            
        Example Return Values:
            # No unauthorized objects:
            {'is_unauthorized': False, 'reason': 'No unauthorized objects detected', ...}
            
            # Detection in progress (not long enough yet):
            {'is_unauthorized': False, 'reason': 'Detection in progress (1.2s / 2.0s)', ...}
            
            # Unauthorized access confirmed:
            {'is_unauthorized': True, 'reason': 'Unauthorized person detected for 2.5s', ...}
        """
        # ====================================================================
        # Step 1: Filter for Unauthorized Object Classes
        # ====================================================================
        
        # Filter detections to only include unauthorized object classes
        # This removes detections of allowed objects (e.g., if only monitoring "person")
        unauthorized_dets = [
            det for det in detections 
            if det['class'] in self.unauthorized_objects
        ]
        
        # If no unauthorized objects detected, reset state and return
        if not unauthorized_dets:
            # Reset detection state since no unauthorized objects present
            self.current_unauthorized_detections = []
            self.detection_start_time = None
            return {
                'is_unauthorized': False,
                'reason': 'No unauthorized objects detected',
                'detections': [],
                'duration': 0.0
            }
        
        # ====================================================================
        # Step 2: Check Minimum Object Count
        # ====================================================================
        
        # Verify we have enough unauthorized objects to trigger monitoring
        # This prevents alerts from single brief detections
        if len(unauthorized_dets) < self.min_objects:
            return {
                'is_unauthorized': False,
                'reason': f'Insufficient objects (found {len(unauthorized_dets)}, need {self.min_objects})',
                'detections': unauthorized_dets,
                'duration': 0.0
            }
        
        # ====================================================================
        # Step 3: Check Time-Based Access Rules
        # ====================================================================
        
        # Evaluate time-based restrictions if enabled
        if self.time_based_rules.get('enabled', False):
            # Get current hour (0-23)
            current_hour = datetime.now().hour
            
            # Get list of restricted hours from configuration
            restricted_hours = self.time_based_rules.get('restricted_hours', [])
            
            if current_hour in restricted_hours:
                # Current hour is in restricted period - continue with detection
                # (unauthorized access is not allowed during these hours)
                pass
            else:
                # Current hour is NOT in restricted period - allow access
                # (unauthorized access is only monitored during restricted hours)
                return {
                    'is_unauthorized': False,
                    'reason': 'Outside restricted hours',
                    'detections': unauthorized_dets,
                    'duration': 0.0
                }
        
        # ====================================================================
        # Step 4: Check Restricted Zones
        # ====================================================================
        
        # Check if detections are in any restricted zones
        # Returns list of zone names that were violated
        zone_violations = self._check_restricted_zones(unauthorized_dets)
        
        # ====================================================================
        # Step 5: Track Detection Duration
        # ====================================================================
        
        # Start tracking detection duration if this is the first frame with unauthorized objects
        if self.detection_start_time is None:
            # Record when unauthorized detection period started
            self.detection_start_time = timestamp
            # Store current detections for duration tracking
            self.current_unauthorized_detections = unauthorized_dets
        
        # Calculate how long unauthorized objects have been continuously detected
        duration = timestamp - self.detection_start_time
        
        # ====================================================================
        # Step 6: Evaluate Duration Threshold and Cooldown
        # ====================================================================
        
        # Check if detection duration exceeds the threshold
        if duration >= self.detection_duration:
            # Duration threshold met - check if we're in cooldown period
            # Cooldown prevents alert spam when objects remain detected
            if timestamp - self.last_alert_time < self.alert_cooldown:
                # Still in cooldown period - don't trigger new alert
                return {
                    'is_unauthorized': False,
                    'reason': 'In cooldown period',
                    'detections': unauthorized_dets,
                    'duration': duration
                }
            
            # ====================================================================
            # Unauthorized Access Confirmed!
            # ====================================================================
            
            # Update last alert time to start cooldown period
            self.last_alert_time = timestamp
            
            # Build human-readable reason message
            # Get unique class names from detections
            unique_classes = set(d['class'] for d in unauthorized_dets)
            reason = f"Unauthorized {', '.join(unique_classes)} detected for {duration:.1f}s"
            
            # Add zone violation information if applicable
            if zone_violations:
                reason += f" in restricted zone(s)"
            
            # Return unauthorized access confirmation
            return {
                'is_unauthorized': True,
                'reason': reason,
                'detections': unauthorized_dets,
                'duration': duration,
                'zone_violations': zone_violations
            }
        
        # ====================================================================
        # Detection in Progress (Not Long Enough Yet)
        # ====================================================================
        
        # Unauthorized objects detected, but duration hasn't exceeded threshold
        # Update current detections and return progress status
        self.current_unauthorized_detections = unauthorized_dets
        return {
            'is_unauthorized': False,
            'reason': f'Detection in progress ({duration:.1f}s / {self.detection_duration}s)',
            'detections': unauthorized_dets,
            'duration': duration
        }
    
    def _check_restricted_zones(self, detections: List[Dict]) -> List[str]:
        """
        Check if any detections are within restricted zones.
        
        This private method evaluates whether detected objects are located
        within any configured restricted zones. A restricted zone is defined
        as a rectangular area (bounding box) where unauthorized access is
        prohibited. The check uses the center point of each detection to
        determine if it's within a zone.
        
        Args:
            detections: List of detection dictionaries
                      Each dict must contain 'center' key with (x, y) tuple
                      
        Returns:
            List of zone names that were violated (strings)
            Empty list if no violations or no zones configured
            
        Zone Configuration Format:
            restricted_zones = [
                {
                    'name': 'Front Door',
                    'bbox': [x1, y1, x2, y2]  # Bounding box coordinates
                },
                ...
            ]
            
        Note:
            This is a private method (indicated by leading underscore)
            It's called internally by check_unauthorized_access()
        """
        # If no restricted zones configured, return empty list
        if not self.restricted_zones:
            return []
        
        # List to store names of violated zones
        violations = []
        
        # Check each configured restricted zone
        for zone in self.restricted_zones:
            # Get zone name (for reporting)
            zone_name = zone.get('name', 'Unknown')
            
            # Get zone bounding box coordinates [x1, y1, x2, y2]
            zone_bbox = zone.get('bbox', [])
            
            # Validate zone bounding box has 4 coordinates
            if len(zone_bbox) != 4:
                # Invalid zone definition - skip
                continue
            
            # Check each detection against this zone
            for det in detections:
                # Get center point of detection
                center = det['center']
                x, y = center
                
                # Check if detection center point is within zone bounding box
                # Zone bbox: [x1, y1, x2, y2] where (x1,y1) is top-left, (x2,y2) is bottom-right
                if (zone_bbox[0] <= x <= zone_bbox[2] and 
                    zone_bbox[1] <= y <= zone_bbox[3]):
                    # Detection is within this restricted zone
                    violations.append(zone_name)
                    # Break inner loop - one violation per zone is enough
                    break
        
        return violations
    
    def reset(self):
        """
        Reset detection state to initial values.
        
        This method clears all tracking state, including current detections,
        detection start time, and detection history. Useful for resetting
        the monitor after an event or when restarting monitoring.
        
        Note:
            This does not reset configuration values - only runtime state
        """
        # Clear current unauthorized detections
        self.current_unauthorized_detections = []
        
        # Reset detection start time (no active detection period)
        self.detection_start_time = None
        
        # Clear detection history
        self.detection_history.clear()
    
    def get_status(self) -> Dict:
        """
        Get current monitoring status and configuration.
        
        This method returns a dictionary containing the current state of
        the security monitor, including configuration values and current
        detection state. Useful for status reporting and debugging.
        
        Returns:
            Dictionary containing:
            - 'monitoring': Always True (monitor is active)
            - 'unauthorized_classes': List of monitored class names
            - 'detection_duration_threshold': Duration threshold in seconds
            - 'min_objects': Minimum objects required for alert
            - 'restricted_zones_count': Number of configured restricted zones
            - 'last_alert_time': Timestamp of last alert (0 if never)
            - 'current_detections': Number of currently detected unauthorized objects
        """
        return {
            'monitoring': True,  # Monitor is always active when instantiated
            'unauthorized_classes': self.unauthorized_objects,  # List of monitored classes
            'detection_duration_threshold': self.detection_duration,  # Duration threshold (seconds)
            'min_objects': self.min_objects,  # Minimum object count
            'restricted_zones_count': len(self.restricted_zones),  # Number of zones
            'last_alert_time': self.last_alert_time,  # Last alert timestamp
            'current_detections': len(self.current_unauthorized_detections)  # Current detection count
        }


