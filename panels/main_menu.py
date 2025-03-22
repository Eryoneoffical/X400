import logging,re
import gi
import subprocess

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from panels.menu import Panel as MenuPanel
from ks_includes.widgets.heatergraph import HeaterGraph
from ks_includes.widgets.keypad import Keypad


class Panel(MenuPanel):
    def __init__(self, screen, title, items=None):
        super().__init__(screen, title, items)
        self.graph_retry_timeout = None
        self.left_panel = None
        self.devices = {}
        self.graph_update = None
        self.active_heater = None
        self.h = self.f = 0
        self.main_menu = self._gtk.HomogeneousGrid()
        self.main_menu.set_hexpand(True)
        self.main_menu.set_vexpand(True)
        self.graph_retry = 0
        scroll = self._gtk.ScrolledWindow()

        logging.info("### Making MainMenu")

        stats = self._printer.get_printer_status_data()["printer"]
        if stats["temperature_devices"]["count"] > 0 or stats["extruders"]["count"] > 0:
            self._gtk.reset_temp_color()
            self.main_menu.attach(self.create_left_panel(), 0, 0, 1, 1)
        if self._screen.vertical_mode:
            self.labels['menu'] = self.arrangeMenuItems(items, 3, True)
            scroll.add(self.labels['menu'])
            self.main_menu.attach(scroll, 0, 1, 1, 1)
        else:
            self.labels['menu'] = self.arrangeMenuItems(items, 2, True)
            scroll.add(self.labels['menu'])
            self.main_menu.attach(scroll, 1, 0, 1, 1)
        self.content.add(self.main_menu)

    def update_graph_visibility(self):
        if self.left_panel is None or not self._printer.get_temp_store_devices():
            if self._printer.get_temp_store_devices():
                logging.info("Retrying to create left panel")
                self._gtk.reset_temp_color()
                self.main_menu.attach(self.create_left_panel(), 0, 0, 1, 1)
            self.graph_retry += 1
            if self.graph_retry < 5:
                if self.graph_retry_timeout is None:
                    self.graph_retry_timeout = GLib.timeout_add_seconds(5, self.update_graph_visibility)
            else:
                logging.debug(f"Could not create graph {self.left_panel} {self._printer.get_temp_store_devices()}")
            return False
        count = 0
        for device in self.devices:
            visible = self._config.get_config().getboolean(f"graph {self._screen.connected_printer}",
                                                           device, fallback=True)
            self.devices[device]['visible'] = visible
            self.labels['da'].set_showing(device, visible)
            if visible:
                count += 1
                self.devices[device]['name'].get_style_context().add_class(self.devices[device]['class'])
                self.devices[device]['name'].get_style_context().remove_class("graph_label_hidden")
            else:
                self.devices[device]['name'].get_style_context().add_class("graph_label_hidden")
                self.devices[device]['name'].get_style_context().remove_class(self.devices[device]['class'])
        if count > 0:
            if self.labels['da'] not in self.left_panel:
                self.left_panel.add(self.labels['da'])
            self.labels['da'].queue_draw()
            self.labels['da'].show()
            if self.graph_update is None:
                # This has a high impact on load
                self.graph_update = GLib.timeout_add_seconds(5, self.update_graph)
        elif self.labels['da'] in self.left_panel:
            self.left_panel.remove(self.labels['da'])
            if self.graph_update is not None:
                GLib.source_remove(self.graph_update)
                self.graph_update = None
        self.graph_retry = 0
        return False
    def wait_confirm(self, dialog, response_id, program):
        if response_id == Gtk.ResponseType.CANCEL:
            self._gtk.remove_dialog(dialog)
            #file = open('/home/mks/printer_data/config/variable.cfg', 'w')
            #file.close()
            return
        self._screen._ws.klippy.gcode_script(f"RESUME_INTERRUPTED")
        self._gtk.remove_dialog(dialog)
    def wait_confirm_c(self, dialog, response_id, program):
        if response_id == Gtk.ResponseType.CANCEL:
            self._gtk.remove_dialog(dialog)
            return
        self._screen.show_panel("calibrate", _("calibrating"))
        script = {"script": """
                                  ABORT
                                  M117 Extruder PID_CALIBRATE  in progress,time left: 15 minutes 
                                  G28  
                                  G1 X200 Y200 Z50 
                                  M119
                                  M106 S255
                                  M140 S50
                                  M117 Extruder PID_CALIBRATE  in progress,time left: 14 minutes
                                  PID_CALIBRATE HEATER=extruder TARGET=220
                                  M106 S255
                                  M117 SHAPER CALIBRATE in progress,time left: 11 minutes 
                                  SHAPER_CALIBRATE
                                  M140 S0
                                  M107
                                  M104 S150
                                  G28
                                  M117 QUAD_GANTRY_LEVEL in progress, time left: 1 minutes
                                  G28
                                  _QUAD_GANTRY_LEVEL  horizontal_move_z=10 retry_tolerance=1 LIFT_SPEED=5
                                  G4 P1000
                                  M104 S0
                                  SAVE_VARIABLE VARIABLE=allcalibrate VALUE=0
                                  M117 ALL calibrate_finish
                                          """}

        self._screen._ws.send_method("printer.gcode.script", script)
        self._gtk.remove_dialog(dialog)
        self._screen.base_panel.action_bar.set_sensitive(False)
        #file = open('/home/mks/printer_data/config/variable.cfg', 'w')
        #file.close()

    def wait_confirm_reboot(self, dialog, response_id, program):
        if response_id == Gtk.ResponseType.CANCEL:
            self._gtk.remove_dialog(dialog)
            return
        subprocess.call(
            "echo makerbase | sudo -S reboot",
            shell=True)

        self._gtk.remove_dialog(dialog)

    def activate(self):
        self.update_graph_visibility()
        self._screen.base_panel_show_all()
        logging.debug(f"main_menu.py...")
        # calibration
        try:
            file = open('/home/mks/printer_data/config/variable.cfg', 'r')
            while 1:
                line = file.readline()
                if not line:
                    print("Read file End or Error")
                    break
                elif 'allcalibrate = 1' in line:
                    label = Gtk.Label("Please calibrate the printer first, that needs about 15 minutes.")
                    buttons = [
                        {"name": _("Calibrate"), "response": Gtk.ResponseType.OK},
                        {"name": _("Later"), "response": Gtk.ResponseType.CANCEL}
                    ]
                    scroll = self._gtk.ScrolledWindow()
                    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    vbox.set_halign(Gtk.Align.CENTER)
                    vbox.set_valign(Gtk.Align.CENTER)
                    vbox.add(label)
                    scroll.add(vbox)
                    self.dialog_wait = self._gtk.Dialog(self._screen, buttons, scroll, self.wait_confirm_c, "title")
                    self.dialog_wait.set_title(_("Update"))
                    return
                elif 'needreboot = 1' in line:
                    label = Gtk.Label("The upgrade is complete, Do you want to reboot the printer now?")
                    buttons = [
                        {"name": _("Reboot"), "response": Gtk.ResponseType.OK},
                        {"name": _("Later"), "response": Gtk.ResponseType.CANCEL}
                    ]
                    scroll = self._gtk.ScrolledWindow()
                    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    vbox.set_halign(Gtk.Align.CENTER)
                    vbox.set_valign(Gtk.Align.CENTER)
                    vbox.add(label)
                    scroll.add(vbox)
                    self.dialog_wait = self._gtk.Dialog(self._screen, buttons, scroll, self.wait_confirm_reboot, "title")
                    self.dialog_wait.set_title(_("Update"))
                    return
                    #break
            file.close()
        except Exception as e:
            pass
        #logging.debug(f"filename==0...")
        # power losse recover
        matchPattern = re.compile(r'filename = ')
        try:
            file = open('/home/mks/printer_data/config/variable.cfg', 'r')
            while 1:
                line = file.readline()
                if not line:
                    print("Read file End or Error")
                    break
                elif matchPattern.search(line):
                    #logging.debug(f"filename==1...")
                    pattern = r'\'(.*?)\''
                    extracted_string = re.findall(pattern, line)
                    label = Gtk.Label("Resume print file: \n \n\n%s ?" % extracted_string[0])
                    buttons = [
                        {"name": _("Print"), "response": Gtk.ResponseType.OK},
                        {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
                    ]
                    scroll = self._gtk.ScrolledWindow()
                    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    vbox.set_halign(Gtk.Align.CENTER)
                    vbox.set_valign(Gtk.Align.CENTER)
                    vbox.add(label)
                    scroll.add(vbox)
                    self.dialog_wait = self._gtk.Dialog(self._screen, buttons, scroll, self.wait_confirm, "title")
                    self.dialog_wait.set_title(_("Update"))
                    break
            file.close()
        except Exception as e:
            pass



    def deactivate(self):
        if self.graph_update is not None:
            GLib.source_remove(self.graph_update)
            self.graph_update = None
        if self.graph_retry_timeout is not None:
            GLib.source_remove(self.graph_retry_timeout)
            self.graph_retry_timeout = None
        if self.active_heater is not None:
            self.hide_numpad()

    def add_device(self, device):

        logging.info(f"Adding device: {device}")

        temperature = self._printer.get_dev_stat(device, "temperature")
        if temperature is None:
            return False

        devname = device.split()[1] if len(device.split()) > 1 else device
        # Support for hiding devices by name
        if devname.startswith("_"):
            return False

        if device.startswith("extruder"):
            if self._printer.extrudercount > 1:
                image = f"extruder-{device[8:]}" if device[8:] else "extruder-0"
            else:
                image = "extruder"
            class_name = f"graph_label_{device}"
            dev_type = "extruder"
        elif device == "heater_bed":
            image = "bed"
            devname = "Heater Bed"
            class_name = "graph_label_heater_bed"
            dev_type = "bed"
        elif device.startswith("heater_generic"):
            self.h += 1
            image = "heater"
            class_name = f"graph_label_sensor_{self.h}"
            dev_type = "sensor"
        elif device.startswith("temperature_fan"):
            self.f += 1
            image = "fan"
            class_name = f"graph_label_fan_{self.f}"
            dev_type = "fan"
        elif self._config.get_main_config().getboolean("only_heaters", False):
            return False
        else:
            self.h += 1
            image = "heat-up"
            class_name = f"graph_label_sensor_{self.h}"
            dev_type = "sensor"

        rgb = self._gtk.get_temp_color(dev_type)

        can_target = self._printer.device_has_target(device)
        self.labels['da'].add_object(device, "temperatures", rgb, False, True)
        if can_target:
            self.labels['da'].add_object(device, "targets", rgb, True, False)

        name = self._gtk.Button(image, self.prettify(devname), None, self.bts, Gtk.PositionType.LEFT, 1)
        name.connect("clicked", self.toggle_visibility, device)
        name.set_alignment(0, .5)
        visible = self._config.get_config().getboolean(f"graph {self._screen.connected_printer}", device, fallback=True)
        if visible:
            name.get_style_context().add_class(class_name)
        else:
            name.get_style_context().add_class("graph_label_hidden")
        self.labels['da'].set_showing(device, visible)

        temp = self._gtk.Button(label="", lines=1)
        if can_target:
            temp.connect("clicked", self.show_numpad, device)

        self.devices[device] = {
            "class": class_name,
            "name": name,
            "temp": temp,
            "can_target": can_target,
            "visible": visible
        }

        devices = sorted(self.devices)
        pos = devices.index(device) + 1

        self.labels['devices'].insert_row(pos)
        self.labels['devices'].attach(name, 0, pos, 1, 1)
        self.labels['devices'].attach(temp, 1, pos, 1, 1)
        self.labels['devices'].show_all()
        return True

    def toggle_visibility(self, widget, device):
        self.devices[device]['visible'] ^= True
        logging.info(f"Graph show {self.devices[device]['visible']}: {device}")

        section = f"graph {self._screen.connected_printer}"
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, f"{device}", f"{self.devices[device]['visible']}")
        self._config.save_user_config_options()

        self.update_graph_visibility()

    def change_target_temp(self, temp):
        name = self.active_heater.split()[1] if len(self.active_heater.split()) > 1 else self.active_heater
        temp = self.verify_max_temp(temp)
        if temp is False:
            return

        if self.active_heater.startswith('extruder'):
            self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(self.active_heater), temp)
        elif self.active_heater == "heater_bed":
            self._screen._ws.klippy.set_bed_temp(temp)
        elif self.active_heater.startswith('heater_generic '):
            self._screen._ws.klippy.set_heater_temp(name, temp)
        elif self.active_heater.startswith('temperature_fan '):
            self._screen._ws.klippy.set_temp_fan_temp(name, temp)
        else:
            logging.info(f"Unknown heater: {self.active_heater}")
            self._screen.show_popup_message(_("Unknown Heater") + " " + self.active_heater)
        self._printer.set_dev_stat(self.active_heater, "target", temp)

    def verify_max_temp(self, temp):
        temp = int(temp)
        max_temp = int(float(self._printer.get_config_section(self.active_heater)['max_temp']))
        logging.debug(f"{temp}/{max_temp}")
        if temp > max_temp:
            self._screen.show_popup_message(_("Can't set above the maximum:") + f' {max_temp}')
            return False
        return max(temp, 0)

    def pid_calibrate(self, temp):
        if self.verify_max_temp(temp):
            script = {"script": f"PID_CALIBRATE HEATER={self.active_heater} TARGET={temp}"}
            self._screen._confirm_send_action(
                None,
                _("Initiate a PID calibration for:") + f" {self.active_heater} @ {temp} ºC"
                + "\n\n" + _("It may take more than 5 minutes depending on the heater power."),
                "printer.gcode.script",
                script
            )

    def create_left_panel(self):

        self.labels['devices'] = Gtk.Grid()
        self.labels['devices'].get_style_context().add_class('heater-grid')
        self.labels['devices'].set_vexpand(False)

        name = Gtk.Label()
        #temp = Gtk.Label(_("3D Farm:\nwww.eryone.club"))
        temp = Gtk.Label(_(" "))
        temp.get_style_context().add_class("heater-grid-temp")

        self.labels['devices'].attach(name, 0, 0, 1, 1)
        self.labels['devices'].attach(temp, 1, 0, 1, 1)

        self.labels['da'] = HeaterGraph(self._printer, self._gtk.font_size)
        self.labels['da'].set_vexpand(True)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.labels['devices'])

        self.left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.left_panel.add(scroll)

        for d in (self._printer.get_tools() + self._printer.get_heaters()):
            self.add_device(d)

        return self.left_panel

    def hide_numpad(self, widget=None):
        self.devices[self.active_heater]['name'].get_style_context().remove_class("button_active")
        self.active_heater = None

        if self._screen.vertical_mode:
            self.main_menu.remove_row(1)
            self.main_menu.attach(self.labels['menu'], 0, 1, 1, 1)
        else:
            self.main_menu.remove_column(1)
            self.main_menu.attach(self.labels['menu'], 1, 0, 1, 1)
        self.main_menu.show_all()

    def process_update(self, action, data):

        if action == "notify_gcode_response" and "load Filament   printing" in data:
            logging.debug(f" =============action:'{action}'==={data}")
            try:
                self._screen.show_panel("extrude", _(""))
            except Exception as e:
                logging.error(f"runout error:\n{e}")
                pass
        if action != "notify_status_update":
            return

        for x in (self._printer.get_tools() + self._printer.get_heaters()):
            self.update_temp(
                x,
                self._printer.get_dev_stat(x, "temperature"),
                self._printer.get_dev_stat(x, "target"),
                self._printer.get_dev_stat(x, "power"),
            )

        return False

    def show_numpad(self, widget, device):

        if self.active_heater is not None:
            self.devices[self.active_heater]['name'].get_style_context().remove_class("button_active")
        self.active_heater = device
        self.devices[self.active_heater]['name'].get_style_context().add_class("button_active")

        if "keypad" not in self.labels:
            self.labels["keypad"] = Keypad(self._screen, self.change_target_temp, self.pid_calibrate, self.hide_numpad)
        can_pid = self._printer.state not in ["printing", "paused"] \
            and self._screen.printer.config[self.active_heater]['control'] == 'pid'
        self.labels["keypad"].show_pid(can_pid)
        self.labels["keypad"].clear()

        if self._screen.vertical_mode:
            self.main_menu.remove_row(1)
            self.main_menu.attach(self.labels["keypad"], 0, 1, 1, 1)
        else:
            self.main_menu.remove_column(1)
            self.main_menu.attach(self.labels["keypad"], 1, 0, 1, 1)
        self.main_menu.show_all()

    def update_graph(self):
        self.labels['da'].queue_draw()
        return True
