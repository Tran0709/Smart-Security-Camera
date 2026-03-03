"""
Quick script to check webcam resolution and capabilities.

This script opens your webcam and displays its current resolution,
frame rate, and other properties without running the full security
camera system.

Usage:
    python check_webcam_resolution.py [camera_index]
    
    camera_index: Camera device index (default: 0)
                  Use 0 for first camera, 1 for second, etc.
"""

import cv2
import sys

def check_webcam_properties(camera_index=0):
    """
    Check and display webcam properties including resolution and frame rate.
    
    Args:
        camera_index: Index of the camera device (default: 0)
    """
    print("=" * 60)
    print("Webcam Resolution Checker")
    print("=" * 60)
    print(f"Opening camera {camera_index}...")
    
    # Open camera
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"\nError: Could not open camera {camera_index}")
        print("\nTips:")
        print("  - Make sure your webcam is connected")
        print("  - Try a different camera index (0, 1, 2, etc.)")
        print("  - Check if another application is using the camera")
        return
    
    # Get current properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    backend = cap.getBackendName()
    
    print(f"\n✓ Camera {camera_index} opened successfully")
    print(f"  Backend: {backend}")
    print(f"\nCurrent Resolution: {width} x {height}")
    
    if fps > 0:
        print(f"Current Frame Rate: {fps:.2f} FPS")
    else:
        print("Current Frame Rate: Unknown (will be measured during capture)")
    
    # Test common resolutions
    print("\n" + "=" * 60)
    print("Testing Common Resolutions:")
    print("=" * 60)
    
    test_resolutions = [
        (640, 480, "VGA"),
        (800, 600, "SVGA"),
        (1024, 768, "XGA"),
        (1280, 720, "HD 720p"),
        (1920, 1080, "Full HD 1080p"),
    ]
    
    supported_resolutions = []
    
    for test_width, test_height, name in test_resolutions:
        # Try to set the resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, test_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, test_height)
        
        # Read a frame to apply the settings
        ret, _ = cap.read()
        
        # Get actual resolution (may differ from requested)
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if actual_width == test_width and actual_height == test_height:
            status = "✓ Supported"
            supported_resolutions.append((test_width, test_height, name))
        else:
            status = f"→ Falls back to {actual_width}x{actual_height}"
        
        print(f"  {name:15} ({test_width:4}x{test_height:4}): {status}")
    
    # Reset to original resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    # Display summary
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"Current Resolution: {width} x {height}")
    if supported_resolutions:
        print(f"\nSupported Resolutions ({len(supported_resolutions)}):")
        for w, h, name in supported_resolutions:
            print(f"  - {name}: {w} x {h}")
    
    # Optional: Show live preview
    print("\n" + "=" * 60)
    response = input("Show live preview? (y/n): ").strip().lower()
    
    if response == 'y':
        print("Showing live preview. Press 'q' to quit...")
        frame_count = 0
        import time
        start_time = time.time()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame")
                break
            
            frame_count += 1
            current_time = time.time()
            elapsed = current_time - start_time
            
            if elapsed > 0:
                fps = frame_count / elapsed
            else:
                fps = 0
            
            # Add info overlay
            info_text = f"Resolution: {width}x{height} | FPS: {fps:.1f}"
            cv2.putText(frame, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow('Webcam Preview', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()
    
    # Cleanup
    cap.release()
    print("\nCamera released.")


if __name__ == "__main__":
    # Get camera index from command line or use default
    camera_index = 0
    if len(sys.argv) > 1:
        try:
            camera_index = int(sys.argv[1])
        except ValueError:
            print(f"Error: Invalid camera index '{sys.argv[1]}'. Using default (0).")
    
    check_webcam_properties(camera_index)


