# -*- coding: utf-8 -*-
import json
import logging
import os
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango
from contextlib import suppress
from math import pi, sqrt
from statistics import median
from time import time
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.grid = self._gtk.HomogeneousGrid()
        self.grid.set_row_homogeneous(False)
        self.pos_z = 0.0
        self.extrusion = 100
        self.speed_factor = 1.0
        self.speed = 100
        self.req_speed = 0
        self.f_layer_h = self.layer_h = 1
        self.oheight = 0.0
        self.current_extruder = None
        self.fila_section = 0.0
        self.filename_label = self.filename = self.prev_pos = self.prev_gpos = None
        self.can_close = False
        self.flow_timeout = self.animation_timeout = None
        self.file_metadata = self.fans = {}
        self.state = "standby"
        self.timeleft_type = "auto"
        self.progress = self.zoffset = self.flowrate = self.vel = 0.0
        self.flowstore = []
        self.mm = _("mm")
        self.mms = _("mm/s")
        self.mms2 = _("mm/s²")
        self.mms3 = _("mm³/s")
        self.status_grid = self.move_grid = self.time_grid = self.extrusion_grid = None

        data = ['pos_x', 'pos_y', 'pos_z', 'time_left', 'duration', 'slicer_time', 'file_time',
                'filament_time', 'est_time', 'speed_factor', 'req_speed', 'max_accel', 'extrude_factor', 'zoffset',
                'zoffset', 'filament_used', 'filament_total', 'advance', 'layer', 'total_layers', 'height',
                'flowrate']

        for item in data:
            self.labels[item] = Gtk.Label(label="-")
            self.labels[item].set_vexpand(True)
            self.labels[item].set_hexpand(True)

        self.labels['left'] = Gtk.Label(_("Left:"))
        self.labels['elapsed'] = Gtk.Label(_("Elapsed:"))
        self.labels['total'] = Gtk.Label(_("Total:"))
        self.labels['slicer'] = Gtk.Label(_("Slicer:"))
        self.labels['file_tlbl'] = Gtk.Label(_("File:"))
        self.labels['fila_tlbl'] = Gtk.Label(_("Filament:"))
        self.labels['speed_lbl'] = Gtk.Label(_("Speed:"))
        self.labels['accel_lbl'] = Gtk.Label(_("Acceleration:"))
        #self.labels['flow'] = Gtk.Label(_("Flow:"))
        self.labels['zoffset_lbl'] = Gtk.Label(_("Z offset:"))
        self.labels['fila_used_lbl'] = Gtk.Label(_("Filament used:"))
        self.labels['fila_total_lbl'] = Gtk.Label(_("Filament total:"))
        self.labels['pa_lbl'] = Gtk.Label(_("Pressure Advance:"))
       #self.labels['flowrate_lbl'] = Gtk.Label(_("Flowrate:"))
        self.labels['height_lbl'] = Gtk.Label(_("Height:"))
        #self.labels['layer_lbl'] = Gtk.Label(_("Layer:"))

        for fan in self._printer.get_fans():
            # fan_types = ["controller_fan", "fan_generic", "heater_fan"]
            if fan == "fan":
                name = " "
            elif fan.startswith("fan_generic"):
                name = " ".join(fan.split(" ")[1:])[:1].upper() + ":"
                if name.startswith("_"):
                    continue
            else:
                continue
            self.fans[fan] = {
                "name": name,
                "speed": "-"
            }

        self.labels['file'] = Gtk.Label(label="Filename")
        self.labels['file'].get_style_context().add_class("printing-filename")
        self.labels['file'].set_hexpand(True)
        self.labels['status'] = Gtk.Label(label="Status")
        self.labels['status'].get_style_context().add_class("printing-status")
        self.labels['lcdmessage'] = Gtk.Label()
        self.labels['lcdmessage'].get_style_context().add_class("printing-status_message")

        for label in self.labels:
            self.labels[label].set_halign(Gtk.Align.START)
            self.labels[label].set_ellipsize(Pango.EllipsizeMode.END)

        fi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        fi_box.add(self.labels['file'])
        fi_box.add(self.labels['status'])
       # fi_box.add(self.labels['lcdmessage'])
        self.grid.attach(fi_box, 1, 0, 3, 1)

        self.labels['darea'] = Gtk.DrawingArea()
        self.labels['darea'].connect("draw", self.on_draw)

        box = Gtk.Box()
        box.set_halign(Gtk.Align.CENTER)
        self.labels['progress_text'] = Gtk.Label(label="0%")
        self.labels['progress_text'].get_style_context().add_class("printing-progress-text")
        box.add(self.labels['progress_text'])

        overlay = Gtk.Overlay()
        overlay.set_hexpand(True)
        overlay.add(self.labels['darea'])
        overlay.add_overlay(box)
        self.grid.attach(overlay, 0, 0, 1, 1)

        self.labels['thumbnail'] = self._gtk.Image()
        self.labels['info_grid'] = Gtk.Grid()
        self.labels['info_grid'].attach(self.labels['thumbnail'], 0, 0, 1, 1)
        if self._printer.get_tools():
            self.current_extruder = self._printer.get_stat("toolhead", "extruder")
            diameter = float(self._printer.get_config_section(self.current_extruder)['filament_diameter'])
            self.fila_section = pi * ((diameter / 2) ** 2)

        self.buttons = {}
        self.create_buttons()
        self.buttons['button_grid'] = self._gtk.HomogeneousGrid()
        self.buttons['button_grid'].set_vexpand(False)
        self.grid.attach(self.buttons['button_grid'], 0, 3, 4, 1)

        self.create_status_grid()
        self.create_extrusion_grid()
        self.create_time_grid()
        self.create_move_grid()
        self.grid.attach(self.labels['info_grid'], 0, 1, 4, 2)
        self.switch_info(info=self.status_grid)
        self.content.add(self.grid)
        self.time_count = 0
    def create_status_grid(self, widget=None):

        buttons = {
            'speed': self._gtk.Button("speed+", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            'z': self._gtk.Button("home-z", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            'extrusion': self._gtk.Button("extrude", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            'fan': self._gtk.Button("fan", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            'elapsed': self._gtk.Button("clock", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            'left': self._gtk.Button("hourglass", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
        }
        for button in buttons:
            buttons[button].set_halign(Gtk.Align.START)
        buttons['fan'].connect("clicked", self.menu_item_clicked, {"panel": "fan", "name": _("Fan")})
        self.buttons.update(buttons)

        self.labels['temp_grid'] = Gtk.Grid()
        nlimit = 2 if self._screen.width <= 500 else 3
        n = 0
        self.buttons['extruder'] = {}
        if self._printer.get_tools():
            self.current_extruder = self._printer.get_stat("toolhead", "extruder")
            for i, extruder in enumerate(self._printer.get_tools()):
                self.labels[extruder] = Gtk.Label(label="-")
                self.buttons['extruder'][extruder] = self._gtk.Button(f"extruder-{i}", "", None, self.bts,
                                                                      Gtk.PositionType.LEFT, 1)
                self.buttons['extruder'][extruder].set_label(self.labels[extruder].get_text())
                self.buttons['extruder'][extruder].connect("clicked", self.menu_item_clicked,
                                                           {"panel": "temperature", "name": _("Temperature"),
                                                            'extra': self.current_extruder})
                self.buttons['extruder'][extruder].set_halign(Gtk.Align.START)
            self.labels['temp_grid'].attach(self.buttons['extruder'][self.current_extruder], n, 0, 1, 1)
            n += 1
        else:
            self.current_extruder = None
        self.buttons['heater'] = {}
        if self._printer.has_heated_bed():
            self.buttons['heater']['heater_bed'] = self._gtk.Button("bed", "", None, self.bts, Gtk.PositionType.LEFT, 1)
            self.labels['heater_bed'] = Gtk.Label(label="-")
            self.buttons['heater']['heater_bed'].set_label(self.labels['heater_bed'].get_text())
            self.buttons['heater']['heater_bed'].connect("clicked", self.menu_item_clicked,
                                                         {"panel": "temperature", "name": _("Temperature"),
                                                          'extra': 'heater_bed'})
            self.buttons['heater']['heater_bed'].set_halign(Gtk.Align.START)
            self.labels['temp_grid'].attach(self.buttons['heater']['heater_bed'], n, 0, 1, 1)
            n += 1
        for dev in self._printer.get_heaters():
            if n >= nlimit:
                break
            if dev.startswith("heater_generic"):
                self.buttons['heater'][dev] = self._gtk.Button("heater", "", None, self.bts, Gtk.PositionType.LEFT, 1)
                self.labels[dev] = Gtk.Label(label="-")
                self.buttons['heater'][dev].set_label(self.labels[dev].get_text())
                self.buttons['heater'][dev].connect("clicked", self.menu_item_clicked,
                                                    {"panel": "temperature", "name": _("Temperature"), "extra": dev})
                self.buttons['heater'][dev].set_halign(Gtk.Align.START)
                self.labels['temp_grid'].attach(self.buttons['heater'][dev], n, 0, 1, 1)
                n += 1
        extra_item = not self._show_heater_power
        if self.ks_printer_cfg is not None:
            titlebar_items = self.ks_printer_cfg.get("titlebar_items", "")
            if titlebar_items is not None:
                titlebar_items = [str(i.strip()) for i in titlebar_items.split(',')]
                logging.info(f"Titlebar items: {titlebar_items}")
                for device in self._printer.get_heaters():
                    if device.startswith("temperature_sensor"):
                        name = " ".join(device.split(" ")[1:])
                        for item in titlebar_items:
                            if name == item:
                                if extra_item:
                                    extra_item = False
                                    nlimit += 1
                                if n >= nlimit:
                                    break
                                self.buttons['heater'][device] = self._gtk.Button("heat-up", "", None, self.bts,
                                                                                  Gtk.PositionType.LEFT, 1)
                                self.labels[device] = Gtk.Label(label="-")
                                self.buttons['heater'][device].set_label(self.labels[device].get_text())
                                self.buttons['heater'][device].connect("clicked", self.menu_item_clicked,
                                                                       {"panel": "temperature",
                                                                        "name": _("Temperature")})
                                self.buttons['heater'][device].set_halign(Gtk.Align.START)
                                self.labels['temp_grid'].attach(self.buttons['heater'][device], n, 1, 1, 1)
                                n += 1
                                break

        szfe = Gtk.Grid()
        szfe.set_column_homogeneous(True)
       # szfe.attach(self.buttons['speed'], 1, 0, 1, 1)
        szfe.attach(self.buttons['left'], 0, 0, 2, 1)
        szfe.attach(self.buttons['elapsed'], 1, 0, 1, 1)
        szfe.attach(self.buttons['elapsed'], 1, 0, 1, 1)
       # if self._printer.get_tools():
       #     szfe.attach(self.buttons['extrusion'], 0, 1, 3, 1)
     #   if self._printer.get_fans():
      #      szfe.attach(self.buttons['fan'], 2, 1, 2, 1)

        info = Gtk.Grid()
        info.set_row_homogeneous(True)
        info.get_style_context().add_class("printing-info")
        info.attach(self.labels['temp_grid'], 0, 1, 1, 1)
        info.attach(self.labels['lcdmessage'], 0, 4, 1, 1)

        info.attach(szfe, 0, 1, 4, 4)
       # info.attach(self.buttons['elapsed'], 0, 3, 1, 1)
      #  info.attach(self.buttons['left'], 0, 2, 3, 1)
        self.status_grid = info

    def create_extrusion_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color1", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)
        goback.get_style_context().add_class("printing-info")

        info = Gtk.Grid()
        info.set_hexpand(True)
        info.set_vexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("printing-info-secondary")
        info.attach(goback, 0, 0, 1, 6)
      #  info.attach(self.labels['flow'], 1, 0, 1, 1)
       # info.attach(self.labels['extrude_factor'], 2, 0, 1, 1)
       # info.attach(self.labels['flowrate_lbl'], 1, 1, 1, 1)
       # info.attach(self.labels['flowrate'], 2, 1, 1, 1)
        info.attach(self.labels['pa_lbl'], 1, 2, 1, 1)
        info.attach(self.labels['advance'], 2, 2, 1, 1)
        info.attach(self.labels['fila_used_lbl'], 1, 3, 1, 1)
        info.attach(self.labels['filament_used'], 2, 3, 1, 1)
        info.attach(self.labels['fila_total_lbl'], 1, 4, 1, 1)
        info.attach(self.labels['filament_total'], 2, 4, 1, 1)
        self.extrusion_grid = info
        self.buttons['extrusion'].connect("clicked", self.switch_info, self.extrusion_grid)

    def create_move_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color2", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)
        goback.get_style_context().add_class("printing-info")

        pos_box = Gtk.Box(spacing=5)
        pos_box.add(self.labels['pos_x'])
        pos_box.add(self.labels['pos_y'])
        pos_box.add(self.labels['pos_z'])

        info = Gtk.Grid()
        info.set_hexpand(True)
        info.set_vexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("printing-info-secondary")
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels['speed_lbl'], 1, 0, 1, 1)
        info.attach(self.labels['req_speed'], 2, 0, 1, 1)
        info.attach(self.labels['accel_lbl'], 1, 1, 1, 1)
        info.attach(self.labels['max_accel'], 2, 1, 1, 1)
        info.attach(pos_box, 1, 2, 2, 1)
        info.attach(self.labels['zoffset_lbl'], 1, 3, 1, 1)
        info.attach(self.labels['zoffset'], 2, 3, 1, 1)
        info.attach(self.labels['height_lbl'], 1, 4, 1, 1)
        info.attach(self.labels['height'], 2, 4, 1, 1)
        #info.attach(self.labels['layer_lbl'], 1, 5, 1, 1)
        #info.attach(self.labels['layer'], 2, 5, 1, 1)
        self.move_grid = info
       # self.buttons['z'].connect("clicked", self.switch_info, self.move_grid)
       # self.buttons['speed'].connect("clicked", self.switch_info, self.move_grid)

    def create_time_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color3", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)

        info = Gtk.Grid()
        info.get_style_context().add_class("printing-info-secondary")
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels['elapsed'], 1, 0, 1, 1)
        info.attach(self.labels['duration'], 2, 0, 1, 1)
        info.attach(self.labels['left'], 1, 1, 1, 1)
        info.attach(self.labels['time_left'], 2, 1, 1, 1)
        info.attach(self.labels['total'], 1, 2, 1, 1)
        info.attach(self.labels['est_time'], 2, 2, 1, 1)
        info.attach(self.labels['slicer'], 1, 3, 1, 1)
        info.attach(self.labels['slicer_time'], 2, 3, 1, 1)
        info.attach(self.labels['file_tlbl'], 1, 4, 1, 1)
        info.attach(self.labels['file_time'], 2, 4, 1, 1)
        info.attach(self.labels['fila_tlbl'], 1, 5, 1, 1)
        info.attach(self.labels['filament_time'], 2, 5, 1, 1)
        self.time_grid = info
       # self.buttons['elapsed'].connect("clicked", self.switch_info, self.time_grid)
       # self.buttons['left'].connect("clicked", self.switch_info, self.time_grid)

    def switch_info(self, widget=None, info=None):
        if not info:
            logging.debug("No info to attach")
            return
        if self._screen.vertical_mode:
            self.labels['info_grid'].remove_row(1)
            self.labels['info_grid'].attach(info, 0, 1, 1, 1)
        else:
            self.labels['info_grid'].remove_column(1)
            self.labels['info_grid'].attach(info, 1, 0, 1, 1)
        self.labels['info_grid'].show_all()

    def on_draw(self, da, ctx):
        w = da.get_allocated_width()
        h = da.get_allocated_height()
        r = min(w, h) * .42

        ctx.set_source_rgb(0.13, 0.13, 0.13)
        ctx.set_line_width(self._gtk.font_size * .75)
        ctx.translate(w / 2, h / 2)
        ctx.arc(0, 0, r, 0, 2 * pi)
        ctx.stroke()
        ctx.set_source_rgb(0.718, 0.110, 0.110)
        ctx.arc(0, 0, r, 3 / 2 * pi, 3 / 2 * pi + (self.progress * 2 * pi))
        ctx.stroke()

    def activate(self):
        #if self.flow_timeout is None:
         #   self.flow_timeout = GLib.timeout_add_seconds(2, self.update_flow)
        self._screen.base_panel_show_all()

    def deactivate(self):
        #if self.flow_timeout is not None:
        #    GLib.source_remove(self.flow_timeout)
            self.flow_timeout = None

    def create_buttons(self):

        self.buttons = {
            'cancel': self._gtk.Button("stop", _("Cancel"), "color2"),
            'control': self._gtk.Button("settings", _("Settings"), "color3"),
            'fine_tune': self._gtk.Button("fine-tune", _("Speed +"), "color4"),
            'menu': self._gtk.Button("complete", _("Main Menu"), "color4"),
            'pause': self._gtk.Button("pause", _("Pause"), "color1"),
            'restart': self._gtk.Button("refresh", _("Print Again"), "color3"),
            'queue_print': self._gtk.Button("refresh", _("Print Job"), "color3"),
            'resume': self._gtk.Button("resume", _("Resume"), "color1"),
            'save_offset_probe': self._gtk.Button("home-z", _("Save Z") + "\n" + "Probe", "color1"),
            'save_offset_endstop': self._gtk.Button("home-z", _("Save Z") + "\n" + "Endstop", "color2"),
        }
        self.buttons['cancel'].connect("clicked", self.cancel)
        self.buttons['control'].connect("clicked", self._screen._go_to_submenu, "")
        self.buttons['fine_tune'].connect("clicked", self.menu_item_clicked, {
            "panel": "fine_tune", "name": _("Fine Tuning")})
        self.buttons['menu'].connect("clicked", self.close_panel)
        self.buttons['pause'].connect("clicked", self.pause)
        self.buttons['restart'].connect("clicked", self.restart)
        self.buttons['queue_print'].connect("clicked", self.queue_print)
        self.buttons['resume'].connect("clicked", self.resume)
        self.buttons['save_offset_probe'].connect("clicked", self.save_offset, "probe")
        self.buttons['save_offset_endstop'].connect("clicked", self.save_offset, "endstop")

    def save_offset(self, widget, device):
        sign = "+" if self.zoffset > 0 else "-"
        label = Gtk.Label()
        if device == "probe":
            probe = self._printer.get_probe()
            saved_z_offset = probe['z_offset'] if probe else "?"
            label.set_label(_("Apply %s%.3f offset to Probe?") % (sign, abs(self.zoffset))
                            + "\n\n"
                            + _("Saved offset: %s") % saved_z_offset)
        elif device == "endstop":
            label.set_label(_("Apply %s%.3f offset to Endstop?") % (sign, abs(self.zoffset)))
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = self._gtk.HomogeneousGrid()
        grid.attach(label, 0, 0, 1, 1)
        buttons = [
            {"name": _("Apply"), "response": Gtk.ResponseType.APPLY},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        dialog = self._gtk.Dialog(self._screen, buttons, grid, self.save_confirm, device)
        dialog.set_title(_("Save Z"))

    def save_confirm(self, dialog, response_id, device):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.APPLY:
            if device == "probe":
                self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_PROBE")
            if device == "endstop":
                self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_ENDSTOP")
            self._screen._ws.klippy.gcode_script("SAVE_CONFIG")

    def restart(self, widget):
        if self.filename:
            self.disable_button("restart")
            if self.state == "error":
                script = {"script": "SDCARD_RESET_FILE"}
                self._screen._send_action(None, "printer.gcode.script", script)
            self._screen._ws.klippy.print_start(self.filename)
            logging.info(f"Starting print: {self.filename}")
            self.new_print()
        else:
            logging.info(f"Could not restart {self.filename}")

    def queue_print(self, widget):

        out = subprocess.run(['curl', '-s', '-d', '/server/job_queue/start', 'http://127.0.0.1/server/job_queue/start'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True  # Python >= 3.7 also accepts "text=True"
                             )
        logging.debug(out.stdout)
        self.disable_button("queue_print")
    def resume(self, widget):
        self._screen._ws.klippy.print_resume()
        self._screen.show_all()

    def pause(self, widget):
        self.disable_button("pause", "resume")
        self._screen._ws.klippy.print_pause()
        self._screen.show_all()

    def cancel(self, widget):
        buttons = [
            {"name": _("Cancel Print"), "response": Gtk.ResponseType.OK},
            {"name": _("Go Back"), "response": Gtk.ResponseType.CANCEL}
        ]
        if len(self._printer.get_stat("exclude_object", "objects")) > 1:
            buttons.insert(0, {"name": _("Exclude Object"), "response": Gtk.ResponseType.APPLY})
        label = Gtk.Label()
        label.set_markup(_("Are you sure you wish to cancel this print?"))
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        dialog = self._gtk.Dialog(self._screen, buttons, label, self.cancel_confirm)
        dialog.set_title(_("Cancel"))

    def cancel_confirm(self, dialog, response_id):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.APPLY:
            self.menu_item_clicked(None, {"panel": "exclude", "name": _("Exclude Object")})
            return
        if response_id == Gtk.ResponseType.CANCEL:
            self.enable_button("pause", "cancel")
            return
        logging.debug("Canceling print")
        self.set_state("cancelling")
        self.disable_button("pause", "resume", "cancel")
        self._screen._ws.klippy.print_cancel()

    def close_panel(self, widget=None):
        if self.can_close:
            logging.debug("Closing job_status panel")
            self._screen.state_ready(wait=False)

    def enable_button(self, *args):
        for arg in args:
            self.buttons[arg].set_sensitive(True)

    def disable_button(self, *args):
        for arg in args:
            self.buttons[arg].set_sensitive(False)

    def _callback_metadata(self, newfiles, deletedfiles, modifiedfiles):
        if not bool(self.file_metadata) and self.filename in modifiedfiles:
            self.update_file_metadata()
            self._files.remove_file_callback(self._callback_metadata)

    def new_print(self):
        self._screen.close_screensaver()
        self.update_progress(0.0)

    def process_update(self, action, data):
        if action == "notify_gcode_response":

           # self._screen.show_popup_message(data)
            if "action:cancel" in data:
                self.set_state("cancelled")
            elif "action:paused" in data:
                self.set_state("paused")

            elif "action:resumed" in data:
                self.set_state("printing")
            elif "runout" in data or "tangled" in data:
                try:
                     
                    self._screen.show_panel("extrude", _("Printing"))
                    self._screen.show_dialog_message(str(data).replace('//',''))
                except Exception as e:
                    logging.error(f"runout error:\n{e}")
                    pass

            return
        elif action != "notify_status_update":
            return

        for x in self._printer.get_tools():
            if x in self.buttons['extruder']:
                self.update_temp(
                    x,
                    self._printer.get_dev_stat(x, "temperature"),
                    self._printer.get_dev_stat(x, "target"),
                    self._printer.get_dev_stat(x, "power"),
                )
                self.buttons['extruder'][x].set_label(self.labels[x].get_text())
        for x in self._printer.get_heaters():
            if x in self.buttons['heater']:
                self.update_temp(
                    x,
                    self._printer.get_dev_stat(x, "temperature"),
                    self._printer.get_dev_stat(x, "target"),
                    self._printer.get_dev_stat(x, "power"),
                )
                self.buttons['heater'][x].set_label(self.labels[x].get_text())

        if "display_status" in data and "message" in data["display_status"] and data['display_status']['message'] is not None:
            if '=bed_obj' in data['display_status']['message']:
                self._screen.show_dialog_message(f"Paused, please clean the bed plate first!  \n\n{data['display_status']['message']} ", '/tmp/p.png')
                data['display_status']['message'] = ''
            self.labels['lcdmessage'].set_label(
                f"{data['display_status']['message'] if data['display_status']['message'] is not None else ''}"
            )

        with suppress(KeyError):
            if data["toolhead"]["extruder"] != self.current_extruder:
                self.labels['temp_grid'].remove_column(0)
                self.labels['temp_grid'].insert_column(0)
                self.current_extruder = data["toolhead"]["extruder"]
                self.labels['temp_grid'].attach(self.buttons['extruder'][self.current_extruder], 0, 0, 1, 1)
                self._screen.show_all()
        with suppress(KeyError):
            self.labels['max_accel'].set_label(f"{data['toolhead']['max_accel']:.0f} {self.mms2}")
        with suppress(KeyError):
            self.labels['advance'].set_label(f"{data['extruder']['pressure_advance']:.2f}")


   #     if self.time_count % 4 != 1 and "print_stats" not in data:  # slow down the cpu consume
    #        return
        if "gcode_move" in data or self.state in ["printing", "paused"]:
            self.time_count = self.time_count + 1
        if "gcode_move" in data:
            with suppress(KeyError):
                self.speed = round(float(data["gcode_move"]["speed_factor"]) * 100)
                self.speed_factor = float(data["gcode_move"]["speed_factor"])
                self.labels['speed_factor'].set_label(f"{self.speed:3}%")
        if "gcode_move" in data and self.time_count % 20 == 1:

            with suppress(KeyError):
                self.pos_z = round(float(data['gcode_move']['gcode_position'][2]), 2)
                self.buttons['z'].set_label(f"Z: {self.pos_z:6.2f}{f'/{self.oheight}' if self.oheight > 0 else ''}")
            with suppress(KeyError):
                self.extrusion = round(float(data["gcode_move"]["extrude_factor"]) * 100)
                self.labels['extrude_factor'].set_label(f"{self.extrusion:3}%")
            with suppress(KeyError):
                self.req_speed = round(float(data["gcode_move"]["speed"]) / 60 * self.speed_factor)
                self.labels['req_speed'].set_label(
                    f"{self.speed}% "
               #     f"{f'{self.mms}' if self.vel < 1000 and self.req_speed < 1000 and self._screen.width > 500 else ''}"
                )
                self.buttons['speed'].set_label(self.labels['req_speed'].get_label())
            with suppress(KeyError):
                self.zoffset = float(data["gcode_move"]["homing_origin"][2])
                self.labels['zoffset'].set_label(f"{self.zoffset:.3f} {self.mm}")
        if "motion_report" in data:
            with suppress(KeyError):
                self.labels['pos_x'].set_label(f"X: {data['motion_report']['live_position'][0]:6.2f}")
                self.labels['pos_y'].set_label(f"Y: {data['motion_report']['live_position'][1]:6.2f}")
                self.labels['pos_z'].set_label(f"Z: {data['motion_report']['live_position'][2]:6.2f}")
                pos = data["motion_report"]["live_position"]
                now = time()
                if self.prev_pos is not None:
                    interval = (now - self.prev_pos[1])
                    # Calculate Flowrate
                    evelocity = (pos[3] - self.prev_pos[0][3]) / interval
                    self.flowstore.append(self.fila_section * evelocity)
                self.prev_pos = [pos, now]
            with suppress(KeyError):
                self.vel = float(data["motion_report"]["live_velocity"])
                self.labels['req_speed'].set_label(
                    f"{self.speed}% "
                    #f"{f'{self.mms}' if self.vel < 1000 and self.req_speed < 1000 and self._screen.width > 500 else ''}"
                )
                self.buttons['speed'].set_label(self.labels['req_speed'].get_label())
            with suppress(KeyError):
                self.flowstore.append(self.fila_section * float(data["motion_report"]["live_extruder_velocity"]))
        fan_label = ""
        for fan in self.fans:
            self.fans[fan]['speed'] = f"{self._printer.get_fan_speed(fan) * 100:3.0f}%"
            fan_label += f" {self.fans[fan]['name']}{self.fans[fan]['speed']}"
       # if fan_label:
        #    self.buttons['fan'].set_label(fan_label[:12])
        if "print_stats" in data:
            with suppress(KeyError):
                self.set_state(
                    data["print_stats"]["state"],
                    msg=f'{data["print_stats"]["message"] if "message" in data["print_stats"] else ""}'
                )
            with suppress(KeyError):
                self.update_filename(data['print_stats']["filename"])
            with suppress(KeyError):
                if 'filament_used' in data["print_stats"]:
                    self.labels['filament_used'].set_label(
                        f"{float(data['print_stats']['filament_used']) / 1000:.1f} m"
                    )
            if 'info' in data["print_stats"]:
                with suppress(KeyError):
                    if data["print_stats"]['info']['total_layer'] is not None:
                        self.labels['total_layers'].set_label(f"{data['print_stats']['info']['total_layer']}")
                with suppress(KeyError):
                    if data["print_stats"]['info']['current_layer'] is not None:
                        self.labels['layer'].set_label(
                            f"{data['print_stats']['info']['current_layer']} / "
                            #f"{self.labels['total_layers'].get_text()}"
                        )
            elif "layer_height" in self.file_metadata and "object_height" in self.file_metadata:
                self.labels['layer'].set_label(
                    f"{1 + round((self.pos_z - self.f_layer_h) / self.layer_h)} / "
                   # f"{self.labels['total_layers'].get_text()}"
                )
            if self.state in ["printing", "paused"] and self.time_count % 20 == 1:
                self.update_time_left()

    def update_flow(self):
        return True
        if not self.flowstore:
            self.flowstore.append(0)
        self.flowrate = median(self.flowstore)
        self.flowstore = []
        self.labels['flowrate'].set_label(f"{self.flowrate:.1f} {self.mms3}")
        self.buttons['extrusion'].set_label(f"{self.extrusion:3}% {self.flowrate:5.1f} {self.mms3}")
        return True

    def update_time_left(self):

        total_duration = float(self._printer.get_stat('print_stats', 'total_duration'))
        print_duration = float(self._printer.get_stat('print_stats', 'print_duration'))
        #logging.debug(f"elapsed:{print_duration},{self.format_time(print_duration)}")
        if 'filament_total' in self.file_metadata and not self.file_metadata['filament_total']:  # No-extrusion
            print_duration = total_duration
        fila_used = float(self._printer.get_stat('print_stats', 'filament_used'))
        progress = float(self._printer.get_stat("virtual_sdcard", "progress"))
        self.labels["duration"].set_label(self.format_time(total_duration))
        elapsed_label = f"{self.labels['elapsed'].get_text()}  {self.labels['duration'].get_text()}"
        self.buttons['elapsed'].set_label(elapsed_label)
        estimated = 0
        slicer_time = filament_time = file_time = None
        timeleft_type = self._config.get_config()['main'].get('print_estimate_method', 'auto')

        with suppress(KeyError):
            if self.file_metadata['estimated_time'] > 0:
                # speed_factor compensation based on empirical testing
                spdcomp = sqrt(self.speed_factor)
                slicer_time = ((self.file_metadata['estimated_time']) / spdcomp)
        self.labels["slicer_time"].set_label(self.format_time(slicer_time))

        with suppress(Exception):
            if self.file_metadata['filament_total'] > fila_used:
                filament_time = (print_duration / (fila_used / self.file_metadata['filament_total']))
        self.labels["filament_time"].set_label(self.format_time(filament_time))
        with suppress(ZeroDivisionError):
            file_time = (print_duration / progress)
        self.labels["file_time"].set_label(self.format_time(file_time))


        if timeleft_type == "file":
            estimated = file_time
        elif timeleft_type == "filament":
            estimated = filament_time
        elif slicer_time is not None:
            if timeleft_type == "slicer":
                estimated = slicer_time
            elif filament_time is not None and progress > 0.14:
                # Weighted arithmetic mean (Slicer is the most accurate)
                estimated = (slicer_time * 3 + filament_time + file_time) / 5
            else:
                # At the begining file and filament are innacurate
                estimated = slicer_time
        #logging.debug(f"filament_time:{filament_time} slicer_time:{slicer_time} ")
        if slicer_time is not None and filament_time is not None:
            if estimated > slicer_time:
                estimated = slicer_time
            else:
                estimated = filament_time
            #logging.debug(f"filament_time:{filament_time} slicer_time:{slicer_time} ")
        if estimated is None:
            estimated = slicer_time
             
        if estimated < 1:


            if filament_time is not None and filament_time > 1:
                estimated = (filament_time + file_time) / 2
            estimated = file_time
            if file_time is None:
                estimated = slicer_time
        if print_duration < 12*60:# print time seconds
            estimated = slicer_time
     #   self.labels["est_time"].set_label(self.format_time(estimated))

        self.labels["time_left"].set_label(self.format_eta(estimated, print_duration))
        remaining_label = f"{self.labels['left'].get_text()}  {self.labels['time_left'].get_text()}"
        self.buttons['left'].set_label(remaining_label)
        if estimated > 0:
            self.update_progress(min(max(print_duration / estimated, 0), 1))

    def update_progress(self, progress: float):
        self.progress = progress
        self.labels['progress_text'].set_label(f"{progress * 100:.0f}%")
        self.labels['darea'].queue_draw()

    def set_state(self, state, msg=""):
        if (self.state == "complete" or self.state == "cancelled" ) and state == "paused":
            logging.debug(f"Avoid Changing job_status state from '{self.state}' to '{state}'")
            self.state = state
            return
        if state == "printing":
            self.labels["status"].set_label(_("Printing"))
        elif state == "complete":
            self.update_progress(1)
            self.labels["status"].set_label(_("Complete"))
            self.buttons['left'].set_label("-")
            self._add_timeout(self._config.get_main_config().getint("job_complete_timeout", 0))
        elif state == "error":
            self.labels['status'].set_label(_("Error"))
            self._screen.show_popup_message(msg)
            self._add_timeout(self._config.get_main_config().getint("job_error_timeout", 0))
        elif state == "cancelling":
            self.labels["status"].set_label(_("Cancelling"))
        elif state == "cancelled" or (state == "standby" and self.state == "cancelled"):
            self.labels["status"].set_label(_("Cancelled"))
            self._add_timeout(self._config.get_main_config().getint("job_cancelled_timeout", 0))
        elif state == "paused":
            self.labels["status"].set_label(_("Paused"))
        elif state == "standby":
            self.labels["status"].set_label(_("Standby"))
        if self.state != state:
            logging.debug(f"Changing job_status state from '{self.state}' to '{state}'")
            self.state = state
        self.show_buttons_for_state()

    def _add_timeout(self, timeout):
        self._screen.close_screensaver()
        if timeout != 0:
            GLib.timeout_add_seconds(timeout, self.close_panel)

    def show_buttons_for_state(self):
        self.buttons['button_grid'].remove_row(0)
        self.buttons['button_grid'].insert_row(0)
        if self.state == "printing":
            self.buttons['button_grid'].attach(self.buttons['pause'], 0, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['cancel'], 1, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['fine_tune'], 2, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['control'], 3, 0, 1, 1)
            self.enable_button("pause", "cancel")
            self.can_close = False
        elif self.state == "paused":
            self.buttons['button_grid'].attach(self.buttons['resume'], 0, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['cancel'], 1, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['fine_tune'], 2, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['control'], 3, 0, 1, 1)
            self.enable_button("resume", "cancel")
            self.can_close = False
        else:
            offset = self._printer.get_stat("gcode_move", "homing_origin")
            self.zoffset = float(offset[2]) if offset else 0
            if self.zoffset != 0:
                endstop = (
                    (
                        self._printer.config_section_exists("stepper_z")
                        and not self._printer.get_config_section("stepper_z")['endstop_pin'].startswith("probe")
                    )
                    or "delta" in self._printer.get_config_section("printer")['kinematics']
                )
                if endstop:
                    self.buttons['button_grid'].attach(self.buttons["save_offset_endstop"], 0, 0, 1, 1)
                else:
                    self.buttons['button_grid'].attach(Gtk.Label(), 0, 0, 1, 1)
                if self._printer.get_probe():
                    #self.save_offset(null, 'probe')
                    self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_PROBE")
                    self._screen._ws.klippy.gcode_script("SAVE_CONFIG")
                    #self.buttons['button_grid'].attach(self.buttons["save_offset_probe"], 1, 0, 1, 1)
                else:
                    self.buttons['button_grid'].attach(Gtk.Label(), 1, 0, 1, 1)
            else:
                self.buttons['button_grid'].attach(Gtk.Label(), 0, 0, 1, 1)
                self.buttons['button_grid'].attach(Gtk.Label(), 1, 0, 1, 1)

            if self.filename:
                self.buttons['button_grid'].attach(self.buttons['restart'], 2, 0, 1, 1)
                self.enable_button("restart")

                out = subprocess.run(['curl', '-s', 'http://127.0.0.1/server/job_queue/status'],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True  # Python >= 3.7 also accepts "text=True"
                                     )
                job_queue = json.loads(out.stdout)
                logging.debug(out.stdout)
                logging.debug(len(job_queue['result']['queued_jobs']))
                if len(job_queue['result']['queued_jobs']) > 0:
                    self.buttons['button_grid'].attach(self.buttons['queue_print'], 1, 0, 1, 1)
                    self.enable_button("queue_print")
                   # first_file = job_queue['result']['queued_jobs'][0]['filename']
                else:
                    self.disable_button("queue_print")

            else:
                self.disable_button("queue_print")
                self.disable_button("restart")
            if self.state != "cancelling":
                self.buttons['button_grid'].attach(self.buttons['menu'], 3, 0, 1, 1)
                self.can_close = True
        self.content.show_all()

    def show_file_thumbnail(self):
        if self._screen.vertical_mode:
            width = self._screen.width * 0.9
            height = self._screen.height / 4
        else:
            width = self._screen.width / 3
            height = self._gtk.content_height * 0.47
        pixbuf = self.get_file_image(self.filename, width, height)
        logging.debug(self.filename)
        if pixbuf is None:
            logging.debug("no pixbuf")
            pixbuf = self._gtk.PixbufFromIcon("file", width / 2, height / 2)
        self.labels['thumbnail'].set_from_pixbuf(pixbuf)

    def update_filename(self, filename):
        if not filename:
            return
        self.filename = filename
        self.labels["file"].set_label(os.path.splitext(self.filename)[0])
        self.filename_label = {
            "complete": self.labels['file'].get_label(),
            "current": self.labels['file'].get_label(),
            "position": 0,
            "limit": (self._screen.width * 37 / 480) // (self._gtk.font_size / 11),
            "length": len(self.labels['file'].get_label())
        }
        if self.animation_timeout is None and (self.filename_label['length'] - self.filename_label['limit']) > 0:
            self.animation_timeout = GLib.timeout_add_seconds(1, self.animate_label)
        self.update_file_metadata()

    def animate_label(self):
        pos = self.filename_label['position']
        if pos > (self.filename_label['length'] - self.filename_label['limit']):
            self.filename_label['position'] = 0
            self.labels['file'].set_label(self.filename_label['complete'])
        else:
            self.labels['file'].set_label(self.filename_label['current'][pos:self.filename_label['length']])
            self.filename_label['position'] += 1
        return True

    def update_file_metadata(self):
        if self._files.file_metadata_exists(self.filename):
            self.file_metadata = self._files.get_file_info(self.filename)
            logging.info(f"Update Metadata. File: {self.filename} Size: {self.file_metadata['size']}")
            if "estimated_time" in self.file_metadata and self.timeleft_type == "slicer":
                self.labels["est_time"].set_label(self.format_time(self.file_metadata['estimated_time']))

            if "filament_total" in self.file_metadata:
                self.labels['filament_total'].set_label(f"{float(self.file_metadata['filament_total']) / 1000:.1f} m")
        else:
            self.file_metadata = {}
            logging.debug("Cannot find file metadata. Listening for updated metadata")
            self._screen.files.add_file_callback(self._callback_metadata)
        self.show_file_thumbnail()
