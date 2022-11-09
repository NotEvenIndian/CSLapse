# CSLapse
Create timelapses of your Cities:Skylines cities from regular CSLMapView saves.

## How to install:
Make sure to have python3.8+ installed on your computer.
Clone this git repository and go to the source of the downloaded directory.

Run ```pip install -r requirements.txt``` to install required modules.

## How to use:
**Please note: running this script certainly puts a heavy load on your CPU, probably on your memory and possibly on your disk!**

Currently the settings need to be entered manually.
Make sure that all your cslma files are in the same directory and the filenames start with your city's name (default settings for CSLMapView).
Start the program > select your CSLMapView.exe file > Select a cslmap file of your city > wait until the process finishes.
It is recommedned to compress the final video with an external software like [freeconvert.com](https://www.freeconvert.com/video-compressor).

## TODO:
* Add exception handling
* Add GUI to enter basic settings and give feedback
* Package into an executable
* (later) Add GUI to edit settings of CSLMapViewConfig.xml