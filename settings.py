from pathlib import Path
import xml.etree.ElementTree as ET
from typing import NamedTuple, Any, List
import logging

import constants
from filemanager import resource_path

"""
Module responsible for interacting with the CSLMapView config file.

Usage should be restricted to the settings dictionary containing
a tree of the settings to be shown in the gui (to be changed to xml)
and the settings_handler object that can manipulate data and the file.
"""


class Xml_setting(NamedTuple):
    text: str
    xmlpath: str


class Local_setting(NamedTuple):
    var: Any
    xmlpath: str


class Settings():
    """Class handling the external xml settings file."""

    def __init__(self, file: Path = None):
        self.file = file
        self.log = logging.getLogger("xmlparser")

        self.tree = None
        self.root = None

        if file is not None:
            self.tree = ET.parse(self.file)
            self.root = self.tree.getroot()
            self.log.info(f"Successfully connected settings file {self.file}")
        else:
            self.log.info("Initiated settings object with no file")
        self.settings = []
        self.state_changed = False

    def set_file(self, file: Path, save_changes: bool = False) -> bool:
        """
        Change the used file to file.

        If save_changes is True, write the changes to the old file before closing.
        Return whether the file was successfully changed.
        """
        try:
            if save_changes:
                if self.state_changed:
                    if self.file is not None:
                        self.write()
                    else:
                        self.log.warning(
                            "Trying to save settings with no file")
            assert file.exists()
            self.file = file
            self.tree = ET.parse(self.file)
            self.root = self.tree.getroot()
            self.state_changed = False
            self.log.info(f"Successfully connected settings file {self.file}")
            return True
        except Exception as e:
            self.log.exception(
                "An exception occoured while trying to assign file")
            raise

    def write(self) -> None:
        """Write all local changes to the source file."""
        if self.tree is not None:
            for setting in self.settings:
                self.tree.find(setting.xmlpath).text = self._to_xml(
                    setting.var.get())
            self.tree.write(self.file)
            self.state_changed = False
            self.log.info("Changes written to file")
        else:
            self.log.warning("Trying to write with no file")

    def add_variable(self, var: Any, xmlpath: str, set_var: bool = False) -> None:
        """
        Add a variable to the settings that can be changed.

        var must have a type that supports get() and set() methods

        If set_var is set, set it to the value found in self.file.
        """
        self.settings.append(Local_setting(var, xmlpath))
        last_index = len(self.settings) - 1
        if set_var:
            self.settings[last_index].var.set(
                self._to_var(self.get(last_index)))

    def get(self, index: int) -> Any:
        """
        Return the value at the given index.
        """
        return self._to_var(self.tree.find(self.settings[index].xmlpath).text)

    def _to_xml(self, setting: Any) -> str:
        """Change the given setting to the corresponding text in the xml file."""
        if setting == 0:
            return "false"
        elif setting == 1:
            return "true"
        else:
            return str(setting)

    def _to_var(self, setting: str) -> Any:
        """Change the given setting to the corresponding value for the local setting variables."""
        if setting == "true":
            return 1
        elif setting == "false":
            return 0
        else:
            return setting

    def change_state(self) -> None:
        """Signal that the state of some elements have been changed."""
        self.state_changed = True

    def has_state_changed(self) -> bool:
        """Return whether the state of some elements is different from the xml file."""
        return self.state_changed


class Layout_loader():
    """Class responsible for reading the layout of settings pages from the xml file."""

    def __init__(self, file: Path):
        self.file = file
        self.log = logging.getLogger("xmlparser")

        self.tree = ET.parse(self.file)
        self.root = self.tree.getroot()
        self.log.info(f"Successfully connected layout file {self.file}")

        self.pages = [page.get("name") for page in self.root]

    def get_page(self, key: str) -> ET.Element:
        return self.root.find(f"page[@name='{key}']")

    def get_pages(self) -> List[str]:
        return self.pages


layout_loader = Layout_loader(resource_path(constants.layout_source))
settings_handler = Settings()
