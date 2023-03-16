"""All constant values used in the prject."""

# TODO: Separate constants to their respective modules where possible

DEFAULT_EXPORT_WIDTH = 2000
DEFAULT_FPS = 24
DEFAULT_THREADS = 6
DEFAULT_RETRY = 5
DEFAULT_AREAS = 9.0
NO_FILE_TEXT = "No file selected"
ROTA_OPTIONS = ["0°", "90°", "180°", "270°"]


class texts:
    OPEN_EXE_TITLE = "Select CSLMapViewer.exe"
    OPEN_SAMPLE_TITLE = "Select a cslmap save of your city"
    NO_EXE_MESSAGE = "Select CSLMapviewer.exe first!"
    NO_SAMPLE_MESSAGE = "Select a city file first!"
    INVALID_FPS_MESSAGE = "Invalid value for fps!"
    INVALID_WIDTH_MESSAGE = "Invalid value for video width!"
    INVALID_THREADS_MESSAGE = "Invalid value for threads!"
    INVALUD_RETRY_MESSAGE = "Invalid value for retry!"
    INVALID_LENGTH_MESSAGE = "Invalid value for video length!"
    ASK_SAVE_SETTINGS_TITLE = "Apply settings?"
    ASK_SAVE_SETTINGS_MESSAGE = "You have made unsaved changes to the settings. Do you want to save them?"
    ASK_ABORT_MESSAGE = "Are you sure you want to abort? This cannot be undone, all progress will be lost."
    ALREADY_RUNNING_MESSAGE = "Cannot abort export process: No export process to abort or an abort process is already running."
    ABORT_RUNNING_EXIT_AFTER_FINISHED_MESSAGE = "An abort operation is running. The program will exit once it has finished."

    # contentframe.py
    NO_SETTINGS_MESSAGE = "Select CSLMapViewer.exe to load settings!"
    SETTINGS_COULD_NOT_LOAD_MESSAGE = "Settings file could not be loaded correctly."

class filetypes:
    exe = [("Executables", "*.exe"), ("All files", "*")]
    cslmap = [("CSLMap files", ("*.cslmap", "*.cslmap.gz")),
              ("All files", "*")]

# contentframe.py
MAIN_PAGE = "general_page"
INACTIVE_PAGE_BUTTON_COLOR = "#dddddd"
ACTIVE_PAGE_BUTTON_COLOR = "#eeeeee"
CLICKABLE = "hand2"
PREVIEW_CURSOR = "fleur"
NO_PREVIEW_IMAGE = "media/NOIMAGE.png"
SAMPLE_COMMAND = ["__exeFile__", "__source_file__", "-output",
                 "__outFile__", "-silent", "-imagewidth", "2000", "-area", "9"]
SETTINGS_FILE_NAME = "CSLMapViewConfig.xml"

# settings.py
LAYOUT_SOURCE = "layout.xml"
