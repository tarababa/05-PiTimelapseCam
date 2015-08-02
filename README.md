#Pi Time-lapse Camera
##Introduction 
A Raspberry PI camera with time-lapse functionality. This project is combines [Adafruit's DIY WiFi Raspberry PI touchscreen Camera](https://learn.adafruit.com/diy-wifi-raspberry-pi-touch-cam/overview)
and some features from David Hunt's [Lapse Pi - Motorised time-lapse Rail with Raspberry Pi](http://www.davidhunt.ie/motorised-time-lapse-rail-with-raspberry-pi/).
The time-lapse image(s) can be uploaded to dropbox and used on a webpage such as a [blog](http://tarababa.blogspot.com/2014/12/langebaan-webcam.html) or in this read.me as shown below.

![Time-lapse Camera](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/timelapseCamInaBox.jpg) <img src="https://dl.dropboxusercontent.com/s/hbpw8lk70x03uzi/IMG_0001.JPG" width="320">

##Overview
An overview of the capabilities of this application, to a large extent a repetition of the information provided by the linked documents in the previous chapter.
###Startup screen
The startup screen as shown below has three buttons at the bottom, from left to right:
* Settings: navigate to settings menus
* Timelapse: toggles timelapse between on and off
* Preview: show photos taken

Touching the screen anywhere else besides the buttons will take a photo, as shown in the righ-hand screenshot below.

![Start-up screen](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/mainscreen.png) | ![Start-up screen working](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/mainscreen_working.png)

###Settings
To navigate between the various settings use the top arrows in the settings menus.The done button at the bottom of the settings menu takes the user back to the main screen.

####Storage
Where your photos should be stored by selecting the desired option. To use Dropbox, which is essentail for the webcam mode described further below, a Dropbox account must be created as described on [raspi.tv](http://raspi.tv/2013/how-to-use-dropbox-with-raspberry-pi)

![Storage settings](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/settings_storage.png) 

####Size
Select the size for your photos.

![Size settings](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/settings_size.png) 

####Effect
Use the bottom arrows to select the desired effect.

![Effect settings](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/settings_effect.png) 

####ISO
Use the bottom arrows to change the ISO setting

![ISO settings](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/settings_iso.png) 

####Time-lapse
Here we can define the number of photos (*Images*), max 9999, and the time-delay in seconds (*Interval*) between the photos for the time-lapse mode.
Click the sprocket symbol next to these values to change them using the keypad dialog as shown in the two screen shots below.

![Time-lapse settings](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/settings_timelapse.png)|![Time-lapse settings](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/settings_timelapse_change.png)

####Webcam
When the *Webcam mode* is enabled then each image taken is resized, renamed and copied to $HOME/Photos/webcam/IMG_0001.JPG and from there to dropbox folder Photos/webcam/IMG_0001.JPG, each time overwriting the previous webcam image. This only works when *Storage Mode: Dropbox* is selected. The original photo in its chosen resolution is not uploaded, it is however stored locally in $HOME/Photos. Webcam mode works independent from the time-lapse mode. This mode and the following two options can be set through the *Webcam* settings screen as shown below by ticking or un-ticking the associated check-boxes

The *Webcam image only* setting works only in conjunction with *Webcam mode* activated and *Storage Mode: Dropbox*. When the checkbox for "Webcam image only" is ticked the camera takes a small image only which is stored locally ($HOME/Photos/webcam/IMG_0001.JPG) and uploaded to dropbox folder Photos/webcam/IMG_0001.JPG. Every new image overwrites the previous one.

![Webcam settings](https://github.com/tarababa/05-PiTimelapseCam/blob/master/img/doc/settings_webcam.png)

*Annotate image* also only works in conjuction with *Webcam mode* ativated. When the checkbox for *Annotate image* is ticked a timestamp is embedded at the top of each picture taken.

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
        sudo python ./05-PiTimelapseCam/src/cam.py

In order to use the webcam mode it is essential to set a dropbox account as described on [raspi.tv](http://raspi.tv/2013/how-to-use-dropbox-with-raspberry-pi)



