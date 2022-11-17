import subprocess
from datetime import datetime
from pathlib import Path
from threading import Lock
import concurrent.futures

import cv2
import easygui


from tkinter import *
from tkinter import ttk
from tkinter import filedialog

def rmtree(root):
    '''Recursively removes directorz tree'''
    for p in root.iterdir():
        if p.is_dir():
            rmtree(p)
        else:
            p.unlink()
    root.rmdir()

def createTempDir(oldFolder,location,time):
    '''prepare temporary directory and delete old one'''
    if not oldFolder==None and oldFolder.exists(): rmtree(oldFolder)
    tempFolder=Path(location,"temp"+time)
    if tempFolder.exists(): rmtree(tempFolder)
    tempFolder.mkdir()
    return tempFolder

class CSLapse():

    def null(self,*args,**kwargs):pass
    '''Placeholder function'''

    def openFile(self,title,filetypes,defDir=None):
        '''Open file opening dialog box and return the full path to the selected file'''
        return filedialog.askopenfilename(title=title,initialdir=defDir,filetypes=filetypes)
        
    def setSampleFile(self,sampleFile):
        '''Store city name and location of the sample file'''
        sampleFile=Path(sampleFile)
        self.sourceDir=sampleFile.parent
        self.cityName=sampleFile.stem.split("-")[0]
        self.tempFolder=createTempDir(self.tempFolder,self.sourceDir,self.timestamp)

    def collectRawFiles(self):
        '''Make an array of files whose name matches the city's name'''
        return sorted(
            filter(
                lambda filename: filename.name.startswith(self.cityName) and ".cslmap" in filename.suffixes, 
                self.sourceDir.iterdir()
            ))

    def openSample(self,title):
        '''Select sample file from dialog and set variables accordingly'''
        self.vars["sampleFile"].set(self.openFile(title, self.filetypes["cslmap"],self.sourceDir))
        self.setSampleFile(self.vars["sampleFile"].get())
        self.rawFiles=self.collectRawFiles()
        self.vars["numOfFiles"].set(len(self.rawFiles))



    def exportSample(self):
        '''Export png from the cslmap file that will be the last frame of the video'''
        pass
    
    def __init__(self):

        #timestamp to have a unique name
        self.timestamp=str(datetime.now()).split(" ")[-1].split(".")[0].replace(":","")

        self.sourceDir=None #Path type, the directory where cslmap files are loaded from
        self.cityName=None #string, the name of the city
        self.tempFolder=None #Path type, the location where temporary files are created
        self.rawFiles=[]
        self.imageFiles=[]

        self.gui=CSLapse.GUI(self)

        self.vars={
            "exeFile":StringVar(value="No file selected"),
            "sampleFile":StringVar(value="No file selected"),
            "numOfFiles":IntVar(value=0),
            "fps":IntVar(value=12),
            "width":IntVar(value=2000),
            "threads":IntVar(value=6),
            "rotation":StringVar(value="0°"),
            "areas":StringVar(value="9"),
            "videoLength":"all",
            "previewImage":PhotoImage(file="C:\\Program Files\\Epic Games\\CitiesSkylines\\CSLMapView\\foo.png")
        }

        self.texts={
            "openExeTitle":"Select CSLMapViewer.exe",
            "openSampleTitle":"Select a cslmap save of your city",
            "all":"all"
        }

        self.filetypes={
            "exe":[("Executables","*.exe"),("All files","*")],
            "cslmap":[("CSLMap files",("*.cslmap","*.cslmap.gz")),("All files","*")]
        }

        self.gui.configureWindow()

    class GUI(object):
        def createMainFrame(self,cb,vars,filetypes,texts):
            self.mainFrame=ttk.Frame(self.root)
            self.fileSelectionBox=ttk.Labelframe(self.mainFrame,text="Files")
            self.exeSelectLabel=ttk.Label(self.fileSelectionBox,text="Path to CSLMapViewer.exe")
            self.exePath=ttk.Entry(self.fileSelectionBox,state=["readonly"],textvariable=vars["exeFile"])
            self.exeSelectBtn=ttk.Button(self.fileSelectionBox,text="Select file",command=
                lambda: vars["exeFile"].set(cb["openExe"](texts["openExeTitle"],filetypes["exe"])))
            self.sampleSelectLabel=ttk.Label(self.fileSelectionBox,text="Select a cslmap file of your city")
            self.samplePath=ttk.Entry(self.fileSelectionBox,state=["readonly"],textvariable=vars["sampleFile"])
            self.sampleSelectBtn=ttk.Button(self.fileSelectionBox,text="Select file",command=
                lambda: cb["openSample"](texts["openSampleTitle"]))
            self.filesLoading=ttk.Progressbar(self.fileSelectionBox)
            self.filesNumLabel=ttk.Label(self.fileSelectionBox,textvariable=vars["numOfFiles"])
            self.filesLoadedLabel=ttk.Label(self.fileSelectionBox,text="files found")

            self.videoSettingsBox=ttk.Labelframe(self.mainFrame,text="Video settings")
            self.fpsLabel=ttk.Label(self.videoSettingsBox,text="Frames per second: ")
            self.fpsEntry=ttk.Entry(self.videoSettingsBox,width=5,textvariable=vars["fps"])
            self.imageWidthLabel=ttk.Label(self.videoSettingsBox,text="Width:")
            self.imageWidthInput=ttk.Entry(self.videoSettingsBox,width=5,textvariable=vars["width"])
            self.imageWidthUnit=ttk.Label(self.videoSettingsBox,text="pixels")
            self.lengthLabel=ttk.Label(self.videoSettingsBox,text="Video length:")
            self.lengthInput=ttk.Combobox(self.videoSettingsBox,textvariable=vars["videoLength"],values=texts["all"])
            self.lengthUnit=ttk.Label(self.videoSettingsBox,text="frames")

            self.advancedSettingBox=ttk.Labelframe(self.mainFrame,text="Advanced")
            self.threadsLabel=ttk.Label(self.advancedSettingBox,text="Threads:")
            self.threadsEntry=ttk.Entry(self.advancedSettingBox,width=5,textvariable=vars["threads"])

            self.submitBtn=ttk.Button(self.mainFrame,text="Export",command=
                lambda: cb["submit"]())

        def createPreviewFrame(self,cb,vars):
            self.middleBar=ttk.Separator(self.root,orient="vertical")

            self.previewFrame=ttk.Frame(self.root)
            self.preview=Canvas(self.previewFrame,width=300,height=300,relief=SUNKEN)
            self.preview.create_image(0,0,image=vars["previewImage"])

            self.zoomLabel=ttk.Label(self.previewFrame,text="Areas:")
            self.zoomEntry=ttk.Entry(self.previewFrame,width=5,textvariable=vars["areas"])
            self.zoomSlider=ttk.Scale(self.previewFrame,orient=HORIZONTAL,from_=0.1,to=9.0,variable=vars["areas"],command=cb["areasSliderChanged"])

            self.rotationLabel=ttk.Label(self.previewFrame,text="Rotation:")
            self.rotationSelection=ttk.Menubutton(self.previewFrame,textvariable=vars["rotation"])
            self.rotationSelection.menu=Menu(self.rotationSelection,tearoff=0)
            self.rotationSelection["menu"]=self.rotationSelection.menu
            for option in ["0°","90°","180°","270°"]:
                self.rotationSelection.menu.add_radiobutton(label=option,variable=vars["rotation"])

        def gridMainFrame(self):
            self.mainFrame.grid(column=0,row=0,sticky=NSEW,padx=5,pady=5)

            self.fileSelectionBox.grid(column=0,row=0,sticky=EW)
            self.exeSelectLabel.grid(column=0,row=0,columnspan=3,sticky=EW)
            self.exePath.grid(column=0,row=1,columnspan=2,sticky=EW)
            self.exeSelectBtn.grid(column=2,row=1)
            self.sampleSelectLabel.grid(column=0,row=2,columnspan=3,sticky=EW)
            self.samplePath.grid(column=0,row=3,columnspan=2,sticky=EW)
            self.sampleSelectBtn.grid(column=2,row=3)
            self.filesNumLabel.grid(column=0,row=4,sticky=W)
            self.filesLoadedLabel.grid(column=1,row=4,sticky=W)

            self.videoSettingsBox.grid(column=0,row=1,sticky=EW)
            self.fpsLabel.grid(column=0,row=0,sticky=W)
            self.fpsEntry.grid(column=1,row=0,sticky=EW)
            self.imageWidthLabel.grid(column=0,row=1,sticky=W)
            self.imageWidthInput.grid(column=1,row=1,sticky=EW)
            self.imageWidthUnit.grid(column=2,row=1,sticky=W)
            self.lengthLabel.grid(column=0,row=2,sticky=W)
            self.lengthInput.grid(column=1,row=2,sticky=W)
            self.lengthUnit.grid(column=2,row=2,sticky=W)

            self.advancedSettingBox.grid(column=0,row=2,sticky=EW)
            self.threadsLabel.grid(column=0,row=0,sticky=W)
            self.threadsEntry.grid(column=1,row=0,sticky=EW)

            self.submitBtn.grid(column=0,row=10,sticky=(S,E,W))

        def gridPreviewFrame(self):
            self.middleBar.grid(column=1,row=0,sticky=SW)

            self.previewFrame.grid(column=20,row=0,sticky=NSEW)
            self.preview.grid(column=0,row=0,columnspan=10)
            self.zoomLabel.grid(column=0,row=1,sticky=W)
            self.zoomEntry.grid(column=1,row=1,sticky=W)
            self.zoomSlider.grid(column=2,row=1,columnspan=8,sticky=EW)
            self.rotationLabel.grid(column=0,row=2,columnspan=3,sticky=W)
            self.rotationSelection.grid(column=1,row=2,columnspan=2,sticky=W)

        def configure(self):
            self.root.columnconfigure(2,weight=1)
            self.root.rowconfigure(0,weight=1)

            self.fileSelectionBox.columnconfigure(0,weight=1)

        
        def refreshPreview():
            pass

        def roundAreas(self,*_):
            '''Round the areas value to 2 decimal places'''
            self.vars["areas"].set(self.vars["areas"].get()[:4])


        def test(self,*args,**kwargs):
            print(self.vars["previewImage"])

        def __init__(self,parent):
            self.external=parent
            self.root=Tk()

        def configureWindow(self):
            '''Sets up widgets, event bindings, grid for the main window'''
            self.callBacks={
                "openExe":self.external.openFile,
                "openSample":self.external.openSample,
                "fpsChanged":self.external.null,
                "videoWidthChanged":self.external.null,
                "threadsChanged":self.external.null,
                "areasEntered":self.external.null,
                "areasSliderChanged":self.roundAreas,
                "submit":self.test
            }

            self.createMainFrame(self.callBacks,self.external.vars,self.external.filetypes,self.external.texts)
            self.createPreviewFrame(self.callBacks,self.external.vars)

            self.gridMainFrame()
            self.gridPreviewFrame()

            self.configure()




if __name__=="__main__":

    O=CSLapse()
    O.gui.root.mainloop()