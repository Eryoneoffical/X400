import time
import re
import gi
import subprocess
import logging
import netifaces as ni
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from datetime import datetime
from ks_includes.screen_panel import ScreenPanel


COLORS = {
    "command": "#bad8ff",
    "error": "#ff6975",
    "response": "#b8b8b8",
    "time": "grey",
    "warning": "#c9c9c9"
}


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.autoscroll = True
        self.hidetemps = True

        o1_button = self._gtk.Button("arrow-down", _("Auto-scroll") + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        o1_button.get_style_context().add_class("button_active")
        o1_button.get_style_context().add_class("buttons_slim")
        o1_button.connect("clicked", self.set_autoscroll)

        o2_button = self._gtk.Button("heat-up", _("Hide temp.") + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        o2_button.get_style_context().add_class("button_active")
        o2_button.get_style_context().add_class("buttons_slim")
        o2_button.connect("clicked", self.hide_temps)

        o3_button = self._gtk.Button("refresh", _('Clear') + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        o3_button.get_style_context().add_class("buttons_slim")
        o3_button.connect("clicked", self.clear)

        options = Gtk.Grid()
        options.set_vexpand(False)
        options.attach(o1_button, 0, 0, 1, 1)
        options.attach(o2_button, 1, 0, 1, 1)
        options.attach(o3_button, 2, 0, 1, 1)

        sw = Gtk.ScrolledWindow()
        sw.set_hexpand(True)
        sw.set_vexpand(True)

        tb = Gtk.TextBuffer()
        tv = Gtk.TextView()
        tv.set_buffer(tb)
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.connect("size-allocate", self._autoscroll)
        tv.connect("focus-in-event", self._screen.remove_keyboard)

        sw.add(tv)

        ebox = Gtk.Box()
        ebox.set_hexpand(True)
        ebox.set_vexpand(False)

        entry = Gtk.Entry()
        entry.set_hexpand(True)
        entry.set_vexpand(False)
        entry.connect("button-press-event", self._screen.show_keyboard)
        entry.connect("focus-in-event", self._screen.show_keyboard)
        entry.connect("activate", self._send_command)
        entry.grab_focus_without_selecting()

        enter = self._gtk.Button("resume", " " + _('Send') + " ", None, .66, Gtk.PositionType.RIGHT, 1)
        enter.get_style_context().add_class("buttons_slim")

        enter.set_hexpand(False)
        enter.connect("clicked", self._send_command)

        ebox.add(entry)
        ebox.add(enter)

        self.labels.update({
            "entry": entry,
            "sw": sw,
            "tb": tb,
            "tv": tv
        })

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.pack_start(options, False, False, 5)
        content_box.add(sw)
        content_box.pack_end(ebox, False, False, 0)
        self.content.add(content_box)

    def clear(self, widget=None):
        self.labels['tb'].set_text("")

    def add_gcode(self, msgtype, msgtime, message):
        if msgtype == "command":
            color = COLORS['command']
        elif message.startswith("!!"):
            color = COLORS['error']
            message = message.replace("!! ", "")
        elif message.startswith("//"):
            color = COLORS['warning']
            message = message.replace("// ", "")
        elif self.hidetemps and re.match('^(?:ok\\s+)?(B|C|T\\d*):', message):
            return
        else:
            color = COLORS['response']

        message = f'<span color="{color}"><b>{message}</b></span>'

        message = message.replace('\n', '\n         ')

        self.labels['tb'].insert_markup(
            self.labels['tb'].get_end_iter(),
            f'\n<span color="{COLORS["time"]}">{datetime.fromtimestamp(msgtime).strftime("%H:%M:%S")}</span> {message}',
            -1
        )
        # Limit the length
        if self.labels['tb'].get_line_count() > 999:
            self.labels['tb'].delete(self.labels['tb'].get_iter_at_line(0), self.labels['tb'].get_iter_at_line(1))

    def gcode_response(self, result, method, params):
        if method != "server.gcode_store":
            return

        for resp in result['result']['gcode_store']:
            self.add_gcode(resp['type'], resp['time'], resp['message'])

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            self.add_gcode("response", time.time(), data)

    def hide_temps(self, widget):
        self.hidetemps ^= True
        self.toggle_active_class(widget, self.hidetemps)

    def set_autoscroll(self, widget):
        self.autoscroll ^= True
        self.toggle_active_class(widget, self.autoscroll)

    @staticmethod
    def toggle_active_class(widget, cond):
        if cond:
            widget.get_style_context().add_class("button_active")
        else:
            widget.get_style_context().remove_class("button_active")

    def _autoscroll(self, *args):
        if self.autoscroll:
            adj = self.labels['sw'].get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())

    def _send_command(self, *args):
        cmd = self.labels['entry'].get_text()
       # subprocess.run([f"/home/mks/change_name.sh {cmd}"])
        self.labels['entry'].set_text('')
        self._screen.remove_keyboard()

        self.add_gcode("command", time.time(), cmd)
        if cmd.find("N") == 0:
            out = subprocess.run(['/home/mks/KlipperScreen/all/change_name.sh', cmd[1:]],stdout = subprocess.PIPE,
              stderr = subprocess.STDOUT,
              universal_newlines = True # Python >= 3.7 also accepts "text=True"
              )
            self.add_gcode("response", time.time(), out.stdout)
           # self._screen.show_panel("main_menu", self._screen.update_ip_id(), remove_all=True, items=self._config.get_menu_items("__main"))
        elif cmd.find("W") == 0:
            out = subprocess.run(['/home/mks/KlipperScreen/all/get_canuid.sh', cmd],
              stdout = subprocess.PIPE,
              stderr = subprocess.STDOUT,
              universal_newlines = True # Python >= 3.7 also accepts "text=True"
              )
            self.add_gcode("response", time.time(), out.stdout)
        elif cmd.find("H") == 0:
            new_cmd='sed -i s/v1_1.cfg/v1_'+cmd[1:2]+'.cfg/g /home/mks/printer_data/config/printer.cfg'
            out = subprocess.run(new_cmd.split(" "),
              stdout = subprocess.PIPE,
              stderr = subprocess.STDOUT,
              universal_newlines = True # Python >= 3.7 also accepts "text=True"
              )
            self.add_gcode("response", time.time(), out.stdout)
            new_cmd='sed -i s/v1_2.cfg/v1_'+cmd[1:2]+'.cfg/g /home/mks/printer_data/config/printer.cfg'
            out = subprocess.run(new_cmd.split(" "),
              stdout = subprocess.PIPE,
              stderr = subprocess.STDOUT,
              universal_newlines = True # Python >= 3.7 also accepts "text=True"
              )
            self.add_gcode("response", time.time(), out.stdout)
            new_cmd='sed -i s/v1_3.cfg/v1_'+cmd[1:2]+'.cfg/g /home/mks/printer_data/config/printer.cfg'
            out = subprocess.run(new_cmd.split(" "),
              stdout = subprocess.PIPE,
              stderr = subprocess.STDOUT,
              universal_newlines = True # Python >= 3.7 also accepts "text=True"
              )
            self.add_gcode("response", time.time(), out.stdout)
        elif cmd.find("h") == 0:
            new_cmd = 'cat /home/mks/printer_data/config/printer.cfg'
            out = subprocess.run(new_cmd.split(" "),
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 universal_newlines=True  # Python >= 3.7 also accepts "text=True"
                                 )
            self.add_gcode("response", time.time(), out.stdout[0:220])

        elif cmd.find("F") == 0:
            out = subprocess.run(['/home/mks/KlipperScreen/all/flash.sh', cmd],
              stdout = subprocess.PIPE,
              stderr = subprocess.STDOUT,
              universal_newlines = True # Python >= 3.7 also accepts "text=True"
              )
            self.add_gcode("response", time.time(), out.stdout)
            #self.add_gcode("response", time.time(), out.decode("utf-8"))
        elif cmd.find("P") == 0:
            out = subprocess.run(['/home/mks/KlipperScreen/all/git_pull.sh', cmd],
              stdout = subprocess.PIPE,
              stderr = subprocess.STDOUT,
              universal_newlines = True # Python >= 3.7 also accepts "text=True"
              )
            self.add_gcode("response", time.time(), out.stdout)
        elif cmd.find("T") == 0:
            out = subprocess.run(['/home/mks/KlipperScreen/all/recovery.sh', cmd],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 universal_newlines=True  # Python >= 3.7 also accepts "text=True"
                                 )
            self.add_gcode("response", time.time(), out.stdout)
        elif cmd.find("rst") ==0:
            self._screen._ws.klippy.gcode_script('SAVE_VARIABLE VARIABLE=allcalibrate VALUE=1')
            out = subprocess.run(['sync'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 universal_newlines=True  # Python >= 3.7 also accepts "text=True"
                                 )
            self.add_gcode("response", time.time(), out.stdout)
        elif cmd.find("sh ") ==0:

            logging.debug(cmd[3:].split(' '))
            out = subprocess.run(['/home/mks/KlipperScreen/all/run_cmd.sh', cmd[3:]], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 universal_newlines=True  # Python >= 3.7 also accepts "text=True"
                                 )
            self.add_gcode("response", time.time(), out.stdout)
        else:
            self._screen._ws.klippy.gcode_script(cmd)

    def activate(self):
        self.clear()
        self._screen._ws.send_method("server.gcode_store", {"count": 100}, self.gcode_response)
