import tkinter
from tkinter import ttk
from abc import ABC, abstractmethod

from . import constants
from .preview import Preview
from . import settings

"""
Module responsible for tkinter frames in the GUI.

Includes different frame classes derived from abstract base class Content_frame.
"""


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
        self.fileSelectionBox = ttk.Labelframe(self.frame, text="Files")
        self.exeSelectLabel = ttk.Label(
            self.fileSelectionBox, text="Path to CSLMapViewer.exe")
        self.exePath = ttk.Entry(self.fileSelectionBox, state=[
                                 "readonly"], textvariable=vars["exe_file"], cursor=constants.clickable)
        self.exeSelectBtn = ttk.Button(self.fileSelectionBox, text="Select file",
                                       cursor=constants.clickable, command=callbacks["select_exe"])
        self.sampleSelectLabel = ttk.Label(
            self.fileSelectionBox, text="Select a cslmap file of your city")
        self.samplePath = ttk.Entry(self.fileSelectionBox, state=[
                                    "readonly"], textvariable=vars["sample_file"], cursor=constants.clickable)
        self.sampleSelectBtn = ttk.Button(
            self.fileSelectionBox, text="Select file", cursor=constants.clickable, command=callbacks["select_sample"])
        self.filesLoading = ttk.Progressbar(self.fileSelectionBox)
        self.filesNumLabel = ttk.Label(
            self.fileSelectionBox, textvariable=vars["num_of_files"])
        self.filesLoadedLabel = ttk.Label(
            self.fileSelectionBox, text="files found")

        self.videoSettingsBox = ttk.Labelframe(
            self.frame, text="Video settings")
        self.fpsLabel = ttk.Label(
            self.videoSettingsBox, text="Frames per second: ")
        self.fpsEntry = ttk.Entry(
            self.videoSettingsBox, width=7, textvariable=vars["fps"])
        self.imageWidthLabel = ttk.Label(self.videoSettingsBox, text="Width:")
        self.imageWidthInput = ttk.Entry(
            self.videoSettingsBox, width=7, textvariable=vars["width"])
        self.imageWidthUnit = ttk.Label(self.videoSettingsBox, text="pixels")
        self.lengthLabel = ttk.Label(
            self.videoSettingsBox, text="Video length:")
        self.lengthInput = ttk.Entry(
            self.videoSettingsBox, width=7, textvariable=vars["video_length"])
        self.lengthUnit = ttk.Label(self.videoSettingsBox, text="frames")

        self.advancedSettingBox = ttk.Labelframe(self.frame, text="Advanced")
        self.threadsLabel = ttk.Label(self.advancedSettingBox, text="Threads:")
        self.threadsEntry = ttk.Entry(
            self.advancedSettingBox, width=5, textvariable=vars["threads"])
        self.retryLabel = ttk.Label(
            self.advancedSettingBox, text="Fail after:")
        self.retryEntry = ttk.Entry(
            self.advancedSettingBox, width=5, textvariable=vars["retry"])

        self.progressFrame = ttk.Frame(self.frame)
        self.exportingLabel = ttk.Label(
            self.progressFrame, text="Exporting files:")
        self.exportingDoneLabel = ttk.Label(
            self.progressFrame, textvariable=vars["exporting_done"])
        self.exportingOfLabel = ttk.Label(self.progressFrame, text=" of ")
        self.exportingTotalLabel = ttk.Label(
            self.progressFrame, textvariable=vars["video_length"])
        self.exportingProgress = ttk.Progressbar(
            self.progressFrame, orient="horizontal", mode="determinate", variable=vars["exporting_done"])
        self.renderingLabel = ttk.Label(
            self.progressFrame, text="Renderig video:")
        self.renderingDoneLabel = ttk.Label(
            self.progressFrame, textvariable=vars["rendering_done"])
        self.renderingOfLabel = ttk.Label(self.progressFrame, text=" of ")
        self.renderingTotalLabel = ttk.Label(self.progressFrame)
        self.renderingProgress = ttk.Progressbar(
            self.progressFrame, orient="horizontal", mode="determinate", variable=vars["rendering_done"])

        self.submitBtn = ttk.Button(
            self.frame, text="Export", cursor=constants.clickable, command=callbacks["submit"])
        self.abortBtn = ttk.Button(
            self.frame, text="Abort", cursor=constants.clickable, command=callbacks["abort"])

    def _grid(self) -> None:
        """Grid the widgets contained in the main frame."""
        self.frame.grid(column=0, row=1, sticky=tkinter.NSEW, padx=2, pady=5)

        self.fileSelectionBox.grid(
            column=0, row=0, sticky=tkinter.EW, padx=2, pady=5)
        self.exeSelectLabel.grid(
            column=0, row=0, columnspan=3, sticky=tkinter.EW)
        self.exePath.grid(column=0, row=1, columnspan=2, sticky=tkinter.EW)
        self.exeSelectBtn.grid(column=2, row=1)
        self.sampleSelectLabel.grid(
            column=0, row=2, columnspan=3, sticky=tkinter.EW)
        self.samplePath.grid(column=0, row=3, columnspan=2, sticky=tkinter.EW)
        self.sampleSelectBtn.grid(column=2, row=3)
        self.filesNumLabel.grid(column=0, row=4, sticky=tkinter.W)
        self.filesLoadedLabel.grid(column=1, row=4, sticky=tkinter.W)

        self.videoSettingsBox.grid(
            column=0, row=1, sticky=tkinter.EW, padx=2, pady=10)
        self.fpsLabel.grid(column=0, row=0, sticky=tkinter.W)
        self.fpsEntry.grid(column=1, row=0, sticky=tkinter.EW)
        self.imageWidthLabel.grid(column=0, row=1, sticky=tkinter.W)
        self.imageWidthInput.grid(column=1, row=1, sticky=tkinter.EW)
        self.imageWidthUnit.grid(column=2, row=1, sticky=tkinter.W)
        self.lengthLabel.grid(column=0, row=2, sticky=tkinter.W)
        self.lengthInput.grid(column=1, row=2, sticky=tkinter.W)
        self.lengthUnit.grid(column=2, row=2, sticky=tkinter.W)

        self.advancedSettingBox.grid(
            column=0, row=2, sticky=tkinter.EW, padx=2, pady=5)
        self.threadsLabel.grid(column=0, row=0, sticky=tkinter.W)
        self.threadsEntry.grid(column=1, row=0, sticky=tkinter.EW)
        self.retryLabel.grid(column=0, row=1, sticky=tkinter.W)
        self.retryEntry.grid(column=1, row=1, sticky=tkinter.EW)

        self.progressFrame.grid(column=0, row=9, sticky=tkinter.EW)
        self.exportingLabel.grid(column=0, row=0)
        self.exportingDoneLabel.grid(column=1, row=0)
        self.exportingOfLabel.grid(column=2, row=0)
        self.exportingTotalLabel.grid(column=3, row=0)
        self.exportingProgress.grid(
            column=0, row=1, columnspan=5, sticky=tkinter.EW)

        self.renderingLabel.grid(column=0, row=2)
        self.renderingDoneLabel.grid(column=1, row=2)
        self.renderingOfLabel.grid(column=2, row=2)
        self.renderingTotalLabel.grid(column=3, row=2)
        self.renderingProgress.grid(
            column=0, row=3, columnspan=5, sticky=tkinter.EW)

        self.submitBtn.grid(column=0, row=10, sticky=(
            tkinter.S, tkinter.E, tkinter.W))
        self.abortBtn.grid(column=0, row=11, sticky=(
            tkinter.S, tkinter.E, tkinter.W))

    def _create_bindings(self, callbacks: dict) -> None:
        """Bind events to widgets in the main frame."""
        self.exePath.bind('<ButtonPress-1>',
                          lambda event: callbacks["select_exe"]())
        self.samplePath.bind(
            '<ButtonPress-1>', lambda event: callbacks["select_sample"]())

    def _configure(self) -> None:
        """Set configuration optionis for the widgets in the main frame."""
        self.frame.rowconfigure(8, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.fileSelectionBox.columnconfigure(1, weight=1)
        self.progressFrame.columnconfigure(4, weight=1)

    def set_state(self, state: str) -> None:
        """Set options for the wisgets in the main frame."""
        if state == constants.main_page:
            self.show()
        elif state in settings.layout_loader.get_pages():
            self.hide()
        elif state == "start_export":
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
            # self.root.configure(cursor = constants.previewCursor)
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
        self.exportingProgress.config(maximum=limit)

    def set_video_limit(self, limit: int) -> None:
        """Set the size of the progressbar for video frames."""
        self.renderingProgress.config(maximum=limit)
        self.renderingTotalLabel.configure(text=limit)


class Preview_frame(Content_frame):
    """Class for the always visible right-hand side with the preview."""

    def _populate(self, vars: dict, callbacks: dict) -> None:
        """Create the widgets contained in the preview frame."""
        self.canvasFrame = ttk.Frame(
            self.frame, relief=tkinter.SUNKEN, borderwidth=2)
        self.preview = Preview(self.frame, constants.no_preview_image)
        self.refreshPreviewBtn = ttk.Button(self.preview.canvas, text="Refresh", cursor=constants.clickable,
                                            command=lambda: callbacks["refresh_preview"]())
        self.fitToCanvasBtn = ttk.Button(self.preview.canvas, text="Fit", cursor=constants.clickable,
                                         command=self.preview.fitToCanvas)
        self.originalSizeBtn = ttk.Button(self.preview.canvas, text="100%", cursor=constants.clickable,
                                          command=self.preview.scaleToOriginal)

        self.canvasSettingFrame = ttk.Frame(self.frame)
        self.zoomLabel = ttk.Label(self.canvasSettingFrame, text="Areas:")
        self.zoomEntry = ttk.Spinbox(self.canvasSettingFrame, width=5, textvariable=vars["areas"], from_=0.1, increment=0.1, to=9.0, wrap=False, validatecommand=(
            callbacks["areas_entered"], "%d", "%P"), validate="all", command=lambda: callbacks["areas_changed"]())
        self.zoomSlider = ttk.Scale(self.canvasSettingFrame, orient=tkinter.HORIZONTAL, from_=0.1, to=9.0,
                                    variable=vars["areas"], cursor=constants.clickable, command=lambda _: callbacks["areas_changed"]())

        self.rotationLabel = ttk.Label(
            self.canvasSettingFrame, text="Rotation:")
        self.rotationSelection = ttk.Menubutton(
            self.canvasSettingFrame, textvariable=vars["rotation"], cursor=constants.clickable)
        self.rotationSelection.menu = tkinter.Menu(
            self.rotationSelection, tearoff=0)
        self.rotationSelection["menu"] = self.rotationSelection.menu
        for option in constants.rotaOptions:
            self.rotationSelection.menu.add_radiobutton(
                label=option, variable=vars["rotation"])

    def _grid(self) -> None:
        """Grid the widgets contained in the preview frame."""
        self.frame.grid(column=20, row=0, rowspan=2, sticky=tkinter.NSEW)

        self.canvasFrame.grid(column=0, row=0, sticky=tkinter.NSEW)
        self.preview.canvas.grid(column=0, row=0, sticky=tkinter.NSEW)
        self.refreshPreviewBtn.grid(column=1, row=0, sticky=tkinter.NE)
        self.fitToCanvasBtn.grid(column=1, row=2, sticky=tkinter.SE)
        self.originalSizeBtn.grid(column=1, row=3, sticky=tkinter.SE)

        self.canvasSettingFrame.grid(column=0, row=1, sticky=tkinter.NSEW)
        self.zoomLabel.grid(column=0, row=0, sticky=tkinter.W)
        self.zoomEntry.grid(column=1, row=0, sticky=tkinter.W)
        self.zoomSlider.grid(column=2, row=0, sticky=tkinter.EW)

        # Functionality not implemented yet
        # self.rotationLabel.grid(column = 0, row = 1, columnspan = 3, sticky = tkinter.W)
        # self.rotationSelection.grid(column = 1, row = 1, columnspan = 2, sticky = tkinter.W)

    def _create_bindings(self, callbacks: dict) -> None:
        """Bind events to widgets in the preview frame."""
        self.preview.createBindings()

    def _configure(self) -> None:
        """Set configuration optionis for the widgets in the preview frame."""
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        self.canvasFrame.columnconfigure(0, weight=1)
        self.canvasFrame.rowconfigure(0, weight=1)
        self.preview.canvas.columnconfigure(0, weight=1)
        self.preview.canvas.rowconfigure(1, weight=1)
        self.canvasSettingFrame.columnconfigure(2, weight=1)
        self.preview.canvas.configure(background="white")

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
            # TODO: Add loading image to canvas
            # TODO: Add loading image to refresh button
            self.preview.canvas.configure(cursor="watch")
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
            self.preview.canvas.configure(cursor=constants.preview_cursor)
        elif state == "preview_load_error":
            self._enable_widgets(self.refreshPreviewBtn)
            self._show_widgets(self.refreshPreviewBtn)
            self.preview.canvas.configure(cursor="")
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
            self.preview.canvas.configure(cursor=constants.preview_cursor)

    def get_preview(self) -> Preview:
        """Return the preview object of the frame."""
        return self.preview


class Pages_frame(Content_frame):

    def _populate(self, vars: dict, callbacks: dict) -> None:
        """Create the widgets contained in the pages frame."""
        self.general_label = ttk.Label(
            self.frame, text="General", cursor=constants.clickable, background=constants.active_page_color)
        self.drawing_target_label = ttk.Label(
            self.frame, text="Drawing targets", cursor=constants.clickable, background=constants.inactive_page_color)
        self.settings_labels = [
            ttk.Label(self.frame, text=page, cursor=constants.clickable,
                      background=constants.inactive_page_color)
            for page in settings.layout_loader.get_pages()
        ]

    def _grid(self) -> None:
        """Grid the widgets contained in the pages frame."""
        self.frame.grid(column=0, row=0, sticky=tkinter.NSEW, padx=2, pady=5)
        self.general_label.grid(column=0, row=0, sticky=tkinter.NSEW, padx=2)
        for i, label in enumerate(self.settings_labels):
            label.grid(column=i + 1, row=0, sticky=tkinter.NSEW, padx=2)

    def _create_bindings(self, callbacks: dict) -> None:
        """Bind events to widgets in the main frame."""
        self.general_label.bind('<ButtonPress-1>', lambda event,
                                cb=callbacks: cb["set_page"](constants.main_page))
        for widget in self.settings_labels:
            # This doesn't work if the lambda doesn't get the page as kwarg.
            # That way when the events fire and the lambda is run, all the widgets fire the exact same event, the one that was last bound
            widget.bind('<ButtonPress-1>', lambda event,
                        page=widget["text"]: callbacks["set_page"](page))

    def _configure(self) -> None:
        self.frame.columnconfigure(100, weight=1)

    def set_state(self, state: str) -> None:
        """Set options for the widgets in the main frame."""
        if state == constants.main_page:
            for w in self.frame.winfo_children():
                w.configure(background=constants.inactive_page_color)
            self.general_label.configure(
                background=constants.active_page_color)
        elif state in settings.layout_loader.get_pages():
            for w in self.frame.winfo_children():
                if w["text"] == state:
                    w.configure(background=constants.active_page_color)
                else:
                    w.configure(background=constants.inactive_page_color)


class Settings_page(Content_frame):

    def __init__(self, parent: tkinter.Widget, vars: dict, callbacks: dict, page: str) -> None:
        super().__init__(parent, vars, callbacks)
        self.page = page

    def _populate(self, vars: dict, callbacks: dict) -> None:
        """Create the non-setting widgets contained in the frame."""

        self.no_file_frame = ttk.Frame(self.frame)
        self.no_file_label = ttk.Label(
            self.no_file_frame, text=constants.texts.no_settings_message)

        self.xml_error_frame = ttk.Frame(self.frame)
        self.xml_error_label = ttk.Label(
            self.xml_error_frame, text=constants.texts.settings_not_loaded_message)

        self.settings_frame = ttk.Frame(self.frame)

    def _grid(self) -> None:
        """Grid the non-setting widgets contained in the frame."""
        self.frame.grid(column=0, row=1, sticky=tkinter.NSEW, padx=2, pady=5)

        self.no_file_frame.grid(column=0, row=0)
        self.no_file_label.grid(column=0, row=0)

        self.xml_error_frame.grid(column=0, row=0)
        self.xml_error_label.grid(column=0, row=0)

        self.settings_frame.grid(column=0, row=0, sticky=tkinter.NSEW)

    def _configure(self) -> None:
        """Set configuration optionis for the non-setting widgets in the frame."""
        self.hide()
        self._hide_widgets(self.settings_frame, self.xml_error_frame)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        self.settings_frame.columnconfigure(0, weight=1)

    def set_state(self, state: str) -> None:
        """Set options for the widgets in the frame."""
        if state == self.page:
            self.show()
        elif state == constants.main_page:
            self.hide()
        elif state in settings.layout_loader.get_pages():
            self.hide()
        elif state == "xml_loaded":
            self._load_settings()
            self._hide_widgets(self.no_file_frame, self.xml_error_frame)
            self._show_widgets(self.settings_frame)
        elif state == "xml_load_error":
            self._hide_widgets(self.no_file_frame, self.settings_frame)
            self._show_widgets(self.xml_error_frame)

    def _load_settings(self) -> None:
        """Delete the setting widgets and create new ones with state set to the value loaded from file."""
        for child in self.settings_frame.winfo_children():
            child.destroy()

        for subframe in settings.layout_loader.get_page(self.page):
            labelframe = ttk.Labelframe(
                self.settings_frame, text=subframe.get("name"))
            labelframe.grid(row=int(subframe.get("row")),
                            column=0, sticky=tkinter.EW)
            for widget in subframe:
                if widget.tag == "setting":
                    var = tkinter.StringVar()
                    settings.settings_handler.add_variable(
                        var, widget.get("path"), True)
                    if widget.get("type") == "checkbutton":
                        w = ttk.Checkbutton(labelframe, text=widget.get("name"), variable=var, onvalue="true", offvalue="false",
                                            cursor=constants.clickable, command = lambda: settings.settings_handler.change_state())
                    elif widget.get("type") == "integer":
                        w = ttk.Frame(labelframe)
                        label = ttk.Label(w, text=widget.get("name"))
                        entry = ttk.Entry(w, width = 4, textvariable = var, validatecommand = lambda *args: True)
                        label.grid(row = 0, column = 0, sticky = tkinter.W)
                        entry.grid(row = 0, column = 1, sticky = tkinter.W)
                    elif widget.get("type") == "menu":
                        w = ttk.Frame(labelframe)
                        label = ttk.Label(w, text=widget.get("name"))
                        mb = ttk.Menubutton(w, textvariable=var, cursor=constants.clickable)
                        menu = tkinter.Menu(mb, tearoff=0, cursor = constants.clickable)
                        mb["menu"] = menu
                        for option in widget.get("options").split(";"):
                            menu.add_radiobutton(label = option, variable=var, value = option, command = lambda: settings.settings_handler.change_state())

                        label.grid(row = 0, column = 0, sticky = tkinter.W)
                        mb.grid(row = 0, column = 1, sticky = tkinter.W)
                    elif widget.tag == "label":
                        w = ttk.Label(labelframe, text=widget.get("name"))

                    w.grid(row=widget.get("row"), column=widget.get(
                        "column", 0), sticky=tkinter.W)
                
        self.settings_frame.rowconfigure(len(self.settings_frame.winfo_children()), weight = 1)
        write_btn = ttk.Button(self.settings_frame, text="Save settings", cursor = constants.clickable, command = lambda: settings.settings_handler.write())
        write_btn.grid(column = 0, row = len(self.settings_frame.winfo_children()) + 1, sticky = tkinter.EW)
