# Point-and-shoot camera for Raspberry Pi w/camera and Adafruit PiTFT.
# This must run as root (sudo python cam.py) due to framebuffer, etc.
#
# Adafruit invests time and resources providing this open source code, 
# please support Adafruit and open-source development by purchasing 
# products from Adafruit, thanks!
#
# http://www.adafruit.com/products/998  (Raspberry Pi Model B)
# http://www.adafruit.com/products/1367 (Raspberry Pi Camera Board)
# http://www.adafruit.com/products/1601 (PiTFT Mini Kit)
# This can also work with the Model A board and/or the Pi NoIR camera.
#
# Prerequisite tutorials: aside from the basic Raspbian setup and
# enabling the camera in raspi-config, you should configure WiFi (if
# using wireless with the Dropbox upload feature) and read these:
# PiTFT setup (the tactile switch buttons are not required for this
# project, but can be installed if you want them for other things):
# http://learn.adafruit.com/adafruit-pitft-28-inch-resistive-touchscreen-display-raspberry-pi
# Dropbox setup (if using the Dropbox upload feature):
# http://raspi.tv/2013/how-to-use-dropbox-with-raspberry-pi
# 15.01.2015 Using native dropbox API to upload files
#
# Written by Phil Burgess / Paint Your Dragon for Adafruit Industries.
# BSD license, all text above must be included in any redistribution.
#
# Adapted by Helios Taraba with parts taken from lapse.py by David Hunt (https://github.com/climberhunt/LapsePiTouch)

import atexit
import cPickle as pickle
import errno, logging, traceback
import fnmatch
import io
import os
import os.path
import picamera
import pygame
import stat
import threading
import time
import datetime as dt
import timers
import sys
import dropbox
import configuration
from pygame.locals import *
from subprocess import call  


# UI classes ---------------------------------------------------------------

# Small resistive touchscreen is best suited to simple tap interactions.
# Importing a big widget library seemed a bit overkill.  Instead, a couple
# of rudimentary classes are sufficient for the UI elements:

# Icon is a very simple bitmap class, just associates a name and a pygame
# image (PNG loaded from icons directory) for each.
# There isn't a globally-declared fixed list of Icons.  Instead, the list
# is populated at runtime from the contents of the 'icons' directory.

class Icon:
  
  def __init__(self, name):
    self.name = name
    try:
      self.bitmap = pygame.image.load(iconPath + '/' + name + '.png')
    except:
      pass
    
# Button is a simple tappable screen region.  Each has:
#  - bounding rect ((X,Y,W,H) in pixels)
#  - optional background color and/or Icon (or None), always centered
#  - optional foreground Icon, always centered
#  - optional single callback function
#  - optional single value passed to callback
# Occasionally Buttons are used as a convenience for positioning Icons
# but the taps are ignored.  Stacking order is important; when Buttons
# overlap, lowest/first Button in list takes precedence when processing
# input, and highest/last Button is drawn atop prior Button(s).  This is
# used, for example, to center an Icon by creating a passive Button the
# width of the full screen, but with other buttons left or right that
# may take input precedence (e.g. the Effect labels & buttons).
# After Icons are loaded at runtime, a pass is made through the global
# buttons[] list to assign the Icon objects (from names) to each Button.

class Button:
  
  def __init__(self, rect, **kwargs):
    self.rect     = rect # Bounds
    self.color    = None # Background fill color, if any
    self.iconBg   = None # Background Icon (atop color fill)
    self.iconFg   = None # Foreground Icon (atop background)
    self.bg       = None # Background Icon name
    self.fg       = None # Foreground Icon name
    self.callback = None # Callback function
    self.value    = None # Value passed to callback
    for key, value in kwargs.iteritems():
      if   key == 'color': self.color    = value
      elif key == 'bg'   : self.bg       = value
      elif key == 'fg'   : self.fg       = value
      elif key == 'cb'   : self.callback = value
      elif key == 'value': self.value    = value
      
  def selected(self, pos):
    x1 = self.rect[0]
    y1 = self.rect[1]
    x2 = x1 + self.rect[2] - 1
    y2 = y1 + self.rect[3] - 1
    if ((pos[0] >= x1) and (pos[0] <= x2) and (pos[1] >= y1) and (pos[1] <= y2)):
      if self.callback:
        if self.value is None: 
          self.callback()
        else:
          self.callback(self.value)
      return True
    return False
      
  def draw(self, screen):
    if self.color:
      screen.fill(self.color, self.rect)
    if self.iconBg:
      screen.blit(self.iconBg.bitmap,
        (self.rect[0]+(self.rect[2]-self.iconBg.bitmap.get_width())/2,
          self.rect[1]+(self.rect[3]-self.iconBg.bitmap.get_height())/2))
    if self.iconFg:
      screen.blit(self.iconFg.bitmap,
        (self.rect[0]+(self.rect[2]-self.iconFg.bitmap.get_width())/2,
          self.rect[1]+(self.rect[3]-self.iconFg.bitmap.get_height())/2))
          
  def setBg(self, name):
    if name is None:
      self.iconBg = None
    else:
      for i in icons:
        if name == i.name:
          self.iconBg = i
          break

  def setFg(self, name):
    if name is None:
      self.iconFg = None
    else:
      for i in icons:
        if name == i.name:
          self.iconFg = i
          break
          
# UI callbacks -------------------------------------------------------------
# These are defined before globals because they're referenced by items in
# the global buttons[] list.

def isoCallback(n): # Pass 1 (next ISO) or -1 (prev ISO)
  global isoMode
  setIsoMode((isoMode + n) % len(isoData))
  
def settingCallback(n): # Pass 1 (next setting) or -1 (prev setting)
  global screenMode
  screenMode += n
  if screenMode < 4:               screenMode = len(buttons) - 1
  elif screenMode >= len(buttons): screenMode = 4
  
def fxCallback(n): # Pass 1 (next effect) or -1 (prev effect)
  global fxMode
  setFxMode((fxMode + n) % len(fxData))
  
def quitCallback(): # Quit confirmation button
  global timelapseTimerThread
  saveSettings()
  try:
    timelapseTimerThread.cancel() #clean up timer thread
  except:
    pass
  raise SystemExit
  
def viewCallback(n): # Viewfinder buttons
  global loadIdx, scaled, screenMode, screenModePrior, settingMode, storeMode
  
  if n is 0:   # Gear icon (settings)
    screenMode = settingMode # Switch to last settings mode
  elif n is 1: # Play icon (image playback)
    if scaled: # Last photo is already memory-resident
      loadIdx         = saveIdx
      screenMode      =  0 # Image playback
      screenModePrior = -1 # Force screen refresh
    else:      # Load image
      r = imgRange(pathData[storeMode])
      if r: showImage(r[1]) # Show last image in directory
      else: screenMode = 2  # No images
  else: # Rest of screen = shutter
    takePicture()
      
def doneCallback(): # Exit settings
  global screenMode, settingMode
  if screenMode > 3:
    settingMode = screenMode
    saveSettings()
  screenMode = 3 # Switch back to viewfinder mode
    
def imageCallback(n): # Pass 1 (next image), -1 (prev image) or 0 (delete)
  global screenMode
  if n is 0:
    screenMode = 1 # Delete confirmation
  else:
    showNextImage(n)
    
def deleteCallback(n): # Delete confirmation
  global loadIdx, scaled, screenMode, storeMode
  screenMode      =  0
  screenModePrior = -1
  if n is True:
    if webcamMode:
      try:
        os.remove(pathData[storeMode] + '/webcam/IMG_' + '%04d' % loadIdx + '.JPG')
      except:
        None
    else:
      try:
        os.remove(pathData[storeMode] + '/IMG_' + '%04d' % loadIdx + '.JPG')
      except:
        None      
    if(imgRange(pathData[storeMode])):
      screen.fill(0)
      pygame.display.update()
      showNextImage(-1)
    else: # Last image deleteted; go to 'no images' mode
      screenMode = 2
      scaled     = None
      loadIdx    = -1
      
def storeModeCallback(n): # Radio buttons on storage settings screen
  global storeMode
  buttons[4][storeMode + 3].setBg('radio3-0')
  storeMode = n
  buttons[4][storeMode + 3].setBg('radio3-1')
  
def sizeModeCallback(n): # Radio buttons on size settings screen
  global sizeMode
  buttons[5][sizeMode + 3].setBg('radio3-0')
  sizeMode = n
  buttons[5][sizeMode + 3].setBg('radio3-1')
  camera.resolution = sizeData[sizeMode][1]
  #  camera.crop       = sizeData[sizeMode][2]
  
def valuesCallback(n): # Pass 1 (next setting) or -1 (prev setting)
  global screenMode
  global returnScreen
  global numberstring
  global numeric
  global v
  global dict_idx
  
  if n == -1:
    screenMode = 0
    saveSettings()
  elif n == 1: #timelapse: set interval
    dict_idx='interval'
    numberstring = str(v[dict_idx])
    screenMode = 9 #numeric keyboard
    returnScreen = 8
  elif n == 2: #timelapse: set number of pics. to take
    dict_idx='images'
    numberstring = str(v[dict_idx])
    screenMode =  9 #numeric keyboard
    returnScreen = 8
      
def numericCallback(n): # Pass 1 (next setting) or -1 (prev setting)
  global screenMode
  global numberstring
  if n < 10:
    numberstring = numberstring + str(n)
  elif n == 10:
    numberstring = numberstring[:-1]
  elif n == 11:
    screenMode = 8
  elif n == 12:
    screenMode = returnScreen
    numeric = int(numberstring)
    v[dict_idx] = numeric    
    
def webcamCallback(n): # Handle webcam configuration
  global webcamMode, webcamImageOnly, webcamModeAnnotation
  #make sure all checkboxes are correctly initialized
  if webcamMode:
    buttons[10][1+2].setFg('tick')
  else:
    buttons[10][1+2].setFg(None)
  if webcamImageOnly:
    buttons[10][2+2].setFg('tick')
  else:
    buttons[10][2+2].setFg(None)
  if webcamModeAnnotation:
    buttons[10][3+2].setFg('tick')
  else:
    buttons[10][3+2].setFg(None)
  #toggle chosen check-box
  if n==1:
    if webcamMode:
      buttons[10][1+2].setFg(None)
      webcamMode = False
    else:
      buttons[10][1+2].setFg('tick')
      webcamMode = True
  elif n==2:
    if webcamImageOnly:
      buttons[10][2+2].setFg(None)
      webcamImageOnly = False
    else:
      buttons[10][2+2].setFg('tick')
      webcamImageOnly = True
  elif n==3:
    if webcamModeAnnotation:
      buttons[10][3+2].setFg(None)
      webcamModeAnnotation=False
    else:
      buttons[10][3+2].setFg('tick')
      webcamModeAnnotation=True
  
    
def timelapseCallback(n): # start or stop timelapse
  global timelapseStarted
  global timelapseTimerThread
  global doTimelapsePicture
  global timelapsePicturesTaken
  if n==1 and timelapseStarted:
    camera.awb_mode = 'auto'
    #stop timelapse
    try:
      timelapseTimerThread.cancel()
    except:
      pass
    timelapseStarted=False
    timelapsePicturesTaken=0
  elif n==1 and not timelapseStarted:
    #start timelapse
    #start repeating weather timer using the interval set 
    timelapseTimerThread = timers.RepeatingTimer(v['interval'], function=timelapseCallback, args=(['2']))
    timelapseTimerThread.name = 'TIMELAPSE_TIMER'
    timelapseTimerThread.start()
    timelapseStarted = True
    # fix automatic white balance and exposure mode so that pictures in sequence
    # look the same from a brightness, contrast and color perspective
    # Give the camera's auto-exposure and auto-white-balance algorithms
    # some time to measure the scene and determine appropriate values
    #time.sleep(2)
    # Now fix the values
    #camera.shutter_speed = camera.exposure_speed
    #camera.exposure_mode = 'off'
    #29.07.2015 setting awb_mode to auto. Perhaps one day I will have time
    #to add a menu so user can set awb
    #g = camera.awb_gains
    camera.awb_mode = 'auto'
    #camera.awb_gains = g    
  elif n=='2':
    #take a photo
    doTimelapsePicture = True
    
# Global stuff -------------------------------------------------------------
    
screenMode      =  3      # Current screen mode; default = viewfinder
screenModePrior = -1      # Prior screen mode (for detecting changes)
settingMode     =  4      # Last-used settings mode (default = storage)
storeMode       =  0      # Storage mode; default = Photos folder
storeModePrior  = -1      # Prior storage mode (for detecting changes)
sizeMode        =  0      # Image size; default = Large
fxMode          =  0      # Image effect; default = Normal
isoMode         =  0      # ISO settingl default = Auto
iconPath        = 'icons' # Subdirectory containing UI bitmaps (PNG format)
saveIdx         = -1      # Image index for saving (-1 = none set yet)
loadIdx         = -1      # Image index for loading
scaled          = None    # pygame Surface w/last-loaded image
# Global stuff for timelapse ----------------------------------------------
timelapseStarted      = False      # timelapse running or not 
timelapseTimerThread  = None       # timelapse timer thread
doTimelapsePicture    = False      # it is time to take another picture
timelapsePicturesTaken= 0          # number of timelapse picutres that have been taken thus far
numeric               = 0          # number from numeric keypad      
numberstring          = "0"        # number string from numeric keypad
dict_idx              = "interval" # Index for time lapse settings
v                     = { "interval": 30,   # time lapse settings
                          "images"  : 5}
webcamMode            = True       # upload file to dropbox always with same name    
webcamImageOnly       = True       # only take small size pic. for upload to dropbox.
webcamModeAnnotation  = True       # Annotate image when in webcame mode
dropboxAccessToken    = None       # dropbox access token

# To use Dropbox uploader, must have previously run the dropbox_uploader.sh
# script to set up the app key and such.  If this was done as the normal pi
# user, set upconfig to the .dropbox_uploader config file in that account's
# home directory.  Alternately, could run the setup script as root and
# delete the upconfig line below.
#uploader        = '/home/pi/Dropbox-Uploader/dropbox_uploader.sh'
#upconfig        = '/home/pi/.dropbox_uploader'

#initialize logger
configuration.logging_configuration()
logger = configuration.init_log('WEBCAM')
logger = logging.getLogger('WEBCAM')  
logger.info('logger initialized')

sizeData = [ # Camera parameters for different size settings
  # Full res      Viewfinder  Crop window
  [(2592, 1944), (320, 240), (0.0   , 0.0   , 1.0   , 1.0   ), (648, 486)], # Large
  [(1920, 1080), (320, 180), (0.1296, 0.2222, 0.7408, 0.5556), (480, 270)], # Med
  [(1440, 1080), (320, 240), (0.2222, 0.2222, 0.5556, 0.5556), (640, 486)]] # Small

isoData = [ # Values for ISO settings [ISO value, indicator X position]
  [  0,  27], [100,  64], [200,  97], [320, 137],
  [400, 164], [500, 197], [640, 244], [800, 297]]

# A fixed list of image effects is used (rather than polling
# camera.IMAGE_EFFECTS) because the latter contains a few elements
# that aren't valid (at least in video_port mode) -- e.g. blackboard,
# whiteboard, posterize (but posterise, British spelling, is OK).
# Others have no visible effect (or might require setting add'l
# camera parameters for which there's no GUI yet) -- e.g. saturation,
# colorbalance, colorpoint.
fxData = [
  'none', 'sketch', 'gpen', 'pastel', 'watercolor', 'oilpaint', 'hatch',
  'negative', 'colorswap', 'posterise', 'denoise', 'blur', 'film',
  'washedout', 'emboss', 'cartoon', 'solarize' ]

pathData = [
  '/home/pi/Photos',       # Path for storeMode = 0 (Photos folder)
  '/boot/DCIM/CANON999',   # Path for storeMode = 1 (Boot partition)
  '/home/pi/Photos',       # Path for storeMode = 2 (Dropbox)
  '/home/pi/Photos/webcam']# path for storeMode = 3 (webcam)

icons = [] # This list gets populated at startup

# buttons[] is a list of lists; each top-level list element corresponds
# to one screen mode (e.g. viewfinder, image playback, storage settings),
# and each element within those lists corresponds to one UI button.
# There's a little bit of repetition (e.g. prev/next buttons are
# declared for each settings screen, rather than a single reusable
# set); trying to reuse those few elements just made for an ugly
# tangle of code elsewhere.

buttons = [
  # Screen mode 0 is photo playback
  [Button((  0,188,320, 52), bg='done' , cb=doneCallback),
   Button((  0,  0, 80, 52), bg='prev' , cb=imageCallback, value=-1),
   Button((240,  0, 80, 52), bg='next' , cb=imageCallback, value= 1),
   Button(( 88, 70,157,102)), # 'Working' label (when enabled)
   Button((148,129, 22, 22)), # Spinner (when enabled)
   Button((121,  0, 78, 52), bg='trash', cb=imageCallback, value= 0)],
  
  # Screen mode 1 is delete confirmation
  [Button((  0,35,320, 33), bg='delete'),
   Button(( 32,86,120,100), bg='yn', fg='yes', cb=deleteCallback, value=True),
   Button((168,86,120,100), bg='yn', fg='no',
  cb=deleteCallback, value=False)],
    
  # Screen mode 2 is 'No Images'
  [Button((0,  0,320,240), cb=doneCallback), # Full screen = button
   Button((0,188,320, 52), bg='done'),       # Fake 'Done' button
   Button((0, 53,320, 80), bg='empty')],     # 'Empty' message
  
  # Screen mode 3 is viewfinder / snapshot
  [Button((  0,188,100, 52), bg='gear', cb=viewCallback, value=0),
   Button((220,188,100, 52), bg='play', cb=viewCallback, value=1),
   Button((  0,  0,320,188)           , cb=viewCallback, value=2),
   Button(( 88, 51,157,102)),  # 'Working' label (when enabled)
   Button((148, 110,22, 22)), # Spinner (when enabled)
   Button((108,188,104, 52), bg='timelapse', cb=timelapseCallback, value=1)], #start/stop timelapse
  
  # Remaining screens are settings modes
  
  # Screen mode 4 is storage settings
  [Button((  0,188,320, 52), bg='done', cb=doneCallback),
   Button((  0,  0, 80, 52), bg='prev', cb=settingCallback, value=-1),
   Button((240,  0, 80, 52), bg='next', cb=settingCallback, value= 1),
   Button((  2, 60,100,120), bg='radio3-1', fg='store-folder',  cb=storeModeCallback, value=0),
   Button((110, 60,100,120), bg='radio3-0', fg='store-boot',    cb=storeModeCallback, value=1),
   Button((218, 60,100,120), bg='radio3-0', fg='store-dropbox', cb=storeModeCallback, value=2),
   Button((  0, 10,320, 35), bg='storage')],
  
  # Screen mode 5 is size settings
  [Button((  0,188,320, 52), bg='done', cb=doneCallback),
   Button((  0,  0, 80, 52), bg='prev', cb=settingCallback, value=-1),
   Button((240,  0, 80, 52), bg='next', cb=settingCallback, value= 1),
   Button((  2, 60,100,120), bg='radio3-1', fg='size-l', cb=sizeModeCallback, value=0),
   Button((110, 60,100,120), bg='radio3-0', fg='size-m', cb=sizeModeCallback, value=1),
   Button((218, 60,100,120), bg='radio3-0', fg='size-s', cb=sizeModeCallback, value=2),
   Button((  0, 10,320, 29), bg='size')],
  
  # Screen mode 6 is graphic effect
  [Button((  0,188,320, 52), bg='done', cb=doneCallback),
   Button((  0,  0, 80, 52), bg='prev', cb=settingCallback, value=-1),
   Button((240,  0, 80, 52), bg='next', cb=settingCallback, value= 1),
   Button((  0, 70, 80, 52), bg='prev', cb=fxCallback     , value=-1),
   Button((240, 70, 80, 52), bg='next', cb=fxCallback     , value= 1),
   Button((  0, 67,320, 91), bg='fx-none'),
   Button((  0, 11,320, 29), bg='fx')],
  
  # Screen mode 7 is ISO
  [Button((  0,188,320, 52), bg='done', cb=doneCallback),
   Button((  0,  0, 80, 52), bg='prev', cb=settingCallback, value=-1),
   Button((240,  0, 80, 52), bg='next', cb=settingCallback, value= 1),
   Button((  0, 70, 80, 52), bg='prev', cb=isoCallback    , value=-1),
   Button((240, 70, 80, 52), bg='next', cb=isoCallback    , value= 1),
   Button((  0, 79,320, 33), bg='iso-0'),
   Button((  9,134,302, 26), bg='iso-bar'),
   Button(( 17,157, 21, 19), bg='iso-arrow'),
   Button((  0, 10,320, 29), bg='iso')],
  
  # Screen mode 8 is time lapse settings
  [Button((  0,188,320, 52), bg='done', cb=doneCallback),
   Button((260, 60, 60, 60), bg='cog',  cb=valuesCallback,  value= 1),
   Button((260,120, 60, 60), bg='cog',  cb=valuesCallback,  value= 2),
   Button((  0,  0, 80, 52), bg='prev', cb=settingCallback, value=-1),
   Button((240,  0, 80, 52), bg='next', cb=settingCallback, value= 2), # skip numeric keypad
   Button(( 81,  7,158, 53), bg='timelapse_title')],
  
  # Screen mode 9 is time lapse settings: numeric keyboard
  [Button(( 0,  0, 320, 60), bg='box'),
   Button((180,120, 60, 60), bg='0',     cb=numericCallback, value= 0),
   Button((  0,180, 60, 60), bg='1',     cb=numericCallback, value= 1),
   Button(( 60,180, 60, 60), bg='2',     cb=numericCallback, value= 2),
   Button((120,180, 60, 60), bg='3',     cb=numericCallback, value= 3),
   Button((  0,120, 60, 60), bg='4',     cb=numericCallback, value= 4),
   Button(( 60,120, 60, 60), bg='5',     cb=numericCallback, value= 5),
   Button((120,120, 60, 60), bg='6',     cb=numericCallback, value= 6),
   Button((  0, 60, 60, 60), bg='7',     cb=numericCallback, value= 7),
   Button(( 60, 60, 60, 60), bg='8',     cb=numericCallback, value= 8),
   Button((120, 60, 60, 60), bg='9',     cb=numericCallback, value= 9),
   Button((240,120, 80, 60), bg='del',   cb=numericCallback, value=10),
   Button((180,180,140, 60), bg='ok',    cb=numericCallback, value=12),
   Button((180, 60,140, 60), bg='cancel',cb=numericCallback, value=11)],
   
   
  # Screen mode 10 webcam mode settings
  [Button((  0,188,320, 52), bg='done', cb=doneCallback),
   Button((  0,  0, 80, 52), bg='prev', cb=settingCallback, value=-2), # skip numeric keypad
   Button((240,  0, 80, 52), bg='next', cb=settingCallback, value= 1),
   Button((278, 60, 42, 42), bg='checkbox', cb=webcamCallback,  value= 1),
   Button((278,102, 42, 42), bg='checkbox', cb=webcamCallback,  value= 2),
   Button((278,144, 42, 42), bg='checkbox', cb=webcamCallback,  value= 3),
   Button(( 81,  7,158, 53), bg='webcam_title'),
   Button(( 0,  60,278, 42), bg='webcamMode'),
   Button(( 0, 102,278, 42), bg='webcamImageOnly'),
   Button(( 0, 144,278, 42), bg='webcamModeAnnotation')
],   
  
  # Screen mode 11 is quit confirmation
  [Button((  0,188,320, 52), bg='done'   , cb=doneCallback),
   Button((  0,  0, 80, 52), bg='prev'   , cb=settingCallback, value=-1),
   Button((240,  0, 80, 52), bg='next'   , cb=settingCallback, value= 1),
   Button((110, 60,100,120), bg='quit-ok', cb=quitCallback),
   Button((  0, 10,320, 35), bg='quit')]
]


# Assorted utility functions -----------------------------------------------

def setFxMode(n):
  global fxMode
  fxMode = n
  camera.image_effect = fxData[fxMode]
  buttons[6][5].setBg('fx-' + fxData[fxMode])
  
def setIsoMode(n):
  global isoMode
  isoMode    = n
  camera.ISO = isoData[isoMode][0]
  buttons[7][5].setBg('iso-' + str(isoData[isoMode][0]))
  buttons[7][7].rect = ((isoData[isoMode][1] - 10,) +  buttons[7][7].rect[1:])
  
def saveSettings():
  global v, webcamMode, webcamImageOnly, webcamModeAnnotation, dropboxAccessToken
  try:
    outfile = open('cam.pkl', 'wb')
    # Use a dictionary (rather than pickling 'raw' values) so
    # the number & order of things can change without breaking.
    d = { 'fx'       : fxMode,
          'iso'      : isoMode,
          'size'     : sizeMode,
          'store'    : storeMode,
          'interval' : v['interval'],
          'images'   : v['images'],
          'webcamMode'           : str(webcamMode),
          'webcamImageOnly'      : str(webcamImageOnly),
          'webcamModeAnnotation' : str(webcamModeAnnotation),
          'dropboxAccessToken'   : str(dropboxAccessToken)}
    pickle.dump(d, outfile)
    outfile.close()
  except:
    pass
  
def loadSettings():
  global v, webcamMode, webcamImageOnly, webcamModeAnnotation, dropboxAccessToken
  try:
    infile = open('cam.pkl', 'rb')
    d      = pickle.load(infile)
    infile.close()
    if 'fx'        in d: setFxMode(   d['fx'])
    if 'iso'       in d: setIsoMode(  d['iso'])
    if 'size'      in d: sizeModeCallback( d['size'])
    if 'store'     in d: storeModeCallback(d['store'])
    if 'interval'  in d: v['interval']=int(d['interval'])
    if 'images'    in d: v['images']=int(d['images'])
    if 'webcamMode' in d: 
       if d['webcamMode'] == 'True':
         webcamMode = True 
       else: 
         webcamMode= False
    if 'webcamImageOnly' in d: 
       if d['webcamImageOnly'] == 'True':
         webcamImageOnly = True 
       else: 
         webcamImageOnly= False      
    if 'webcamModeAnnotation' in d: 
       if d['webcamModeAnnotation'] == 'True':
         webcamModeAnnotation = True 
       else: 
         webcamModeAnnotation= False
    if 'dropboxAccessToken' in d:
      dropboxAccessToken=d['dropboxAccessToken']
    else:
      dropboxAccessToken = None
  except:
    pass
  
# Scan files in a directory, locating JPEGs with names matching the
# software's convention (IMG_XXXX.JPG), returning a tuple with the
# lowest and highest indices (or None if no matching files).
def imgRange(path):
  min = 9999
  max = 0
  try:
    for file in os.listdir(path):
      if fnmatch.fnmatch(file, 'IMG_[0-9][0-9][0-9][0-9].JPG'):
        i = int(file[4:8])
        if(i < min): min = i
        if(i > max): max = i
  finally:
    return None if min > max else (min, max)
        
# Busy indicator.  To use, run in separate thread, set global 'busy'
# to False when done.
def spinner():
  global busy, screenMode, screenModePrior
  
  buttons[screenMode][3].setBg('working')
  buttons[screenMode][3].draw(screen)
  pygame.display.update()
  
  busy = True
  n    = 0
  while busy is True:
    buttons[screenMode][4].setBg('work-' + str(n))
    buttons[screenMode][4].draw(screen)
    pygame.display.update()
    n = (n + 1) % 5
    time.sleep(0.15)
    
  buttons[screenMode][3].setBg(None)
  buttons[screenMode][4].setBg(None)
  screenModePrior = -1 # Force refresh
  
def takePicture():
  global busy, gid, loadIdx, saveIdx, scaled, sizeMode, storeMode, storeModePrior, uid, webcamMode, webcamModeAnnotation, webcamImageOnly, dropboxAccessToken, logger
  
  if not os.path.isdir(pathData[storeMode]):
    try:
      os.makedirs(pathData[storeMode])
      # Set new directory ownership to pi user, mode to 755
      os.chown(pathData[storeMode], uid, gid)
      os.chmod(pathData[storeMode],
        stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
        stat.S_IRGRP | stat.S_IXGRP |
        stat.S_IROTH | stat.S_IXOTH)
    except OSError as e:
      # errno = 2 if can't create folder
      print errno.errorcode[e.errno]
      return
  
  if webcamMode and not os.path.isdir(pathData[3]): 
    try:
      os.makedirs(pathData[3])
      # Set new directory ownership to pi user, mode to 755
      os.chown(pathData[storeMode], uid, gid)
      os.chmod(pathData[storeMode],
        stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
        stat.S_IRGRP | stat.S_IXGRP |
        stat.S_IROTH | stat.S_IXOTH)
    except OSError as e:
      # errno = 2 if can't create folder
      #print errno.errorcode[e.errno]
      logger.error('unexpected error ['+ str(traceback.format_exc()) + ']')  
      return
    
  # If this is the first time accessing this directory,
  # scan for the max image index, start at next pos.
  if storeMode != storeModePrior:
    if webcamMode and webcamImageOnly:
      #only want webcam image, always has the same index
      saveIdx=1
    else:
      r = imgRange(pathData[storeMode])
      if r is None:
        saveIdx = 1
      else:
        saveIdx = r[1] + 1
        if saveIdx > 9999: saveIdx = 0
    storeModePrior = storeMode
      
  # Scan for next available image slot
  if webcamMode and webcamImageOnly: 
    #only want a "webcam" image
    filename = pathData[3] + '/IMG_' + '%04d' % saveIdx + '.JPG'
  else: 
    while True:
      filename = pathData[storeMode] + '/IMG_' + '%04d' % saveIdx + '.JPG'
      if not os.path.isfile(filename): break
      saveIdx += 1
      if saveIdx > 9999: saveIdx = 0

    
  t = threading.Thread(target=spinner)
  t.start()
  
  scaled = None
  camera.resolution = sizeData[sizeMode][0]
  camera.crop       = sizeData[sizeMode][2]
  if webcamMode and webcamModeAnnotation:
    camera.annotate_background = True
    camera.annotate_text       = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  try:
    if webcamMode and webcamImageOnly:
      camera.capture(filename, use_video_port=False, format='jpeg', thumbnail=None, resize=sizeData[sizeMode][3])
    else:
      camera.capture(filename, use_video_port=False, format='jpeg', thumbnail=None)
    # Set image file ownership to pi user, mode to 644
    # os.chown(filename, uid, gid) # Not working, why?
    os.chmod(filename, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    img    = pygame.image.load(filename)
    scaled = pygame.transform.scale(img, sizeData[sizeMode][1])
    if storeMode == 2: # Dropbox
      #get the dropbox client, if a valid dropbox access token was load in loadSettings
      #if dropboxAccessToken is not None:
      try:
        dropboxClient = dropbox.client.DropboxClient(dropboxAccessToken)
      except:
        logger.error('unexpected error ['+ str(traceback.format_exc()) + ']')  
        dropboxClient = None
      if dropboxClient is not None:
        if webcamMode and not webcamImageOnly:
          #since I pay for data I want to upload a small image even if I 
          #want to keep a large resolution image file locally
          webcamImage = pygame.transform.scale(img, sizeData[sizeMode][3]) 
          pygame.image.save(webcamImage, pathData[storeMode]+'/webcam/IMG_0001.JPG')
          #cmd = uploader + ' -f ' + upconfig + ' upload ' + pathData[storeMode]+'/webcam/IMG_0001.JPG' + ' Photos/webcam/IMG_0001.JPG'
          f=open(pathData[storeMode]+'/webcam/IMG_0001.JPG', 'rb')
          try:
            response = dropboxClient.put_file('Photos/webcam/IMG_0001.JPG', f, overwrite=True)
            logger.info('1: uploaded image')  
          except:
            logger.error('1: unexpected error ['+ str(traceback.format_exc()) + ']')  
        elif webcamMode and webcamImageOnly:
          #cmd = uploader + ' -f ' + upconfig + ' upload ' + filename + ' Photos/webcam/' + os.path.basename(filename)
          f=open(filename, 'rb')
          try:
            response = dropboxClient.put_file('Photos/webcam/' + os.path.basename(filename), f, overwrite=True)
            logger.info('2: uploaded image')
          except:
            logger.error('2: unexpected error ['+ str(traceback.format_exc()) + ']')  
        else:
          f=open(filename, 'rb')
          #cmd = uploader + ' -f ' + upconfig + ' upload ' + filename + ' Photos/' + os.path.basename(filename)
          try:
            response = dropboxClient.put_file('Photos/' + os.path.basename(filename), f, overwrite=True)
            logger.info('3: uploaded image')
          except:
            logger.error('3: unexpected error ['+ str(traceback.format_exc()) + ']')  
  except:
    #catch any error and log it
    logger.error('unexpected error ['+ str(traceback.format_exc()) + ']')  
  finally:
    # Add error handling/indicator (disk full, etc.)
    camera.resolution = sizeData[sizeMode][1]
    camera.crop       = (0.0, 0.0, 1.0, 1.0)
    #sure spinner thread is joined.
    busy = False
    t.join()    


  if webcamMode and webcamModeAnnotation:
    camera.annotate_background = False
    camera.annotate_text       = '' 
  
  if scaled:
    if scaled.get_height() < 240: # Letterbox
      screen.fill(0)
      screen.blit(scaled,
        ((320 - scaled.get_width() ) / 2,
          (240 - scaled.get_height()) / 2))
      pygame.display.update()
      time.sleep(2.5)
      loadIdx = saveIdx
      
def showNextImage(direction):
  global busy, loadIdx
  
  t = threading.Thread(target=spinner)
  t.start()
  
  n = loadIdx
  while True:
    n += direction
    if(n > 9999): n = 0
    elif(n < 0):  n = 9999
    if os.path.exists(pathData[storeMode]+'/IMG_'+'%04d'%n+'.JPG'):
      showImage(n)
      break
      
  busy = False
  t.join()
  
def showImage(n):
  global busy, loadIdx, scaled, screenMode, screenModePrior, sizeMode, storeMode
  
  t = threading.Thread(target=spinner)
  t.start()
  
  img      = pygame.image.load(pathData[storeMode] + '/IMG_' + '%04d' % n + '.JPG')
  scaled   = pygame.transform.scale(img, sizeData[sizeMode][1])
  loadIdx  = n
  
  busy = False
  t.join()
  
  screenMode      =  0 # Photo playback
  screenModePrior = -1 # Force screen refresh
  
  
# Initialization -----------------------------------------------------------

# Init framebuffer/touchscreen environment variables
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV'      , '/dev/fb1')
os.putenv('SDL_MOUSEDRV'   , 'TSLIB')
os.putenv('SDL_MOUSEDEV'   , '/dev/input/touchscreen')

# Get user & group IDs for file & folder creation
# (Want these to be 'pi' or other user, not root)
s = os.getenv("SUDO_UID")
uid = int(s) if s else os.getuid()
s = os.getenv("SUDO_GID")
gid = int(s) if s else os.getgid()

# Buffers for viewfinder data
rgb = bytearray(320 * 240 * 3)

# Init pygame and screen
pygame.init()
pygame.mouse.set_visible(False)
#screen = pygame.display.set_mode((320,240))
screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)

# Init camera and set up default values
camera            = picamera.PiCamera()
atexit.register(camera.close)
camera.resolution = sizeData[sizeMode][1]
#camera.crop       = sizeData[sizeMode][2]
camera.crop       = (0.0, 0.0, 1.0, 1.0)

# Load all icons at startup.
for file in os.listdir(iconPath):
  if fnmatch.fnmatch(file, '*.png'):
    icons.append(Icon(file.split('.')[0]))
    
# Assign Icons to Buttons, now that they're loaded
for s in buttons:        # For each screenful of buttons...
  for b in s:            #  For each button on screen...
    for i in icons:      #   For each icon...
      if b.bg == i.name: #    Compare names; match?
        b.iconBg = i     #     Assign Icon to Button
        b.bg     = None  #     Name no longer used; allow garbage collection
      if b.fg == i.name:
        b.iconFg = i
        b.fg     = None
          
loadSettings() # Must come last; fiddles with Button/Icon states
webcamCallback(None) # Must come after load settings; fiddles with Button/Icon states in the webcam config screen.

#Set your dropbox access token here, the program must run at least once to 
#"pickle" the access token
if dropboxAccessToken is None or dropboxAccessToken == 'None': 
  dropboxAccessToken = 'YOUR_ACCESS_TOKEN'
  saveSettings()



# Main loop ----------------------------------------------------------------

while(True):
  
  # Process touchscreen input
  while True:
    for event in pygame.event.get():
      if(event.type is MOUSEBUTTONDOWN):
        pos = pygame.mouse.get_pos()
        for b in buttons[screenMode]:
          if b.selected(pos): break
    # If in viewfinder or settings modes, stop processing touchscreen
    # and refresh the display to show the live preview.  In other modes
    # (image playback, etc.), stop and refresh the screen only when
    # screenMode changes.
    if screenMode >= 3 or screenMode != screenModePrior: break
          
          
          
  if doTimelapsePicture and timelapseStarted : # taking a timelapse picture
    takePicture()
    doTimelapsePicture = False
    timelapsePicturesTaken +=1
    if timelapsePicturesTaken >= v['images']:
      timelapseCallback(1) #toggle timelapse to off
      # Refresh display
  elif screenMode >= 3: # Viewfinder or settings modes
    stream = io.BytesIO() # Capture into in-memory stream
    camera.capture(stream, use_video_port=True, format='rgb')
    stream.seek(0)
    stream.readinto(rgb)  # stream -> RGB buffer
    stream.close()
    img = pygame.image.frombuffer(rgb[0:
    (sizeData[sizeMode][1][0] * sizeData[sizeMode][1][1] * 3)],
    sizeData[sizeMode][1], 'RGB')
  elif screenMode < 2: # Playback mode or delete confirmation
    img = scaled       # Show last-loaded image
  else:                # 'No Photos' mode
    img = None         # You get nothing, good day sir
        
  if img is None or img.get_height() < 240: # Letterbox, clear background
    screen.fill(0)
  if img:
    screen.blit(img,
      ((320 - img.get_width() ) / 2,
       (240 - img.get_height()) / 2))
    
  # Overlay buttons on display and update
  for i,b in enumerate(buttons[screenMode]):
    b.draw(screen)
    
  # stuff for timelapse
  if screenMode == 8:  # timelapse settings
    myfont = pygame.font.SysFont('Arial', 30)
    label = myfont.render('Interval:', 1, (255,255,255))
    screen.blit(label, (2,70))
    label = myfont.render(str(v['interval']) + 's', 1, (255,255,255))
    screen.blit(label, (102,70))
    label = myfont.render('Images:', 1, (255,255,255))
    screen.blit(label, (2,130))
    label = myfont.render(str(v['images']), 1, (255,255,255))
    screen.blit(label, (103,130))
  elif screenMode == 9: # numeric keypad
    myfont = pygame.font.SysFont('Arial', 50)
    label = myfont.render(numberstring, 1, (255,255,255))
    screen.blit(label, (10,2))
  if timelapseStarted and screenMode == 3:
    myfont = pygame.font.SysFont('Arial', 30)
    label = myfont.render(str(timelapsePicturesTaken) + '/' + str(v['images']), 1, (255,255,255))
    screen.blit(label, (10,2))
  
  pygame.display.update()
      
  screenModePrior = screenMode
