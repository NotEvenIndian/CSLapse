"""All constant values used in the prject."""

abort = False
sampleExportWidth = 2000
defaultFPS = 24
defaultExportWidth = 2000
defaultThreads = 6
defaultRetry = 5
defaultAreas = 9.0
noFileText = "No file selected"
rotaOptions = ["0°", "90°", "180°", "270°"]
main_page = "general_page"


class texts:
    openExeTitle = "Select CSLMapViewer.exe"
    openSampleTitle = "Select a cslmap save of your city"
    noExeMessage = "Select CSLMapviewer.exe first!"
    noSampleMessage = "Select a city file first!"
    no_settings_message = "Select CSLMapViewer.exe to load settings!"
    settings_not_loaded_message = "Settings file could not be loaded correctly."
    invalidLengthMessage = "Invalid video length!"
    invalidLengthMessage = "Invalid video length!"
    invalidLengthMessage = "Invalid video length!"
    invalidLengthMessage = "Invalid video length!"
    invalidLengthMessage = "Invalid video length!"
    save_settings = "Apply settings?"
    ask_save_settings = "You have made unsaved changes to the settings. Do you want to save them?"
    askAbort = "Are you sure you want to abort? This cannot be undone, all progress will be lost."
    abortAlreadyRunning = "Cannot abort export process: No export process to abort or an abort process is already running."
    exitAfterAbortEnded = "An abort operation is running. The program will exit once it has finished."


class filetypes:
    exe = [("Executables", "*.exe"), ("All files", "*")]
    cslmap = [("CSLMap files", ("*.cslmap", "*.cslmap.gz")),
              ("All files", "*")]


inactive_page_color = "#dddddd"
active_page_color = "#eeeeee"
clickable = "hand2"
preview_cursor = "fleur"
no_preview_image = "media/NOIMAGE.png"
layout_source = "layout.xml"
sampleCommand = ["__exeFile__", "__source_file__", "-output",
                 "__outFile__", "-silent", "-imagewidth", "2000", "-area", "9"]
xml_file_name = "CSLMapViewConfig.xml"
