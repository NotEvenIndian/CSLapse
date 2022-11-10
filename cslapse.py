import os
import easygui
from datetime import datetime
import cv2

from pathlib import Path

from threading import Lock
import concurrent.futures

def rmtree(root):
    for p in root.iterdir():
        if p.is_dir():
            rmtree(p)
        else:
            p.unlink()
    root.rmdir()

#prepare temporary directory
def createTempDir(location,time):
    tempFolder=Path(location,"temp"+time)
    if tempFolder.exists():
        rmtree(tempFolder)
    tempFolder.mkdir()
    return tempFolder

#Make an array of files whose name matches the city's name
def collectRawFiles(infolder,cityName):
    return sorted(
        filter(
            lambda filename: filename.name.startswith(cityName) and ".cslmap" in filename.suffixes, 
            infolder.iterdir()
        ))

#Run on separate threads: call CSLMapView to export one image file
def threaded(lock,srcFile,shared):
    #Prepare command that calls cslmapview.exe
    newFileName=Path(shared["tempFolder"],srcFile.stem.encode("ascii", "ignore").decode()).with_suffix(".png")
    cmd=shared["cmd"].format(old=str(srcFile),new=str(newFileName))

    #call CSLMapview.exe to export the image. Try at most 15 times, abort after.
    for i in range(15):
        os.system(cmd)
        #Ensure that the image file was successfully created. 
        if  newFileName.exists():
            #record that a new image was created and continue to the next one
            with lock:
                shared["imageFiles"].append(str(newFileName))
            return

#Export all image files (or all up to the set limit)
def createImages(rawFiles,settings):
    #set amount of files to be processed
    limit = len(rawFiles) if settings["limit"]==0 else min(len(rawFiles),settings["limit"])

    #Prepare shared resources for threading
    shared={
        "tempFolder":settings["tempFolder"],
        "cmd":'start /W '+settings["exeName"]+' "{old}" -output "{new}" -silent -imagewidth '+str(settings["imageWidth"])+' -area '+str(settings["area"]),
        "imageFiles":[]
    }

    #Run CSLMapView on several threads parallel
    l=Lock()
    with concurrent.futures.ThreadPoolExecutor(settings["threads"]) as executor:
        for i in range(limit):
            executor.submit(threaded,l,rawFiles[i],shared)

    #Return a sorted array as the order might have changed during threading
    return sorted(shared["imageFiles"])

#Combine image files into a video file. Potentially very huge filesize.
def renderVideo(images,outFile,settings):
    print("Creating video:")
    #create video file
    out = cv2.VideoWriter(outFile,cv2.VideoWriter_fourcc(*"mp4v"), settings["fps"], (settings["imageWidth"],settings["imageWidth"]))
    i=0
    for file in images:
        #Display status
        ratio=50*i//len(images)
        print(f"\r |{'#'*ratio}{'-'*(50-ratio)}| {i} of {len(images)} ",end="")

        #add frame to video
        img = cv2.imread(file)
        out.write(img)

        i+=1
    print(f"\r |{'#'*50}| {i} of {len(images)}")
    out.release()

#Delete temporary folder and files
def cleanup(folder):
    rmtree(folder)


def main():
    #timestamp to have a unique name
    time=str(datetime.now()).split(" ")[-1].split(".")[0].replace(":","")

    #Settings for processing and the video
    #Currently only supports 1:1 aspect ratio
    settings={
        "fps":12,               #fps: 12 with 5 min autosave yields 3600x speed
        "area":3.2,             #Ingame tiles on the video, centered at the center of the map
        "limit":20,              #Limit the frames in the video, ideal for test runs to see how it will look. Keep at 0 to ignore
        "imageWidth":2000,      #Image (and video) dimensions in pixels
        "threads":6,            #Number of threads to use - more threads put a heavier load on cpu and not necessarily increase speed
        "exeName":"",           #CSLMapView.exe but better be safe
        "tempFolder":""         #Folder where temporary image files will be stored, it's deleted before the program exits
    }

    #Locate cslmapviewer.exe
    exeFile=Path(easygui.fileopenbox(title="Select file",msg="Select CSLmapview.exe",filetypes=["*.exe"]))
    settings["exeName"]=exeFile.name
    os.chdir(exeFile.parent)

    #locate the source files
    sampleFile=Path(easygui.fileopenbox(
        title="Open file",msg="Choose a cslmap file of your city",
        filetypes=[["*.cslmap.gz", "*.cslmap", "CSLmap files"]]
        ))
    sourceDir=sampleFile.parent
    print(sourceDir)
    cityName=sampleFile.stem.split("-")[0]

    #prepare temporary directory
    settings["tempFolder"]=createTempDir(sourceDir, time)

    try:
        #collect files to be used in a list
        rawFiles=collectRawFiles(sourceDir,cityName)

        #export images from source files
        imgFiles=createImages(rawFiles,settings)

        #Join the images into a video and save it to the source directory
        print("\nRendering video from images...",end="")
        outFile=str(Path(sourceDir,f'{cityName.encode("ascii", "ignore").decode()}-{time}.mp4'))
        renderVideo(imgFiles, outFile,settings)

        print("See your timelapse at",outFile)
    except Exception as e:
        print(e)
    finally:
        #Clean up image files and temporary folder
        print("Cleaning up temporary files...",end="")
        cleanup(settings["tempFolder"])
        print("Done")

if __name__=='__main__':
    main()