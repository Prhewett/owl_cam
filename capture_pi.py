#!/usr/bin/env python3
"""
capture_pi.py

Simple utility to capture images from a Raspberry Pi camera using Picamera2.

Usage examples:
  Single capture:
    python3 capture_pi.py --single --outdir ./images

  Timelapse (every 5s, 10 frames):
    python3 capture_pi.py --timelapse --interval 5 --count 10 --outdir ./images

  Button-triggered capture (GPIO pin 17, falling edge):
    python3 capture_pi.py --button --button-pin 17 --outdir ./images

Requirements:
  - Raspberry Pi OS with libcamera (Bullseye/Bookworm or later)
  - python3-picamera2 package (see README below)
  - Optional: RPi.GPIO for button support
"""
import argparse
import os
import sys
import time
from datetime import datetime

try:
    from picamera2 import Picamera2
except Exception as e:
    print("Error importing Picamera2:", e)
    print("Install picamera2 (see README in this script). Exiting.")
    sys.exit(1)

# Optional import for button mode
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

def timestamped_filename(outdir, prefix="image", ext="jpg"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return os.path.join(outdir, f"{prefix}_{ts}.{ext}")

def ensure_outdir(path):
    os.makedirs(path, exist_ok=True)

def single_capture(picam2, outdir):
    ensure_outdir(outdir)
    fname = timestamped_filename(outdir)
    picam2.capture_file(fname)
    print("Saved:", fname)

def timelapse_capture(picam2, outdir, interval, count):
    ensure_outdir(outdir)
    i = 0
    try:
        while count is None or i < count:
            fname = timestamped_filename(outdir, prefix=f"img{i:04d}")
            picam2.capture_file(fname)
            print(f"[{i+1}] Saved: {fname}")
            i += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Timelapse interrupted by user.")

def button_capture(picam2, outdir, button_pin, bouncetime=300):
    if not GPIO_AVAILABLE:
        print("RPi.GPIO module not available. Install RPi.GPIO to use button mode.")
        return

    ensure_outdir(outdir)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    print(f"Waiting for button presses on GPIO {button_pin}. Ctrl-C to quit.")

    def handler(channel):
        fname = timestamped_filename(outdir, prefix="btn")
        picam2.capture_file(fname)
        print("Button pressed — saved:", fname)

    GPIO.add_event_detect(button_pin, GPIO.FALLING, callback=handler, bouncetime=bouncetime)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting button capture.")
    finally:
        GPIO.cleanup()

def main():
    parser = argparse.ArgumentParser(description="Capture images from Pi camera using Picamera2")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--single", action="store_true", help="Take a single still image")
    mode.add_argument("--timelapse", action="store_true", help="Take repeated images at interval")
    mode.add_argument("--button", action="store_true", help="Capture on GPIO button press")

    parser.add_argument("--outdir", default="./images", help="Output directory for images")
    parser.add_argument("--interval", type=float, default=5.0, help="Interval between timelapse captures (seconds)")
    parser.add_argument("--count", type=int, default=None, help="Number of timelapse frames (omit for infinite)")
    parser.add_argument("--button-pin", type=int, default=17, help="BCM GPIO pin for button mode (default 17)")
    parser.add_argument("--width", type=int, default=None, help="Requested image width (optional)")
    parser.add_argument("--height", type=int, default=None, help="Requested image height (optional)")

    args = parser.parse_args()

    # Create and configure camera
    picam2 = Picamera2()
    # If user specified resolution, configure a still config with that size. Otherwise use default still config.
    if args.width and args.height:
        cfg = picam2.create_still_configuration(main={"size": (args.width, args.height)})
    else:
        cfg = picam2.create_still_configuration()
    picam2.configure(cfg)

    # Start camera and give AE/AGC a moment to settle
    picam2.start()
    time.sleep(1.5)

    try:
        if args.single:
            single_capture(picam2, args.outdir)
        elif args.timelapse:
            timelapse_capture(picam2, args.outdir, args.interval, args.count)
        elif args.button:
            button_capture(picam2, args.outdir, args.button_pin)
    finally:
        picam2.stop()

if __name__ == "__main__":
    main()
