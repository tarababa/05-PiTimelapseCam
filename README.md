Setup dropbox account, adapted from http://raspi.tv/2013/how-to-use-dropbox-with-raspberry-pi

1. DropBox account

First of all you need a DropBox account. Hop on over to DropBox and get one – it’s free.

2. Download and Set Up DropBox Uploader

cd ~  #this ensures you are in /home/pi
git clone https://github.com/andreafabrizi/Dropbox-Uploader.git
ls 

(If this fails, you may need to install git with sudo apt-get install git-core)

You should be able to see a directory called Dropbox-Uploader

cd Dropbox-Uploader
ls

3. Now the fiddly bit – API keys

Run the script with ./dropbox_uploader.sh (if it fails, try chmod +x dropbox_uploader.sh)