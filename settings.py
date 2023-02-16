from pathlib import Path
import xml.etree.ElementTree as ET
from typing import NamedTuple, Any
import logging

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

settings = {
        "drawing_target": {
            "Elements": {
                "Terrain": Xml_setting("Terrain", "./RenderTerrain"),
                "Forest": Xml_setting("Forest", "./RenderForest"),
                "Buildings": Xml_setting("Buildings", "./RenderBuilding"),
                "Roads": Xml_setting("Roads", "./RenderRoad"),
                "Railways": Xml_setting("Railways", "./RenderRail")
            },
            "Rail lines": {
                "Train": Xml_setting("Train", "./RenderRailTrain"),
                "Tram": Xml_setting("Tram", "./RenderRailTram"),
                "Metro": Xml_setting("Metro", "./RenderRailMetro"),
                "Monorail": Xml_setting("Monorail", "./RenderRailMonorail"),
                "Cable car": Xml_setting("Cable car", "./RenderRailCableCar")
            },
            "Overlay": {
                "Grid": Xml_setting("Grid", "./RenderGrid"),
                "Districts": Xml_setting("District names", "./RenderDistrictName"),
                "Building names": Xml_setting("Building names", "./RenderBuildingName"),
                "Map symbols": Xml_setting("Map symbols", "./RenderMapSymbol"),
                "Road names": Xml_setting("Road names", "./RenderRoadName"),
                "Park names": Xml_setting("Park names", "./RenderParkName")
            }

        },
        "public_transport": {
            "General": {
                "transport_routes": Xml_setting("Public transport routes", "./RenderTransportRoute"),
                "route_numbering": Xml_setting("Route numberigs", "./RenderTransport")
            },
            "Lines and stops": {
                "Bus lines": Xml_setting("Bus lines", "./RouteMapConfig/RenderBusLine"),
                "Bus stops": Xml_setting("Bus stops", "./RouteMapConfig/RenderBusStop"),
                "Tram lines": Xml_setting("Tram lines", "./RouteMapConfig/RenderTramLine"),
                "Tram stops": Xml_setting("Tram stops", "./RouteMapConfig/RenderTramStop"),
                "Metro lines": Xml_setting("Metro lines", "./RouteMapConfig/RenderMetroLine"),
                "Metro stops": Xml_setting("Metro stops", "./RouteMapConfig/RenderMetroStation"),
                "Train lines": Xml_setting("Train lines", "./RouteMapConfig/RenderTrainLine"),
                "Train stops": Xml_setting("Train stops", "./RouteMapConfig/RenderTrainStation"),
                "Monorail lines": Xml_setting("Monorail lines", "./RouteMapConfig/RenderMonorailLine"),
                "Monorail stops": Xml_setting("Monorail stops", "./RouteMapConfig/RenderMonorailStation"),
                "Blimp lines": Xml_setting("Blimp lines", "./RouteMapConfig/RenderBlimpLine"),
                "Blimp stops": Xml_setting("Blimp stops", "./RouteMapConfig/RenderBlimpStop"),
                "Ferry lines": Xml_setting("Ferry lines", "./RouteMapConfig/RenderFerryLine"),
                "Ferry stops": Xml_setting("Ferry stops", "./RouteMapConfig/RenderFerryHarbor")
            },
            "Misc": {
                "merge_bus_tram": Xml_setting("Merge bus and tram stops nearby", "./RouteMapConfig/MergeBusTramStop"),
                "merge_train_metro": Xml_setting("Merge train and metro stations nearby", "./RouteMapConfig/MergeTrainMetroStaion"),
                "auto_color": Xml_setting("Auto coloring", "./RouteMapConfig/AutoColoring"),
                "widen_line": Xml_setting("Widen line if paths share same segment", "./RouteMapConfig/WidenOnSharedLines"),
                "detect_end_loops": Xml_setting("Detect end loops", "./RouteMapConfig/DetectEndLoop"),
                "mark_one_way": Xml_setting("Mark one way routes", "./RouteMapConfig/MarkOneWayRoutes"),
                "merged_numbering": Xml_setting("Merged route numberings", "./RouteMapConfig/UseMergedRouteNumberings")
            }

        }

    }

class Settings():
    """Class handling the external xml settings file."""

    def __init__(self, file: Path = None):
        self.file = Path
        self.log = logging.getLogger("xmlparser")

        self.tree = None
        self.root = None

        if file is not None:
            self.tree = ET.parse(self.file)
            self.root = self.tree.getroot()
            self.log.info(f"Successfully connected settings file {self.file}")
        else:
            self.log.info("Initiated settings object with no file")
        self.settings = {}
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
                        self.log.warning("Trying to save settings with no file")
            assert file.exists()
            self.file = file
            self.tree = ET.parse(self.file)
            self.root = self.tree.getroot()
            self.state_changed = False
            self.log.info(f"Successfully connected settings file {self.file}")
            return True
        except Exception as e:
            self.log.exception("An exception occoured while trying to assign file")
            raise

    def write(self) -> None:
        """Write all local changes to the source file."""
        if self.tree is not None:
            for setting in self.settings.values():
                self.tree.find(setting.xmlpath).text = self._to_xml(setting.var.get())
            self.tree.write(self.file)
            self.state_changed = False
            self.log.info("Changes written to file")
        else:
            self.log.warning("Trying to write with no file")

    def add_variable(self, key: str, var: Any, xmlpath: str, set_var: bool = False) -> None:
        """
        Add a variable to the settings that can be changed.

        var must have a type that supports get() and set() methods
        
        If set_var is set, set it to the value fund in self.file.
        """
        self.settings[key] = Local_setting(var, xmlpath)
        if set_var:
            self.settings[key].var.set(self._to_var(self.get(key)))

    def get(self, setting_key: str) -> Any:
        """
        Return the value associated with setting_key.
        
        Raise KeyError if there is no value associated with the key.
        """
        if setting_key in self.settings:
            return self._to_var(self.tree.find(self.settings[setting_key].xmlpath).text)
        else:
            raise KeyError(f"Key {setting_key} not in settings dictionary")

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

settings_handler = Settings()