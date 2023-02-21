import tkinter
from tkinter import ttk
from PIL import ImageTk, Image

from pathlib import Path
from filemanager import resource_path

"""
Module repsondible for the preview window on the right.

This includes all the objects on the canvas.
"""


class Preview():
    """ Object that handles the preview functionaltiy in the GUI"""
    # TODO: When exporting, the printarea is set to the areas value when the export finished, not to that when it started Should be fixed.

    class Printarea():
        """Class for the outline of the area that will be exported."""

        def __init__(self, canvas: tkinter.Canvas):
            # X coordinate of the top left corner of the print area on the original image
            self.x_start = 0
            self.y_start = 0  # Y coordinate of the top left corner of the printarea on the original image
            self.width = 0  # Width of printarea on the original image
            self.height = 0  # Height of printarea on the original image

            self.canvas = canvas

            self.north = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill="gray",
                outline="",
                state=tkinter.NORMAL,
                tags=["printarea"]
            )
            self.south = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill="gray",
                outline="",
                state=tkinter.NORMAL,
                tags=["printarea"]
            )
            self.west = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill="gray",
                outline="",
                state=tkinter.NORMAL,
                tags=["printarea"]
            )
            self.east = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill="gray",
                outline="",
                state=tkinter.NORMAL,
                tags=["printarea"]
            )
            self.border = self.canvas.create_rectangle(
                (0, 0, 0, 0),
                fill="",
                outline="red",
                state=tkinter.NORMAL,
                tags=["printarea"],
            )

        def show(self) -> None:
            """Show the outline on canvas."""
            self.canvas.itemconfigure("printarea", state=tkinter.NORMAL)

        def hide(self) -> None:
            """Hide the outline on canvas."""
            self.canvas.itemconfigure("printarea", state=tkinter.HIDDEN)

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
            canvasBottom = image_y + scale_factor * \
                (self.y_start + self.height)
            canvasLeft = image_x + scale_factor * self.x_start
            canvasRight = image_x + scale_factor * (self.x_start + self.width)

            self.canvas.coords(self.north, 0, 0, canvas_w, canvasTop)
            self.canvas.coords(self.south, 0, canvasBottom, canvas_w, canvas_h)
            self.canvas.coords(self.west, 0, canvasTop,
                               canvasLeft, canvasBottom)
            self.canvas.coords(self.east, canvasRight,
                               canvasTop, canvas_w, canvasBottom)
            self.canvas.coords(self.border, canvasLeft,
                               canvasTop, canvasRight, canvasBottom)

        def get_width(self) -> float:
            """Get width of printare in pixels."""
            return self.width
        
        def get_height(self) -> float:
            """Get height of printare in pixels."""
            return self.height

    def __init__(self, parentFrame: tkinter.Widget, default_image: Path):
        self.canvas = tkinter.Canvas(parentFrame, cursor="")
        self.active = False

        # Width of drawable canvas in pixels
        self.fullWidth = self.canvas.winfo_screenwidth()
        # Height of drawable canvas in pixels
        self.fullHeight = self.canvas.winfo_screenheight()
        self.imageWidth = 0   # Width of original image in pixels
        self.imageHeight = 0  # Height of original image in pixels
        self.preview_image = None  # The image object shown on canvas
        self.image_source = None  # The image object loaded from the exported preview, unchanged

        self.previewAreas = 0  # Areas printed on the currently active preview image
        self.imageX = 0  # X Coordinate on canvas of pixel in top left of image
        self.imageY = 0  # Y Coordinate on canvas of pixel in top left of image
        self.scaleFactor = 1  # Conversion factor: canvas pixels / original image pixels

        self.placeholderImage = ImageTk.PhotoImage(
            Image.open(resource_path(default_image)))
        self.canvas.create_image(
            0, 0, image=self.placeholderImage, tags="placeholder")

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
        self.imageX = self.fullWidth / 2 - \
            ((self.fullWidth / 2-self.imageX) / self.scaleFactor) * newFactor
        self.imageY = self.fullHeight / 2 - \
            ((self.fullHeight / 2-self.imageY) / self.scaleFactor) * newFactor

        self.scaleFactor = newFactor

        self.preview_image = ImageTk.PhotoImage(self.image_source.resize(
            (int(self.imageWidth * self.scaleFactor), int(self.imageHeight * self.scaleFactor))))
        self.canvas.itemconfigure(self.activeImage, image=self.preview_image)
        self.canvas.moveto(self.activeImage, x=self.imageX, y=self.imageY)

        self.update_printarea()

    def fitToCanvas(self) -> None:
        """Resize activeImage so that it touches the borders of canvas and the full image is visible, keep aspect ratio."""
        newScaleFactor = min(self.fullWidth / self.printarea.get_width(),
                             self.fullHeight / self.printarea.get_height())
        self.resizeImage(newScaleFactor)
        self.canvas.moveto(self.activeImage, x=(self.fullWidth-int(self.imageWidth * self.scaleFactor)
                                                ) / 2, y=(self.fullHeight-int(self.imageHeight * self.scaleFactor)) / 2)
        self.imageX = (self.fullWidth-self.imageWidth * self.scaleFactor) / 2
        self.imageY = (self.fullHeight-self.imageHeight * self.scaleFactor) / 2

        self.update_printarea()

    def scaleToOriginal(self) -> None:
        """Rescale to the original size of the preview image."""
        self.resizeImage(1)

    def justExported(self, image_source, exported_width: int, exported_areas: float, current_areas: float = None) -> None:
        """Show newly exported preview image."""
        self.imageWidth = exported_width
        self.imageHeight = exported_width
        self.previewAreas = exported_areas

        self.image_source = image_source
        self.preview_image = ImageTk.PhotoImage(image_source)
        if self.active:
            self.canvas.itemconfigure(
                self.activeImage, image=self.preview_image)
        else:
            self.activeImage = self.canvas.create_image(
                0, 0, anchor=tkinter.CENTER, image=self.preview_image, tags="activeImage")


        self.active = True
        self.canvas.itemconfigure("placeholder", state="hidden")

        self.update_printarea(current_areas if current_areas is not None else self.previewAreas)
        self.printarea.raise_above("activeImage")
        self.printarea.show()
        
        self.fitToCanvas()

    def resized(self, event: tkinter.Event) -> None:
        """Handle change in the canvas's size."""
        if self.active:
            # Center of the canvas should stay the center of the canvas when the window is resized
            self.imageX = ((self.imageX+self.imageWidth * self.scaleFactor / 2) *
                           event.width / self.fullWidth)-(self.imageWidth * self.scaleFactor / 2)
            self.imageY = ((self.imageY+self.imageHeight * self.scaleFactor / 2) *
                           event.height / self.fullHeight)-(self.imageHeight * self.scaleFactor / 2)
            self.canvas.moveto(self.activeImage, x=self.imageX, y=self.imageY)

        if not self.active:
            self.canvas.moveto("placeholder", x=str((event.width-self.placeholderImage.width()) / 2),
                               y=str((event.height-self.placeholderImage.height()) / 2))
        self.fullWidth = event.width
        self.fullHeight = event.height

        self.update_printarea()

    def scrolled(self, event: tkinter.Event) -> None:
        """Handle scrolling event (zoom) on canvas."""
        if self.active:
            self.resizeImage(self.scaleFactor * (1+6 / (event.delta)))

    def dragged(self, event: tkinter.Event) -> None:
        """Handle dragging event (panning) on canvas."""
        if self.active:
            deltaX = event.x-self.lastClick[0]
            deltaY = event.y-self.lastClick[1]
            self.canvas.moveto(self.activeImage, x=self.imageX +
                               deltaX, y=self.imageY + deltaY)
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
                self.printarea.resize(
                    self.imageWidth, self.imageHeight, self.previewAreas, new_areas)
            self.printarea.move(self.fullWidth, self.fullHeight,
                                self.imageX, self.imageY, self.scaleFactor)
