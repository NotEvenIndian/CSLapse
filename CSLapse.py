import sys
import subprocess
from datetime import datetime
from pathlib import Path
import threading
import concurrent.futures
from typing import List, Tuple, Any, Callable
from shutil import rmtree

import logging
import logging.config
import logging.handlers

import cv2

import tkinter
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox

from PIL import ImageTk, Image

# I know the code is extremely badly organized and the classes make almost no difference.
#
# This project was a huge learning experience for me as I have never worked with any of
# these modules before. Nor have I made a program this large. Or released an application for public use.
#
# Suggestions for any sort of improvement are welcome.

def get_logger_config_dict() -> dict:
    """Return the logger configuration dictionary."""
    dictionary = {
        "version": 1,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers":{
            "logfile": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": logging.INFO,
                "formatter": "default",
                "filename": "./cslapse.log",
                "maxBytes": 200000,
                "backupCount": 1
            }
        },
        "loggers":{
            "root": {
                "level": logging.INFO,
                "handlers": ["logfile"]
            },
            "cslapse": {
                "level": logging.INFO,
                "handlers": ["logfile"]
            },
            "gui": {
                "level": logging.INFO,
                "handlers": ["logfile"]
            }
        }
    }

    return dictionary


class AbortException(Exception):pass
class ExportError(Exception):pass


class ThreadCollector(threading.Thread):
    """Cancel and join all running threads and futures except for threads in keepAlive.
    
    Optionally count finished threads so far in counter
    """

    def __init__(   self,
                    keepAlive: List[threading.Thread],
                    futures: List[concurrent.futures.Future] = None,
                    counter: tkinter.IntVar = None,
                    callback: Callable[[],None] = None
        ):
        threading.Thread.__init__(self)
        
        self.log = logging.getLogger("root")
        self._counter = counter
        if self._counter is not None:
            self._counter.set(0)
        self._callback = callback
        
        # Cancel what you can, the rest will be collected
        if futures is not None:
            for future in futures:
                future.cancel()

        self._garbage_threads = list(filter(
            lambda t: t not in [*keepAlive, threading.current_thread()],
            threading.enumerate()
        ))

        self.log.info("Threadcollector object initiated.")

    def total(self) -> int:
        """Returns total number of threads and futures to cancel."""
        return len(self._garbage_threads)

    def run(self) -> None:
        self.log.info("Threadcollector started.")
        for t in self._garbage_threads:
            t.join()
            if self._counter is not None:
                self._counter.set(self._counter.get() + 1)
        if self._callback is not None:
            self._callback()
        self.log.info("Threadcollector finished.")
        return


def exportFile(srcFile: str, outFolder: Path, cmd: List[str], retry: int, abortEvent: threading.Event = None) -> str:
    """Call CSLMapView to export one image file and return outfile's name.

    Exceptions:
        Abortexpression: propagates
        Cannot export file after [retry] tries: raises ExportError
    """

    log = logging.getLogger("root")

    #Prepare command that calls cslmapview.exe
    newFileName = Path(outFolder, srcFile.stem.encode("ascii", "ignore").decode()).with_suffix(".png")
    cmd[1] = str(srcFile)
    cmd[3] = str(newFileName)

    log.info(f"Export started with command '{' '.join(cmd)}'")

    #call CSLMapview.exe to export the image. Try again at fail, abort after many tries.
    for n in range(retry):
        try:
            #Call the program in a separate process
            subprocess.run(cmd, shell = False, stderr = subprocess.DEVNULL, stdout = subprocess.DEVNULL, check = False)

            #Return prematurely on abort
            #Needs to be after export command, otherwise won't work. Probably dead Lock.
            if abortEvent is not None:
                if abortEvent.is_set():
                    raise AbortException("Abort initiated on another thread.")

            #Ensure that the image file was successfully created. 
            assert newFileName.exists()
            
            log.info(f"Successfully exported file '{newFileName}' after {n+1} attempts.")
            return str(newFileName)
        except AbortException as error:
            log.exception(f"Aborted while exporting file '{newFileName}'.")
            raise AbortException from error
        except subprocess.CalledProcessError as e:
            log.warning(f"Process error while exporting file '{newFileName}'.")
            pass
        except AssertionError as e:
            log.warning(f"File '{newFileName}' does not exist after exporting.")
            pass
        except Exception as e:
            log.warning(f"Unknown exception while exporting file '{newFileName}'.")
            pass

    log.warning(f"Failed to export file after {retry} attempts with command '{' '.join(cmd)}'")

    #Throw exception after repeatedly failing
    raise ExportError(str('Could not export file.\nCommand: "'
        + ' '.join(cmd)
        + '"\nThis problem can arise normally, usually when resources are taken.'))


def timeStamp() -> str:
    """Return a timestamp in format hhmmss."""
    return str(datetime.now()).split(" ")[-1].split(".")[0].replace(":", "")


def resourcePath(relativePath: str) -> Path:
    """
    Get absolute path to resource, works for dev and for PyInstaller.

    source: https://stackoverflow.com/a/13790741/19634396
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent.resolve()
    return Path(base_path, relativePath)


def roundToTwoDecimals(var: tkinter.StringVar) -> None:
    """Round the decimal in var to 2 decimal places."""
    var.set(str(round(float(var.get()), 2)))


class CSLapse():
    """Class containing details of the CSLapse GUI application."""

    def null(self, * args: Any, ** kwargs: Any) -> None:
        """Placeholder function, do nothing."""
        pass        

    def clearTempFolder(self) -> None:
        """
        Remove the all files from self.tempFolder, create Directory if doesn't exist.

        If tempFolder is None, or doesnt exist, create the folder and return.
        If a file can not be removed, show a warning.
        If an other issue comes up: 
        """
        while 1:
            try:
                with self.lock:
                    if self.tempFolder.exists():
                        rmtree(self.tempFolder, ignore_errors = False)
                    self.tempFolder.mkdir()
                self.log.info("Tempfolder cleared or created successfully.")
                return
            except Exception as e:
                self.log.exception("Error while clearing / creating tempFolder.")
                self.gui.askFatalError(str(e))

    def openFile(self, title: str, filetypes: List[Tuple], defDir: str = None) -> str:
        """Open file opening dialog box and return the full path to the selected file."""
        filename = filedialog.askopenfilename(title = title, initialdir = defDir, filetypes = filetypes)
        self.log.info(f"File '{filename}' selected.")
        return filename
        
    def setSampleFile(self, sampleFile: str) -> None:
        """Store city name and location of the sample file."""
        sampleFile = Path(sampleFile)
        self.sourceDir = sampleFile.parent
        self.cityName = sampleFile.stem.split("-")[0]
        self.tempFolder = Path(self.sourceDir, f"temp{self.timestamp}")
        self.clearTempFolder()

    def collectRawFiles(self) -> List[Path]:
        """Make an array of files whose name matches the city's name."""
        return sorted(
            filter(
                lambda filename: filename.name.startswith(self.cityName) and ".cslmap" in filename.suffixes, 
                self.sourceDir.iterdir()
            ))

    def exportSample(self, sample: str, retry: int) -> None:
        """
        Export png from the cslmap file that will be the given frame of the video.

        This function should run on a separate thread.
        
        Exceptions:
            AbortException gets propagated
            ExportError: non-fatal
            Other exceptions: non-fatal
        """
        while 1:
            try:
                exported = exportFile(
                    sample, 
                    self.tempFolder, 
                    self.collections["sampleCommand"],
                    1,
                    self.abortEvent
                    ) 
                with self.lock:
                    self.vars["previewSource"] = Image.open(exported)
                self.previewLoadedEvent.set()
                return
            except AbortException:
                #logging handled in exportfile
                self.previewLoadErrorEvent.set()
                return
            except ExportError as e:
                if not self.gui.askNonFatalError(str(e)):
                    self.previewLoadErrorEvent.set()
                    self.log.exception(f"Returning after failed export of sample file '{sample}'")
                    return
            except Exception as e:
                if not self.gui.askNonFatalError(str(e)):
                    self.previewLoadErrorEvent.set()
                    self.log.exception(f"Returning after failed export due to unnown exception of sample file '{sample}'")
                    return

    def refreshPreview(self, manual: bool = False) -> None:
        """Export the preview CSLMap file with current settings."""
        if self.vars["exeFile"].get() == constants["noFileText"]:
            if manual:
                self.gui.showWarning(title = "Warning", message = constants["texts"]["noExeMessage"])
            return
        if self.vars["sampleFile"].get() == constants["noFileText"]:
            if manual:
                self.gui.showWarning(title = "Warning", message = constants["texts"]["noSampleMessage"])
            return
        if self.vars["videoLength"].get() > len(self.rawFiles):
            if manual:
                self.gui.showWarning(title = "Warning", message = "Not enough files to match video frames!")
            return
        self.gui.setGUI("previewLoading")
        self.collections["sampleCommand"][6] = str(self.vars["width"].get())
        self.collections["sampleCommand"][8] = str(self.vars["areas"].get())

        self.log.info("Refreshing preview started.")
        exporter = threading.Thread(
            target = self.exportSample,
            args = (
                self.rawFiles[self.vars["videoLength"].get()-1],
                self.vars["retry"].get()
            )
        )
        exporter.start()

    def openSample(self, title: str) -> None:
        """Select sample file from dialog and set variables accordingly."""
        selectedFile = self.openFile(title, self.filetypes["cslmap"], self.sourceDir)
        if not selectedFile == "" and not selectedFile == self.vars["sampleFile"].get():
            self.vars["sampleFile"].set(selectedFile)
            self.setSampleFile(self.vars["sampleFile"].get())
            self.rawFiles = self.collectRawFiles()
            self.vars["numOfFiles"].set(len(self.rawFiles))
            if self.vars["videoLength"].get() == 0:
                self.vars["videoLength"].set(self.vars["numOfFiles"].get())
            else:
                self.vars["videoLength"].set(min(self.vars["videoLength"].get(), self.vars["numOfFiles"].get()))
            self.refreshPreview()
        else:
            self.vars["sampleFile"].set(constants["noFileText"])

    def openExe(self, title: str) -> None:
        """Select SCLMapViewer.exe from dialog and set variables accordingly."""
        selectedFile = self.openFile(title, self.filetypes["exe"], self.sourceDir)
        if not selectedFile == "":
            self.vars["exeFile"].set(selectedFile)
            self.collections["sampleCommand"][0] = self.vars["exeFile"].get()
            self.refreshPreview()
        else:
            self.vars["exeFile"].set(constants["noFileText"])

    def exportImageOnThread(self, srcFile: str, cmd: List[str]) -> None:
        """Call the given command to export the given image, add filename to self.imageFiles.
        
        This function should run on a separate thread for each file.

        Exceptions:
            AbortException: propagate
            ExportError: non-fatal
            Other exceptions: non-fatal
        """
        while True:
            try:
                newFileName = exportFile(srcFile, self.tempFolder, cmd, int(self.vars["retry"].get()), self.abortEvent)
                break
            except AbortException as e:
                raise AbortException from e
            except ExportError as e:
                if not self.gui.askNonFatalError(str(e)):
                    self.log.exception(f"Skipping file '{srcFile}' after too many unsuccessful attempts.")
                    return
                self.log.info(f"Retrying to export '{srcFile}' after too many unsuccessful attempts.")
            except Exception as e:
                if not self.gui.askNonFatalError(str(e)):
                    self.log.exception(f"Skipping file '{srcFile}' after unknown exception.")
                    return
                self.log.info(f"Retrying to export '{srcFile}' after unknown exception.")
        with self.lock:
            self.imageFiles.append(newFileName)
            self.vars["exportingDone"].set(self.vars["exportingDone"].get() + 1)
        return

    def export(self) -> None:
        """Handle the export process."""
        if self.isRunning or self.isAborting:
            self.gui.showWarning("An export operation is already running.")
            return
        self.prepare()
        threading.Thread(target = self.run, daemon = True).start()

    def prepare(self) -> None:
        """Prepare variables and environment for exporting."""
        self.isRunning = True
        self.isAborting = False
        self.abortEvent.clear()
        self.clearTempFolder()
        self.imageFiles = []
        self.futures = []
        self.gui.setGUI("startExport")
        self.log.info("Exporting process started.")

    def run(self) -> None:
        """Export images and create video from them.
        
        Exceptions:
            Starting second export: warning
            AbortException: return
        """
        try:
            self.log.info("Exporting image files started.")
            self.exportImageFiles()
            self.log.info("Exporting image files finished.")
            self.imageFilesExportedEvent.set()
            self.gui.setGUI("startRender")
            self.log.info("Rendering video started.")
            self.renderVideo()
            self.log.info("Rendering video finished.")
            self.exportingDoneEvent.set()
        except AbortException as e:
            self.abortEvent.set()
            self.log.exception("Aborting export process due to AbortException")
            return

    def exportImageFiles(self) -> None:
        """Call CSLMapView to export the collected cslmap files one-by-one on separate threads.
        
        Exceptions:
            Raise AbortException if abort is requested
        """
        limit = self.vars["videoLength"].get()        
        cmd = [
            self.vars["exeFile"].get(),
            "__srcFile__",
            "-output",
            "__outFile__",
            "-silent",
            "-imagewidth",
            str(self.vars["width"].get()),
            "-area",
            str(self.vars["areas"].get())
            ]

        with concurrent.futures.ThreadPoolExecutor(self.vars["threads"].get()) as executor:
            for i in range(limit):
                self.futures.append(
                    executor.submit(self.exportImageOnThread, self.rawFiles[i], cmd[:])
                )
        if self.abortEvent.is_set():
            raise AbortException("Abort initiated on another thread.")

        #Sort array as the order might have changed during threading
        self.imageFiles = sorted(self.imageFiles)
        
    def renderVideo(self) -> None:
        """Create an mp4 video file from all the exported images.
        
        Exceptions:
            Raise AbortException if abort is requested
            AbortException: propagate
            Cannot open video file: raise AbortException
            Cannot add image to video: non-fatal
        """

        self.outFile = str(Path(self.sourceDir, f'{self.cityName.encode("ascii", "ignore").decode()}-{timeStamp()}.mp4'))
        while True:
            try:
                out = cv2.VideoWriter(
                    self.outFile,
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    int(self.vars["fps"].get()),
                    (int(self.vars["width"].get()), int(self.vars["width"].get()))
                    )
                break
            except AbortException as e:
                self.log.exception("Aborted rendering video due to AbortException.")
                raise AbortException from e
            except Exception as e:
                if not self.gui.askAbortingError(str(e)):
                    self.log.exception("Aborted rendering video due to ubnknown Exception.")
                    self.gui.root.event_generate('<<Abort>>', when = "tail")
                    raise AbortException("Aborted due to unresolved aborting error.") from e
                else:
                    self.log.warning("Continuing rendering video after unknown Exception.")

        try:
            i = 0
            while i < len(self.imageFiles):
                if self.abortEvent.is_set():
                    raise AbortException("Abort initiated on another thread.")
                try:
                    img = cv2.imread(self.imageFiles[i])
                    out.write(img)
                    with self.lock:
                        self.vars["renderingDone"].set(self.vars["renderingDone"].get()+ 1)
                    i += 1
                except AbortException as e:
                    self.log.exception("Aborted rendering video due to AbortException.")
                    raise AbortException from e
                except cv2.error as e:
                    #For some reason it still cannot catch cv2 errors
                    if not self.gui.askNonFatalError(str(e)):
                        i += 1
                        self.log.exception(f"Skipping image '{self.imageFiles[i]}' after cv2 Exception.")
                    else:
                        self.log.warning(f"Retrying adding image '{self.imageFiles[i]}' to video after cv2 Exception.")
                except Exception as e:
                    if not self.gui.askNonFatalError(str(e)):
                        i += 1
                        self.log.warning(f"Skipping image '{self.imageFiles[i]}' after unknow Exception.")
                    else:
                        self.log.warning(f"Retrying adding image '{self.imageFiles[i]}' to video after unknown Exception.")
        except AbortException as e:
            self.log.exception("Aborted rendering video due to AbortException.")
            raise AbortException from e
        finally:
            out.release()
            self.log.info(f"Released video file '{self.outFile}'")

    def abort(self, event: tkinter.Event = None) -> None:
        """Stop currently running export process.
        
        If called on the main thread, collect all running threads.
        Otherwise raise an exception.

        Impossible to recover state afterwards.
        """
        if self.isAborting or not self.isRunning :
            self.gui.showWarning(constants["texts"]["abortAlreadyRunning"])
            self.abortEvent.clear()
            return

        if threading.current_thread() is not threading.main_thread():
            raise AbortException("Abort initiated.")
        else:
            self.isAborting = True
            self.isRunning = False
            self.gui.setGUI("aborting")

            self.log.info("Abort procedure started on main thread.")

            self.vars["threadCollecting"].set(0)
            collector = ThreadCollector([threading.current_thread()], self.futures, counter = self.vars["threadCollecting"], callback=self.abortFinishedEvent.set)
            self.gui.progressPopup(self.vars["threadCollecting"], collector.total())
            collector.start()

    def cleanupAfterSuccess(self) -> None:
        """Clean up variables and environment after successful exporting."""
        self.clearTempFolder()
        self.imageFiles = []
        self.futures = []
        self.isRunning = False
        self.log.info("Successful cleanup after successful export.")

    def cleanupAfterAbort(self) -> None:
        """Clean up variables and environment after aborted exporting."""
        self.clearTempFolder()
        self.imageFiles = []
        self.futures = []
        self.gui.setGUI("afterAbort")
        self.abortEvent.clear()
        self.isAborting = False
        self.log.info("Successful cleanup after aborted export.")
        if self.exitEvent.is_set():
            self.gui.root.destroy()
            self.log.info("Exiting after aborted export.")

    def _resetState(self) -> None:
        """Set all variables to the default state."""
        self.sourceDir = None
        self.cityName = None
        self.tempFolder = None
        self.rawFiles = []
        self.imageFiles = []
        self.isRunning = False
        self.outFile = ""

        self.vars["exeFile"].set(constants["noFileText"])
        self.vars["sampleFile"].set(constants["noFileText"])
        self.vars["numOfFiles"].set(0)
        self.vars["fps"].set(constants["defaultFPS"])
        self.vars["width"].set(constants["defaultExportWidth"])
        self.vars["threads"].set(constants["defaultThreads"])
        self.vars["rotation"].set(constants["rotaOptions"][0])
        self.vars["areas"].set(constants["defaultAreas"])
        self.vars["videoLength"].set(0)
        self.vars["exportingDone"].set(0)
        self.vars["renderingDone"].set(0)
    
    def checkThreadEvents(self) -> None:
        """Check if the threading events are set, repeat after 100 ms."""
        if self.previewLoadedEvent.is_set():
            self.previewLoadedEvent.clear()
            self.gui.preview.justExported()
            self.gui.setGUI("previewLoaded")
        if self.previewLoadErrorEvent.is_set():
            self.previewLoadErrorEvent.clear()
            self.gui.setGUI("previewLoadError")
        if self.abortEvent.is_set():
            if not self.isAborting:
                self.abort()
        if self.threadsCollectedEvent.is_set():
            self.threadsCollectedEvent.clear()
            self.gui.setGUI("defaultState")
        if self.imageFilesExportedEvent.is_set():
            self.imageFilesExportedEvent.clear()
            self.gui.setGUI("startRender")
        if self.exportingDoneEvent.is_set():
            self.exportingDoneEvent.clear()
            self.cleanupAfterSuccess()
            self.gui.showInfo(f"See your timelapse at {self.outFile}", "Video completed")
            self.gui.setGUI("renderDone")
            self.isRunning = False
        if self.abortFinishedEvent.is_set():
            self.abortFinishedEvent.clear()
            self.cleanupAfterAbort()
        self.gui.root.after(100, self.checkThreadEvents)

    def __init__(self):
        self.timestamp = timeStamp()
        self.lock = threading.Lock()
        self.log = logging.getLogger("cslapse")
        self.gui = CSLapse.GUI(self)

        self.abortEvent = threading.Event()
        self.abortEvent.clear()
        self.previewLoadedEvent = threading.Event()
        self.previewLoadedEvent.clear()
        self.previewLoadErrorEvent = threading.Event()
        self.previewLoadErrorEvent.clear()
        self.threadsCollectedEvent = threading.Event()
        self.threadsCollectedEvent.clear()
        self.imageFilesExportedEvent = threading.Event()
        self.imageFilesExportedEvent.clear()
        self.exportingDoneEvent = threading.Event()
        self.exportingDoneEvent.clear()
        self.abortFinishedEvent = threading.Event()
        self.abortFinishedEvent.clear()
        self.exitEvent = threading.Event()
        self.exitEvent.clear()

        self.vars = {
            "exeFile":tkinter.StringVar(value = constants["noFileText"]),
            "sampleFile":tkinter.StringVar(value = constants["noFileText"]),
            "numOfFiles":tkinter.IntVar(value = 0),
            "fps":tkinter.IntVar(value = constants["defaultFPS"]),
            "width":tkinter.IntVar(value = constants["defaultExportWidth"]),
            "threads":tkinter.IntVar(value = constants["defaultThreads"]),
            "retry":tkinter.IntVar(value = constants["defaultRetry"]),
            "rotation":tkinter.StringVar(value = constants["rotaOptions"][0]),
            "areas":tkinter.StringVar(value = constants["defaultAreas"]),
            "videoLength":tkinter.IntVar(value = 0),
            "exportingDone":tkinter.IntVar(value = 0),
            "renderingDone":tkinter.IntVar(value = 0),
            "threadCollecting":tkinter.IntVar(value = 0),
            "previewSource":"",
            "previewImage":""
        }
        
        self.sourceDir = None # Path type, the directory where cslmap files are loaded from
        self.cityName = None # string, the name of the city
        self.tempFolder = None # Path type, the location where temporary files are created
        self.rawFiles = []    # Collected cslmap files with matching city name
        self.imageFiles = []
        self.futures = []   # concurrent.futures.Future objects that are exporting images
        self.isRunning = False # If currently there is exporting going on
        self.isAborting = False # If an abort pre=ocess is in progress
        self.outFile = "" # Name of output file

        self.filetypes = {
            "exe":[("Executables", "*.exe"), ("All files", "*")],
            "cslmap":[("CSLMap files", ("*.cslmap", "*.cslmap.gz")), ("All files", "*")]
        }

        self.collections = {
            "sampleCommand":["__exeFile__", "__srcFile__", "-output", "__outFile__", "-silent", "-imagewidth", str(constants["sampleExportWidth"]), "-area", str(constants["defaultAreas"])]
        }

        self._resetState()
        self.gui.configureWindow()
        self.gui.setGUI("defaultState")
        self.gui.root.after(0, self.checkThreadEvents)

        self.log.info("CSLapse object initiated.")

    def __enter__(self) -> object:
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up after the object"""
        if self.tempFolder is not None and self.tempFolder.exists():
            rmtree(self.tempFolder, ignore_errors = True)
        collector = ThreadCollector([threading.current_thread()], counter = self.vars["threadCollecting"])
        collector.start()
        self.log.info("Cleanup after object done")
    
    class GUI(object):
        """Object that contains the GUI elements and methods of the program."""

        def _createMainFrame(self, cb, vars, filetypes, texts) -> None:
            """Create the widgets in the left main window"""
            self.mainFrame = ttk.Frame(self.root)
            self.fileSelectionBox = ttk.Labelframe(self.mainFrame, text = "Files")
            self.exeSelectLabel = ttk.Label(self.fileSelectionBox, text = "Path to CSLMapViewer.exe")
            self.exePath = ttk.Entry(self.fileSelectionBox, width = 40, state = ["readonly"], textvariable = vars["exeFile"], cursor = constants["clickable"])
            self.exeSelectBtn = ttk.Button(self.fileSelectionBox, text = "Select file", cursor = constants["clickable"], command = cb["openExe"])
            self.sampleSelectLabel = ttk.Label(self.fileSelectionBox, text = "Select a cslmap file of your city")
            self.samplePath = ttk.Entry(self.fileSelectionBox, state = ["readonly"], textvariable = vars["sampleFile"], cursor = constants["clickable"])
            self.sampleSelectBtn = ttk.Button(self.fileSelectionBox, text = "Select file", cursor = constants["clickable"], command = cb["openSample"])
            self.filesLoading = ttk.Progressbar(self.fileSelectionBox)
            self.filesNumLabel = ttk.Label(self.fileSelectionBox, textvariable = vars["numOfFiles"])
            self.filesLoadedLabel = ttk.Label(self.fileSelectionBox, text = "files found")

            self.videoSettingsBox = ttk.Labelframe(self.mainFrame, text = "Video settings")
            self.fpsLabel = ttk.Label(self.videoSettingsBox, text = "Frames per second: ")
            self.fpsEntry = ttk.Entry(self.videoSettingsBox, width = 7, textvariable = vars["fps"])
            self.imageWidthLabel = ttk.Label(self.videoSettingsBox, text = "Width:")
            self.imageWidthInput = ttk.Entry(self.videoSettingsBox, width = 7, textvariable = vars["width"])
            self.imageWidthUnit = ttk.Label(self.videoSettingsBox, text = "pixels")
            self.lengthLabel = ttk.Label(self.videoSettingsBox, text = "Video length:")
            self.lengthInput = ttk.Entry(self.videoSettingsBox, width = 7, textvariable = vars["videoLength"])
            self.lengthUnit = ttk.Label(self.videoSettingsBox, text = "frames")

            self.advancedSettingBox = ttk.Labelframe(self.mainFrame, text = "Advanced")
            self.threadsLabel = ttk.Label(self.advancedSettingBox, text = "Threads:")
            self.threadsEntry = ttk.Entry(self.advancedSettingBox, width = 5, textvariable = vars["threads"])
            self.retryLabel = ttk.Label(self.advancedSettingBox, text = "Fail after:")
            self.retryEntry = ttk.Entry(self.advancedSettingBox, width = 5, textvariable = vars["retry"])

            self.progressFrame = ttk.Frame(self.mainFrame)
            self.exportingLabel = ttk.Label(self.progressFrame, text = "Exporting files:")
            self.exportingDoneLabel = ttk.Label(self.progressFrame, textvariable = vars["exportingDone"])
            self.exportingOfLabel = ttk.Label(self.progressFrame, text = " of ")
            self.exportingTotalLabel = ttk.Label(self.progressFrame, textvariable = vars["videoLength"])
            self.exportingProgress = ttk.Progressbar(self.progressFrame, orient = "horizontal", mode = "determinate", variable = vars["exportingDone"])
            self.renderingLabel = ttk.Label(self.progressFrame, text = "Renderig video:")
            self.renderingDoneLabel = ttk.Label(self.progressFrame, textvariable = vars["renderingDone"])
            self.renderingOfLabel = ttk.Label(self.progressFrame, text = " of ")
            self.renderingTotalLabel = ttk.Label(self.progressFrame)
            self.renderingProgress = ttk.Progressbar(self.progressFrame, orient = "horizontal", mode = "determinate", variable = vars["renderingDone"])

            self.submitBtn = ttk.Button(self.mainFrame, text = "Export", cursor = constants["clickable"], command = cb["submit"])
            self.abortBtn = ttk.Button(self.mainFrame, text = "Abort", cursor = constants["clickable"], command = cb["abort"])

        def _createPreviewFrame(self, cb, vars) -> None:
            """Create widgets related to the preview canvas, initialize Preview object"""

            self.previewFrame = ttk.Frame(self.root)

            self.canvasFrame = ttk.Frame(self.previewFrame, relief = tkinter.SUNKEN, borderwidth = 2)
            self.preview = Preview(self, self.previewFrame)
            self.refreshPreviewBtn = ttk.Button(self.preview.canvas, text = "Refresh", cursor = constants["clickable"],
                command = lambda:cb["refreshPreview"]())
            self.fitToCanvasBtn = ttk.Button(self.preview.canvas, text = "Fit", cursor = constants["clickable"],
                command = self.preview.fitToCanvas)
            self.originalSizeBtn = ttk.Button(self.preview.canvas, text = "100%", cursor = constants["clickable"],
                command = self.preview.scaleToOriginal)

            self.canvasSettingFrame = ttk.Frame(self.previewFrame)
            self.zoomLabel = ttk.Label(self.canvasSettingFrame, text = "Areas:")
            self.zoomEntry = ttk.Spinbox(self.canvasSettingFrame, width = 5, textvariable = vars["areas"], from_ = 0.1, increment = 0.1, to = 9.0, wrap = False, validatecommand = (cb["areasChanged"], "%d", "%P"), validate = "all", command = lambda: self.preview.update_printarea(float(vars["areas"].get())))
            self.zoomSlider = ttk.Scale(self.canvasSettingFrame, orient = tkinter.HORIZONTAL, from_ = 0.1, to = 9.0, variable = vars["areas"], cursor = constants["clickable"], command = lambda _: self.preview.update_printarea(float(vars["areas"].get())))

            self.rotationLabel = ttk.Label(self.canvasSettingFrame, text = "Rotation:")
            self.rotationSelection = ttk.Menubutton(self.canvasSettingFrame, textvariable = vars["rotation"], cursor = constants["clickable"])
            self.rotationSelection.menu = tkinter.Menu(self.rotationSelection, tearoff = 0)
            self.rotationSelection["menu"] = self.rotationSelection.menu
            for option in constants["rotaOptions"]:
                self.rotationSelection.menu.add_radiobutton(label = option, variable = vars["rotation"])

        def _gridMainFrame(self) -> None:
            """Add main widgets to the grid"""
            self.mainFrame.grid(column = 0, row = 0, sticky = tkinter.NSEW, padx = 2, pady = 5)

            self.fileSelectionBox.grid(column = 0, row = 0, sticky = tkinter.EW, padx = 2, pady = 5)
            self.exeSelectLabel.grid(column = 0, row = 0, columnspan = 3, sticky = tkinter.EW)
            self.exePath.grid(column = 0, row = 1, columnspan = 2, sticky = tkinter.EW)
            self.exeSelectBtn.grid(column = 2, row = 1)
            self.sampleSelectLabel.grid(column = 0, row = 2, columnspan = 3, sticky = tkinter.EW)
            self.samplePath.grid(column = 0, row = 3, columnspan = 2, sticky = tkinter.EW)
            self.sampleSelectBtn.grid(column = 2, row = 3)
            self.filesNumLabel.grid(column = 0, row = 4, sticky = tkinter.W)
            self.filesLoadedLabel.grid(column = 1, row = 4, sticky = tkinter.W)

            self.videoSettingsBox.grid(column = 0, row = 1, sticky = tkinter.EW, padx = 2, pady = 10)
            self.fpsLabel.grid(column = 0, row = 0, sticky = tkinter.W)
            self.fpsEntry.grid(column = 1, row = 0, sticky = tkinter.EW)
            self.imageWidthLabel.grid(column = 0, row = 1, sticky = tkinter.W)
            self.imageWidthInput.grid(column = 1, row = 1, sticky = tkinter.EW)
            self.imageWidthUnit.grid(column = 2, row = 1, sticky = tkinter.W)
            self.lengthLabel.grid(column = 0, row = 2, sticky = tkinter.W)
            self.lengthInput.grid(column = 1, row = 2, sticky = tkinter.W)
            self.lengthUnit.grid(column = 2, row = 2, sticky = tkinter.W)

            self.advancedSettingBox.grid(column = 0, row = 2, sticky = tkinter.EW, padx = 2, pady = 5)
            self.threadsLabel.grid(column = 0, row = 0, sticky = tkinter.W)
            self.threadsEntry.grid(column = 1, row = 0, sticky = tkinter.EW)
            self.retryLabel.grid(column = 0, row = 1, sticky = tkinter.W)
            self.retryEntry.grid(column = 1, row = 1, sticky = tkinter.EW)

            self.progressFrame.grid(column = 0, row = 9, sticky = tkinter.EW)
            self.exportingLabel.grid(column = 0, row = 0)
            self.exportingDoneLabel.grid(column = 1, row = 0)
            self.exportingOfLabel.grid(column = 2, row = 0)
            self.exportingTotalLabel.grid(column = 3, row = 0)
            self.exportingProgress.grid(column = 0, row = 1, columnspan = 5, sticky = tkinter.EW)

            self.renderingLabel.grid(column = 0, row = 2)
            self.renderingDoneLabel.grid(column = 1, row = 2)
            self.renderingOfLabel.grid(column = 2, row = 2)
            self.renderingTotalLabel.grid(column = 3, row = 2)
            self.renderingProgress.grid(column = 0, row = 3, columnspan = 5, sticky = tkinter.EW)

            self.submitBtn.grid(column = 0, row = 10, sticky = (tkinter.S, tkinter.E, tkinter.W))
            self.abortBtn.grid(column = 0, row = 11, sticky = (tkinter.S, tkinter.E, tkinter.W))

        def _gridPreviewFrame(self) -> None:
            """Add widgets related to preview to the grid"""

            self.previewFrame.grid(column = 20, row = 0, sticky = tkinter.NSEW)

            self.canvasFrame.grid(column = 0, row = 0, sticky = tkinter.NSEW)
            self.preview.canvas.grid(column = 0, row = 0, sticky = tkinter.NSEW)
            self.refreshPreviewBtn.grid(column = 1, row = 0, sticky = tkinter.NE)
            self.fitToCanvasBtn.grid(column = 1, row = 2, sticky = tkinter.SE)
            self.originalSizeBtn.grid(column = 1, row = 3, sticky = tkinter.SE)

            self.canvasSettingFrame.grid(column = 0, row = 1, sticky = tkinter.NSEW)
            self.zoomLabel.grid(column = 0, row = 0, sticky = tkinter.W)
            self.zoomEntry.grid(column = 1, row = 0, sticky = tkinter.W)
            self.zoomSlider.grid(column = 2, row = 0, sticky = tkinter.EW)

            #Functionality not implemented yet
            #self.rotationLabel.grid(column = 0, row = 1, columnspan = 3, sticky = tkinter.W)
            #self.rotationSelection.grid(column = 1, row = 1, columnspan = 2, sticky = tkinter.W)

        def registerCallbacks(self) -> None:
            
            self.callBacks = {
                "openExe":self.selectExe,
                "openSample":self.selectSample,
                "fpsChanged":self.external.null,
                "videoWidthChanged":self.external.null,
                "threadsChanged":self.external.null,
                "areasChanged": self.root.register(self.validateAreas),
                "areasSliderChanged":roundToTwoDecimals,
                "submit": self.submitPressed,
                "abort":self.abortPressed,
                "refreshPreview":self.refreshPressed
            }

        def validateAreas(self, action, newText) -> bool:
            if action == "0":
                return True
            try:
                number = float(newText)
                if number >= 0.1 and number <= 9.0:
                    self.preview.update_printarea(number)
                    return True
                return False
            except Exception:
                return False

        def _applyToTree(self, root: tkinter.Widget, callback: Callable[[tkinter.Widget],None]) -> None:
            """Call callback for every widget in the tree whose origin is root."""
            callback(root)
            for child in root.winfo_children():
                self._applyToTree(child, callback)

        def _defaultConfiguration(self, widget: tkinter.Widget) -> None:
            """Configure widget with default options set in this place."""
            style=ttk.Style()

            try:
                widget.configure(background = "white")
            except Exception:
                pass

        def _configure(self) -> None:
            """Configure widgets."""
            self.root.columnconfigure(20, weight = 1)
            self.root.rowconfigure(0, weight = 1)
            self.root.configure(padx = 2, pady = 2)

            self.mainFrame.rowconfigure(8, weight = 1)
            self.fileSelectionBox.columnconfigure(1, weight = 1)
            self.progressFrame.columnconfigure(4, weight = 1)

            self.previewFrame.columnconfigure(0, weight = 1)
            self.previewFrame.rowconfigure(0, weight = 1)
            self.canvasFrame.columnconfigure(0, weight = 1)
            self.canvasFrame.rowconfigure(0, weight = 1)
            self.preview.canvas.columnconfigure(0, weight = 1)
            self.preview.canvas.rowconfigure(1, weight = 1)
            self.canvasSettingFrame.columnconfigure(2, weight = 1)

            self.preview.canvas.configure(background = "white")

            self._createBindings()

        def _createStyles(self) -> None:
            """Create ttk styles. Not used."""
            s = ttk.Style()

        def _createBindings(self) -> None:
            """Bind events to GUI widgets"""
            self.preview.createBindings()
            self.root.event_add('<<Abort>>', '<Control-C>')
            self.root.bind('<<Abort>>', lambda event: self.external.abortEvent.set())
            self.root.protocol("WM_DELETE_WINDOW", self.closePressed)
            self.exePath.bind('<ButtonPress-1>', lambda event: self.selectExe())
            self.samplePath.bind('<ButtonPress-1>', lambda event: self.selectSample())

        def _enable(self, * args: tkinter.Widget) -> None:
            """Set all argument widgets to enabled"""
            for widget in args:
                widget.state(["!disabled"])

        def _disable(self, * args: tkinter.Widget) -> None:
            """Set all argument widgets to disabled"""
            for widget in args:
                widget.state(["disabled"])

        def _show(self, * args: tkinter.Widget) -> None:
            """Show all argument widgets"""
            for widget in args:
                widget.grid()

        def _hide(self, * args: tkinter.Widget) -> None:
            """Hide all argument widgets"""
            for widget in args:
                widget.grid_remove()

        def setGUI(self, state: str) -> None:
            """
            Set the GUI to a predefined state.
            
            This sets the GUI variables and widgets.
            state should be one of ["startExport", "startRender", "renderDone", "defaultState"] and more.
            """
            if state == "startExport":
                self.external.vars["exportingDone"].set(0)
                self.exportingProgress.config(maximum = self.external.vars["videoLength"].get())
                self._disable(
                    self.exeSelectBtn, 
                    self.sampleSelectBtn, 
                    self.fpsEntry, 
                    self.imageWidthInput, 
                    self.lengthInput, 
                    self.threadsEntry,
                    self.retryEntry,
                    self.zoomSlider, 
                    self.zoomEntry
                )
                self._enable(self.abortBtn)
                self._hide(
                    self.submitBtn, 
                    self.renderingProgress,
                    self.renderingLabel, 
                    self.renderingDoneLabel, 
                    self.renderingOfLabel, 
                    self.renderingTotalLabel
                )
                self._show(
                    self.progressFrame, 
                    self.exportingProgress, 
                    self.exportingLabel,
                    self.exportingDoneLabel, 
                    self.exportingOfLabel, 
                    self.exportingTotalLabel, 
                    self.abortBtn
                )
            elif state == "startRender":
                self.external.vars["renderingDone"].set(0)
                self.renderingTotalLabel.configure(text = len(self.external.imageFiles))
                self.renderingProgress.config(maximum = len(self.external.imageFiles))
                self._disable(
                    self.exeSelectBtn,
                    self.sampleSelectBtn,
                    self.fpsEntry, 
                    self.imageWidthInput,
                    self.lengthInput, 
                    self.threadsEntry, 
                    self.retryEntry, 
                    self.zoomSlider, 
                    self.zoomEntry
                )
                self._enable(self.abortBtn)
                self._hide(
                    self.submitBtn, 
                    self.exportingProgress, 
                    self.exportingLabel, 
                    self.exportingDoneLabel,
                    self.exportingOfLabel,
                    self.exportingTotalLabel
                )
                self._show(
                    self.progressFrame,
                    self.renderingProgress,
                    self.renderingLabel,
                    self.renderingDoneLabel,
                    self.renderingOfLabel,
                    self.renderingTotalLabel
                )
            elif state == "renderDone":
                self._disable(self.abortBtn)
                self._enable(
                    self.exeSelectBtn,
                    self.sampleSelectBtn,
                    self.fpsEntry,
                    self.imageWidthInput,
                    self.lengthInput,
                    self.threadsEntry,
                    self.retryEntry,
                    self.zoomSlider,
                    self.zoomEntry
                )
                self._show(self.submitBtn)
                self._hide(
                    self.progressFrame,
                    self.abortBtn
                )
            elif state == "defaultState":
                for p in self.popups:
                    p.destroy()
                self._disable(
                    self.progressFrame,
                    self.abortBtn, 
                    self.fitToCanvasBtn, 
                    self.originalSizeBtn
                )
                self._enable(
                    self.submitBtn, 
                    self.exeSelectBtn, 
                    self.sampleSelectBtn, 
                    self.fpsEntry, 
                    self.imageWidthInput, 
                    self.lengthInput, 
                    self.threadsEntry, 
                    self.retryEntry, 
                    self.zoomSlider, 
                    self.zoomEntry, 
                    self.rotationSelection
                )
                self._hide(
                    self.progressFrame,
                    self.abortBtn,
                    self.refreshPreviewBtn,
                    self.fitToCanvasBtn,
                    self.originalSizeBtn
                )
                self._show(self.submitBtn)
            elif state == "previewLoading":
                self._disable(
                    self.refreshPreviewBtn,
                    self.fitToCanvasBtn,
                    self.originalSizeBtn
                )
                #TODO: Add loading image to canvas
                #TODO: Add loading image to refresh button
                self.preview.canvas.configure(cursor = "watch")
            elif state == "previewLoaded":
                self._enable(
                    self.refreshPreviewBtn,
                    self.fitToCanvasBtn,
                    self.originalSizeBtn
                )
                self._show(
                    self.refreshPreviewBtn,
                    self.fitToCanvasBtn,
                    self.originalSizeBtn
                )
                self.preview.canvas.configure(cursor = constants["previewCursor"])
            elif state == "previewLoadError":
                self._enable(self.refreshPreviewBtn)
                self._show(self.refreshPreviewBtn)
                self.preview.canvas.configure(cursor = "")
            elif state == "aborting":
                self._disable(
                    self.exeSelectBtn,
                    self.sampleSelectBtn,
                    self.fpsEntry, 
                    self.imageWidthInput, 
                    self.lengthInput, 
                    self.threadsEntry, 
                    self.retryEntry,
                    self.zoomSlider, 
                    self.zoomEntry, 
                    self.abortBtn, 
                    self.fitToCanvasBtn, 
                    self.originalSizeBtn, 
                    self.refreshPreviewBtn
                )
                self.root.configure(cursor = constants["previewCursor"])
            elif state == "afterAbort":
                for p in self.popups:
                    p.destroy()
                self._disable(self.abortBtn)
                self._enable(
                    self.exeSelectBtn,
                    self.sampleSelectBtn,
                    self.fpsEntry, 
                    self.imageWidthInput, 
                    self.lengthInput, 
                    self.threadsEntry, 
                    self.retryEntry,
                    self.zoomSlider, 
                    self.zoomEntry, 
                    self.abortBtn, 
                    self.fitToCanvasBtn, 
                    self.originalSizeBtn, 
                    self.refreshPreviewBtn
                )
                self._hide(
                    self.progressFrame,
                    self.abortBtn
                )
                self._show(self.submitBtn)
                self.root.configure(cursor = "")
                self.preview.canvas.configure(cursor = constants["previewCursor"])
            
            self.log.info(f"GUI set to {state}")

        def showWarning(self, message: str, title: str = "Warning") -> None:
            """
            Show warning dialog box.
            
            Warnings are for when an action can not be performed currently
            but the issue can be resolved within the application.

            For more serious issues use errors.
            """
            self.log.info(f"Warning shown: {title} | {message}")
            messagebox.showwarning(title, message)

        def showInfo(self, message: str, title: str = "Info") -> None:
            """Show info dialog box with given message and title."""
            self.log.info(f"Info shown: {title} | {message}")
            messagebox.showinfo(title, message)

        def askNonFatalError(self, message: str, title: str = "Error") -> bool:
            """
            Show error dialog box.

            Returns True  if the user wants to retry, False otherwise.
            
            Non-fatal errors are for when an action can not be performed currently
            and can not be resolved entirely within the application,
            but can be resumed and successfully completed from the current state
            after changing some settings on the user's machine.

            Non-fatal errors can be dismissed.
            """
            self.log.info(f"Non-fatal error shown: {title} | {message}")
            return messagebox.askretrycancel(title, message)

        def askAbortingError(self, message: str, title: str = "Fatal error") -> None:
            """
            Show Aborting error dialog box.
            
            Initiates abort if the user cancels.

            Aborting errors are for when an action cannot be performed
            that is an integral part of the exporting process.
            Aborting errors do not threaten exitin the rogram,
            only aborting the exporting process.

            The user can decide to retry and continue exporting or abort it.
            """
            message += "\n\nRetry or exporting will be aborted."
            self.log.info(f"Aborting error shown: {title} | {message}")
            if not messagebox.askretrycancel(title, message):
                self.log.info(f"Abort initiated from aborting error: {title} | {message}")
                self.root.event_generate('<<Abort>>', when = "tail")

        def askFatalError(self, message: str, title: str = "Fatal error") -> bool:
            """
            Show fatal error dialgbox.

            Returns True  if the user wants to retry, False otherwise.
            
            Fatal errors are for when an action cannot be performed
            which is an essential part of the program.
            Fatal errors lead to termination that should be initiated by the caller.
            
            The user can decide to retry and continue the program
            or Cancel and exit prematurely.
            """
            message += "\n\nRetry or the program will exit automatically."
            self.log.info(f"Fatal error shown: {title} | {message}")
            return messagebox.askretrycancel(title, message)

        def progressPopup(self, var: tkinter.IntVar, maximum: int) -> tkinter.Toplevel:
            """Return a GUI popup window with a progressbar tied to var."""
            win = tkinter.Toplevel(cursor = "watch")
            label = ttk.Label(win, text = "Collecting threads: ")
            progressLabel = ttk.Label(win, textvariable = var)
            ofLabel = ttk.Label(win, text = " of ")
            totalLabel = ttk.Label(win, text = maximum)
            progressBar = ttk.Progressbar(win, variable = var, maximum = maximum)

            label.grid(row = 0, column = 0, sticky = tkinter.EW)
            progressLabel.grid(row = 0, column = 1, sticky = tkinter.EW)
            ofLabel.grid(row = 0, column = 2, sticky = tkinter.EW)
            totalLabel.grid(row = 0, column = 3, sticky = tkinter.EW)
            progressBar.grid(row = 1, column = 0, columnspan = 5, sticky = tkinter.EW)

            win.columnconfigure(4, weight = 1)
            win.configure(padx = 5, pady = 5, border = 1, relief = tkinter.SOLID)

            win.overrideredirect(1)
            w = 400
            h = 60
            x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
            win.geometry(f"{w}x{h}+{x}+{y}")

            self.popups.append(win)
            self.log.info(f"Progress popup created: {var.get()}/{maximum}")
            return win

        def __init__(self, parent: object):
            self.log = logging.getLogger("gui")
            self.popups = []
            self.external = parent
            self.root = tkinter.Tk()
            self.root.title("CSLapse")
            iconfile = resourcePath("media/thumbnail.ico")
            self.root.iconbitmap(default = iconfile)
            self.log.info("GUI initiated successfully.")

        def selectExe(self) -> None:
            """Call function to seelct CSLMapView.exe."""
            self.external.openExe(constants["texts"]["openExeTitle"])

        def selectSample(self) -> None:
            """Call function to select a cslmap file."""
            self.external.openSample(constants["texts"]["openSampleTitle"])

        def submitPressed(self) -> None:
            """Check if all conditions are satified and start exporting if yes. Show warning if not."""
            try:
                if self.external.vars["exeFile"].get() == constants["noFileText"]:
                    self.showWarning(constants["texts"]["noExeMessage"])
                elif self.external.vars["sampleFile"].get() == constants["noFileText"]:
                    self.showWarning(constants["texts"]["noSampleMessage"])
                elif not self.external.vars["fps"].get() > 0:
                    self.showWarning(constants["texts"]["invalidFPSMessage"])
                elif not self.external.vars["width"].get() > 0:
                    self.showWarning(constants["texts"]["invalidWidthMessage"])
                elif not self.external.vars["videoLength"].get() > 0:
                    self.showWarning(constants["texts"]["invalidLengthMessage"])
                elif not self.external.vars["threads"].get() > 0:
                    self.showWarning(constants["texts"]["invalidThreadsMessage"])
                elif not self.external.vars["retry"].get() > -1:
                    self.showWarning(constants["texts"]["invalidRetryMessage"])
                else:
                    self.external.export()
            except Exception:
                self.log.warning(f'Submit button pressed with faulty entry data: \
                    exefile={self.external.vars["exeFile"].get()}, \
                    samplefile={self.external.vars["sampleFile"].get()}, \
                    fps={self.external.vars["fps"].get()}, \
                    width={self.external.vars["width"].get()},\
                    videolenght={self.external.vars["videoLength"].get()}, \
                    threads={self.external.vars["threads"].get()}, \
                    retry={self.external.vars["retry"].get()}')
                self.showWarning("Something went wrong. Check your settings and try again.")

        def abortPressed(self) -> None:
            """Ask user if really wants to abort. Generate abort tinter event if yes."""
            if messagebox.askyesno(title = "Abort action?", message = constants["texts"]["askAbort"]):
                self.log.info("Abort initiated by abort button.")
                self.root.event_generate('<<Abort>>', when = "tail")

        def refreshPressed(self) -> None:
            """Call function to refresh the preview image."""
            self.log.info("Refresh button pressed.")
            self.external.refreshPreview(manual = True)

        def closePressed(self) -> None:
            """Aks user if really wnats to quit. If yes, initiate abort and exit afterwards"""
            if self.external.isRunning:
                if messagebox.askyesno(title = "Are you sure you want to exit?", message = constants["texts"]["askAbort"]):
                    self.external.exitEvent.set()
                    self.root.event_generate('<<Abort>>', when = "tail")
                    self.log.info("Abort process initiated by close button.")
            elif self.external.isAborting:
                self.external.exitEvent.set()
                self.showWarning(constants["texts"]["exitAfterAbortEnded"])
            else:
                self.log.info("Exiting due to close button pressed.")
                self.root.destroy()

        def configureWindow(self) -> None:
            """Set up widgets, event bindings, grid for the main window"""

            self._createStyles()

            self.registerCallbacks()

            self._createMainFrame(self.callBacks, self.external.vars, self.external.filetypes, constants["texts"])
            self._createPreviewFrame(self.callBacks, self.external.vars)

            self._gridMainFrame()
            self._gridPreviewFrame()

            self._configure()

            self.log.info("Graphical user interface configured.")

class Preview(object):
    """ Object that handles the preview functionaltiy in the GUI"""

    class Printarea(object):
        """Class for the outline of the area that will be exported."""

        def __init__(self, canvas: tkinter.Canvas):
            self.x_start = 0 #X coordinate of the top left corner of the print area on the original image
            self.y_start = 0 #Y coordinate of the top left corner of the printarea on the original image
            self.width = 0   #Width of printarea on the original image
            self.height = 0  #Height of printarea on the original image

            self.canvas = canvas

            self.north = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill = "gray",
                outline = "",
                state = tkinter.NORMAL,
                tags = ["printarea"]
            )
            self.south = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill = "gray",
                outline = "",
                state = tkinter.NORMAL,
                tags = ["printarea"]
            )
            self.west = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill = "gray",
                outline = "",
                state = tkinter.NORMAL,
                tags = ["printarea"]
            )
            self.east = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill = "gray",
                outline = "",
                state = tkinter.NORMAL,
                tags = ["printarea"]
            )
            self.border = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill = "",
                outline = "red",
                state = tkinter.NORMAL,
                tags = ["printarea"],
            )

        def show(self) -> None:
            """Show the outline on canvas."""
            self.canvas.itemconfigure("printarea", state = tkinter.NORMAL)

        def hide(self) -> None:
            """Hide the outline on canvas."""
            self.canvas.itemconfigure("printarea", state = tkinter.HIDDEN)

        def raise_above(self, tagorid: str) -> None:
            """Raise the ourline above the object(s) given by tagorid on canvas."""
            self.canvas.tag_raise("printarea", tagorid)

        def resize(self, exported_w: int, exported_h: int, exported_areas: float, new_areas: float) -> None:
            """Resize the outline when the areas to be show chage."""
            wRatio = exported_w / exported_areas
            self.x_start = (exported_areas - new_areas) / 2 * wRatio
            self.width = wRatio * new_areas

            hRatio = exported_h / exported_areas
            self.y_start = (exported_areas - new_areas) / 2 * hRatio
            self.height = hRatio * new_areas

        def move(self, canvas_w: int, canvas_h: int, image_x: int, image_y: int, scale_factor: float) -> None:
            """Move the printarea rectangle to the location of the preview image."""
            canvasTop = image_y + scale_factor * self.y_start
            canvasBottom = image_y + scale_factor * (self.y_start + self.height)
            canvasLeft = image_x + scale_factor * self.x_start
            canvasRight = image_x + scale_factor * (self.x_start + self.width)

            self.canvas.coords(self.north, 0, 0, canvas_w, canvasTop)
            self.canvas.coords(self.south, 0, canvasBottom, canvas_w, canvas_h)
            self.canvas.coords(self.west, 0, canvasTop, canvasLeft, canvasBottom)
            self.canvas.coords(self.east, canvasRight, canvasTop, canvas_w, canvasBottom)
            self.canvas.coords(self.border, canvasLeft, canvasTop, canvasRight, canvasBottom)

    def __init__(self, parent: object, parentFrame: tkinter.Widget):
        self.gui = parent
        self.canvas = tkinter.Canvas(parentFrame, cursor = "")
        self.active = False

        self.fullWidth = self.canvas.winfo_screenwidth()    #Width of drawable canvas in pixels
        self.fullHeight = self.canvas.winfo_screenheight()   #Height of drawable canvas in pixels
        self.imageWidth = 0   #Width of original image in pixels
        self.imageHeight = 0  #Height of original image in pixels

        self.previewAreas = 0 #Areas printed on the currently active preview image
        self.imageX = 0  #X Coordinate on canvas of pixel in top left of image
        self.imageY = 0  #Y Coordinate on canvas of pixel in top left of image
        self.scaleFactor = 1  #Conversion factor: canvas pixels / original image pixels

        self.placeholderImage = ImageTk.PhotoImage(Image.open(constants["noPreviewImage"]))
        self.canvas.create_image(0, 0, image = self.placeholderImage, tags = "placeholder")

        self.printarea = Preview.Printarea(self.canvas)
        self.printarea.hide()

    def createBindings(self) -> None:
        """Bind actions to events on the canvas."""
        self.canvas.bind("<Configure>", self.resized)
        self.canvas.bind("<MouseWheel>", self.scrolled)
        self.canvas.bind("<B1-Motion>", self.dragged)
        self.canvas.bind("<ButtonPress-1>", self.clicked)

    def resizeImage(self, newFactor: float) -> None:
        """Change the activeImage to one with the current scaleFactor, keep center pixel in center."""
        self.imageX = self.fullWidth / 2-((self.fullWidth / 2-self.imageX) / self.scaleFactor) * newFactor
        self.imageY = self.fullHeight / 2-((self.fullHeight / 2-self.imageY) / self.scaleFactor) * newFactor

        self.scaleFactor = newFactor

        self.gui.external.vars["previewImage"] = ImageTk.PhotoImage(self.gui.external.vars["previewSource"].resize((int(self.imageWidth * self.scaleFactor), int(self.imageHeight * self.scaleFactor))))
        self.canvas.itemconfigure(self.activeImage, image = self.gui.external.vars["previewImage"])
        self.canvas.moveto(self.activeImage, x = self.imageX, y = self.imageY)

        self.update_printarea()

    def fitToCanvas(self) -> None:
        """Resize activeImage so that it touches the borders of canvas and the full image is visible, keep aspect ratio."""
        newScaleFactor = min(self.fullWidth / self.imageWidth, self.fullHeight / self.imageHeight)
        self.resizeImage(newScaleFactor)
        self.canvas.moveto(self.activeImage, x = (self.fullWidth-int(self.imageWidth * self.scaleFactor)) / 2, y = (self.fullHeight-int(self.imageHeight * self.scaleFactor)) / 2)
        self.imageX = (self.fullWidth-self.imageWidth * self.scaleFactor) / 2
        self.imageY = (self.fullHeight-self.imageHeight * self.scaleFactor) / 2

        self.update_printarea()

    def scaleToOriginal(self) -> None:
        """Rescale to the original size of the preview image."""
        self.resizeImage(1)

    def justExported(self) -> None:
        """Show newly exported preview image."""
        self.imageWidth = self.gui.external.vars["width"].get()
        self.imageHeight = self.gui.external.vars["width"].get()

        self.previewAreas = float(self.gui.external.vars["areas"].get())
        self.printAreaX = 0
        self.printAreaW = self.gui.external.vars["width"].get()
        self.printAreaY = 0
        self.printAreaH = self.gui.external.vars["width"].get()
        
        self.gui.external.vars["previewImage"] = ImageTk.PhotoImage(self.gui.external.vars["previewSource"])
        if self.active:
            self.canvas.itemconfigure(self.activeImage, image = self.gui.external.vars["previewImage"])
        else:
            self.activeImage = self.canvas.create_image(0, 0, anchor = tkinter.CENTER, image = self.gui.external.vars["previewImage"], tags = "activeImage")

        self.fitToCanvas()

        self.active = True
        self.canvas.itemconfigure("placeholder", state = "hidden")

        self.update_printarea(self.previewAreas)
        self.printarea.raise_above("activeImage")
        self.printarea.show()

    def resized(self, event: tkinter.Event) -> None:
        """Handle change in the canvas's size."""
        if self.active:
            #Center of the canvas should stay the center of the canvas when the window is resized
            self.imageX = ((self.imageX+self.imageWidth * self.scaleFactor / 2) * event.width / self.fullWidth)-(self.imageWidth * self.scaleFactor / 2)
            self.imageY = ((self.imageY+self.imageHeight * self.scaleFactor / 2) * event.height / self.fullHeight)-(self.imageHeight * self.scaleFactor / 2)
            self.canvas.moveto(self.activeImage, x = self.imageX, y = self.imageY)

        if not self.active:
            self.canvas.moveto("placeholder", x = str((event.width-self.placeholderImage.width()) / 2),
                                            y = str((event.height-self.placeholderImage.height()) / 2))
        self.fullWidth = event.width
        self.fullHeight = event.height

        self.update_printarea()

    def scrolled(self, event: tkinter.Event) -> None:
        """Handle scrolling event (zoom) on canvas."""
        if self.active:
            self.resizeImage(self.scaleFactor * (1+6 /(event.delta)))

    def dragged(self, event: tkinter.Event) -> None:
        """Handle dragging event (panning) on canvas."""
        if self.active:
            deltaX = event.x-self.lastClick[0]
            deltaY = event.y-self.lastClick[1]
            self.canvas.moveto(self.activeImage, x = self.imageX + deltaX, y = self.imageY + deltaY)
            self.imageX = self.imageX + deltaX
            self.imageY = self.imageY + deltaY
            self.lastClick = (event.x, event.y)

            self.update_printarea()

    def clicked(self, event: tkinter.Event) -> None:
        """Handle buttonpress event on canvas."""
        if self.active:
            self.lastClick = (event.x, event.y)

    def update_printarea(self, new_areas: float = None) -> None:
        """Reflect change on preview canvas areas on printarea."""
        if self.active:
            if new_areas is not None:
                self.printarea.resize(self.imageWidth, self.imageHeight, self.previewAreas, new_areas)
            self.printarea.move(self.fullWidth, self.fullHeight, self.imageX, self.imageY, self.scaleFactor)
        

def main() -> None:
    logging.getLogger("root").info("")
    logging.getLogger("root").info("-"*50)
    logging.getLogger("root").info("")
    logging.getLogger("root").info(f"CSLapse started with working directory '{currentDirectory}'.")
    with CSLapse() as O:
        O.gui.root.mainloop()
    logging.getLogger("root").info("CSLapse exited peacefully")


if __name__ == "__main__":
    logging.config.dictConfig(get_logger_config_dict())
    currentDirectory = Path(__file__).parent.resolve() # current directory
    constants = {
        "abort":False,
        "sampleExportWidth":2000,
        "defaultFPS":24,
        "defaultExportWidth":2000,
        "defaultThreads":6,
        "defaultRetry":15,
        "defaultAreas":9.0,
        "noFileText":"No file selected",
        "rotaOptions":["0°", "90°", "180°", "270°"],
        "texts":{
            "openExeTitle":"Select CSLMapViewer.exe",
            "openSampleTitle":"Select a cslmap save of your city",
            "noExeMessage":"Select CSLMapviewer.exe first!",
            "noSampleMessage":"Select a city file first!",
            "invalidLengthMessage":"Invalid video length!",
            "invalidLengthMessage":"Invalid video length!",
            "invalidLengthMessage":"Invalid video length!",
            "invalidLengthMessage":"Invalid video length!",
            "invalidLengthMessage":"Invalid video length!",
            "askAbort":"Are you sure you want to abort? This cannot be undone, all progress will be lost.",
            "abortAlreadyRunning":"Cannot abort export process: No export process to abort or an abort process is already running.",
            "exitAfterAbortEnded":"An abort operation is running. The program will exit once it has finished."
            
        },
        "clickable":"hand2",
        "previewCursor":"fleur",
        "noPreviewImage": resourcePath("media/NOIMAGE.png")
    }
    main()