import subprocess
from datetime import datetime
from pathlib import Path
from threading import Lock,Thread
import concurrent.futures

import cv2

from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox

from PIL import ImageTk, Image

def rmtree(root):
    '''Recursively removes directory tree'''
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

def exportFile(srcFile,outFolder,cmd,retry):
    '''Call CSLMapView to export one image file and return outfile's name. Should run on separate thread'''

    #Prepare command that calls cslmapview.exe
    newFileName=Path(outFolder,srcFile.stem.encode("ascii", "ignore").decode()).with_suffix(".png")
    cmd[1]=str(srcFile)
    cmd[3]=str(newFileName)

    #call CSLMapview.exe to export the image. Try again at fail, abort after manz tries.
    for _ in range(retry):
        try:
            #Return prematurely on abort
            if constants["abort"]:return

            subprocess.run(cmd,shell=False,stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL,check=False)

            #Ensure that the image file was successfully created. 
            assert newFileName.exists()
            
            return str(newFileName)
        except e:
            print(e)
        except subprocess.CalledProcessError(returncode,cmd):pass
        except AssertionError():pass
    return None

def roundToTwoDecimals(var):
    '''Round the decimal in textvariable to 2 decimal places'''
    var.set(str(round(float(var.get()),2)))

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

    def exportSample(self):
        '''Run this on separate thread - Export png from the cslmap file that will be the last frame of the video'''
        if (not self.vars["exeFile"].get()==constants["noFileText"]) and (not self.vars["sampleFile"].get()==constants["noFileText"]):
            exported=exportFile(
                self.rawFiles[self.vars["videoLength"].get()-1], 
                self.tempFolder, 
                self.collections["sampleCommand"][:],
                constants["defaultRetry"]
                )
            with self.lock:
                self.vars["previewSource"]=Image.open(exported)
                self.gui.preview.justExported()
            self.gui.setGUI("previewLoaded")
        else:
            self.gui.setGUI("previewLoadError")

    def refreshPreview(self):
        '''Export the preview CSLMap file with current settings'''
        self.gui.setGUI("previewLoading")
        self.collections["sampleCommand"][6]=str(
            #int(self.vars["width"].get() * constants["defaultAreas"] / float(self.vars["areas"].get())))
            self.vars["width"].get())
        self.collections["sampleCommand"][8]=str(self.vars["areas"].get())
        Thread(target=self.exportSample,daemon=True).start()

    def openSample(self,title):
        '''Select sample file from dialog and set variables accordingly'''
        selectedFile=self.openFile(title, self.filetypes["cslmap"],self.sourceDir)
        if not selectedFile =="" and not selectedFile==self.vars["sampleFile"].get():
            self.vars["sampleFile"].set(selectedFile)
            self.setSampleFile(self.vars["sampleFile"].get())
            self.rawFiles=self.collectRawFiles()
            self.vars["numOfFiles"].set(len(self.rawFiles))
            if self.vars["videoLength"].get()==0:
                self.vars["videoLength"].set(self.vars["numOfFiles"].get())
            else:
                self.vars["videoLength"].set(min(self.vars["videoLength"].get(),self.vars["numOfFiles"].get()))
            self.refreshPreview()
        else:
            self.vars["sampleFile"].set(constants["noFileText"])

    def openExe(self,title):
        '''Select SCLMapViewer.exe from dialog and set variables accordingly'''
        selectedFile=self.openFile(title, self.filetypes["exe"],self.sourceDir)
        if not selectedFile =="":
            self.vars["exeFile"].set(selectedFile)
            self.collections["sampleCommand"][0]=self.vars["exeFile"].get()
            self.refreshPreview()
        else:
            self.vars["exeFile"].set(constants["noFileText"])

    def exportImageOnThread(self,srcFile,cmd):
        '''Call this on separate thread - calls the given command to export the given image, records success'''
        newFileName=None
        while newFileName==None and not constants["abort"]:
            newFileName=exportFile(srcFile, self.tempFolder, cmd,int(self.vars["retry"].get()))
            #TODO:Ask for confirmation if it fails many times, with timer. When timer runs out, try again automatically.


        with self.lock:
            self.imageFiles.append(newFileName)
            self.vars["exportingDone"].set(self.vars["exportingDone"].get()+1)

    def exportImageFiles(self):
        '''Calls CSLMapView to export the collected cslmap files one-by-one on separate threads'''
        self.gui.setGUI("startExport")

        limit = self.vars["videoLength"].get()        
        cmd=[self.vars["exeFile"].get(),"__srcFile__","-output","__outFile__","-silent","-imagewidth",str(self.vars["width"].get()),"-area",str(self.vars["areas"].get())]

        with concurrent.futures.ThreadPoolExecutor(self.vars["threads"].get()) as executor:
            for i in range(limit):
                #start exporting on a new thread
                executor.submit(self.exportImageOnThread,self.rawFiles[i],cmd[:])

        if constants["abort"]:return
        #Sort array as the order might have changed during threading
        self.imageFiles=sorted(self.imageFiles)
        
    def renderVideo(self):
        '''Creates an mp4 video file from all the exported images'''
        self.gui.setGUI("startRender")
        #create video file
        outFile=str(Path(self.sourceDir,f'{self.cityName.encode("ascii", "ignore").decode()}-{self.timestamp}.mp4'))
        out = cv2.VideoWriter(outFile,cv2.VideoWriter_fourcc(*"mp4v"), int(self.vars["fps"].get()), (int(self.vars["width"].get()),int(self.vars["width"].get())))
        for file in self.imageFiles:
            if constants["abort"]:break
            #add frame to video
            img = cv2.imread(file)
            out.write(img)
            with self.lock:
                self.vars["renderingDone"].set(self.vars["renderingDone"].get()+1)
        out.release()

    def run(self):
        '''Exports images and creatrs video from them'''
        if constants["abort"]:return
        self.exportImageFiles()
        if constants["abort"]:return
        self.renderVideo()
        if constants["abort"]:return
        self.gui.setGUI("renderDone")

    def abort(self):
        '''Stops currently running process. Impossible to recover state afterwards'''
        constants["abort"]=True
        exit(1)
        #TODO: Change the way concurrent threads are killed couse this is not nice

    def resetState(self):
        '''Sets all variables to the default state'''
        self.sourceDir=None
        self.cityName=None
        self.tempFolder=None
        self.rawFiles=[]
        self.imageFiles=[]

        self.vars["exeFile"].set(constants["noFileText"])
        self.vars["sampleFile"].set(constants["noFileText"])
        self.vars["numOfFiles"].set(0)
        self.vars["fps"].set(constants["defaultFPS"])
        self.vars["width"].set(constants["defaultExportWidth"])
        self.vars["threads"].set(constants["defaultThreads"])
        self.vars["rotation"].set(constants["rotaOptions"][0])
        self.vars["areas"].set(constants["defaultAreas"])
        self.vars["videoLength"].set(0)
    
    def __init__(self):
        #timestamp to have a unique name
        self.timestamp=str(datetime.now()).split(" ")[-1].split(".")[0].replace(":","")
        self.gui=CSLapse.GUI(self)
        self.lock=Lock()


        self.vars={
            "exeFile":StringVar(value=constants["noFileText"]),
            "sampleFile":StringVar(value=constants["noFileText"]),
            "numOfFiles":IntVar(value=0),
            "fps":IntVar(value=constants["defaultFPS"]),
            "width":IntVar(value=constants["defaultExportWidth"]),
            "threads":IntVar(value=constants["defaultThreads"]),
            "retry":IntVar(value=constants["defaultRetry"]),
            "rotation":StringVar(value=constants["rotaOptions"][0]),
            "areas":StringVar(value=constants["defaultAreas"]),
            "videoLength":IntVar(value=0),
            "exportingDone":IntVar(value=0),
            "renderingDone":IntVar(value=0),
            "previewSource":"",
            "previewImage":""
        }
        
        self.sourceDir=None #Path type, the directory where cslmap files are loaded from
        self.cityName=None #string, the name of the city
        self.tempFolder=None #Path type, the location where temporary files are created
        self.rawFiles=[]    #Collected cslmap files with matching city name
        self.imageFiles=[]

        self.filetypes={
            "exe":[("Executables","*.exe"),("All files","*")],
            "cslmap":[("CSLMap files",("*.cslmap","*.cslmap.gz")),("All files","*")]
        }

        self.collections={
            "sampleCommand":["__exeFile__","__srcFile__","-output","__outFile__","-silent","-imagewidth",str(constants["sampleExportWidth"]),"-area",str(constants["defaultAreas"])]
        }

        self.resetState()
        self.gui.configureWindow()
        self.gui.setGUI("defaultState")

    def __del__(self):
        if self.tempFolder:
            rmtree(self.tempFolder)
    
    class GUI(object):
        def createMainFrame(self,cb,vars,filetypes,texts):
            '''Create the widgets in the left main window'''
            self.mainFrame=ttk.Frame(self.root)
            self.fileSelectionBox=ttk.Labelframe(self.mainFrame,text="Files")
            self.exeSelectLabel=ttk.Label(self.fileSelectionBox,text="Path to CSLMapViewer.exe")
            self.exePath=ttk.Entry(self.fileSelectionBox,state=["readonly"],textvariable=vars["exeFile"],cursor=constants["clickable"])
            self.exeSelectBtn=ttk.Button(self.fileSelectionBox,text="Select file",cursor=constants["clickable"],command=
                lambda: cb["openExe"](texts["openExeTitle"]))
            self.sampleSelectLabel=ttk.Label(self.fileSelectionBox,text="Select a cslmap file of your city")
            self.samplePath=ttk.Entry(self.fileSelectionBox,state=["readonly"],textvariable=vars["sampleFile"],cursor=constants["clickable"])
            self.sampleSelectBtn=ttk.Button(self.fileSelectionBox,text="Select file",cursor=constants["clickable"],command=
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
            self.lengthLabel=ttk.Label(self.videoSettingsBox,width=5,text="Video length:")
            self.lengthInput=ttk.Entry(self.videoSettingsBox,textvariable=vars["videoLength"])
            self.lengthUnit=ttk.Label(self.videoSettingsBox,text="frames")

            self.advancedSettingBox=ttk.Labelframe(self.mainFrame,text="Advanced")
            self.threadsLabel=ttk.Label(self.advancedSettingBox,text="Threads:")
            self.threadsEntry=ttk.Entry(self.advancedSettingBox,width=5,textvariable=vars["threads"])
            self.retryLabel=ttk.Label(self.advancedSettingBox,text="Fail after:")
            self.retryEntry=ttk.Entry(self.advancedSettingBox,width=5,textvariable=vars["retry"])

            self.progressFrame=ttk.Frame(self.mainFrame)
            self.exportingLabel=ttk.Label(self.progressFrame,text="Exporting files:")
            self.exportingDoneLabel=ttk.Label(self.progressFrame,textvariable=vars["exportingDone"])
            self.exportingOfLabel=ttk.Label(self.progressFrame,text=" of ")
            self.exportingTotalLabel=ttk.Label(self.progressFrame,textvariable=vars["videoLength"])
            self.exportingProgress=ttk.Progressbar(self.progressFrame,orient="horizontal",mode="determinate",variable=vars["exportingDone"])
            self.renderingLabel=ttk.Label(self.progressFrame,text="Renderig video:")
            self.renderingDoneLabel=ttk.Label(self.progressFrame,textvariable=vars["renderingDone"])
            self.renderingOfLabel=ttk.Label(self.progressFrame,text=" of ")
            self.renderingTotalLabel=ttk.Label(self.progressFrame)
            self.renderingProgress=ttk.Progressbar(self.progressFrame,orient="horizontal",mode="determinate",variable=vars["renderingDone"])

            self.submitBtn=ttk.Button(self.mainFrame,text="Export",cursor=constants["clickable"],command=
                lambda: cb["submit"]())
            self.abortBtn=ttk.Button(self.mainFrame,text="Abort",cursor=constants["clickable"],command=
                lambda:cb["abort"]())

        def createPreviewFrame(self,cb,vars):
            '''Create widgets related to the preview canvas, initialize Preview object'''
            self.middleBar=ttk.Separator(self.root,orient="vertical")

            self.previewFrame=ttk.Frame(self.root)

            self.canvasFrame=ttk.Frame(self.previewFrame,relief=SUNKEN,borderwidth=2)
            self.preview=CSLapse.GUI.Preview(self)
            self.refreshPreviewBtn=ttk.Button(self.preview.canvas,text="Refresh",cursor=constants["clickable"],
                command=lambda:cb["refreshPreview"]())
            self.fitToCanvasBtn=ttk.Button(self.preview.canvas,text="Fit",cursor=constants["clickable"],
                command=self.preview.fitToCanvas)
            self.originalSizeBtn=ttk.Button(self.preview.canvas,text="100%",cursor=constants["clickable"],
                command=self.preview.scaleToOriginal)

            self.canvasSettingFrame=ttk.Frame(self.previewFrame)
            self.zoomLabel=ttk.Label(self.canvasSettingFrame,text="Areas:")
            self.zoomEntry=ttk.Entry(self.canvasSettingFrame,width=5,textvariable=vars["areas"])
            self.zoomSlider=ttk.Scale(self.canvasSettingFrame,orient=HORIZONTAL,from_=0.1,to=9.0,variable=vars["areas"],cursor=constants["clickable"],command=cb["areasSliderChanged"](vars["areas"]))

            self.rotationLabel=ttk.Label(self.canvasSettingFrame,text="Rotation:")
            self.rotationSelection=ttk.Menubutton(self.canvasSettingFrame,textvariable=vars["rotation"],cursor=constants["clickable"])
            self.rotationSelection.menu=Menu(self.rotationSelection,tearoff=0)
            self.rotationSelection["menu"]=self.rotationSelection.menu
            for option in constants["rotaOptions"]:
                self.rotationSelection.menu.add_radiobutton(label=option,variable=vars["rotation"])

        def gridMainFrame(self):
            '''Add main widgets to the grid'''
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
            self.retryLabel.grid(column=0,row=1,sticky=W)
            self.retryEntry.grid(column=1,row=1,sticky=EW)

            self.progressFrame.grid(column=0,row=9,sticky=EW)
            self.exportingLabel.grid(column=0,row=0)
            self.exportingDoneLabel.grid(column=1,row=0)
            self.exportingOfLabel.grid(column=2,row=0)
            self.exportingTotalLabel.grid(column=3,row=0)
            self.exportingProgress.grid(column=0,row=1,columnspan=5,sticky=EW)

            self.renderingLabel.grid(column=0,row=2)
            self.renderingDoneLabel.grid(column=1,row=2)
            self.renderingOfLabel.grid(column=2,row=2)
            self.renderingTotalLabel.grid(column=3,row=2)
            self.renderingProgress.grid(column=0,row=3,columnspan=5,sticky=EW)

            self.submitBtn.grid(column=0,row=10,sticky=(S,E,W))
            self.abortBtn.grid(column=0,row=11,sticky=(S,E,W))

        def gridPreviewFrame(self):
            '''Add widgets related to preview to the grid'''
            self.middleBar.grid(column=1,row=0,sticky=SW)

            self.previewFrame.grid(column=20,row=0,sticky=NSEW)

            self.canvasFrame.grid(column=0,row=0,sticky=NSEW)
            self.preview.canvas.grid(column=0,row=0,sticky=NSEW)
            self.refreshPreviewBtn.grid(column=1,row=0,sticky=NE)
            self.fitToCanvasBtn.grid(column=1,row=2,sticky=SE)
            self.originalSizeBtn.grid(column=1,row=3,sticky=SE)

            self.canvasSettingFrame.grid(column=0,row=1,sticky=NSEW)
            self.zoomLabel.grid(column=0,row=0,sticky=W)
            self.zoomEntry.grid(column=1,row=0,sticky=W)
            self.zoomSlider.grid(column=2,row=0,sticky=EW)

            #Functionality not implemented yet
            #self.rotationLabel.grid(column=0,row=1,columnspan=3,sticky=W)
            #self.rotationSelection.grid(column=1,row=1,columnspan=2,sticky=W)

        def configure(self):
            '''Configure widgets'''
            self.root.columnconfigure(20,weight=1)
            self.root.rowconfigure(0,weight=1)

            self.mainFrame.rowconfigure(8,weight=1)
            self.fileSelectionBox.columnconfigure(1,weight=1)
            self.progressFrame.columnconfigure(4,weight=1)

            self.previewFrame.columnconfigure(0,weight=1)
            self.previewFrame.rowconfigure(0,weight=1)
            self.canvasFrame.columnconfigure(0,weight=1)
            self.canvasFrame.rowconfigure(0,weight=1)
            self.preview.canvas.columnconfigure(0,weight=1)
            self.preview.canvas.rowconfigure(1,weight=1)
            self.canvasSettingFrame.columnconfigure(2,weight=1)

            self.createBindings()

        def createBindings(self):
            '''Bind events to GUI widgets'''
            self.preview.createBindings()

        def enable(self,*args):
            '''Set all argument widgets to enabled'''
            for widget in args:
                widget.state(["!disabled"])

        def disable(self,*args):
            '''Set all argument widgets to disabled'''
            for widget in args:
                widget.state(["disabled"])

        def show(self,*args):
            '''Show all argument widgets'''
            for widget in args:
                widget.grid()

        def hide(self,*args):
            '''Hide all argument widgets'''
            for widget in args:
                widget.grid_remove()

        def setGUI(self,state):
            '''Set the GUI to a predefined state. This sets the GUI variables and widgets.
            state should be one of ["startExport","startRender","renderDone","defaultState"]'''
            if state == "startExport":
                self.external.vars["exportingDone"].set(0)
                self.exportingProgress.config(maximum=self.external.vars["videoLength"].get())
                self.disable(self.exeSelectBtn,self.sampleSelectBtn,self.fpsEntry,self.imageWidthInput,self.lengthInput,self.threadsEntry,self.retryEntry,self.zoomSlider,self.zoomEntry)
                self.enable(self.abortBtn)
                self.hide(self.submitBtn,self.renderingProgress,self.renderingLabel,self.renderingDoneLabel,self.renderingOfLabel,self.renderingTotalLabel)
                self.show(self.progressFrame,self.exportingProgress,self.exportingLabel,self.exportingDoneLabel,self.exportingOfLabel,self.exportingTotalLabel,self.abortBtn)
            elif state=="startRender":
                self.external.vars["renderingDone"].set(0)
                self.renderingTotalLabel.configure(text=len(self.external.imageFiles))
                self.renderingProgress.config(maximum=len(self.external.imageFiles))
                self.disable(self.exeSelectBtn,self.sampleSelectBtn,self.fpsEntry,self.imageWidthInput,self.lengthInput,self.threadsEntry,self.retryEntry,self.zoomSlider,self.zoomEntry)
                self.enable(self.abortBtn)
                self.hide(self.submitBtn,self.exportingProgress,self.exportingLabel,self.exportingDoneLabel,self.exportingOfLabel,self.exportingTotalLabel)
                self.show(self.progressFrame,self.renderingProgress,self.renderingLabel,self.renderingDoneLabel,self.renderingOfLabel,self.renderingTotalLabel)
            elif state=="renderDone":
                self.disable(self.abortBtn)
                self.enable(self.exeSelectBtn,self.sampleSelectBtn,self.fpsEntry,self.imageWidthInput,self.lengthInput,self.threadsEntry,self.retryEntry,self.zoomSlider,self.zoomEntry)
                self.show(self.submitBtn)
                self.hide(self.progressFrame,self.abortBtn)
            elif state=="defaultState":
                self.external.resetState()
                self.disable(self.progressFrame,self.abortBtn,self.fitToCanvasBtn,self.originalSizeBtn)
                self.enable(self.submitBtn,self.exeSelectBtn,self.sampleSelectBtn,self.fpsEntry,self.imageWidthInput,self.lengthInput,self.threadsEntry,self.retryEntry,self.zoomSlider,self.zoomEntry,self.rotationSelection)
                self.hide(self.progressFrame,self.abortBtn,self.refreshPreviewBtn,self.fitToCanvasBtn,self.originalSizeBtn)
                self.show(self.submitBtn)
            elif state=="previewLoading":
                self.disable(self.refreshPreviewBtn,self.fitToCanvasBtn,self.originalSizeBtn)
                #TODO: Add loading image to canvas
                #TODO: Add loading image to refresh button
                self.preview.canvas.configure(cursor="watch")
            elif state=="previewLoaded":
                self.enable(self.refreshPreviewBtn,self.fitToCanvasBtn,self.originalSizeBtn)
                self.show(self.refreshPreviewBtn,self.fitToCanvasBtn,self.originalSizeBtn)
                self.preview.canvas.configure(cursor=constants["previewCursor"])
            elif state=="previewLoadError":
                self.enable(self.refreshPreviewBtn)
                self.show(self.refreshPreviewBtn)
                self.preview.canvas.configure(cursor="")
            elif state=="aborting":
                self.disable(self.exeSelectBtn,self.sampleSelectBtn,self.fpsEntry,self.imageWidthInput,self.lengthInput,self.threadsEntry,self.zoomSlider,self.zoomEntry,self.abortBtn,self.fitToCanvasBtn,self.originalSizeBtn,self.refreshPreviewBtn)


        def __init__(self,parent):
            self.external=parent
            self.root=Tk()
            self.root.title("CSLapse")

        def submitPressed(self):
            '''Checks if all conditions are satified and starts exporting if yes. Shows warning if not'''
            if self.external.vars["exeFile"].get()==constants["noFileText"]:
                messagebox.showwarning(title="Warning",message=constants["texts"]["noExeMessage"])
            elif self.external.vars["sampleFile"].get()==constants["noFileText"]:
                messagebox.showwarning(title="Warning",message=constants["texts"]["noSampleMessage"])
            elif not self.external.vars["videoLength"].get()>0:
                messagebox.showwarning(title="Warning",message=constants["texts"]["invalidLengthMessage"])
            else:
                Thread(target=self.external.run,daemon=True).start()

        def abortPressed(self):
            '''Asks user if really wants to kill. Kills if yes, nothing if no.'''
            if messagebox.askyesno(title="Abort action?",message=constants["texts"]["askAbort"]):
                self.external.abort()

        def refreshPressed(self):
            '''Handles refresh button press event'''
            if self.external.vars["exeFile"].get()==constants["noFileText"]:
                messagebox.showwarning(title="Warning",message=constants["texts"]["noExeMessage"])
            elif self.external.vars["sampleFile"].get()==constants["noFileText"]:
                messagebox.showwarning(title="Warning",message=constants["texts"]["noSampleMessage"])
            else:
                self.external.refreshPreview()

        def configureWindow(self):
            '''Sets up widgets, event bindings, grid for the main window'''
            self.callBacks={
                "openExe":self.external.openExe,
                "openSample":self.external.openSample,
                "fpsChanged":self.external.null,
                "videoWidthChanged":self.external.null,
                "threadsChanged":self.external.null,
                "areasEntered":roundToTwoDecimals,
                "areasSliderChanged":roundToTwoDecimals,
                "submit": self.submitPressed,
                "abort":self.abortPressed,
                "refreshPreview":self.refreshPressed
            }

            self.createMainFrame(self.callBacks,self.external.vars,self.external.filetypes,constants["texts"])
            self.createPreviewFrame(self.callBacks,self.external.vars)

            self.gridMainFrame()
            self.gridPreviewFrame()

            self.configure()

        class Preview(object):
            def __init__(self, parent):
                self.gui=parent
                self.canvas=Canvas(self.gui.canvasFrame,cursor="")
                self.active=False

                self.fullWidth=self.canvas.winfo_screenwidth()    #Width of drawable canvas in pixels
                self.fullHeight=self.canvas.winfo_screenheight()   #Height of drawable canvas in pixels
                self.imageWidth=0   #Width of original image in pixels
                self.imageHeight=0  #Height of original image in pixels

                self.printAreaX=0   #X coordinate of the top left corner of the print area on the original image
                self.printAreaY=0   #Y coordinate of the top left corner of the printarea on the original image
                self.printAreaW=0   #Width of printarea on the original image
                self.printAreaH=0   #Height of printarea on the original image
                self.previewAreas=0 #Areas printed on the currently active preview image

                self.imageX=0  #X Coordinate on canvas of pixel in top left of image
                self.imageY=0  #Y Coordinate on canvas of pixel in top left of image
                self.scaleFactor=1  #Conversion factor: canvas pixels / original image pixels

                self.placeholderImage=ImageTk.PhotoImage(Image.open(constants["noPreviewImage"]))
                self.canvas.create_image(0,0,image=self.placeholderImage,tags="placeholder")

            def createBindings(self):
                '''Bind actions to events on the canvas'''
                self.canvas.bind("<Configure>", self.resized)
                self.canvas.bind("<MouseWheel>",self.scrolled)
                self.canvas.bind("<B1-Motion>",self.dragged)
                self.canvas.bind("<ButtonPress-1>",self.clicked)

            def resizeImage(self,newFactor):
                '''Change the activeImage to one with the current scaleFactor, keep center pixel in center'''
                #TODO: Change this so that center pixels remains in center
                self.imageX=self.fullWidth/2-((self.fullWidth/2-self.imageX)/self.scaleFactor)*newFactor
                self.imageY=self.fullHeight/2-((self.fullHeight/2-self.imageY)/self.scaleFactor)*newFactor

                self.scaleFactor=newFactor

                self.gui.external.vars["previewImage"]=ImageTk.PhotoImage(self.gui.external.vars["previewSource"].resize((int(self.imageWidth*self.scaleFactor),int(self.imageHeight*self.scaleFactor))))
                self.canvas.itemconfigure(self.activeImage,image=self.gui.external.vars["previewImage"])
                self.canvas.moveto(self.activeImage,x=self.imageX,y=self.imageY)

            def fitToCanvas(self):
                '''Resize activeImage so that it touches the borders of canvas and the full image is visible, keep aspect ratio'''
                newScaleFactor=min(self.fullWidth/self.imageWidth,self.fullHeight/self.imageHeight)
                self.resizeImage(newScaleFactor)
                self.canvas.moveto(self.activeImage,x=(self.fullWidth-int(self.imageWidth*self.scaleFactor))/2,y=(self.fullHeight-int(self.imageHeight*self.scaleFactor))/2)
                self.imageX=(self.fullWidth-self.imageWidth*self.scaleFactor)/2
                self.imageY=(self.fullHeight-self.imageHeight*self.scaleFactor)/2

            def scaleToOriginal(self):
                '''Rescale to the original size of the preview image'''
                self.resizeImage(1)

            def justExported(self):
                '''Show newly exported preview image'''
                self.imageWidth=self.gui.external.vars["width"].get()
                self.imageHeight=self.gui.external.vars["width"].get()

                self.previewAreas=float(self.gui.external.vars["areas"].get())
                self.printAreaX=0
                self.printAreaW=self.gui.external.vars["width"].get()
                self.printAreaY=0
                self.printAreaH=self.gui.external.vars["width"].get()
                
                self.gui.external.vars["previewImage"]=ImageTk.PhotoImage(self.gui.external.vars["previewSource"])
                if self.active:
                    self.canvas.itemconfigure(self.activeImage,image=self.gui.external.vars["previewImage"])
                else:
                    self.activeImage=self.canvas.create_image(0,0,anchor=CENTER,image=self.gui.external.vars["previewImage"])

                self.fitToCanvas()

                self.active=True
                self.canvas.itemconfigure("placeholder",state="hidden")

            def resized(self,event):
                '''Handle change in the canvas's size'''
                if self.active:
                    #Center of the canvas should stay the center of the canvas when the window is resized
                    self.imageX=((self.imageX+self.imageWidth*self.scaleFactor/2)*event.width/self.fullWidth)-(self.imageWidth*self.scaleFactor/2)
                    self.imageY=((self.imageY+self.imageHeight*self.scaleFactor/2)*event.height/self.fullHeight)-(self.imageHeight*self.scaleFactor/2)
                    self.canvas.moveto(self.activeImage,x=self.imageX,y=self.imageY)

                if not self.active:
                    self.canvas.moveto("placeholder",x=str((event.width-self.placeholderImage.width())/2),
                                                    y=str((event.height-self.placeholderImage.height())/2))
                self.fullWidth=event.width
                self.fullHeight=event.height

            def scrolled(self,event):
                '''Handle scrolling (zoom) on canvas'''
                if self.active:
                    self.resizeImage(self.scaleFactor*(1+6/(event.delta)))

            def dragged(self,event):
                '''Handle dragging (panning) on canvas'''
                if self.active:
                    deltaX=event.x-self.lastClick[0]
                    deltaY=event.y-self.lastClick[1]
                    self.canvas.moveto(self.activeImage,x=self.imageX+deltaX,y=self.imageY+deltaY)
                    self.imageX=self.imageX+deltaX
                    self.imageY=self.imageY+deltaY
                    self.lastClick=(event.x,event.y)

            def clicked(self,event):
                '''Handle buttonpress event on canvas'''
                if self.active:
                    self.lastClick=(event.x,event.y)

            def areasChanged(self):
                '''Currently out of use: Reflect change in export areas on preview'''
                wRatio=self.imageWidth/self.previewAreas
                self.printAreaX=(self.previewAreas-float(self.gui.external.vars["areas"].get()))/2*wRatio
                self.printAreaW=wRatio*float(self.gui.external.vars["areas"].get())
                hRatio=self.imageHeight/self.previewAreas
                self.printAreaY=(self.previewAreas-float(self.gui.external.vars["areas"].get()))/2*hRatio
                self.printAreaH=hRatio*float(self.gui.external.vars["areas"].get())


def main():
    O=CSLapse()
    O.gui.root.mainloop()

if __name__=="__main__":
    currentDirectory=Path(__file__).parent.resolve() # current directory
    constants={
        "abort":False,
        "sampleExportWidth":2000,
        "defaultFPS":24,
        "defaultExportWidth":2000,
        "defaultThreads":6,
        "defaultRetry":15,
        "defaultAreas":9.0,
        "noFileText":"No file selected",
        "rotaOptions":["0°","90°","180°","270°"],
        "texts":{
            "openExeTitle":"Select CSLMapViewer.exe",
            "openSampleTitle":"Select a cslmap save of your city",
            "noExeMessage":"Select CSLMapviewer.exe first!",
            "noSampleMessage":"Select a city file first!",
            "invalidLengthMessage":"Invalid video length!",
            "askAbort":"Are you sure you want to abort? This cannot be undone, all progress will be lost."
            
        },
        "clickable":"hand2",
        "previewCursor":"fleur",
        "noPreviewImage":"media/NOIMAGE.png"#Path(currentDirectory,"media","NOIMGAE.png")
    }
    main()