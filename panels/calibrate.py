import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango,GLib
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    distances = ['.1', '.5', '1', '5', '10', '25', '50']
    distance = distances[-2]

    def __init__(self, screen, title):
        super().__init__(screen, title)
        #self.settings = {}
        self._screen = screen
        self._gtk = screen.gtk
        self.menu = ['move_menu']
        self.buttons = {

            'z+': self._gtk.Button("extruder", _("Shaper calibrate"), "color3"),
           # 'z-': self._gtk.Button("z-closer", _("Z Calibrate"), "color3"),
            'ALL': self._gtk.Button("z-closer", _("Calibrate All"), "color3"),

            'home': self._gtk.Button("heat-up", _("PID calibrate"), "color4"),
            'bed_pid': self._gtk.Button("heat-up", _("PID calibrate")+'BED', "color4"),
            'motors_off': self._gtk.Button("z-tilt", _("Z Tilt"), "color4"),
        }
        self.height_map_range = ''
        self.retrying = ''
        script = {"script": """M117 SHAPER_CALIBRATE
                           G28
                           SHAPER_CALIBRATE
                           G28
                           _QUAD_GANTRY_LEVEL  horizontal_move_z=10 retry_tolerance=1 LIFT_SPEED=5
                           G4 P1000
                           M117 SHAPER_CALIBRATE calibrate_finish"""}
        self.buttons['z+'].connect("clicked", self._confirm_send_action,
                                           _("Are you sure to Calibrate?"),
                                           "printer.gcode.script", script)

        script = {"script": """M119
                       M106 S255
                       M117 PID_CALIBRATE Nozzle
                       G28
                       G1 X200 Y200 Z50
                       PID_CALIBRATE HEATER=extruder TARGET=220
                       M117 Extruder PID calibrate_finish
                       M107"""}
        self.buttons['home'].connect("clicked", self._confirm_send_action,
                                           _("Are you sure to Calibrate?"),
                                           "printer.gcode.script", script)
        script = {"script": """M104 S150
                                M117 QUAD_GANTRY_LEVEL
                                G28 
                                _QUAD_GANTRY_LEVEL  horizontal_move_z=10 retry_tolerance=1 LIFT_SPEED=5                             
                                M117 QGL calibrate_finish"""}
        self.buttons['motors_off'].connect("clicked", self._confirm_send_action,
                                           _("Are you sure to Calibrate?"),
                                           "printer.gcode.script", script)
        script = {"script": """
                                  ABORT
                                  SET_PIN PIN=LED VALUE=0.50
                                  SET_FAN_SPEED FAN=filter_fan SPEED=0.5
                                  SET_PIN PIN=Board_FAN VALUE=0.50
                                  M106 S100
                                  M117 Extruder PID_CALIBRATE  in progress,time left: 20 minutes 
                                  G28  
                                  G1 X200 Y200 Z50 
                                  M119
                                  M106 S255
                                  M140 S50
                                  M117 Extruder PID_CALIBRATE  in progress,time left: 19 minutes
                                  PID_CALIBRATE HEATER=extruder TARGET=220
                                  M106 S255
                                  M117 SHAPER CALIBRATE in progress,time left: 16 minutes 
                                  SHAPER_CALIBRATE
                                  M140 S0
                                  M107
                                  M117 Bed PID_CALIBRATE in progress,time left: 10 minutes 
                                  PID_CALIBRATE HEATER=heater_bed TARGET=60
                                  M104 S150
                                  G28
                                  M117 QUAD_GANTRY_LEVEL in progress, time left: 1 minutes
                                  G28
                                  _QUAD_GANTRY_LEVEL  horizontal_move_z=10 retry_tolerance=1 LIFT_SPEED=5
                                  BED_MESH_CALIBRATE PROFILE='default'
                                  G4 P1000
                                  M104 S0
                                  SAVE_VARIABLE VARIABLE=allcalibrate VALUE=0
                                  M117 ALL calibrate_finish
                                  """}
        self.buttons['ALL'].connect("clicked", self._confirm_send_action,
                                           _("Are you sure to Calibrate?"),
                                           "printer.gcode.script", script)

        script = {"script": """M119
                               M106 S255
                               M117 PID_CALIBRATE BED
                               G28
                               G1 X200 Y200 Z50
                               PID_CALIBRATE HEATER=heater_bed TARGET=60
                               SAVE_CONFIG
                               M117 Bed PID calibrate finish
                               M107"""}
        self.buttons['bed_pid'].connect("clicked", self._confirm_send_action,
                                     _("Are you sure to Calibrate?"),
                                     "printer.gcode.script", script)

        grid = self._gtk.HomogeneousGrid()

        grid.attach(self.buttons['z+'], 2, 1, 1, 1)
        #grid.attach(self.buttons['z-'], 1, 1, 1, 1)
        grid.attach(self.buttons['home'], 2, 0, 1, 1)
        grid.attach(self.buttons['motors_off'], 1, 1, 1, 1)
        grid.attach(self.buttons['ALL'], 1, 0, 1, 1)
        grid.attach(self.buttons['bed_pid'], 3, 0, 1, 1)

        distgrid = Gtk.Grid()

        for p in ('pos_x', 'pos_y', 'pos_z'):
            self.labels[p] = Gtk.Label()
            self.labels[p].get_style_context().add_class("printing-status_message")
        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))

        bottomgrid = self._gtk.HomogeneousGrid()
        bottomgrid.set_direction(Gtk.TextDirection.LTR)
        bottomgrid.attach(self.labels['pos_z'], 2, 1, 1, 1)
        self.labels['move_menu'] = self._gtk.HomogeneousGrid()
        self.labels['move_menu'].attach(grid, 0, 0, 1, 3)
        self.labels['move_menu'].attach(bottomgrid, 0, 3, 1, 1)
        self.labels['move_menu'].attach(distgrid, 0, 4, 1, 1)

        self.content.add(self.labels['move_menu'])

        printer_cfg = self._printer.get_config_section("printer")
        # The max_velocity parameter is not optional in klipper config.
        max_velocity = int(float(printer_cfg["max_velocity"]))
        if max_velocity <= 1:
            logging.error(f"Error getting max_velocity\n{printer_cfg}")
            max_velocity = 50
        if "max_z_velocity" in printer_cfg:
            max_z_velocity = int(float(printer_cfg["max_z_velocity"]))
        else:
            max_z_velocity = max_velocity
        self._screen._send_action(None, "printer.gcode.script", "M119")
        configurable_options = [
            {"invert_x": {"section": "main", "name": _("Invert X"), "type": "binary", "value": "False"}},
            {"invert_y": {"section": "main", "name": _("Invert Y"), "type": "binary", "value": "False"}},
            {"invert_z": {"section": "main", "name": _("Invert Z"), "type": "binary", "value": "False"}},
            {"move_speed_xy": {
                "section": "main", "name": _("XY Speed (mm/s)"), "type": "scale", "value": "50",
                "range": [1, max_velocity], "step": 1}},
            {"move_speed_z": {
                "section": "main", "name": _("Z Speed (mm/s)"), "type": "scale", "value": "10",
                "range": [1, max_z_velocity], "step": 1}}
        ]

        self.labels['options_menu'] = self._gtk.ScrolledWindow()
        self.labels['options'] = Gtk.Grid()
        self.labels['options_menu'].add(self.labels['options'])

    def process_busy(self, busy):
        buttons = ("z+","z-","home", "motors_off","ALL","bed_pid")
        for button in buttons:
            if button in self.buttons:
                self.buttons[button].set_sensitive(not busy)

    def _dialog_show(self, widget, text, method, params=None):
        buttons = [
            {"name": _("OK"), "response": Gtk.ResponseType.CANCEL}
        ]

       # label = Gtk.Label(text)
        label = Gtk.Label()
        label.set_markup(text)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        self.confirm = self._gtk.Dialog(self._screen, buttons, label, self._confirm_send_action_response, method, params)
       # dialog =       self._gtk.Dialog(self._screen, buttons, scroll, self.reboot_poweroff_update_confirm, method)
        self.confirm.set_title("KlipperScreen")

    def process_update(self, action, data):
        #logging.info(f"### data {data}, action {action}")
        if action == "notify_gcode_response":
            if data.startswith("!!"):# error
                self._screen.base_panel.action_bar.set_sensitive(True)
                data = data.replace("!! ", "")
                script = {"script": "M117 Calibration Failed: "+data}
                self._screen._send_action(None, "printer.gcode.script", script)

                script = {"script": " "}
                self._dialog_show(self._screen, "Calibration Failed! Problem:" + data, "printer.gcode.script", script)
            #logging.info(f"### data {data}, action {action}")
            if "height map range:" in data:#Retrying
                self.height_map_range = data
            if "Retrying" in data:  # Retrying
                self.retrying += 'Retrying '
                #logging.info(f"startswith ")
        if action == "notify_status_update":
           #logging.info(f"### data {data}, action {action}")
            if "display_status" in data and "message" in data["display_status"] and data['display_status'] is not None:
                logging.info(f"### data {data['display_status']['message']}")
                lcd_msg = ""
                if data['display_status']['message'] is not None:
                    lcd_msg = str(data['display_status']['message'])
                    lcd_msg = lcd_msg.replace("\\n", "\n")
                    logging.info(lcd_msg)
                self.labels['pos_z'].set_label(lcd_msg)

                if "calibrate_finish" in lcd_msg:
                    #self._screen.base_panel.action_bar.
                    #self._screen.base_panel.action_bar.show()
                    self._screen.base_panel.action_bar.set_sensitive(True)
                    script = {"script": "M117 ."}
                    self._screen._send_action(None, "printer.gcode.script", script)
                    script = {"script": "save_config"}
                    self._confirm_send_action(self._screen, lcd_msg + ",  Save to Printer?\n"+self.height_map_range+"\n"+self.retrying, "printer.gcode.script", script)
                    self.height_map_range = ""
                    self.retrying = ""

        if action == "notify_busy":
            self.process_busy(data)
            return
        #if "PID parameters: pid_Kp=" in data:


        if action != "notify_status_update":
            return

        homed_axes = self._printer.get_stat("toolhead", "homed_axes")
        if homed_axes == "xyz":
            if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                self.labels['pos_x'].set_text(f"X: {data['gcode_move']['gcode_position'][0]:.2f}")
                self.labels['pos_y'].set_text(f"Y: {data['gcode_move']['gcode_position'][1]:.2f}")
               # self.labels['pos_z'].set_text(f"Z: {data['gcode_move']['gcode_position'][2]:.2f}")
        else:
            if "x" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.labels['pos_x'].set_text(f"X: {data['gcode_move']['gcode_position'][0]:.2f}")
            else:
                self.labels['pos_x'].set_text("X: ?")
            if "y" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.labels['pos_y'].set_text(f"Y: {data['gcode_move']['gcode_position'][1]:.2f}")
            else:
                self.labels['pos_y'].set_text("Y: ?")
          #  if "z" in homed_axes:
          #      if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
            #        self.labels['pos_z'].set_text(f"Z: {data['gcode_move']['gcode_position'][2]:.2f}")
            #else:
           #     self.labels['pos_z'].set_text("Z: ?")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def move(self, widget, axis, direction):
        if self._config.get_config()['main'].getboolean(f"invert_{axis.lower()}", False):
            direction = "-" if direction == "+" else "+"

        dist = f"{direction}{self.distance}"
        config_key = "move_speed_z" if axis == "Z" else "move_speed_xy"
        speed = None if self.ks_printer_cfg is None else self.ks_printer_cfg.getint(config_key, None)
        if speed is None:
            speed = self._config.get_config()['main'].getint(config_key, 20)
        speed = 60 * max(1, speed)

        self._screen._ws.klippy.gcode_script(f"{KlippyGcodes.MOVE_RELATIVE}\n{KlippyGcodes.MOVE} {axis}{dist} F{speed}")
        if self._printer.get_stat("gcode_move", "absolute_coordinates"):
            self._screen._ws.klippy.gcode_script("G90")

    def add_option(self, boxname, opt_array, opt_name, option):
        name = Gtk.Label()
        name.set_markup(f"<big><b>{option['name']}</b></big>")
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.get_style_context().add_class("frame-item")
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.set_valign(Gtk.Align.CENTER)
        dev.add(name)

        if option['type'] == "binary":
            box = Gtk.Box()
            box.set_vexpand(False)
            switch = Gtk.Switch()
            switch.set_hexpand(False)
            switch.set_vexpand(False)
            switch.set_active(self._config.get_config().getboolean(option['section'], opt_name))
            switch.connect("notify::active", self.switch_config_option, option['section'], opt_name)
            switch.set_property("width-request", round(self._gtk.font_size * 7))
            switch.set_property("height-request", round(self._gtk.font_size * 3.5))
            box.add(switch)
            dev.add(box)
        elif option['type'] == "scale":
            dev.set_orientation(Gtk.Orientation.VERTICAL)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL,
                                             min=option['range'][0], max=option['range'][1], step=option['step'])
            scale.set_hexpand(True)
            scale.set_value(int(self._config.get_config().get(option['section'], opt_name, fallback=option['value'])))
            scale.set_digits(0)
            scale.connect("button-release-event", self.scale_moved, option['section'], opt_name)
            dev.add(scale)

        opt_array[opt_name] = {
            "name": option['name'],
            "row": dev
        }

        opts = sorted(list(opt_array), key=lambda x: opt_array[x]['name'])
        pos = opts.index(opt_name)

        self.labels[boxname].insert_row(pos)
        self.labels[boxname].attach(opt_array[opt_name]['row'], 0, pos, 1, 1)
        self.labels[boxname].show_all()

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False

    def home(self, widget):
        if "delta" in self._printer.get_config_section("printer")['kinematics']:
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)
            return
        name = "homing"
        disname = self._screen._config.get_menu_name("move", name)
        menuitems = self._screen._config.get_menu_items("move", name)
        self._screen.show_popup_message(f"Make sure nothing is on the BED! ",1)
        self._screen.show_panel("menu", disname, items=menuitems)


    def _confirm_send_action(self, widget, text, method, params=None):
        buttons = [
            {"name": _("Continue"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

       # label = Gtk.Label(text)
        label = Gtk.Label()
        label.set_markup(text)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        self.confirm = self._gtk.Dialog(self._screen, buttons, label, self._confirm_send_action_response, method, params)
       # dialog =       self._gtk.Dialog(self._screen, buttons, scroll, self.reboot_poweroff_update_confirm, method)
        self.confirm.set_title("KlipperScreen")

    def _confirm_send_action_response(self, dialog, response_id, method, params):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            self._screen._send_action(None, method, params)
            logging.info(str(params["script"]))
            if "save_config" not in str(params["script"]):
                self._screen.base_panel.action_bar.set_sensitive(False)
            #script = {"script": "save_config"}
            #self._confirm_send_action(self._screen, "save config?", "printer.gcode.script", script)


