Quick setup / notes

Install required system packages (run on the Pi):
Update the system: sudo apt update && sudo apt full-upgrade -y
Install libcamera apps and Picamera2 (on Raspberry Pi OS these are available in the repos): sudo apt install -y python3-picamera2 python3-libcamera libcamera-apps
If you want the command-line test tool: rpicam-still -o test.jpg
For GPIO button support: sudo apt install -y python3-rpi.gpio

Short usage examples

Single capture: python3 capture_pi.py --single --outdir ./images
Timelapse evecapt  ry 10 seconds indefinitely: python3 capture_pi.py --timelapse --interval 10 --outdir ./images

Timelapse, 60 frames every 2 seconds: python3 capture_pi.py --timelapse --interval 2 --count 60 --outdir ./images

Button capture on GPIO17: python3 capture_pi.py --button --button-pin 17 --outdir ./images


