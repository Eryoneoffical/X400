import re
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


# X and Y frequencies
XY_FREQ = [
    {'name': 'X', 'config': 'shaper_freq_x', 'min': 0, 'max': 133},
    {'name': 'Y', 'config': 'shaper_freq_y', 'min': 0, 'max': 133},
]
SHAPERS = ['zv', 'mzv', 'zvd', 'ei', '2hump_ei', '3hump_ei']


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.freq_xy_adj = {}
        self.freq_xy_combo = {}
        self.calibrate_btn = self._gtk.Button("move", _('Finding ADXL'), "color0", lines=1)
        self.calibrate_btn.connect("clicked", self.on_popover_clicked)
        self.calibrate_btn.set_sensitive(False)
        self.status = Gtk.Label()
        self.status.set_hexpand(True)
        self.status.set_vexpand(False)
        self.status.set_halign(Gtk.Align.START)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        self.calibrating_axis = None
        self.calibrating_axis = None

        auto_calibration_label = Gtk.Label()
        auto_calibration_label.set_markup('<big><b>Auto Calibration</b></big>')
        auto_calibration_label.set_hexpand(True)

        auto_grid = Gtk.Grid()
        auto_grid.attach(auto_calibration_label, 0, 0, 2, 2)
        auto_grid.attach(self.calibrate_btn, 1, 1, 2, 2)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(auto_grid)
        box.add(self.status)

        self.content.add(box)

        pobox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        test_both = self._gtk.Button(label=_("Measure Both"))
        test_both.connect("clicked", self.start_calibration, "both")
        pobox.pack_start(test_both, True, True, 8)
        self.labels['popover'] = Gtk.Popover()
        self.labels['popover'].add(pobox)
        self.labels['popover'].set_position(Gtk.PositionType.LEFT)

    def on_popover_clicked(self, widget):
        self.labels['popover'].set_relative_to(widget)
        self.labels['popover'].show_all()

    def start_calibration(self, widget, method):
        self.labels['popover'].popdown()
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)
        self.calibrating_axis = method
        if method == "x":
            self._screen._ws.klippy.gcode_script('SHAPER_CALIBRATE AXIS=X')
        if method == "y":
            self._screen._ws.klippy.gcode_script('SHAPER_CALIBRATE AXIS=Y')
        if method == "both":
            self._screen._ws.klippy.gcode_script('SHAPER_CALIBRATE')

        self.calibrate_btn.set_label(_('Calibrating') + '...')
        self.calibrate_btn.set_sensitive(False)

    def set_opt_value(self, widget, opt, *args):
        shaper_freq_x = self.freq_xy_adj['shaper_freq_x'].get_value()
        shaper_freq_y = self.freq_xy_adj['shaper_freq_y'].get_value()
        shaper_type_x = self.freq_xy_combo['shaper_type_x'].get_active_text()
        shaper_type_y = self.freq_xy_combo['shaper_type_y'].get_active_text()

        self._screen._ws.klippy.gcode_script(
            f'SET_INPUT_SHAPER '
            f'SHAPER_FREQ_X={shaper_freq_x} '
            f'SHAPER_TYPE_X={shaper_type_x} '
            f'SHAPER_FREQ_Y={shaper_freq_y} '
            f'SHAPER_TYPE_Y={shaper_type_y}'
        )

    def save_config(self):

        script = {"script": "SAVE_CONFIG"}
        self._screen._confirm_send_action(
            None,
            _("Save configuration?") + "\n\n" + _("Klipper will reboot"),
            "printer.gcode.script",
            script
        )

    def activate(self):
        # This will return the current values
        self._screen._ws.klippy.gcode_script('SET_INPUT_SHAPER')
        # Check for the accelerometer
        self._screen._ws.klippy.gcode_script('ACCELEROMETER_QUERY')
        # Send at least two commands, with my accelerometer the first command after a reboot will fail
        self._screen._ws.klippy.gcode_script('MEASURE_AXES_NOISE')

    def process_update(self, action, data):
        if action != "notify_gcode_response":
            return
        #self.status.set_text(f"{data.replace('shaper_', '').replace('damping_', '')}")
        data = data.lower()
        if 'got 0' in data:
            self.calibrate_btn.set_label(_('Check ADXL Wiring'))
            self.calibrate_btn.set_sensitive(False)
        if 'unknown command:"accelerometer_query"' in data:
            self.calibrate_btn.set_label(_('ADXL Not Configured'))
            self.calibrate_btn.set_sensitive(False)
        if 'adxl345 values' in data or 'axes noise' in data:
            self.calibrate_btn.set_sensitive(True)
            self.calibrate_btn.set_label(_('Auto-calibrate'))
        # Recommended shaper_type_y = ei, shaper_freq_y = 48.4 Hz
        if 'recommended shaper_type_' in data:
            results = re.search(r'shaper_type_(?P<axis>[xy])\s*=\s*(?P<shaper_type>.*?), shaper_freq_.\s*=\s*('
                                r'?P<shaper_freq>[0-9.]+)', data).groupdict()
            self.freq_xy_adj['shaper_freq_' + results['axis']].set_value(float(results['shaper_freq']))
           # self.freq_xy_combo['shaper_type_' + results['axis']].set_active(SHAPERS.index(results['shaper_type']))
            if self.calibrating_axis == results['axis'] or (self.calibrating_axis == "both" and results['axis'] == 'y'):
                self.calibrate_btn.set_sensitive(True)
                self.calibrate_btn.set_label(_('Calibrated'))
                self.save_config()
        # shaper_type_y:ei shaper_freq_y:48.400 damping_ratio_y:0.100000
        if 'shaper_type_' in data:
            results = re.search(r'shaper_type_(?P<axis>[xy]):(?P<shaper_type>.*?) shaper_freq_.:('
                                r'?P<shaper_freq>[0-9.]+)', data).groupdict()
            self.freq_xy_adj['shaper_freq_' + results['axis']].set_value(float(results['shaper_freq']))
           # self.freq_xy_combo['shaper_type_' + results['axis']].set_active(SHAPERS.index(results['shaper_type']))
