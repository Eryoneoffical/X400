import logging
import re
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        macros = self._printer.get_gcode_macros()
        self.load_filament = any("LOAD_FILAMENT" in macro.upper() for macro in macros)
        self.unload_filament = any("UNLOAD_FILAMENT" in macro.upper() for macro in macros)

        self.buttons = {
           # 'extrude': self._gtk.Button("extrude", _("Extrude"), "color4"),
            'load': self._gtk.Button("arrow-down", _("Load"), "color3"),
            'unload': self._gtk.Button("arrow-up", _("Unload"), "color2"),
           # 'retract': self._gtk.Button("retract", _("Retract"), "color1"),
            'temperature': self._gtk.Button("heat-up", _("Temperature"), "color4"),
        }
        #self.buttons['extrude'].connect("clicked", self.extrude, "+")
        self.buttons['load'].connect("clicked", self.load_unload, "+")
        self.buttons['unload'].connect("clicked", self.load_unload, "-")
        #self.buttons['retract'].connect("clicked", self.extrude, "-")
        self.buttons['temperature'].connect("clicked", self.menu_item_clicked, {
            "name": "Temperature",
            "panel": "temperature"
        })

        extgrid = self._gtk.HomogeneousGrid()
        limit = 5
        i = 0
        for extruder in self._printer.get_tools():
            if self._printer.extrudercount > 1:
                self.labels[extruder] = self._gtk.Button(f"extruder-{i}", f"T{self._printer.get_tool_number(extruder)}")
            else:
                self.labels[extruder] = self._gtk.Button("extruder", "")
            if len(self._printer.get_tools()) > 1:
                self.labels[extruder].connect("clicked", self.change_extruder, extruder)
            if extruder == self.current_extruder:
                self.labels[extruder].get_style_context().add_class("button_active")
            if i < limit:
                extgrid.attach(self.labels[extruder], i, 0, 1, 1)
                i += 1
        if i < (limit - 1):
            extgrid.attach(self.buttons['temperature'], i + 1, 0, 1, 1)


        self.speed = 10
        self.distances = '10'
        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.attach(extgrid, 0, 0, 4, 1)

        if self._screen.vertical_mode:
           #grid.attach(self.buttons['extrude'], 0, 1, 2, 1)
            #grid.attach(self.buttons['retract'], 2, 1, 2, 1)
            grid.attach(self.buttons['load'], 0, 2, 2, 1)
            grid.attach(self.buttons['unload'], 2, 2, 2, 1)
          #  grid.attach(distbox, 0, 3, 4, 1)
         #   grid.attach(speedbox, 0, 4, 4, 1)
          #  grid.attach(sensors, 0, 5, 4, 1)
        else:
           # grid.attach(self.buttons['extrude'], 0, 2, 1, 1)
            grid.attach(self.buttons['load'], 1, 2, 1, 1)
            grid.attach(self.buttons['unload'], 2, 2, 1, 1)
            #grid.attach(self.buttons['retract'], 3, 2, 1, 1)
         #   grid.attach(distbox, 0, 3, 2, 1)
         #   grid.attach(speedbox, 2, 3, 2, 1)
         #   grid.attach(sensors, 0, 4, 4, 1)

        self.content.add(grid)

    def process_busy(self, busy):
        for button in self.buttons:
            if button == "temperature":
                continue
            self.buttons[button].set_sensitive((not busy))

    def process_update(self, action, data):
        if action == "notify_busy":
            self.process_busy(data)
            return
        if action != "notify_status_update":
            return
        for x in self._printer.get_tools():
            self.update_temp(
                x,
                self._printer.get_dev_stat(x, "temperature"),
                self._printer.get_dev_stat(x, "target"),
                self._printer.get_dev_stat(x, "power"),
                lines=2,
            )

        if ("toolhead" in data and "extruder" in data["toolhead"] and
                data["toolhead"]["extruder"] != self.current_extruder):
            for extruder in self._printer.get_tools():
                self.labels[extruder].get_style_context().remove_class("button_active")
            self.current_extruder = data["toolhead"]["extruder"]
            self.labels[self.current_extruder].get_style_context().add_class("button_active")



    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"dist{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"dist{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def change_extruder(self, widget, extruder):
        logging.info(f"Changing extruder to {extruder}")
        for tool in self._printer.get_tools():
            self.labels[tool].get_style_context().remove_class("button_active")
        self.labels[extruder].get_style_context().add_class("button_active")

        self._screen._ws.klippy.gcode_script(f"T{self._printer.get_tool_number(extruder)}")

    def change_speed(self, widget, speed):
        logging.info(f"### Speed {speed}")
        self.labels[f"speed{self.speed}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"speed{speed}"].get_style_context().add_class("distbutton_active")
        self.speed = speed

    def extrude(self, widget, direction):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.EXTRUDE_REL)
        self._screen._ws.klippy.gcode_script(KlippyGcodes.extrude(f"{direction}{self.distance}", f"{self.speed * 60}"))

    def load_unload(self, widget, direction):
        #self.buttons['load'].set_sensitive(False)
        #self.buttons['unload'].set_sensitive(False)
        if direction == "-":
            self._screen.show_popup_message("It will pause the printer and unload filament itself")
            if not self.unload_filament:
                self._screen.show_popup_message("Macro UNLOAD_FILAMENT not found")
            else:
                self._screen._ws.klippy.gcode_script(f"UNLOAD_FILAMENT ")
        if direction == "+":
            self._screen.show_popup_message("It will pause the printer and load filament itself")
            if not self.load_filament:
                self._screen.show_popup_message("Macro LOAD_FILAMENT not found")
            else:
                self._screen._ws.klippy.gcode_script(f"LOAD_FILAMENT  ")

    def enable_disable_fs(self, switch, gparams, name, x):
        if switch.get_active():
            self._printer.set_dev_stat(x, "enabled", True)
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=1")
            if self._printer.get_stat(x, "filament_detected"):
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
            else:
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
        else:
            self._printer.set_dev_stat(x, "enabled", False)
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=0")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")
