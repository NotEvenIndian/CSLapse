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
from functools import wraps

import constants
from filemanager import resource_path
import settings
import contentframe

# Suggestions for any sort of improvement are welcome.


class AbortException(Exception):
    pass


class ExportError(Exception):
    pass


def get_logger_config_dict(debug: bool = False) -> dict:
    """Return the logger configuration dictionary."""
    dictionary = {
        "version": 1,
        "formatters": {
            "basic": {
                "format": "%(asctime)s %(levelname)s [%(name)s/%(threadName)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "debug": {
                "format": "%(levelname)s  [%(name)s/%(threadName)s] %(message)s"
            }
        },
        "handlers": {
            "logfile": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": logging.INFO,
                "formatter": "basic",
                "filename": "./cslapse.log",
                "maxBytes": 200000,
                "backupCount": 1
            }
        },
        "loggers": {
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
            },
            "xmlparser": {
                "level": logging.DEBUG,
                "handlers": ["logfile"]
            }
        }
    }
    
    if debug:
        dictionary["handlers"]["debugfile"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": logging.DEBUG,
            "formatter": "debug",
            "filename": "./debug.log",
        }

    return dictionary


class ThreadCollector(threading.Thread):
    """Cancel and join all running threads and futures except for threads in keep_alive.

    Optionally count finished threads so far in counter
    """

    def __init__(self,
                 keep_alive: List[threading.Thread],
                 futures: List[concurrent.futures.Future] = None,
                 counter: tkinter.IntVar = None,
                 callback: Callable[[], None] = None
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


def ask_retry_on_fail(on_fail: Callable = None) -> None:
    """
    Try running the function and prompt the user when n exception occours.

    The user may choose to retryy the function or not,
    in which case on_fail is executed and None is returned.
    """

    def decorator(function: Callable[..., None]) -> None:
        log = logging.getLogger("root")

        @wraps(function)
        def wrapper(*args, **kwargs):
            while True:
                try:
                    return function(*args, **kwargs)
                except AbortException as e:
                    log.exception("Aborting operation without asking")
                    break
                except Exception as e:
                    if not ask_non_fatal_error(f"An exception occoured:\n{str(e)}\nDo you want to retry?"):
                        log.exception("Not retrying operation after exception")
                        break
            if on_fail is not None:
                on_fail()
            return None
        return wrapper

    return decorator


def ask_save_settings(function: Callable):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if settings.settings_handler.has_state_changed():
            action = messagebox.askyesnocancel(
                title=constants.texts.save_settings, message=constants.texts.ask_save_settings)
            if action is None:
                return
            elif action:
                settings.settings_handler.write()
        function(*args, **kwargs)

    return wrapper


class App():
    """Class overlooking everything - the gui, the variables, the constants and more."""

    def __enter__(self) -> object:
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up after the object"""
        if self.exporter.temp_folder is not None and self.exporter.temp_folder.exists():
            rmtree(self.exporter.temp_folder, ignore_errors=True)
        collector = ThreadCollector(
            [threading.current_thread()], counter=self.vars["thread_collecting"])
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
            "exe_file": tkinter.StringVar(value=constants.noFileText),
            "sample_file": tkinter.StringVar(value=constants.noFileText),
            "num_of_files": tkinter.IntVar(value=0),
            "fps": tkinter.IntVar(value=constants.defaultFPS),
            "width": tkinter.IntVar(value=constants.defaultExportWidth),
            "threads": tkinter.IntVar(value=constants.defaultThreads),
            "retry": tkinter.IntVar(value=constants.defaultRetry),
            "rotation": tkinter.StringVar(value=constants.rotaOptions[0]),
            "areas": tkinter.StringVar(value=constants.defaultAreas),
            "video_length": tkinter.IntVar(value=0),
            "exporting_done": tkinter.IntVar(value=0),
            "rendering_done": tkinter.IntVar(value=0),
            "thread_collecting": tkinter.IntVar(value=0),
            "preview_source": ""
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
            self.preview.justExported(self.vars["preview_source"], int(
                self.vars["width"].get()), float(self.vars["areas"].get()))
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
            self.window.set_video_limit(
                self.exporter.get_num_of_exported_files())
            self.window.set_state("start_render")
        if events.exporting_done.is_set():
            events.exporting_done.clear()
            self.cleanup_after_success()
            self.window.set_state("render_done")
            show_info(
                f"See your timelapse at {self.exporter.out_file}", "Video completed")
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
            target=self.export_sample,
            args=(
                cmd,
                self.exporter.get_file(self.vars["video_length"].get() - 1),
                1
            )
        )
        exporter_thread.start()

    @ask_retry_on_fail(on_fail=events.preview_load_error.set)
    def export_sample(self, command: List[str], sample: str, retry: int) -> None:
        """
        Export png from the cslmap file that will be the given frame of the video.

        This function should run on a separate thread.
        """
        exported = self.exporter.export_file(
            sample,
            command,
            retry
        )
        with self.lock:
            self.vars["preview_source"] = Image.open(exported)
        events.preview_loaded.set()

    def open_file(self, title: str, filetypes: List[Tuple], default_directory: str = None) -> str:
        """Open file opening dialog box and return the full path to the selected file."""
        filename = filedialog.askopenfilename(
            title=title, initialdir=default_directory, filetypes=filetypes)
        self.log.info(f"File '{filename}' selected.")
        return filename

    def select_sample(self) -> None:
        """Ask user to select sample file from dialog and set variables accordingly."""
        selected_file = self.open_file(
            constants.texts.openSampleTitle, constants.filetypes.cslmap)
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
                self.vars["video_length"].set(
                    min(self.vars["video_length"].get(), num_of_files))
            self.refresh_preview()
        else:
            self.vars["sample_file"].set(constants.noFileText)

    def select_exe(self) -> None:
        """Ask user to select SCLMapViewer.exe from dialog and set variables accordingly."""
        selected_file = self.open_file(
            constants.texts.openSampleTitle, constants.filetypes.exe)
        if selected_file != "":
            self.vars["exe_file"].set(selected_file)
            constants.sampleCommand[0] = selected_file
            self.exporter.set_exefile(selected_file)
            if self.load_settings_xml(Path(selected_file).parent):
                self.window.set_state("xml_loaded")
            else:
                self.window.set_state("xml_load_error")
            self.refresh_preview()
        else:
            self.vars["exe_file"].set(constants.noFileText)

    def load_settings_xml(self, directory: Path) -> bool:
        """
        Attempt to load the settings xml file to Settings object.

        Return True if successful, False otherwise.
        """
        while True:
            try:
                xml_file = Path(directory, constants.xml_file_name)
                settings.settings_handler.set_file(xml_file)
                return True
            except Exception as e:
                if ask_non_fatal_error(f"Could not load settings file {xml_file}.\n{str(e)}"):
                    self.log.info(
                        "Retrying after failed attempt to load settings file")
                    continue
                else:
                    self.log.exception(
                        "Returning fter failed to load settings file.")
                    return False

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
            raise AbortException("Abort initiated on thread other than main.")
        else:
            self.exporter.set_abort()
            self.window.set_state("aborting")

            self.log.info("Abort procedure started on main thread.")

            self.vars["thread_collecting"].set(0)
            collector = ThreadCollector([threading.current_thread()], self.exporter.get_futures(
            ), counter=self.vars["thread_collecting"], callback=events.abort_finished.set)
            self.window.progress_popup(
                self.vars["thread_collecting"], collector.total())
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
            "refresh_preview": self.refresh_pressed,
            "set_page": lambda new_state: self.window.set_state(new_state)
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

    @ask_save_settings
    def refresh_pressed(self) -> None:
        """
        Callback to be called when the refresh preview button is pressed.

        Check if all required variables are set correctly and if yes, refresh the preview.
        Show a warning message otherwise.
        """
        if self.vars["exe_file"].get() == constants.noFileText:
            show_warning(title="Warning", message=constants.texts.noExeMessage)
            return
        if self.vars["sample_file"].get() == constants.noFileText:
            show_warning(title="Warning",
                         message=constants.texts.noSampleMessage)
            return
        sample = self.exporter.get_file(self.vars["video_length"].get() - 1)
        if sample == "":
            show_warning(title="Warning",
                         message="Not enough files to match video frames!")
            return
        self.refresh_preview()

    @ask_save_settings
    def submit_pressed(self) -> None:
        """Check if all conditions are satified and start exporting if yes. Show warning if not."""
        self.log.info(
            f'Submit button pressed with entry data:\nexefile={self.vars["exe_file"].get()}\nfps={self.vars["fps"].get()}\nwidth={self.vars["width"].get()}\nvideolenght={self.vars["video_length"].get()}\nthreads={self.vars["threads"].get()}\nretry={self.vars["retry"].get()}')
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
                    self.showWoarning(
                        "An export operation is already running!")
        except Exception:
            self.log.exception("Incorrect entry data.")
            show_warning(
                "Something went wrong. Check your settings and try again.")

    def abort_pressed(self) -> None:
        """Ask user if really wants to abort. Generate abort tkinter event if yes."""
        if messagebox.askyesno(title="Abort action?", message=constants.texts.askAbort):
            self.log.info("Abort initiated by abort button.")
            self.root.event_generate('<<Abort>>', when="tail")

    def areas_changed(self) -> None:
        """
        Callback to be called when the areas slider is moved.

        Updates the printarea rectangle to the appropriate size.
        """
        self.preview.update_printarea(float(self.vars["areas"].get()))

    def close_pressed(self) -> None:
        """Ask user if really wnats to quit. If yes, initiate abort and exit afterwards"""
        if self.exporter.is_running:
            if messagebox.askyesno(title="Are you sure you want to exit?", message=constants.texts.askAbort):
                events.close.set()
                self.root.event_generate('<<Abort>>', when="tail")
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
        # Path type, the directory where cslmap files are loaded from
        self.source_directory = None
        self.city_name = None  # string, the name of the city
        self.temp_folder = None  # Path type, the location where temporary files are created
        self.raw_files = []    # Collected cslmap files with matching city name
        self.image_files = []
        self.futures = []   # concurrent.futures.Future objects that are exporting images
        self.is_running = False  # If currently there is exporting going on
        self.is_aborting = False  # If an abort pre=ocess is in progress
        self.out_file = ""  # Name of output file

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
        return (not self.is_aborting) and self.is_running

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
                        rmtree(self.temp_folder, ignore_errors=False)
                    self.temp_folder.mkdir()
                self.log.info("Tempfolder cleared or created successfully.")
                return
            except Exception as e:
                self.log.exception(
                    "Error while clearing / creating temp_folder.")
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
                lambda filename: filename.name.startswith(
                    self.city_name) and ".cslmap" in filename.suffixes,
                self.source_directory.iterdir()
            ))
        return len(self.raw_files)

    def export_file(self, source_file: str, cmd: List[str], retry: int) -> str:
        """Call CSLMapView to export one image file and return outfile's name.

        Exceptions:
            Abortexpression: propagates
            Cannot export file after [retry] tries: raises ExportError
        """

        # Prepare command that calls cslmapview.exe
        new_file_name = Path(self.temp_folder, source_file.stem.encode(
            "ascii", "ignore").decode()).with_suffix(".png")
        cmd[1] = str(source_file)
        cmd[3] = str(new_file_name)

        self.log.info(f"Export of file '.../{source_file.name}' 'started")

        # call CSLMapview.exe to export the image. Try again at fail, abort after many tries.
        for n in range(retry):
            try:
                # Call the program in a separate process
                subprocess.run(cmd, shell=False, stderr=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, check=False)

                # Return prematurely on abort
                # Needs to be after export command, otherwise won't work. Probably dead Lock.
                if events.abort.is_set():
                    raise AbortException("Abort initiated on another thread.")

                # Ensure that the image file was successfully created.
                assert new_file_name.exists()

                self.log.info(
                    f"Successfully exported file '.../{new_file_name.name}' after {n+1} attempts.")
                return str(new_file_name)
            except AbortException as error:
                self.log.exception(
                    f"Aborted while exporting file '{new_file_name}'.")
                raise AbortException from error
            except subprocess.CalledProcessError as e:
                self.log.exception(
                    f"Process error while exporting file '{new_file_name}'.")
                pass
            except AssertionError as e:
                self.log.warning(
                    f"File '{new_file_name}' does not exist after exporting.")
                pass
            except Exception as e:
                self.log.exception(
                    f"Unknown exception while exporting file '{new_file_name}'.")
                pass

        self.log.warning(
            f"Failed to export file after {retry} attempts with command '{' '.join(cmd)}'")

        # Throw exception after repeatedly failing
        raise ExportError(str('Could not export file.\nCommand: "'
                              + ' '.join(cmd)
                              + '"\nThis problem might arise normally, usually when resources are taken.'))

    def export(self, width: int, areas: float, length: int, fps: int, threads: int, retry: int, image_files_counter: tkinter.IntVar, video_counter: tkinter.IntVar) -> bool:
        """Start exporting and return True if possible, False if exporting is already running."""
        if self.is_running or self.is_aborting:
            return False
        self.prepare(image_files_counter, video_counter)
        threading.Thread(
            target=self.run,
            args=(
                width,
                areas,
                length,
                fps,
                threads,
                retry,
                image_files_counter,
                video_counter
            ),
            daemon=True
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
            self.export_image_files(
                width, areas, length, threads, retry, image_files_var)
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
                    executor.submit(
                        self.export_image, self.raw_files[i], cmd[:], retry, progress_variable)
                )
        if events.abort.is_set():
            raise AbortException("Abort initiated on another thread.")

        # Sort array as the order might have changed during threading
        self.image_files = sorted(self.image_files)

    @ask_retry_on_fail()
    def export_image(self, source: str, cmd: List[str], retry: int, progress_variable: tkinter.IntVar) -> None:
        """Call the given command to export the given image, add filename to self.imageFiles.

        This function should run on a separate thread for each file.

        Exceptions:
            AbortException: propagate
            ExportError: non-fatal
            Other exceptions: non-fatal
        """
        new_file_name = self.export_file(source, cmd, retry)
        with self.lock:
            self.image_files.append(new_file_name)
            progress_variable.set(progress_variable.get() + 1)

    @ask_retry_on_fail(events.abort.set)
    def prepare_video_file(self, width: int, fps: int, out_file: Path = None) -> cv2.VideoWriter:
        """Create the video file with the required parameters."""
        return cv2.VideoWriter(
            self.out_file,
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, width)
        )

    def render_video(self, width: int, fps: int, progress_variable: tkinter.IntVar, out_file: Path = None) -> None:
        """Create an mp4 video file from all the exported images.

        Exceptions:
            Raise AbortException if abort is requested
            AbortException: propagate
            Cannot open video file: raise AbortException
            Cannot add image to video: non-fatal
        """
        self.out_file = out_file if out_file is not None else str(Path(
            self.source_directory, f'{self.city_name.encode("ascii", "ignore").decode()}-{timestamp()}.mp4'))

        out = self.prepare_video_file(width, fps, out_file)

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
                    self.log.exception(
                        "Aborted rendering video due to AbortException.")
                    raise AbortException from e
                except cv2.error as e:
                    # For some reason it still cannot catch cv2 errors
                    if not ask_non_fatal_error(str(e)):
                        i += 1
                        self.log.exception(
                            f"Skipping image '{self.imageFiles[i]}' after cv2 Exception.")
                    else:
                        self.log.warning(
                            f"Retrying adding image '{self.image_files[i]}' to video after cv2 Exception.")
                except Exception as e:
                    if not ask_non_fatal_error(str(e)):
                        i += 1
                        self.log.warning(
                            f"Skipping image '{self.imageFiles[i]}' after unknow Exception.")
                    else:
                        self.log.warning(
                            f"Retrying adding image '{self.image_files[i]}' to video after unknown Exception.")
        except AbortException as e:
            self.log.exception(
                "Aborted rendering video due to AbortException.")
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

    def create_frames(self, vars: dict, callbacks: dict) -> List[contentframe.Content_frame]:
        """Initialize and save the tkinter frames that make up the gui."""
        self.pages_frame = contentframe.Pages_frame(self.root, vars, callbacks)
        self.preview_frame = contentframe.Preview_frame(
            self.root, vars, callbacks)
        self.main_frame = contentframe.Main_frame(self.root, vars, callbacks)
        setting_frames = [contentframe.Settings_page(
            self.root, vars, callbacks, page) for page in settings.layout_loader.get_pages()]
        return [
            self.pages_frame,
            self.main_frame,
            self.preview_frame,
            *setting_frames
        ]

    def _configure_window(self) -> None:
        """Configure options for the window and the root widget."""
        self.root.title("CSLapse")
        iconfile = resource_path("media/thumbnail.ico")
        self.root.iconbitmap(default=iconfile)

        self.root.columnconfigure(20, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.root.configure(padx=2, pady=2)

    def progress_popup(self, var: tkinter.IntVar, maximum: int) -> tkinter.Toplevel:
        """Return a GUI popup window with a progressbar tied to var."""
        win = tkinter.Toplevel(cursor="watch")
        label = ttk.Label(win, text="Collecting threads: ")
        progressLabel = ttk.Label(win, textvariable=var)
        ofLabel = ttk.Label(win, text=" of ")
        totalLabel = ttk.Label(win, text=maximum)
        progressBar = ttk.Progressbar(win, variable=var, maximum=maximum)

        label.grid(row=0, column=0, sticky=tkinter.EW)
        progressLabel.grid(row=0, column=1, sticky=tkinter.EW)
        ofLabel.grid(row=0, column=2, sticky=tkinter.EW)
        totalLabel.grid(row=0, column=3, sticky=tkinter.EW)
        progressBar.grid(row=1, column=0, columnspan=5, sticky=tkinter.EW)

        win.columnconfigure(4, weight=1)
        win.configure(padx=5, pady=5, border=1, relief=tkinter.SOLID)

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
            self.root.configure(cursor=constants.preview_cursor)
        elif state == "after_abort":
            for p in self.popups:
                p.destroy()
            self.root.configure(cursor="")

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
    debug = False
    gettrace = getattr(sys, 'gettrace', None)
    if gettrace is not None and gettrace():
        debug = True
    logging.config.dictConfig(get_logger_config_dict(debug))
    current_directory = Path(__file__).parent.resolve()  # current directory
    main()
