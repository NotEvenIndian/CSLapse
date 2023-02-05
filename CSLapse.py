from __future__ import annotations
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

from abc import ABC, abstractmethod

# Suggestions for any sort of improvement are welcome.

class AbortException(Exception):pass
class ExportError(Exception):pass

def get_logger_config_dict() -> dict:
    """Return the logger configuration dictionary."""
    dictionary = {
        "version": 1,
        "formatters": {
            "basic": {
                "format": "%(asctime)s %(levelname)s [%(name)s/%(threadName)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers":{
            "logfile": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": logging.INFO,
                "formatter": "basic",
                "filename": "./cslapse.log",
                "maxBytes": 200000,
                "backupCount": 1
            }
        },
        "loggers":{
            "app": {
                "level": logging.INFO,
                "handlers": ["logfile"]
            },
            "root": {
                "level": logging.INFO,
                "handlers": ["logfile"]
            },
            "exporter": {
                "level": logging.INFO,
                "handlers": ["logfile"]
            },
            "window": {
                "level": logging.INFO,
                "handlers": ["logfile"]
            }
        }
    }

    return dictionary


class ThreadCollector(threading.Thread):
    """Cancel and join all running threads and futures except for threads in keep_alive.
    
    Optionally count finished threads so far in counter
    """

    def __init__(   self,
                    keep_alive: List[threading.Thread],
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
            lambda t: t not in [*keep_alive, threading.current_thread()],
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


def timestamp() -> str:
    """Return a timestamp in format hhmmss."""
    return str(datetime.now()).split(" ")[-1].split(".")[0].replace(":", "")


def resource_path(relative_path: str) -> Path:
    """
    Get absolute path to resource, works for dev and for PyInstaller.

    source: https://stackoverflow.com/a/13790741/19634396
    """
    try:
        # PyInstaller creates a temporary folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent.resolve()
    return Path(base_path, relative_path)


def roundToTwoDecimals(var: tkinter.StringVar) -> None:
    """Round the decimal in var to 2 decimal places."""
    var.set(str(round(float(var.get()), 2)))


def show_warning(message: str, title: str = "Warning") -> None:
    """
    Show warning dialog box.
    
    Warnings are for when an action can not be performed currently
    but the issue can be resolved within the application.

    For more serious issues use errors.
    """
    log = logging.getLogger("root")
    log.info(f"Warning shown: {title} | {message}")
    messagebox.showwarning(title, message)

def show_info(message: str, title: str = "Info") -> None:
    """Show info dialog box with given message and title."""
    log = logging.getLogger("root")
    log.info(f"Info shown: {title} | {message}")
    messagebox.showinfo(title, message)

def ask_non_fatal_error(message: str, title: str = "Error") -> bool:
    """
    Show error dialog box.

    Returns True  if the user wants to retry, False otherwise.
    
    Non-fatal errors are for when an action can not be performed currently
    and can not be resolved entirely within the application,
    but can be resumed and successfully completed from the current state
    after changing some settings on the user's machine.

    Non-fatal errors can be dismissed.
    """
    log = logging.getLogger("root")
    log.info(f"Non-fatal error shown: {title} | {message}")
    return messagebox.askretrycancel(title, message)

def ask_aborting_error(message: str, title: str = "Fatal error") -> None:
    """
    Show Aborting error dialog box.
    
    Initiates abort if the user cancels.

    Aborting errors are for when an action cannot be performed
    that is an integral part of the exporting process.
    Aborting errors do not threaten exitin the rogram,
    only aborting the exporting process.

    The user can decide to retry and continue exporting or abort it.
    """
    log = logging.getLogger("root")
    message += "\n\nRetry or exporting will be aborted."
    log.info(f"Aborting error shown: {title} | {message}")
    if not messagebox.askretrycancel(title, message):
        log.info(f"Abort initiated from aborting error: {title} | {message}")
        events.abort.set()

def ask_fatal_error(message: str, title: str = "Fatal error") -> bool:
    """
    Show fatal error dialgbox.

    Returns True  if the user wants to retry, False otherwise.
    
    Fatal errors are for when an action cannot be performed
    which is an essential part of the program.
    Fatal errors lead to termination that should be initiated by the caller.
    
    The user can decide to retry and continue the program
    or Cancel and exit prematurely.
    """
    log = logging.getLogger("root")
    message += "\n\nRetry or the program will exit automatically."
    log.info(f"Fatal error shown: {title} | {message}")
    return messagebox.askretrycancel(title, message)


class events:
    """Namespace containing threading events used by the application."""
    abort = threading.Event()
    preview_loaded = threading.Event()
    preview_load_error = threading.Event()
    threads_collected = threading.Event()
    export_started = threading.Event()
    image_files_exported = threading.Event()
    exporting_done = threading.Event()
    abort_finished = threading.Event()
    close = threading.Event()


class constants:
    abort = False
    sampleExportWidth = 2000
    defaultFPS = 24
    defaultExportWidth = 2000
    defaultThreads = 6
    defaultRetry = 15
    defaultAreas = 9.0
    noFileText = "No file selected"
    rotaOptions = ["0°", "90°", "180°", "270°"]
    class texts:
        openExeTitle = "Select CSLMapViewer.exe"
        openSampleTitle = "Select a cslmap save of your city"
        noExeMessage = "Select CSLMapviewer.exe first!"
        noSampleMessage = "Select a city file first!"
        invalidLengthMessage = "Invalid video length!"
        invalidLengthMessage = "Invalid video length!"
        invalidLengthMessage = "Invalid video length!"
        invalidLengthMessage = "Invalid video length!"
        invalidLengthMessage = "Invalid video length!"
        askAbort = "Are you sure you want to abort? This cannot be undone, all progress will be lost."
        abortAlreadyRunning = "Cannot abort export process: No export process to abort or an abort process is already running."
        exitAfterAbortEnded = "An abort operation is running. The program will exit once it has finished."    
    class filetypes:
        exe = [("Executables", "*.exe"), ("All files", "*")]
        cslmap = [("CSLMap files", ("*.cslmap", "*.cslmap.gz")), ("All files", "*")]
    clickable = "hand2"
    previewCursor = "fleur"
    noPreviewImage =  resource_path("media/NOIMAGE.png")
    sampleCommand = ["__exeFile__", "__source_file__", "-output", "__outFile__", "-silent", "-imagewidth", "2000", "-area", "9"]



class App():
    """Class overlooking everything - the gui, the variables, the constants and more."""
    
    def __enter__(self) -> object:
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up after the object"""
        if self.exporter.temp_folder is not None and self.exporter.temp_folder.exists():
            rmtree(self.exporter.temp_folder, ignore_errors = True)
        collector = ThreadCollector([threading.current_thread()], counter = self.vars["thread_collecting"])
        collector.start()
        collector.join()
        self.log.info("Cleanup after App done")

    def __init__(self):
        self.timestamp = timestamp()
        self.lock = threading.Lock()
        self.log = logging.getLogger("app")
        self.root = tkinter.Tk()
        self.root.event_add('<<Abort>>', '<Control-C>')
        self.root.bind('<<Abort>>', lambda event: events.abort.set())
        self.root.protocol("WM_DELETE_WINDOW", self.close_pressed)
        self.vars = {
            "exe_file":tkinter.StringVar(value = constants.noFileText),
            "sample_file":tkinter.StringVar(value = constants.noFileText),
            "num_of_files":tkinter.IntVar(value = 0),
            "fps":tkinter.IntVar(value = constants.defaultFPS),
            "width":tkinter.IntVar(value = constants.defaultExportWidth),
            "threads":tkinter.IntVar(value = constants.defaultThreads),
            "retry":tkinter.IntVar(value = constants.defaultRetry),
            "rotation":tkinter.StringVar(value = constants.rotaOptions[0]),
            "areas":tkinter.StringVar(value = constants.defaultAreas),
            "video_length":tkinter.IntVar(value = 0),
            "exporting_done":tkinter.IntVar(value = 0),
            "rendering_done":tkinter.IntVar(value = 0),
            "thread_collecting":tkinter.IntVar(value = 0),
            "preview_source":""
        }
        callbacks = self.register_callbacks()

        self.exporter = Exporter(self.lock)
        self.window = CSLapse_window(self.root, self.vars, callbacks)
        self.preview = self.window.get_preview()
        
        self.root.after(0, self._checkThreadEvents)

        self.log.info("App object initiated.")

    def null(self, * args: Any, ** kwargs: Any) -> None:
        """Placeholder function, do nothing."""
        pass 

    def _checkThreadEvents(self) -> None:
        """Check if the threading events are set, repeat after 100 ms."""
        if events.preview_loaded.is_set():
            events.preview_loaded.clear()
            self.preview.justExported(self.vars["preview_source"], int(self.vars["width"].get()), float(self.vars["areas"].get()))
            self.window.set_state("preview_loaded")
        if events.preview_load_error.is_set():
            events.preview_load_error.clear()
            self.window.set_state("preview_load_error")
        if events.abort.is_set():
            if not self.exporter.is_aborting:
                self.abort()
        if events.threads_collected.is_set():
            events.threads_collected.clear()
            self.window.set_state("defaultState")
        if events.export_started.is_set():
            events.export_started.clear()
            self.window.set_export_limit(int(self.vars["video_length"].get()))
            self.window.set_state("start_export")
        if events.image_files_exported.is_set():
            events.image_files_exported.clear()
            self.window.set_video_limit(self.exporter.get_num_of_exported_files())
            self.window.set_state("start_render")
        if events.exporting_done.is_set():
            events.exporting_done.clear()
            self.cleanup_after_success()
            self.window.set_state("render_done")
            show_info(f"See your timelapse at {self.exporter.out_file}", "Video completed")
        if events.abort_finished.is_set():
            events.abort_finished.clear()
            self.cleanup_after_abort()
        self.root.after(100, self._checkThreadEvents)

    def refresh_preview(self) -> None:
        """Export the preview CSLMap file with current settings."""
        if self.vars["exe_file"].get() == constants.noFileText:
            return
        if self.vars["sample_file"].get() == constants.noFileText:
            return
        sample = self.exporter.get_file(self.vars["video_length"].get() - 1)
        if sample == "":
            return
        self.window.set_state("preview_loading")
        cmd = constants.sampleCommand[:]
        cmd[6] = str(self.vars["width"].get())
        cmd[8] = str(self.vars["areas"].get())

        self.log.info("Refreshing preview started.")
        exporter_thread = threading.Thread(
            target = self.export_sample,
            args = (
                cmd,
                self.exporter.get_file(self.vars["video_length"].get() - 1),
                1
            )
        )
        exporter_thread.start()

    def export_sample(self, command: List[str], sample: str, retry: int) -> None:
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
                exported = self.exporter.export_file(
                    sample,
                    command,
                    retry
                    ) 
                with self.lock:
                    self.vars["preview_source"] = Image.open(exported)
                events.preview_loaded.set()
                return
            except AbortException:
                events.preview_load_error.set()
                return
            except ExportError as e:
                if not ask_non_fatal_error(str(e)):
                    events.preview_load_error.set()
                    self.log.exception(f"Returning after failed export of sample file '{sample}'")
                    return
            except Exception as e:
                if not ask_non_fatal_error(str(e)):
                    events.preview_load_error.set()
                    self.log.exception(f"Returning after failed export due to unnown exception of sample file '{sample}'")
                    return

    def open_file(self, title: str, filetypes: List[Tuple], default_directory: str = None) -> str:
        """Open file opening dialog box and return the full path to the selected file."""
        filename = filedialog.askopenfilename(title = title, initialdir = default_directory, filetypes = filetypes)
        self.log.info(f"File '{filename}' selected.")
        return filename

    def select_sample(self) -> None:
        """Ask user to select sample file from dialog and set variables accordingly."""
        selected_file = self.open_file(constants.texts.openSampleTitle, constants.filetypes.cslmap)
        if selected_file == self.vars["sample_file"].get():
            return
        elif selected_file != "":
            self.vars["sample_file"].set(selected_file)
            self.exporter.set_sample_file(selected_file)
            num_of_files = self.exporter.collect_raw_files(selected_file)
            self.vars["num_of_files"].set(num_of_files)
            if self.vars["video_length"].get() == 0:
                self.vars["video_length"].set(num_of_files)
            else:
                self.vars["video_length"].set(min(self.vars["video_length"].get(), num_of_files))
            self.refresh_preview()
        else:
            self.vars["sample_file"].set(constants.noFileText)

    def select_exe(self) -> None:
        """Ask user to select SCLMapViewer.exe from dialog and set variables accordingly."""
        selected_file = self.open_file(constants.texts.openSampleTitle, constants.filetypes.exe)
        if selected_file != "":
            self.vars["exe_file"].set(selected_file)
            constants.sampleCommand[0] = selected_file
            self.exporter.set_exefile(selected_file)
            self.refresh_preview()
        else:
            self.vars["exe_file"].set(constants.noFileText)

    def abort(self, event: tkinter.Event = None) -> None:
        """Stop currently running export process.
        
        If called on the main thread, collect all running threads.
        Otherwise raise an exception.

        Impossible to recover state afterwards.
        """
        if not self.exporter.can_abort():
            show_warning(constants.texts.abortAlreadyRunning)
            return

        if threading.current_thread() is not threading.main_thread():
            raise AbortException("Abort initiated.")
        else:
            self.exporter.set_abort()
            self.window.set_state("aborting")

            self.log.info("Abort procedure started on main thread.")

            self.vars["thread_collecting"].set(0)
            collector = ThreadCollector([threading.current_thread()], self.exporter.get_futures(), counter = self.vars["thread_collecting"], callback=events.abort_finished.set)
            self.window.progressPopup(self.vars["thread_collecting"], collector.total())
            collector.start()

    def cleanup_after_success(self) -> None:
        """Clean up variables and environment after successful exporting."""
        self.exporter.cleanup()

    def cleanup_after_abort(self) -> None:
        """Clean up variables and environment after aborted exporting."""
        events.abort.clear()
        self.exporter.cleanup()
        self.log.info("Successful cleanup after aborted export.")
        self.window.set_state("after_abort")
        if events.close.is_set():
            self.root.destroy()
            self.log.info("Exiting after aborted export.")
            
    def register_callbacks(self) -> dict:
        """Prepare the callback methods for tkinter widgets and return a dictionary containing them."""
        callbacks = {
            "submit": self.submit_pressed,
            "abort": self.abort_pressed,
            "select_exe": self.select_exe,
            "select_sample": self.select_sample,
            "areas_entered": self.root.register(self.areas_entered),
            "areas_changed": self.areas_changed,
            "refresh_preview": self.refresh_pressed
        }
        return callbacks

    def areas_entered(self, action, new_text) -> bool:
        """Callback to be executed when the areas widget is changed."""
        if action == "0":
            return True
        try:
            number = float(new_text)
            if number >= 0.1 and number <= 9.0:
                self.preview.update_printarea(number)
                return True
            return False
        except Exception:
            return False

    def refresh_pressed(self) -> None:
        """
        Callback to be called when the refresh preview button is pressed.
        
        Check if all required variables are set correctly and if yes, refresh the preview.
        Show a warning message otherwise.
        """
        if self.vars["exe_file"].get() == constants.noFileText:
            show_warning(title = "Warning", message = constants.texts.noExeMessage)
            return
        if self.vars["sample_file"].get() == constants.noFileText:
            show_warning(title = "Warning", message = constants.texts.noSampleMessage)
            return
        sample = self.exporter.get_file(self.vars["video_length"].get() - 1)
        if sample == "":
            show_warning(title = "Warning", message = "Not enough files to match video frames!")
            return
        self.refresh_preview()

    def submit_pressed(self) -> None:
        """Check if all conditions are satified and start exporting if yes. Show warning if not."""
        self.log.info(f'Submit button pressed with entry data:\nexefile={self.vars["exe_file"].get()}\nfps={self.vars["fps"].get()}\nwidth={self.vars["width"].get()}\nvideolenght={self.vars["video_length"].get()}\nthreads={self.vars["threads"].get()}\nretry={self.vars["retry"].get()}')
        try:
            if self.vars["exe_file"].get() == constants.noFileText:
                show_warning(constants.texts.noExeMessage)
            elif self.vars["sample_file"].get() == constants.noFileText:
                show_warning(constants.texts.noSampleMessage)
            elif not self.vars["fps"].get() > 0:
                show_warning(constants.texts.invalidFPSMessage)
            elif not self.vars["width"].get() > 0:
                show_warning(constants.texts.invalidWidthMessage)
            elif not self.vars["video_length"].get() > 0:
                show_warning(constants.texts.invalidLengthMessage)
            elif not self.vars["threads"].get() > 0:
                show_warning(constants.texts.invalidThreadsMessage)
            elif not self.vars["retry"].get() > -1:
                show_warning(constants.texts.invalidRetryMessage)
            else:
                if not self.exporter.export(
                    self.vars["width"].get(),
                    self.vars["areas"].get(),
                    self.vars["video_length"].get(),
                    self.vars["fps"].get(),
                    self.vars["threads"].get(),
                    self.vars["retry"].get(),
                    self.vars["exporting_done"],
                    self.vars["rendering_done"]
                ):
                    self.showWoarning("An export operation is already running!")
        except Exception:
            self.log.exception("Incorrect entry data.")
            show_warning("Something went wrong. Check your settings and try again.")

    def abort_pressed(self) -> None:
        """Ask user if really wants to abort. Generate abort tkinter event if yes."""
        if messagebox.askyesno(title = "Abort action?", message = constants.texts.askAbort):
            self.log.info("Abort initiated by abort button.")
            self.root.event_generate('<<Abort>>', when = "tail")

    def areas_changed(self) -> None:
        """
        Callback to be called when the areas slider is moved.

        Updates the printarea rectangle to the appropriate size.
        """
        self.preview.update_printarea(float(self.vars["areas"].get()))
        
    def close_pressed(self) -> None:
        """Ask user if really wnats to quit. If yes, initiate abort and exit afterwards"""
        if self.exporter.is_running:
            if messagebox.askyesno(title = "Are you sure you want to exit?", message = constants.texts.askAbort):
                events.close.set()
                self.root.event_generate('<<Abort>>', when = "tail")
                self.log.info("Abort process initiated by close button.")
        elif self.exporter.is_aborting:
            events.close.set()
            show_warning(constants.texts.exitAfterAbortEnded)
        else:
            self.log.info("Exiting due to close button pressed.")
            events.abort.set()
            events.close.set()
            self.root.destroy()


class Exporter():
    """Class responsible for exporting images and assembling the video from them."""
    def __init__(self, lock: threading.Lock):
        self.log = logging.getLogger("exporter")
        self.lock = lock
        self.source_directory = None # Path type, the directory where cslmap files are loaded from
        self.city_name = None # string, the name of the city
        self.temp_folder = None # Path type, the location where temporary files are created
        self.raw_files = []    # Collected cslmap files with matching city name
        self.image_files = []
        self.futures = []   # concurrent.futures.Future objects that are exporting images
        self.is_running = False # If currently there is exporting going on
        self.is_aborting = False # If an abort pre=ocess is in progress
        self.out_file = "" # Name of output file

    def get_file(self, n: int) -> str:
        """
        Return the nth (0-indexed) file among the collected raw_files.

        If there are not enough files, return an empty string.
        """
        if n >= len(self.raw_files):
            return ""
        else:
            return self.raw_files[n]

    def get_num_of_exported_files(self) -> int:
        """Return the number of files exported in theis export process."""
        with self.lock:
            num = len(self.image_files)
        return num

    def get_futures(self) -> List[concurrent.futures.Future]:
        """Return future objects used for export."""
        return self.futures

    def can_abort(self) -> bool:
        """Return if the export process can be aborted."""
        return not (self.is_aborting or self.is_running)

    def set_abort(self) -> None:
        """Set variables to start aborting."""
        self.is_aborting = True
        self.isRunning = False

    def clear_temp_folder(self) -> None:
        """
        Remove the all files from self.temp_folder, create Directory if doesn't exist.

        If temp_folder is None, or doesnt exist, create the folder and return.
        If a file can not be removed, show a warning.
        If an other issue comes up: 
        """
        while 1:
            try:
                with self.lock:
                    if self.temp_folder.exists():
                        rmtree(self.temp_folder, ignore_errors = False)
                    self.temp_folder.mkdir()
                self.log.info("Tempfolder cleared or created successfully.")
                return
            except Exception as e:
                self.log.exception("Error while clearing / creating temp_folder.")
                if not ask_fatal_error(str(e)):
                    raise
        
    def set_sample_file(self, sample: str) -> None:
        """Store city name and location of the sample file."""
        sample_file = Path(sample)
        self.source_directory = sample_file.parent
        self.temp_folder = Path(self.source_directory, f"temp-{timestamp()}")
        self.city_name = sample_file.stem.split("-")[0]
        self.clear_temp_folder()

    def set_exefile(self, exefile: str) -> None:
        """Set the executable used for exporting to exefile."""
        self.exefile = exefile

    def collect_raw_files(self, filename: str) -> int:
        """Make an array of files whose name matches the city's name and return its length"""
        self.raw_files = sorted(
            filter(
                lambda filename: filename.name.startswith(self.city_name) and ".cslmap" in filename.suffixes, 
                self.source_directory.iterdir()
            ))
        return len(self.raw_files)

    def export_file(self, source_file: str, cmd: List[str], retry: int) -> str:
        """Call CSLMapView to export one image file and return outfile's name.

        Exceptions:
            Abortexpression: propagates
            Cannot export file after [retry] tries: raises ExportError
        """

        #Prepare command that calls cslmapview.exe
        new_file_name = Path(self.temp_folder, source_file.stem.encode("ascii", "ignore").decode()).with_suffix(".png")
        cmd[1] = str(source_file)
        cmd[3] = str(new_file_name)

        self.log.info(f"Export started with command '{' '.join(cmd)}'")

        #call CSLMapview.exe to export the image. Try again at fail, abort after many tries.
        for n in range(retry):
            try:
                #Call the program in a separate process
                subprocess.run(cmd, shell = False, stderr = subprocess.DEVNULL, stdout = subprocess.DEVNULL, check = False)

                #Return prematurely on abort
                #Needs to be after export command, otherwise won't work. Probably dead Lock.
                if events.abort.is_set():
                    raise AbortException("Abort initiated on another thread.")

                #Ensure that the image file was successfully created. 
                assert new_file_name.exists()
                
                self.log.info(f"Successfully exported file '{new_file_name}' after {n+1} attempts.")
                return str(new_file_name)
            except AbortException as error:
                self.log.exception(f"Aborted while exporting file '{new_file_name}'.")
                raise AbortException from error
            except subprocess.CalledProcessError as e:
                self.log.exception(f"Process error while exporting file '{new_file_name}'.")
                pass
            except AssertionError as e:
                self.log.warning(f"File '{new_file_name}' does not exist after exporting.")
                pass
            except Exception as e:
                self.log.exception(f"Unknown exception while exporting file '{new_file_name}'.")
                pass

        self.log.warning(f"Failed to export file after {retry} attempts with command '{' '.join(cmd)}'")

        #Throw exception after repeatedly failing
        raise ExportError(str('Could not export file.\nCommand: "'
            + ' '.join(cmd)
            + '"\nThis problem might arise normally, usually when resources are taken.'))

    def export(self, width: int, areas: float, length: int, fps: int, threads: int, retry: int, image_files_counter: tkinter.IntVar, video_counter: tkinter.IntVar) -> bool:
        """Start exporting and return True if possible, False if exporting is already running."""
        if self.is_running or self.is_aborting:
            return False
        self.prepare(image_files_counter, video_counter)
        threading.Thread(
            target = self.run,
            args = (
                width,
                areas,
                length,
                fps,
                threads,
                retry,
                image_files_counter,
                video_counter
            ),
            daemon = True
        ).start()
        return True

    def prepare(self, image_files_counter: tkinter.IntVar, video_counter: tkinter.IntVar) -> None:
        """Prepare variables and environment for exporting."""
        self.log.info(f"Exporting process initiated.")
        self.is_running = True
        self.is_aborting = False
        events.abort.clear()
        self.clear_temp_folder()
        self.image_files = []
        self.futures = []
        image_files_counter.set(0)
        video_counter.set(0)

    def run(self, width: int, areas: float, length: int, fps: int, threads: int, retry: int, image_files_var: tkinter.IntVar, video_var: tkinter.IntVar) -> None:
        """Export images and create video from them.
        
        Exceptions:
            Starting second export: warning
            AbortException: return
        """
        try:
            events.export_started.set()
            self.log.info("Exporting image files started.")
            self.export_image_files(width, areas, length, threads, retry, image_files_var)
            self.log.info("Exporting image files finished.")
            events.image_files_exported.set()
            self.log.info("Rendering video started.")
            self.render_video(width, fps, video_var)
            self.log.info("Rendering video finished.")
            events.exporting_done.set()
        except AbortException as e:
            events.abort.set()
            self.log.exception("Aborting export process due to AbortException")
            raise

    def export_image_files(self, width: int, areas: float, length: int, threads: int, retry: int, progress_variable: tkinter.IntVar) -> None:
        """Call CSLMapView to export the collected cslmap files one-by-one on separate threads.
        
        Exceptions:
            Raise AbortException if abort is requested
        """     
        cmd = [
            self.exefile,
            "__source_file__",
            "-output",
            "__outFile__",
            "-silent",
            "-imagewidth",
            str(width),
            "-area",
            str(areas)
            ]

        with concurrent.futures.ThreadPoolExecutor(threads) as executor:
            for i in range(length):
                self.futures.append(
                    executor.submit(self.export_image, self.raw_files[i], cmd[:], retry, progress_variable)
                )
        if events.abort.is_set():
            raise AbortException("Abort initiated on another thread.")

        #Sort array as the order might have changed during threading
        self.image_files = sorted(self.image_files)

    def export_image(self, source: str, cmd: List[str], retry: int, progress_variable: tkinter.IntVar) -> None:
        """Call the given command to export the given image, add filename to self.imageFiles.
        
        This function should run on a separate thread for each file.

        Exceptions:
            AbortException: propagate
            ExportError: non-fatal
            Other exceptions: non-fatal
        """
        while True:
            try:
                new_file_name = self.export_file(source, cmd, retry)
                break
            except AbortException as e:
                raise AbortException from e
            except ExportError as e:
                if not ask_non_fatal_error(str(e)):
                    self.log.exception(f"Skipping file '{source}' after too many unsuccessful attempts.")
                    return
                self.log.info(f"Retrying to export '{source}' after too many unsuccessful attempts.")
            except Exception as e:
                if not ask_non_fatal_error(str(e)):
                    self.log.exception(f"Skipping file '{source}' after unknown exception.")
                    return
                self.log.info(f"Retrying to export '{source}' after unknown exception.")
        with self.lock:
            self.image_files.append(new_file_name)
            progress_variable.set(progress_variable.get() + 1)
        return

    def render_video(self, width: int, fps: int, progress_variable: tkinter.IntVar, out_file: Path = None) -> None:
        """Create an mp4 video file from all the exported images.
        
        Exceptions:
            Raise AbortException if abort is requested
            AbortException: propagate
            Cannot open video file: raise AbortException
            Cannot add image to video: non-fatal
        """
        self.out_file = out_file if out_file is not None else str(Path(self.source_directory, f'{self.city_name.encode("ascii", "ignore").decode()}-{timestamp()}.mp4'))
        while True:
            try:
                out = cv2.VideoWriter(
                    self.out_file,
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    fps,
                    (width, width)
                    )
                break
            except AbortException as e:
                self.log.exception("Aborted rendering video due to AbortException.")
                raise
            except Exception as e:
                if not ask_aborting_error(str(e)):
                    self.log.exception("Aborted rendering video due to ubnknown Exception.")
                    self.gui.root.event_generate('<<Abort>>', when = "tail")
                    raise AbortException("Aborted due to unresolved aborting error.") from e
                else:
                    self.log.warning("Continuing rendering video after unknown Exception.")

        try:
            i = 0
            while i < len(self.image_files):
                if events.abort.is_set():
                    raise AbortException("Abort initiated on another thread.")
                try:
                    img = cv2.imread(self.image_files[i])
                    out.write(img)
                    with self.lock:
                        progress_variable.set(progress_variable.get() + 1)
                    i += 1
                except AbortException as e:
                    self.log.exception("Aborted rendering video due to AbortException.")
                    raise AbortException from e
                except cv2.error as e:
                    #For some reason it still cannot catch cv2 errors
                    if not ask_non_fatal_error(str(e)):
                        i += 1
                        self.log.exception(f"Skipping image '{self.imageFiles[i]}' after cv2 Exception.")
                    else:
                        self.log.warning(f"Retrying adding image '{self.image_files[i]}' to video after cv2 Exception.")
                except Exception as e:
                    if not ask_non_fatal_error(str(e)):
                        i += 1
                        self.log.warning(f"Skipping image '{self.imageFiles[i]}' after unknow Exception.")
                    else:
                        self.log.warning(f"Retrying adding image '{self.image_files[i]}' to video after unknown Exception.")
        except AbortException as e:
            self.log.exception("Aborted rendering video due to AbortException.")
            raise AbortException from e
        finally:
            out.release()
            self.log.info(f"Released video file '{self.out_file}'")

    def cleanup(self) -> None:
        """Clean up after exporting and/or aborting."""
        self.clear_temp_folder()
        self.image_files = []
        self.futures = []
        self.is_running = False
        self.is_aborting = False
        self.log.info("Successful cleanup after export or abort.")



class CSLapse_window():
    
    def __init__(self, root: tkinter.Toplevel, vars: dict, callbacks: dict):
        self.log = logging.getLogger("window")
        self.popups = []
        self.root = root
        self._configure_window()
        self.frames = self.create_frames(vars, callbacks)
        self.set_state("default_state")
        self.log.info("Window initiated successfully.")

    def create_frames(self, vars: dict, callbacks: dict) -> List[Content_frame]:
        """Initialize and save the tkinter frames that make up the gui."""
        self.preview_frame = Preview_frame(self.root, vars, callbacks)
        self.main_frame = Main_frame(self.root, vars, callbacks)
        return [
            self.main_frame,
            self.preview_frame
        ]

    def _configure_window(self) -> None:
        """Configure options for the window and the root widget."""
        self.root.title("CSLapse")
        iconfile = resource_path("media/thumbnail.ico")
        self.root.iconbitmap(default = iconfile)

        self.root.columnconfigure(20, weight = 1)
        self.root.rowconfigure(0, weight = 1)
        self.root.configure(padx = 2, pady = 2)

    def progress_popup(self, var: tkinter.IntVar, maximum: int) -> tkinter.Toplevel:
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

    def set_state(self, state: str) -> None:
        """Set options for the window and the root widget, then for each of the frames."""
        if state == "default_state":
            for p in self.popups:
                p.destroy()
        elif state == "aborting":
            self.root.configure(cursor = constants.preview_cursor)
        elif state == "after_abort":
            for p in self.popups:
                p.destroy()
            self.root.configure(cursor = "")

        for f in self.frames:
            f.set_state(state)
        
        self.log.info(f"Window set to {state}")

    def get_preview(self) -> Preview:
        """Return the preview object of the preview frame."""
        return self.preview_frame.get_preview()

    def set_export_limit(self, limit: int) -> None:
        """Set the size of the progress bar for exported images."""
        self.main_frame.set_export_limit(limit)

    def set_video_limit(self, limit: int) -> None:
        """Set the size of the progressbar for video frames."""
        self.main_frame.set_video_limit(limit)


class Content_frame(ABC):
    """A Frame widget that encloses a section of the gui that is shown or hidden together."""

    def __init__(self, parent: tkinter.Widget, vars: dict, callbacks: dict) -> None:
        self.frame = ttk.Frame(parent)
        self._populate(vars, callbacks)
        self._grid()
        self._create_bindings(callbacks)
        self._configure()

    @abstractmethod
    def _populate(self, vars: dict, callbacks: dict) -> None:
        """Create the widgets contained in the frame."""
        pass

    @abstractmethod
    def _grid(self) -> None:
        """Grid the widgets contained in the frame."""
        pass

    def _create_bindings(self, callbacks: dict) -> None:
        """Bind events to input."""
        pass

    def _configure(self) -> None:
        """Set configuration optionis for the widgets in the frame."""
        pass

    def _show_widgets(self, * args: tkinter.Widget) -> None:
        """Show all argument widgets."""
        for widget in args:
            widget.grid()

    def _hide_widgets(self, * args: tkinter.Widget) -> None:
        """Hide all argument widgets."""
        for widget in args:
            widget.grid_remove()
            
    def _enable_widgets(self, * args: tkinter.Widget) -> None:
        """Set all argument widgets to enabled."""
        for widget in args:
            widget.state(["!disabled"])

    def _disable_widgets(self, * args: tkinter.Widget) -> None:
        """Set all argument widgets to disabled."""
        for widget in args:
            widget.state(["disabled"])  

    def set_state(self, state: str) -> None:
        """Set the layout and visibility of children according to the parameter string."""
        pass

    def show(self) -> None:
        """Show the frame."""
        self.frame.grid()

    def hide(self) -> None:
        """Hide the frame."""
        self.frame.grid_remove()

class Main_frame(Content_frame):
    """Class for the main settings and export options frame."""

    def _populate(self, vars: dict, callbacks: dict) -> None:
        """Create the widgets contained in the main frame."""
        self.fileSelectionBox = ttk.Labelframe(self.frame, text = "Files")
        self.exeSelectLabel = ttk.Label(self.fileSelectionBox, text = "Path to CSLMapViewer.exe")
        self.exePath = ttk.Entry(self.fileSelectionBox, width = 40, state = ["readonly"], textvariable = vars["exe_file"], cursor = constants.clickable)
        self.exeSelectBtn = ttk.Button(self.fileSelectionBox, text = "Select file", cursor = constants.clickable, command = callbacks["select_exe"])
        self.sampleSelectLabel = ttk.Label(self.fileSelectionBox, text = "Select a cslmap file of your city")
        self.samplePath = ttk.Entry(self.fileSelectionBox, state = ["readonly"], textvariable = vars["sample_file"], cursor = constants.clickable)
        self.sampleSelectBtn = ttk.Button(self.fileSelectionBox, text = "Select file", cursor = constants.clickable, command = callbacks["select_sample"])
        self.filesLoading = ttk.Progressbar(self.fileSelectionBox)
        self.filesNumLabel = ttk.Label(self.fileSelectionBox, textvariable = vars["num_of_files"])
        self.filesLoadedLabel = ttk.Label(self.fileSelectionBox, text = "files found")

        self.videoSettingsBox = ttk.Labelframe(self.frame, text = "Video settings")
        self.fpsLabel = ttk.Label(self.videoSettingsBox, text = "Frames per second: ")
        self.fpsEntry = ttk.Entry(self.videoSettingsBox, width = 7, textvariable = vars["fps"])
        self.imageWidthLabel = ttk.Label(self.videoSettingsBox, text = "Width:")
        self.imageWidthInput = ttk.Entry(self.videoSettingsBox, width = 7, textvariable = vars["width"])
        self.imageWidthUnit = ttk.Label(self.videoSettingsBox, text = "pixels")
        self.lengthLabel = ttk.Label(self.videoSettingsBox, text = "Video length:")
        self.lengthInput = ttk.Entry(self.videoSettingsBox, width = 7, textvariable = vars["video_length"])
        self.lengthUnit = ttk.Label(self.videoSettingsBox, text = "frames")

        self.advancedSettingBox = ttk.Labelframe(self.frame, text = "Advanced")
        self.threadsLabel = ttk.Label(self.advancedSettingBox, text = "Threads:")
        self.threadsEntry = ttk.Entry(self.advancedSettingBox, width = 5, textvariable = vars["threads"])
        self.retryLabel = ttk.Label(self.advancedSettingBox, text = "Fail after:")
        self.retryEntry = ttk.Entry(self.advancedSettingBox, width = 5, textvariable = vars["retry"])

        self.progressFrame = ttk.Frame(self.frame)
        self.exportingLabel = ttk.Label(self.progressFrame, text = "Exporting files:")
        self.exportingDoneLabel = ttk.Label(self.progressFrame, textvariable = vars["exporting_done"])
        self.exportingOfLabel = ttk.Label(self.progressFrame, text = " of ")
        self.exportingTotalLabel = ttk.Label(self.progressFrame, textvariable = vars["video_length"])
        self.exportingProgress = ttk.Progressbar(self.progressFrame, orient = "horizontal", mode = "determinate", variable = vars["exporting_done"])
        self.renderingLabel = ttk.Label(self.progressFrame, text = "Renderig video:")
        self.renderingDoneLabel = ttk.Label(self.progressFrame, textvariable = vars["rendering_done"])
        self.renderingOfLabel = ttk.Label(self.progressFrame, text = " of ")
        self.renderingTotalLabel = ttk.Label(self.progressFrame)
        self.renderingProgress = ttk.Progressbar(self.progressFrame, orient = "horizontal", mode = "determinate", variable = vars["rendering_done"])

        self.submitBtn = ttk.Button(self.frame, text = "Export", cursor = constants.clickable, command = callbacks["submit"])
        self.abortBtn = ttk.Button(self.frame, text = "Abort", cursor = constants.clickable, command = callbacks["abort"])

    def _grid(self) -> None:
        """Grid the widgets contained in the main frame."""
        self.frame.grid(column = 0, row = 0, sticky = tkinter.NSEW, padx = 2, pady = 5)

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

    def _create_bindings(self, callbacks: dict) -> None:
        """Bind events to widgets in the main frame."""
        self.exePath.bind('<ButtonPress-1>', lambda event: callbacks["select_exe"]())
        self.samplePath.bind('<ButtonPress-1>', lambda event: callbacks["select_sample"]())

    def _configure(self) -> None:
        """Set configuration optionis for the widgets in the main frame."""
        self.frame.rowconfigure(8, weight = 1)
        self.fileSelectionBox.columnconfigure(1, weight = 1)
        self.progressFrame.columnconfigure(4, weight = 1)

    def set_state(self, state: str) -> None:
        """Set options for the wisgets in the main frame."""
        if state == "start_export":
            self._disable_widgets(
                self.exeSelectBtn,
                self.sampleSelectBtn,
                self.fpsEntry,
                self.imageWidthInput,
                self.lengthInput,
                self.threadsEntry,
                self.retryEntry,
            )
            self._enable_widgets(self.abortBtn)
            self._hide_widgets(
                self.submitBtn, 
                self.renderingProgress,
                self.renderingLabel, 
                self.renderingDoneLabel, 
                self.renderingOfLabel, 
                self.renderingTotalLabel
            )
            self._show_widgets(
                self.progressFrame, 
                self.exportingProgress, 
                self.exportingLabel,
                self.exportingDoneLabel, 
                self.exportingOfLabel, 
                self.exportingTotalLabel, 
                self.abortBtn
            )
        elif state == "start_render":
            self._disable_widgets(
                self.exeSelectBtn,
                self.sampleSelectBtn,
                self.fpsEntry, 
                self.imageWidthInput,
                self.lengthInput, 
                self.threadsEntry, 
                self.retryEntry,
            )
            self._enable_widgets(self.abortBtn)
            self._hide_widgets(
                self.submitBtn, 
                self.exportingProgress, 
                self.exportingLabel, 
                self.exportingDoneLabel,
                self.exportingOfLabel,
                self.exportingTotalLabel
            )
            self._show_widgets(
                self.progressFrame,
                self.renderingProgress,
                self.renderingLabel,
                self.renderingDoneLabel,
                self.renderingOfLabel,
                self.renderingTotalLabel
            )
        elif state == "render_done":
            self._disable_widgets(self.abortBtn)
            self._enable_widgets(
                self.exeSelectBtn,
                self.sampleSelectBtn,
                self.fpsEntry,
                self.imageWidthInput,
                self.lengthInput,
                self.threadsEntry,
                self.retryEntry,
            )
            self._show_widgets(self.submitBtn)
            self._hide_widgets(
                self.progressFrame,
                self.abortBtn
            )
        elif state == "default_state":
            self._disable_widgets(
                self.progressFrame,
                self.abortBtn,
            )
            self._enable_widgets(
                self.submitBtn, 
                self.exeSelectBtn, 
                self.sampleSelectBtn, 
                self.fpsEntry, 
                self.imageWidthInput, 
                self.lengthInput, 
                self.threadsEntry, 
                self.retryEntry, 
            )
            self._hide_widgets(
                self.progressFrame,
                self.abortBtn,
            )
            self._show_widgets(self.submitBtn)
        elif state == "aborting":
            self._disable_widgets(
                self.exeSelectBtn,
                self.sampleSelectBtn,
                self.fpsEntry, 
                self.imageWidthInput, 
                self.lengthInput, 
                self.threadsEntry, 
                self.retryEntry,
                self.abortBtn,
            )
            #self.root.configure(cursor = constants.previewCursor)
        elif state == "after_abort":
            self._disable_widgets(self.abortBtn)
            self._enable_widgets(
                self.exeSelectBtn,
                self.sampleSelectBtn,
                self.fpsEntry, 
                self.imageWidthInput, 
                self.lengthInput, 
                self.threadsEntry, 
                self.retryEntry,
                self.abortBtn,
            )
            self._hide_widgets(
                self.progressFrame,
                self.abortBtn
            )
            self._show_widgets(self.submitBtn)

    def set_export_limit(self, limit: int) -> None:
        """Set the size of the progress bar for exported images."""
        self.exportingProgress.config(maximum = limit)

    def set_video_limit(self, limit: int) -> None:
        """Set the size of the progressbar for video frames."""
        self.renderingProgress.config(maximum = limit)
        self.renderingTotalLabel.configure(text = limit)

class Preview_frame(Content_frame):
    """Class for the always visible right-hand side with the preview."""

    def _populate(self, vars: dict, callbacks: dict) -> None:
        """Create the widgets contained in the preview frame."""
        self.canvasFrame = ttk.Frame(self.frame, relief = tkinter.SUNKEN, borderwidth = 2)
        self.preview = Preview(self.frame)
        self.refreshPreviewBtn = ttk.Button(self.preview.canvas, text = "Refresh", cursor = constants.clickable,
            command = lambda:callbacks["refresh_preview"]())
        self.fitToCanvasBtn = ttk.Button(self.preview.canvas, text = "Fit", cursor = constants.clickable,
            command = self.preview.fitToCanvas)
        self.originalSizeBtn = ttk.Button(self.preview.canvas, text = "100%", cursor = constants.clickable,
            command = self.preview.scaleToOriginal)

        self.canvasSettingFrame = ttk.Frame(self.frame)
        self.zoomLabel = ttk.Label(self.canvasSettingFrame, text = "Areas:")
        self.zoomEntry = ttk.Spinbox(self.canvasSettingFrame, width = 5, textvariable = vars["areas"], from_ = 0.1, increment = 0.1, to = 9.0, wrap = False, validatecommand = (callbacks["areas_entered"], "%d", "%P"), validate = "all", command = lambda: callbacks["areas_changed"]())
        self.zoomSlider = ttk.Scale(self.canvasSettingFrame, orient = tkinter.HORIZONTAL, from_ = 0.1, to = 9.0, variable = vars["areas"], cursor = constants.clickable, command = lambda _: callbacks["areas_changed"]())

        self.rotationLabel = ttk.Label(self.canvasSettingFrame, text = "Rotation:")
        self.rotationSelection = ttk.Menubutton(self.canvasSettingFrame, textvariable = vars["rotation"], cursor = constants.clickable)
        self.rotationSelection.menu = tkinter.Menu(self.rotationSelection, tearoff = 0)
        self.rotationSelection["menu"] = self.rotationSelection.menu
        for option in constants.rotaOptions:
            self.rotationSelection.menu.add_radiobutton(label = option, variable = vars["rotation"])

    def _grid(self) -> None:
        """Grid the widgets contained in the preview frame."""
        self.frame.grid(column = 20, row = 0, sticky = tkinter.NSEW)

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

    def _create_bindings(self, callbacks: dict) -> None:
        """Bind events to widgets in the preview frame."""
        self.preview.createBindings()

    def _configure(self) -> None:
        """Set configuration optionis for the widgets in the preview frame."""
        self.frame.columnconfigure(0, weight = 1)
        self.frame.rowconfigure(0, weight = 1)
        self.canvasFrame.columnconfigure(0, weight = 1)
        self.canvasFrame.rowconfigure(0, weight = 1)
        self.preview.canvas.columnconfigure(0, weight = 1)
        self.preview.canvas.rowconfigure(1, weight = 1)
        self.canvasSettingFrame.columnconfigure(2, weight = 1)
        self.preview.canvas.configure(background = "white")

    def set_state(self, state: str) -> None:
        """Set options for the wisgets in the preview frame."""
        if state == "start_export":
            self._disable_widgets(
                self.zoomSlider, 
                self.zoomEntry
            )
        elif state == "start_render":
            self._disable_widgets(
                self.zoomSlider, 
                self.zoomEntry
            )
        elif state == "render_done":
            self._enable_widgets(
                self.zoomSlider,
                self.zoomEntry
            )
        elif state == "default_state":
            self._disable_widgets(
                self.fitToCanvasBtn, 
                self.originalSizeBtn
            )
            self._enable_widgets(
                self.zoomSlider, 
                self.zoomEntry, 
                self.rotationSelection
            )
            self._hide_widgets(
                self.refreshPreviewBtn,
                self.fitToCanvasBtn,
                self.originalSizeBtn
            )
        elif state == "preview_loading":
            self._disable_widgets(
                self.refreshPreviewBtn,
                self.fitToCanvasBtn,
                self.originalSizeBtn
            )
            #TODO: Add loading image to canvas
            #TODO: Add loading image to refresh button
            self.preview.canvas.configure(cursor = "watch")
        elif state == "preview_loaded":
            self._enable_widgets(
                self.refreshPreviewBtn,
                self.fitToCanvasBtn,
                self.originalSizeBtn
            )
            self._show_widgets(
                self.refreshPreviewBtn,
                self.fitToCanvasBtn,
                self.originalSizeBtn
            )
            self.preview.canvas.configure(cursor = constants.previewCursor)
        elif state == "preview_load_error":
            self._enable_widgets(self.refreshPreviewBtn)
            self._show_widgets(self.refreshPreviewBtn)
            self.preview.canvas.configure(cursor = "")
        elif state == "aborting":
            self._disable_widgets(
                self.zoomSlider,
                self.zoomEntry,
                self.fitToCanvasBtn,
                self.originalSizeBtn,
                self.refreshPreviewBtn
            )
        elif state == "after_abort":
            self._enable_widgets(
                self.zoomSlider,
                self.zoomEntry,
                self.fitToCanvasBtn,
                self.originalSizeBtn,
                self.refreshPreviewBtn
            )
            self.preview.canvas.configure(cursor = constants.previewCursor)

    def get_preview(self) -> Preview:
        """Return the preview object of the frame.""" 
        return self.preview


class Preview():
    """ Object that handles the preview functionaltiy in the GUI"""

    class Printarea():
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

    def __init__(self, parentFrame: tkinter.Widget):
        self.canvas = tkinter.Canvas(parentFrame, cursor = "")
        self.active = False

        self.fullWidth = self.canvas.winfo_screenwidth()    # Width of drawable canvas in pixels
        self.fullHeight = self.canvas.winfo_screenheight()   # Height of drawable canvas in pixels
        self.imageWidth = 0   # Width of original image in pixels
        self.imageHeight = 0  # Height of original image in pixels
        self.preview_image = None # The image object shown on canvas
        self.image_source = None # The image object loaded from the exported preview, unchanged

        self.previewAreas = 0 # Areas printed on the currently active preview image
        self.imageX = 0  # X Coordinate on canvas of pixel in top left of image
        self.imageY = 0  # Y Coordinate on canvas of pixel in top left of image
        self.scaleFactor = 1  # Conversion factor: canvas pixels / original image pixels

        self.placeholderImage = ImageTk.PhotoImage(Image.open(constants.noPreviewImage))
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

        self.preview_image = ImageTk.PhotoImage(self.image_source.resize((int(self.imageWidth * self.scaleFactor), int(self.imageHeight * self.scaleFactor))))
        self.canvas.itemconfigure(self.activeImage, image = self.preview_image)
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

    def justExported(self, image_source, width: int, areas: float) -> None:
        """Show newly exported preview image."""
        self.imageWidth = width
        self.imageHeight = width

        self.previewAreas = areas
        self.printAreaX = 0
        self.printAreaW = width
        self.printAreaY = 0
        self.printAreaH = width
        
        self.image_source = image_source
        self.preview_image = ImageTk.PhotoImage(image_source)
        if self.active:
            self.canvas.itemconfigure(self.activeImage, image = self.preview_image)
        else:
            self.activeImage = self.canvas.create_image(0, 0, anchor = tkinter.CENTER, image = self.preview_image, tags = "activeImage")

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
    log = logging.getLogger("root")
    log.info("")
    log.info("-"*50)
    log.info("")
    log.info(f"CSLapse started with working directory '{current_directory}'.")
    try:
        with App() as app:
            app.root.mainloop()
    except Exception as e:
        log.exception("An unhandled exception occoured.")
        raise
    log.info("CSLapse exited peacefully")


if __name__ == "__main__":
    logging.config.dictConfig(get_logger_config_dict())
    current_directory = Path(__file__).parent.resolve() # current directory
    main()