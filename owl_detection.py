"""
owl_detection.py

Subroutine to detect if an image contains an owl using multiple methods.
Supports both YOLO (via ultralytics) and basic feature-based detection.

Installation:
  For YOLO detection (recommended):
    pip3 install ultralytics opencv-python-headless pillow

  For basic detection (no additional deps beyond Pillow):
    Uses only PIL and built-in libraries
"""

import os
from PIL import Image
import logging

# Optional imports for YOLO detection
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# Optional OpenCV import for advanced image processing
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

logger = logging.getLogger(__name__)


def detect_owl_yolo(image_path, confidence_threshold=0.5):
    """
    Detect owls in an image using YOLOv8 (requires ultralytics and models).
    
    Args:
        image_path (str): Path to image file
        confidence_threshold (float): Minimum confidence score (0-1)
    
    Returns:
        dict: {
            'is_owl': bool,
            'confidence': float (0-1),
            'detections': int (number of owl detections),
            'method': 'yolo',
            'error': str or None
        }
    """
    if not YOLO_AVAILABLE:
        return {
            'is_owl': False,
            'confidence': 0.0,
            'detections': 0,
            'method': 'yolo',
            'error': 'YOLO not available. Install ultralytics: pip3 install ultralytics'
        }
    
    try:
        # Load YOLOv8 model (nano version is faster, but larger models are more accurate)
        # First time will download model (~6MB for nano, ~80MB for small)
        model = YOLO('yolov8n.pt')  # nano model (fastest)
        
        # Run inference
        results = model(image_path, conf=confidence_threshold, verbose=False)
        
        # Check if any detections are labeled as 'bird' or similar
        # COCO dataset doesn't have 'owl' class, but owls are detected as birds
        owl_detected = False
        max_confidence = 0.0
        detection_count = 0
        
        for result in results:
            if result.boxes is None:
                continue
            
            for box in result.boxes:
                class_id = int(box.cls)
                confidence = float(box.conf)
                class_name = model.names[class_id]
                
                # COCO class 14 is 'bird', 0 is 'person', etc.
                # Owls typically detected as 'bird' class
                if class_name.lower() in ['bird', 'owl']:
                    if confidence > max_confidence:
                        max_confidence = confidence
                    detection_count += 1
                    owl_detected = True
        
        return {
            'is_owl': owl_detected,
            'confidence': max_confidence,
            'detections': detection_count,
            'method': 'yolo',
            'error': None
        }
    
    except Exception as e:
        logger.error(f"YOLO detection failed for {image_path}: {e}")
        return {
            'is_owl': False,
            'confidence': 0.0,
            'detections': 0,
            'method': 'yolo',
            'error': str(e)
        }


def detect_owl_basic(image_path):
    """
    Basic feature-based owl detection using image analysis.
    Looks for characteristics typical of owls:
    - Circular/round shapes (head)
    - Dark center regions (eyes)
    - Relatively dark coloration
    
    Args:
        image_path (str): Path to image file
    
    Returns:
        dict: {
            'is_owl': bool,
            'confidence': float (0-1, rough estimate),
            'features_found': list of detected features,
            'method': 'basic',
            'error': str or None
        }
    """
    try:
        img = Image.open(image_path).convert('RGB')
        width, height = img.size
        
        # Check if image is reasonable size (not a blank/error image)
        if width < 50 or height < 50:
            return {
                'is_owl': False,
                'confidence': 0.0,
                'features_found': [],
                'method': 'basic',
                'error': f'Image too small: {width}x{height}'
            }
        
        # Convert to array for analysis
        img_array = list(img.getdata())
        
        # Calculate average brightness
        brightness_scores = [sum(pixel) // 3 for pixel in img_array]
        avg_brightness = sum(brightness_scores) // len(brightness_scores)
        
        # Owls are typically photographed at night/dusk: darker images
        is_dark = avg_brightness < 120
        
        # Check for high contrast regions (typical of eyes)
        contrast_high = any(
            abs(brightness_scores[i] - avg_brightness) > 100
            for i in range(min(len(brightness_scores), 1000))
        )
        
        # Check for non-uniform distribution (object vs background)
        brightness_variance = sum(
            (b - avg_brightness) ** 2 for b in brightness_scores[:min(len(brightness_scores), 1000)]
        ) / min(len(brightness_scores), 1000)
        has_structure = brightness_variance > 1000
        
        features_found = []
        confidence = 0.0
        
        if is_dark:
            features_found.append('dark_image')
            confidence += 0.2
        
        if contrast_high:
            features_found.append('high_contrast_regions')
            confidence += 0.3
        
        if has_structure:
            features_found.append('structured_content')
            confidence += 0.2
        
        # If image is not just darkness (not a blank frame)
        if avg_brightness > 20 and avg_brightness < 200:
            features_found.append('reasonable_exposure')
            confidence += 0.15
        
        # Conservative estimate: basic detection is weak
        is_owl = confidence >= 0.5
        confidence = min(confidence, 1.0)
        
        return {
            'is_owl': is_owl,
            'confidence': confidence,
            'features_found': features_found,
            'method': 'basic',
            'error': None
        }
    
    except Exception as e:
        logger.error(f"Basic detection failed for {image_path}: {e}")
        return {
            'is_owl': False,
            'confidence': 0.0,
            'features_found': [],
            'method': 'basic',
            'error': str(e)
        }


def examine_image_for_owl(image_path, use_yolo=None, confidence_threshold=0.5, debug=False):
    """
    Main subroutine to examine an image for owl presence.
    
    Args:
        image_path (str): Path to image file
        use_yolo (bool): Force YOLO (True) or basic detection (False).
                        If None, auto-selects based on availability.
        confidence_threshold (float): Minimum confidence (0-1)
        debug (bool): Print detailed results
    
    Returns:
        dict: {
            'image_path': str,
            'is_owl': bool,
            'confidence': float,
            'method': str ('yolo' or 'basic'),
            'detections': int (for YOLO) or None,
            'features': list (for basic) or None,
            'error': str or None
        }
    """
    
    # Validate file exists
    if not os.path.exists(image_path):
        result = {
            'image_path': image_path,
            'is_owl': False,
            'confidence': 0.0,
            'method': 'none',
            'error': f'File not found: {image_path}'
        }
        if debug:
            print(f"[OWL DETECT] {result['error']}")
        return result
    
    # Select detection method
    if use_yolo is None:
        use_yolo = YOLO_AVAILABLE
    
    if use_yolo and YOLO_AVAILABLE:
        result = detect_owl_yolo(image_path, confidence_threshold)
    else:
        result = detect_owl_basic(image_path)
    
    # Add image path to result
    result['image_path'] = image_path
    
    if debug:
        status = "✓ OWL DETECTED" if result['is_owl'] else "✗ NO OWL"
        confidence = result.get('confidence', 0.0)
        method = result.get('method', 'unknown')
        print(f"[OWL DETECT] {status} | Confidence: {confidence:.2f} | Method: {method} | File: {os.path.basename(image_path)}")
        
        if result.get('error'):
            print(f"  Error: {result['error']}")
        
        if result.get('detections') is not None:
            print(f"  Detections: {result['detections']}")
        
        if result.get('features_found'):
            print(f"  Features: {', '.join(result['features_found'])}")
    
    return result


def batch_examine_directory(directory, extension='.jpg', use_yolo=None, confidence_threshold=0.5, debug=False):
    """
    Examine all images in a directory for owls.
    
    Args:
        directory (str): Directory containing images
        extension (str): File extension to search for (e.g., '.jpg', '.png')
        use_yolo (bool): Force detection method
        confidence_threshold (float): Minimum confidence
        debug (bool): Print debug info
    
    Returns:
        list of dicts with results
    """
    results = []
    
    try:
        files = sorted([f for f in os.listdir(directory) if f.lower().endswith(extension)])
    except FileNotFoundError:
        logger.error(f"Directory not found: {directory}")
        return results
    
    if debug:
        print(f"[OWL DETECT] Scanning {len(files)} images in {directory}")
    
    for filename in files:
        image_path = os.path.join(directory, filename)
        result = examine_image_for_owl(image_path, use_yolo=use_yolo, confidence_threshold=confidence_threshold, debug=debug)
        results.append(result)
    
    # Summary
    owl_count = sum(1 for r in results if r['is_owl'])
    if debug:
        print(f"[OWL DETECT] Summary: {owl_count}/{len(results)} images contain owls")
    
    return results


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 owl_detection.py <image_path> [--yolo] [--debug]")
        print("   or: python3 owl_detection.py --batch <directory> [--yolo] [--debug]")
        sys.exit(1)
    
    debug_mode = '--debug' in sys.argv
    use_yolo_mode = '--yolo' in sys.argv or None
    
    if sys.argv[1] == '--batch' and len(sys.argv) > 2:
        results = batch_examine_directory(sys.argv[2], use_yolo=use_yolo_mode, debug=debug_mode)
        owl_images = [r for r in results if r['is_owl']]
        print(f"\n📸 Images with owls: {len(owl_images)}")
        for r in owl_images:
            print(f"  - {os.path.basename(r['image_path'])} (confidence: {r['confidence']:.2f})")
    else:
        result = examine_image_for_owl(sys.argv[1], use_yolo=use_yolo_mode, debug=True)
        print(f"\nResult: {result}")
