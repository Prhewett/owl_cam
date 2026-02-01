Backgound. 
I build an Owl Box to encourage A family of Owls to move onto our place and hopefully eat some of the rodents that are living in and near the barn.
After it was built and mounted 5 meters up a pole, I realised I really wanted to see what was going on there.
I had many questions:
What is habitated ?
Were there some baby owls ?
What do Owls get up to during the day ?
The obvious answer was a camera, but the Owl box is not near power and a long way up a pole - so changing batteries in a trail cam....wasnt an options 
So I figured I'd build my own owl camera and power it off a battery and a solar panel. 
But that meant I needed to have a camera that was low power but sophisticatd enough to take timelpase video and push it to the cloud
Enter the Raspberry Pi Zero 2 W with a wide angle IR Pi3 Camera. 
(see the images in the repo of the setup)
This Repo is replicated on the pi and the pi is on our home Wifi so I can make changes, ssh to the pi Zero and test them live. 
So far it works pretty well (Jan 2026).
The Pi seems to use little enough power that a full charge of the 90 AH battery keeps it running all night, while taking still every 15 minutes and making a time lapse, then pushing them to an EC2 server. 

Github Copilot was used to write most of the code, then modified for my purposes.
It works well and I've since added a bash script to do some cleanup and use ffmpeg to make the timelapse.
Why FFMpeg ? The Pi Zero doesn't have a lot of CPU and No GPU's so creating video onboard is a delcate job of tuning - I learnt that the picamera library really taxes the Pi , so I take hi res images in python, then use ffmpeg to stitch together lower res images once the python code has captured them. 
The code then creates a html file and pushes the file the images and the timelapse video to the simple apache web server running on an AWS EC2 Micro instance.

Quick setup / notes

Install required system packages (run on the Pi):

Update the system: sudo apt update && sudo apt full-upgrade -y

Install libcamera apps and Picamera2 (on Raspberry Pi OS these are available in the repos): sudo apt install -y python3-picamera2 python3-libcamera libcamera-apps

If you want the command-line test tool: rpicam-still -o test.jpg

Short usage examples

Single capture: python3 capture_pi.py --single --outdir ./images

Timelapse, 60 frames every 5 seconds: python3 capture_pi.py --timelapse --interval 5 --count 60 --outdir ./images



