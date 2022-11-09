import os
import sys
import shutil
import easygui
from datetime import datetime
import cv2

import threading
import concurrent.futures


#Make an array of files whose name matches the city's name
def collectRawFiles(infolder,name):
    return [os.path.join(infolder,f) for f in sorted(filter(lambda filename: filename.startswith(name+"-") and "cslmap" in filename, os.listdir(os.getcwd())))]


#Run on separate threads: call CSLMapView to export one image file
def threaded(lock,srcFile,shared):

    #Prepare command that calls cslmapview.exe
    newFileName=os.path.join(shared["tempFolder"],os.path.basename(srcFile).strip('.gz').strip('.cslmap').encode("ascii", "ignore").decode()+".png")
    cmd=shared["cmd"].format(old=srcFile,new=newFileName)

    #call CSLMapview.exe to export the image
    while True:
        os.system(cmd)
        #Ensure that the image file was successfully created. This part may cause an infinite loop.
        if  os.path.exists(newFileName):
            break
        
    #record that a new image was created and continue to the next one
    with lock:
        shared["imageFiles"].append(newFileName)


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
    l=threading.Lock()
    with concurrent.futures.ThreadPoolExecutor(settings["threads"]) as executor:
        for i in range(limit):
            executor.submit(threaded,l,rawFiles[i],shared)

    #Return a sorted array as the order might have changed during threading
    return sorted(shared["imageFiles"])

#Combine image files into a video file. Potentially very huge filesize.
def renderVideo(images,outFile,settings):
    #create video file
    out = cv2.VideoWriter(outFile,cv2.VideoWriter_fourcc(*'DIVX'), settings["fps"], (settings["imageWidth"],settings["imageWidth"]))
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
    shutil.rmtree(folder)


def main():
    #timestamp to have a unique name
    time=str(datetime.now()).split(" ")[-1].split(".")[0].replace(":","")

    #Settings for processing and the video
    #Currently only supports 1:1 aspect ratio
    settings={
        "fps":12,               #fps: 12 with 5 min autosave yields 3600x speed
        "area":3.2,             #Ingame tiles on the video, centered at the center of the map
        "limit":0,              #Limit the frames in the video, ideal for test runs to see how it will look. Keep at 0 to ignore
        "imageWidth":2000,      #Image (and video) dimensions in pixels
        "threads":6,            #Number of threads to use - more threads put a heavier load on cpu and not necessarily increase speed
        "exeName":"",           #CSLMapView.exe but better be safe
        "tempFolder":""         #Folder where temporary image files will be stored, it's deleted before the program exits
    }

    #Locate cslmapviewer.exe
    exeFile=easygui.fileopenbox(title="Select file",msg="Select CSLmapview.exe",filetypes=["*.exe"])
    settings["exeName"]=os.path.basename(exeFile)
    os.chdir(exeFile[:-len(os.path.basename(exeFile))])

    #locate the source files
    sampleFile=easygui.fileopenbox(title="Open file",msg="Choose a cslmap file of your city",filetypes=[["*.cslmap.gz", "*.cslmap", "CSLmap files"]])
    sourceDir=sampleFile[:-len(os.path.basename(sampleFile))]
    cityName=os.path.basename(sampleFile).split(".")[0].split("-")[0]

    #prepare temporary directory
    settings["tempFolder"]=os.path.join(sourceDir,"temp"+time)
    os.mkdir(settings["tempFolder"])

    try:
        #collect files to be used in a list
        rawFiles=collectRawFiles(sourceDir,cityName)

        #export images from source files
        imgFiles=createImages(rawFiles,settings)

        #Join the images into a video and save it to the source directory
        print("\nRendering video from images...",end="")
        outFile=os.path.join(sourceDir,f'{cityName.encode("ascii", "ignore").decode()}-{time}.mp4')
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