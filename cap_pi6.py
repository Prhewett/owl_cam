#!/usr/bin/env python3
"""
cap_pi6.py

Simple utility to capture images from a Raspberry Pi camera using Picamera2.

Usage examples:
  Single capture:
    python3 capture_pi4.py --single --outdir ./images

  Timelapse (every 5s, 10 frames):
    python3 capture_pi4.py --timelapse --interval 5 --count 10 --outdir ./images

  Single capture and upload to remote server via SCP:
    python3 capture_pi4.py --single --outdir ./images --scp --remote-host ec2-1-2-3-4.compute-1.amazonaws.com --remote-user ec2-user --remote-path /home/ec2-user/html --ssh-key /home/pi/.ssh/mykey.pem

  Timelapse and build/upload index:
    python3 capture_pi4.py --timelapse --interval 10 --count 100 --outdir ./images --scp --remote-host ec2-1-2-3-4.compute-1.amazonaws.com --remote-user ec2-user 
    --remote-path /home/ec2-user/html --ssh-key /home/pi/.ssh/mykey.pem --build-index

Requirements:
  - Raspberry Pi OS with libcamera (Bullseye/Bookworm or later)
  - python3-picamera2 package (see README in this script)
  - Optional: RPi.GPIO for button support
  - Optional: Pillow (PIL) to stamp date/time onto images
  - scp/ssh command-line tools for remote uploads (or install/enable them on the Pi)
"""
import argparse
import os
import sys
import time
from datetime import datetime
import subprocess
import shutil
import html
import libcamera

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

# Optional Pillow import for drawing timestamp on images
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

def image_rotate(input_path, degrees):
    """
    Rotates an image using the transpose method for 90-degree increments.
    Example Usage:
    image_transpose('input_image.jpg', 90)
    """
    try:
        with Image.open(input_path) as img:
            if degrees == 90:
                # rotate 90 degrees anti clockwise.
                rotated_img = img.transpose(Image.ROTATE_90)
            elif degrees == 180:
                # rotate 180 degrees counter-clockwise.
                rotated_img = img.transpose(Image.ROTATE_180)
            elif degrees == 270:
                # rotate 270 degrees counter-clockwise(90 degrees clockwise.
                rotated_img = img.transpose(Image.ROTATE_270)
            else:
                raise ValueError("Invalid rotation amount. Use '90', '180', or '270'")
            rotated_img.save(input_path)
            print(f"Image rotated using transpose and saved to {output_path}")
    except FileNotFoundError:
        print(f"Error: {input_path} not found. Please provide a valid image path.")
    except Exception as e:
        print(f"An error occurred: {e}")

def timestamped_filename(outdir, prefix="image", ext="jpg"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    #print ("file name date time string is:", ts)
    return os.path.join(outdir, f"{prefix}_{ts}.{ext}")

def ensure_outdir(path):
    os.makedirs(path, exist_ok=True)

def _ensure_remote_dir(remote_user, remote_host, remote_path, ssh_key=None, ssh_port=22):
    """Ensure the remote directory exists (uses ssh to run mkdir -p)."""
    if shutil.which("ssh") is None:
        print("ssh command not found; cannot ensure remote directory exists.")
        return False
    cmd = ["ssh", "-p", str(ssh_port)]
    if ssh_key:
        cmd.extend(["-i", ssh_key])
    # Quote remote_path for the remote shell
    remote_cmd = f"mkdir -p '{remote_path}'"
    cmd.append(f"{remote_user}@{remote_host}")
    cmd.append(remote_cmd)
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError as e:
        print("Failed to ensure remote directory:", e)
        return False

def _scp_upload(local_path, remote_user, remote_host, remote_path, ssh_key=None, ssh_port=22):
    """Upload a single file to remote server via scp. remote_path should be a directory."""
    if shutil.which("scp") is None:
        print("scp command not found; cannot upload file.")
        return False

    # Ensure remote directory exists
    ok = _ensure_remote_dir(remote_user, remote_host, remote_path, ssh_key=ssh_key, ssh_port=ssh_port)
    if not ok:
        print("Skipping upload; could not ensure remote directory.")
        return False

    # Build remote target path with same basename
    basename = os.path.basename(local_path)
    remote_target = f"{remote_user}@{remote_host}:{remote_path.rstrip('/')}/{basename}"

    cmd = ["scp", "-P", str(ssh_port)]
    if ssh_key:
        cmd.extend(["-i", ssh_key])
    cmd.extend([local_path, remote_target])
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        print("Uploaded:", local_path, "->", f"{remote_user}@{remote_host}:{remote_path}")
        return True
    except subprocess.CalledProcessError as e:
        # Capture stderr if available to help debugging
        stderr = e.stderr.decode("utf-8") if isinstance(e.stderr, (bytes, bytearray)) else str(e.stderr)
        print("SCP upload failed:", stderr.strip())
        return False

def build_index_html(outdir, title="Owl box Timelapse Image Index"):
    """
    Build a simple index.html in outdir that lists image files found there.
    Returns the path to the generated index file.
    """
    image_exts = ("jpg", "jpeg", "png", "gif", "webp", "mp4")
    try:
        entries = [f for f in os.listdir(outdir) if os.path.splitext(f)[1].lstrip(".").lower() in image_exts]
    except FileNotFoundError:
        entries = []

    # Sort by modification time descending (newest first)
    entries.sort(key=lambda fn: os.path.getmtime(os.path.join(outdir, fn)), reverse=True)

    # Basic HTML
    safe_title = html.escape(title)
    html_lines = [
        "<!doctype html>",
        "<html>",
        "<head>",
        f"  <meta charset='utf-8'>",
        f"  <title>{safe_title}</title>",
        "  <meta name='viewport' content='width=device-width,initial-scale=1'>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; margin: 0; padding: 1rem; }",
        "    .grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(200px,1fr)); grid-gap: 10px; }",
        "    .card { border: 1px solid #ddd; padding: 6px; background: #fff; }",
        "    img { max-width: 100%; height: auto; display: block; }",
        "    .meta { font-size: 0.85rem; color: #555; margin-top: 6px; }",
        "  </style>",
        "  <!-- Standard Favicon link -->",
        "  <link rel='icon' href='favicon.ico' type='image/x-icon'>",
        "</head>",
        "<body>",
        f"  <h1>{safe_title}</h1>",
        "  <div class='grid'>"
    ]
    # added a div section to create a thumbnail image href point to the timelapse
    html_lines.extend([
            "    <div class='card'>",
            f"      <a href='timelapse.mp4'><img src='thumbnail.jpg' alt='timelapse.mp4'></a>",
            f"      <div class='meta'>Time Lapse video.</div>",
            "    </div>"
        ])
    for fn in entries:
        path = html.escape(fn)
        full_path = os.path.join(outdir, fn)
        try:
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(full_path)))
            size_kb = os.path.getsize(full_path) // 1024
        except Exception:
            mtime = ""
            size_kb = ""
        html_lines.extend([
            "    <div class='card'>",
            f"      <a href='{path}'><img src='{path}' alt='{path}'></a>",
            f"      <div class='meta'>{path} &middot; {mtime} &middot; {size_kb} KB</div>",
            "    </div>"
        ])

    html_lines.extend([
        "  </div>",
        "</body>",
        "</html>"
    ])

    index_path = os.path.join(outdir, "index.html")
    try:
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(html_lines))
        print("Built index:", index_path)
        return index_path
    except Exception as e:
        print("Failed to write index.html:", e)
        return None

def _annotate_image_with_timestamp(image_path, text=None, font_path=None):
    """
    Annotate the saved image with a timestamp (draw text on the image).
    Uses Pillow (PIL). If PIL is not available, this is a no-op.
    Pete: Added flip and rotate functionality
    """
    print("Starting Annotate and manipulate subroutine")
    if not PIL_AVAILABLE:
        print("Pillow (PIL) not available; skipping image annotation.")
        return False

    if text is None:
        text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if args.debug: print("inside annotation - txt = none")

    try:
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # Choose font - try provided font_path, then DejaVuSans, otherwise default
        font_size = max(14, width // 40)
        font = None
        tried = []
        if font_path:
            tried.append(font_path)
            try:
                font = ImageFont.truetype(font_path, font_size)
            except Exception:
                font = None
        if font is None:
            # try common system font
            common = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            tried.append(common)
            try:
                font = ImageFont.truetype(common, font_size)
            except Exception:
                font = None
        if font is None:
            font = ImageFont.load_default()

        # Measure text
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
        except Exception:
            text_w, text_h = draw.textsize(text, font=font)

        margin = max(8, width // 200)
        x = width - text_w - margin
        y = height - text_h - margin

        # Draw background rectangle for readability
        rect_pad = max(4, margin // 2)
        rect_coords = [x - rect_pad, y - rect_pad, x + text_w + rect_pad, y + text_h + rect_pad]
        draw.rectangle(rect_coords, fill=(0, 0, 0))

        # Draw text in white
        draw.text((x, y), text, font=font, fill=(255, 255, 255))
        # Overwrite original file (keep JPEG quality reasonable)
        img.save(image_path, quality=85)
        return True
    except Exception as e:
        print("Failed to annotate image:", e)
        return False

def single_capture(picam2, outdir, scp_config=None, build_index=False, index_title="Image Index", args.rotate=None):
    ensure_outdir(outdir)
    fname = timestamped_filename(outdir)
    picam2.capture_file(fname)
    # Annotate image with timestamp (draw on image) if Pillow available
    ts_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if args.debug: print("Args.rotate value is: ", args.rotate)
    image_rotate(fname, args.rotate)
    annotated = _annotate_image_with_timestamp(fname, text=ts_text)
    if annotated:
        print("Annotated with timestamp:", ts_text)
    print("Saved:", fname)
    if scp_config:
        _scp_upload(fname, **scp_config)

    if build_index:
        idx = build_index_html(outdir, title=index_title)
        if idx and scp_config:
            _scp_upload(idx, **scp_config)

def timelapse_capture(picam2, outdir, interval, count, scp_config=None, build_index=False, index_title="Image Index", args.rotate=None):
    ensure_outdir(outdir)
    i = 0
    try:
        while count is None or i < count:
            fname = timestamped_filename(outdir, prefix=f"img{i:04d}")
            picam2.capture_file(fname)
            ts_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            annotated = _annotate_image_with_timestamp(fname, text=ts_text)
            if annotated:
                print(f"[{i+1}] Annotated with timestamp: {ts_text}")
            print(f"[{i+1}] Saved: {fname}")
            i += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Timelapse interrupted by user.")

def main():
    parser = argparse.ArgumentParser(description="Capture images from Pi camera using Picamera2")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--single", action="store_true", help="Take a single still image")
    mode.add_argument("--timelapse", action="store_true", help="Take repeated images at interval")

    parser.add_argument("--outdir", default="./images", help="Output directory for images")
    parser.add_argument("--interval", type=float, default=5.0, help="Interval between timelapse captures (seconds)")
    parser.add_argument("--count", type=int, default=None, help="Number of timelapse frames (omit for infinite)")
    parser.add_argument("--width", type=int, default=None, help="Requested image width (optional)")
    parser.add_argument("--height", type=int, default=None, help="Requested image height (optional)")

    # SCP / remote upload options
    parser.add_argument("--scp", action="store_true", help="Enable SCP upload of captured images to remote server")
    parser.add_argument("--remote-host", help="Remote host for SCP (e.g. ec2-1-2-3-4.compute-1.amazonaws.com)")
    parser.add_argument("--remote-user", help="Remote SSH user (e.g. ubuntu)")
    parser.add_argument("--remote-path", help="Remote directory path to upload files into (must be writable)")
    parser.add_argument("--ssh-key", help="Path to SSH private key for authentication (optional)")
    parser.add_argument("--ssh-port", type=int, default=22, help="SSH port for remote host (default 22)")

    # Index generation/upload options
    parser.add_argument("--build-index", action="store_true", help="Build a simple index.html in outdir listing captured images and upload it when SCP is enabled")
    parser.add_argument("--index-title", default="Owl Box Image Index", help="Title for generated index.html")

    # Pete: debug options
    parser.add_argument("--debug", action="store_true", help="will cause the script to output various printed debug lines")
    # Pete - Add argument to flip or rotate the image
    parser.add_argument("--hflip", action="store_true", help="will flip the image(s) at capture, horizontally. ")
    parser.add_argument("--vflip", action="store_true", help="will flip the image(s) at capture, vertically. ")
    parser.add_argument("--rotate", type=int, default=90, help="will rotate the image(s) (default 90) degrees at capture, counter clockwise. Use 270 for 90 clockwise ")
  
    args = parser.parse_args()

    scp_config = None
    if args.scp:
        # Validate required fields for scp
        missing = []
        if not args.remote_host:
            missing.append("--remote-host")
        if not args.remote_user:
            missing.append("--remote-user")
        if not args.remote_path:
            missing.append("--remote-path")
        if missing:
            parser.error("SCP enabled but missing required options: " + ", ".join(missing))
        scp_config = {
            "remote_user": args.remote_user,
            "remote_host": args.remote_host,
            "remote_path": args.remote_path,
            "ssh_key": args.ssh_key,
            "ssh_port": args.ssh_port,
        }

    # Create and configure camera
    picam2 = Picamera2()
    # If user specified resolution, configure a still config with that size. Otherwise use default still config.
    if args.width and args.height:
        cfg = picam2.create_still_configuration(main={"size": (args.width, args.height)})
    else:
        cfg = picam2.create_still_configuration()

    # added by pete to rotate the image
    if args.rotate:
        print("args.rotate found. value is: ", args.rotate)  
    picam2.configure(cfg)

    # Start camera and give AE/AGC a moment to settle
    picam2.start()
    time.sleep(1.5)

    if not PIL_AVAILABLE:
        print("Note: Pillow (PIL) not installed. Images will still be saved, but timestamps will not be drawn on the images.")
        print("Install Pillow with: sudo apt install python3-pil or pip3 install pillow")

    try:
        if args.single:
            single_capture(picam2, args.outdir, scp_config=scp_config, build_index=args.build_index, index_title=args.index_title, args.rotate)
        elif args.timelapse:
            timelapse_capture(picam2, args.outdir, args.interval, args.count, scp_config=scp_config, build_index=args.build_index, index_title=args.index_title, args.rotate)
    finally:
        # added by pete to create the index at the end and upload all at once
        #if build_index:
        idx = build_index_html(args.outdir, title="Owl Box Timelapse Image Index")
        if idx and scp_config:
            _scp_upload(idx, **scp_config)  
        image_exts = ("jpg", "jpeg", "png", "gif", "webp", "mp4")
        try:
            entries = [f for f in os.listdir(args.outdir) if os.path.splitext(f)[1].lstrip(".").lower() in image_exts]
        except FileNotFoundError:
            entries = []
        # Sort by modification time descending (newest first)
        entries.sort(key=lambda fn: os.path.getmtime(os.path.join(args.outdir, fn)), reverse=True)
        # and then upload them all
        for fn in entries:  
            fn = args.outdir + "/" + fn
            #print (fn)
            _scp_upload(fn, **scp_config)
        # created a thumbnail of the last iage and upload it
        shutil.copy2(fn, "thumbnail.jpg")
        _scp_upload("thumbnail.jpg", **scp_config)
    #Added debug for stopping camera
    if args.debug:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("######## Stopping camera inside python at: ", now)
    picam2.stop()
    if args.debug:
        print("######## after picam.stop: ", now)
    picam2.close()
    if args.debug:
        print("######## after picam.close: ", now)
        print("######## sleeping for 5: ", now)
    time.sleep(5)
    if args.debug:
        print("######## sleeping complete - end of puthon: ", now)
  
if __name__ == "__main__":
    main()
