#Pi Time-lapse Camera
##Introduction 
A Raspberry PI camera with time-lapse functionality. This project is combines [Adafruit's DIY WiFi Raspberry PI touchscreen Camera](https://learn.adafruit.com/diy-wifi-raspberry-pi-touch-cam/overview)
and some features from David Hunt's [Lapse Pi - Motorised time-lapse Rail with Raspberry Pi](http://www.davidhunt.ie/motorised-time-lapse-rail-with-raspberry-pi/).
The time-lapse image image(s) can be uploaded to dropbox and used on a webpage such as a [blog](http://tarababa.blogspot.com/2014/12/langebaan-webcam.html)

##Time-lapse
This project provides the Raspberry PI camera with a time lapse mode allowing the user to set the number of images and the delay between images using the PI TFT 2.8 inch touch screen.

##WebcamMode
When the *webcam* mode is enabled the camera will up take each images taken, resize, copy and rename it to $HOME/Photos/webcam/IMG_0001.JPG to dropbox folder Photos/webcam/IMG_0001.JPG.
This only works when *Store Mode: Dropbox* is selected. The original photo in its chosen resolution is not uploaded, it is however stored locally in $HOME/Photos. WebcamMode works indepent
from the time-lapse mode and at the time of writing cannot be set using the GUI. 

###WebcamImageOnly
Works only in conjunction with webcamMode activated and *Store Mode: Dropbox*. When webcamImageOnly is set to True then the camera takes a small image only which is stored locally ( $HOME/Photos/webcam/IMG_0001.JPG) 
and uploaded to dropbox folder Photos/webcam/IMG_0001.JPG. Every new image overwrites the previous one. This option cannot controlled through GUI (yet).

###WebcamModeAnnotation
Works only in conjuction with webcamMode ativated. When webcamModeAnnotation is set to True a timestamp is embedded at the top of each picture taken. This option cannot be controlled through the GUI (yet).

##Setup
### Adafruit PiTFT 2.8" Touchscreen
Setup your Raspberry PI and follow the instructions to setup [Adafruit's PITFT - 2.8" Touchscreen display for Raspberry PI](https://learn.adafruit.com/adafruit-pitft-28-inch-resistive-touchscreen-display-raspberry-pi/overview)([pdf](https://learn.adafruit.com/downloads/pdf/adafruit-pitft-28-inch-resistive-touchscreen-display-raspberry-pi.pdf)). 
It is not necessary to add the shutdown button or any other tactile buttons on the PiTFT.

### Camera software
To install the Pi Timelapse camera software follow Adafruit's instructions to setup the [DIY WiFI Raspberry Pi Touschscreen Camera](https://learn.adafruit.com/diy-wifi-raspberry-pi-touch-cam/overview) ([pdf](https://learn.adafruit.com/downloads/pdf/diy-wifi-raspberry-pi-touch-cam.pdf)), with
the following exceptions:

1. Install the *latest* version of picamera

        sudo apt-get install python-pip
        sudo pip install picamera
2. Download and use PiTimelapseCam

        wget https://github.com/tarababa/05-PiTimelapseCam/archive/master.zip
        unzip master.zip
        python cam.py

In order to use the webcam mode it is essential to set a dropbox account as described on [raspi.tv](http://raspi.tv/2013/how-to-use-dropbox-with-raspberry-pi)

Both webcamMode and webcamImagesOnly are by default setup to True and at this point cannot be altered through the user interface in order to change alter the relevant lines in cam.py:
```
webcamMode            = True       # upload file to dropbox always with same name    
webcamImageOnly       = True       # only take small size pic. for upload to dropbox.
```

To disable the timestamp at the top of the image, which is enabled by default, turn off webcamModeAnnotation. Again this flag cannot (yet) be set using the user interface and must be
altered directly in the code:
```
webcamModeAnnotation  = True       # Annotate image when in webcame mode
```

