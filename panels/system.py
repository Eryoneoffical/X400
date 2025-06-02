import logging
import os
import gi
import subprocess
import netifaces as ni

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GLib
from ks_includes.screen_panel import ScreenPanel


# Same as ALLOWED_SERVICES in moonraker
# https://github.com/Arksine/moonraker/blob/master/moonraker/components/machine.py
ALLOWED_SERVICES = (
    #"Eryone_App",
    #"MoonCord",
    #"moonraker",
    #"moonraker-telegram-bot",
    #"klipper",
    #"KlipperScreen",
    #"sonar",
    #"webcamd",
)


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.widgets = {}
        self.refresh = None
        self.update_dialog = None
        self.progress_bar = None
        self.grid = self._gtk.HomogeneousGrid()
        self.grid.set_row_homogeneous(False)

        update_all = self._gtk.Button('arrow-up', _('Full Update'), 'color1')
        update_all.connect("clicked", self.show_update_info, "full")
        update_all.set_vexpand(False)
        self.refresh = self._gtk.Button('refresh', _('Recovery'), 'color2')
        self.refresh.connect("clicked", self.reboot_poweroff_update,"recovery")
        self.refresh.set_vexpand(False)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_hexpand(True)
        # grid.attach(self.progress_bar, 0, 3, 3, 1)
  
        self.gcode_label = Gtk.Label(label="")
        self.gcode_label.set_line_wrap(True)
        self.gcode_label.set_max_width_chars(40)
        self.gcode_label.set_hexpand(True)
        self.gcode_label.set_halign(Gtk.Align.START)
        self.grid.attach(self.gcode_label, 0, 4, 3, 1)

        self.upgrade = self._gtk.Button('arrow-up', _('Update'), 'color4')
        self.upgrade.connect("clicked", self.reboot_poweroff_update, "update")
        self.upgrade.set_vexpand(False)
        self.upgrade.set_sensitive(False)


        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        infogrid = Gtk.Grid()
        infogrid.get_style_context().add_class("system-program-grid")
        update_resp = 0 # self._screen.apiclient.send_request("machine/update/status")

        if not update_resp:
            self.update_status = {}
            logging.info("No update manager configured")
        else:
            self.update_status = update_resp['result']
            vi = update_resp['result']['version_info']
            items = sorted(list(vi))
            i = 0
            self.text_str = ""
            for prog in items:
                self.text_str = prog
                self.labels[prog] = Gtk.Label()
                self.labels[prog].set_hexpand(True)
                self.labels[prog].set_halign(Gtk.Align.START)


                self.labels[f"{prog}_status"] = self._gtk.Button()
                self.labels[f"{prog}_status"].set_hexpand(False)
                self.labels[f"{prog}_status"].connect("clicked", self.show_update_info, prog)

                if prog in ALLOWED_SERVICES:
                    self.labels[f"{prog}_restart"] = self._gtk.Button("info", scale=.7)
                    #self.labels[f"{prog}_restart"].connect("clicked", self.restart, prog)
                   # infogrid.attach(self.labels[f"{prog}_restart"], 0, i, 1, 1)

                #infogrid.attach(self.labels[f"{prog}_status"], 2, i, 1, 1)
                #self.update_program_info(prog)

                #infogrid.attach(self.labels["Eryone_App"], 1, i, 1, 1)
                self.labels[prog].get_style_context().add_class('updater-item')
                i = i + 1
        printer_name =""
        try:
            file1 = open("/etc/hostname", "r")
            printer_name=file1.read().replace('\n', '')
            file1.close()
        except Exception as e:
            pass
        out = subprocess.run(['cat', "/home/mks/printer_data/config/printer.cfg"],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True
                             )
        version = str(out.stdout)
        hw_version =''
        try:
            hw_version="v1_"+version.split("v1_")[1][:2]
        except Exception as e:
            pass
        self.ipmac = "    Printer Name:   "+printer_name+"\n    Printer Address: "+ni.ifaddresses('eth0')[ni.AF_LINK][0]["addr"] +"\n\n    Hardware:"+hw_version
        self.ipmac = self.ipmac  + "\n\n    Remote control & monitoring:\n    goto 3D Farm https://eryone.club \n    scan the left QR code to add this printer"
        self.labels["version"] = Gtk.Label(label="MAC:")
        self.labels["version"].set_hexpand(True)
        self.labels["version"].set_halign(Gtk.Align.START)
        self.labels["ipmac"] = Gtk.Label(label= self.ipmac)
        self.labels["ipmac"].set_hexpand(True)
        self.labels["ipmac"].set_halign(Gtk.Align.START)


        labels_image = self._screen.gtk.Image()
        pixbuf = self._screen.gtk.PixbufFromFile("/tmp/qrcode.png", 260, 260)
        if pixbuf is not None:
            labels_image.set_from_pixbuf(pixbuf)
            infogrid.attach(labels_image, 0, 1, 1, 1)
        infogrid.attach(self.labels["version"], 1, 2, 2, 1)
       # infogrid.attach(self.labels["Eryone_App"], 1, 2, 1, 1)
        infogrid.attach(self.labels["ipmac"], 1, 1, 1, 1)
        self.labels["version"].get_style_context().add_class('updater-item')
        self.labels["ipmac"].get_style_context().add_class('updater-item')



        scroll.add(infogrid)

        self.grid.attach(scroll, 0, 0, 3, 2)
       # grid.attach(update_all, 1, 2, 1, 1)
        self.grid.attach(self.refresh, 1, 2, 1, 1)
        #grid.attach(reboot, 1, 2, 1, 1)
        self.grid.attach(self.upgrade, 2, 2, 1, 1)

    #scroll.add(vbox)
        self.content.add(self.grid)

    def wait_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
    def activate(self):
        self.get_updates()

    def refresh_updates(self, widget=None):
        self.get_updates()
        #subprocess.run(["/home/mks/KlipperScreen/all/get_canuid.sh", ""])
        subprocess.run(["/home/mks/mainsail/all/recovery.sh", "&"])
        self.refresh.set_sensitive(False)
        self._screen.show_popup_message(_("Checking for updates, please wait..."), level=1)
        GLib.timeout_add_seconds(1, subprocess.run(["/home/mks/mainsail/all/recovery.sh", "&"]), "true")


    def get_updates(self, refresh="false"):

        out = subprocess.run(['cat', "/home/mks/KlipperScreen/version.md"],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True
                             )
        version = str(out.stdout)
        start_l = version.find("X400 ")
        local_v=version[start_l + 5:].replace("\n", "")
        if '192.168' in self._screen.show_title_IP:
            
            out = subprocess.run(['wget','--timeout=4','-q', "https://raw.gitcode.com/xpp012/KlipperScreen/raw/master/version.md",'-O','-'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True
                             )
            remote_version = str(out.stdout)
        else:
            remote_version = 'thinker X'    
        #remote_version = str(out.stdout)
        start_l_r = remote_version.find("X400 ")
        remote_v=remote_version[start_l_r + 5:].replace("\n", "")
        if local_v != remote_v and start_l_r > 0:
            logging.info(f"start_!=: {local_v},{remote_v}")
            self.labels["version"].set_label(
                "    Soft Version:" + local_v + "\n    New  available:" + remote_v)
            self.upgrade.set_sensitive(True)
        else:
            logging.info(f"start_==: {local_v},{remote_v}")
            self.labels["version"].set_label(
                "    Version:" + local_v + "\n   \n")
            self.upgrade.set_sensitive(False)
        #remote_version[start_l_r:]
        #self.labels['MAC'].get_style_context().add_class("printing-status_message")

        self.labels["ipmac"].set_label( self.ipmac )
      #  self.labels[self.text_str].set_label("    This is already the latest Version:\n\n    " + version[start_l:])
        return
        update_resp = self._screen.apiclient.send_request(f"machine/update/status?refresh={refresh}")
        if not update_resp:
            self.update_status = {}
            logging.info("No update manager configured")
        else:
            self.update_status = update_resp['result']
            vi = update_resp['result']['version_info']
            items = sorted(list(vi))
            for prog in items:
                self.update_program_info(prog)
        self.refresh.set_sensitive(True)
        self._screen.close_popup_message()

    def restart(self, widget, program):
        if program not in ALLOWED_SERVICES:
            return

        logging.info(f"Restarting service: {program}")
        self._screen._ws.send_method("machine.services.restart", {"service": program})

    def show_update_info(self, widget, program):
        info = self.update_status['version_info'][program] if program in self.update_status['version_info'] else {}

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)

        label = Gtk.Label()
        label.set_line_wrap(True)
        if program == "full":
            label.set_markup('<b>' + _("Perform a full upgrade?") + '</b>')
            vbox.add(label)
        elif 'configured_type' in info and info['configured_type'] == 'git_repo':
            if not info['is_valid'] or info['is_dirty']:
                label.set_markup(_("Do you want to recover %s?") % program)
                vbox.add(label)
                scroll.add(vbox)
                recoverybuttons = [
                    {"name": _("Recover Hard"), "response": Gtk.ResponseType.OK},
                    {"name": _("Recover Soft"), "response": Gtk.ResponseType.APPLY},
                    {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
                ]
                dialog = self._gtk.Dialog(self._screen, recoverybuttons, scroll, self.reset_confirm, program)
                dialog.set_title(_("Recover"))
                return
            else:
                if info['version'] == info['remote_version']:
                    return
                ncommits = len(info['commits_behind'])
                label.set_markup("<b>" +
                                 _("Outdated by %d") % ncommits +
                                 " " + ngettext("commit", "commits", ncommits) +
                                 ":</b>\n")
                vbox.add(label)

                for c in info['commits_behind']:
                    commit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    title = Gtk.Label()
                    title.set_line_wrap(True)
                    title.set_line_wrap_mode(Pango.WrapMode.CHAR)
                    title.set_markup(f"\n<b>{c['subject']}</b>\n<i>{c['author']}</i>\n")
                    title.set_halign(Gtk.Align.START)
                    commit_box.add(title)

                    details = Gtk.Label(label=f"{c['message']}")
                    details.set_line_wrap(True)
                    details.set_halign(Gtk.Align.START)
                    commit_box.add(details)
                    commit_box.add(Gtk.Separator())
                    vbox.add(commit_box)

        elif "package_count" in info:
            label.set_markup((
                f'<b>{info["package_count"]} '
                + ngettext("Package will be updated", "Packages will be updated", info["package_count"])
                + ':</b>\n'
            ))
            label.set_halign(Gtk.Align.CENTER)
            vbox.add(label)
            grid = Gtk.Grid()
            grid.set_column_homogeneous(True)
            grid.set_halign(Gtk.Align.CENTER)
            grid.set_valign(Gtk.Align.CENTER)
            i = 0
            for j, c in enumerate(info["package_list"]):
                label = Gtk.Label()
                label.set_markup(f"  {c}  ")
                label.set_halign(Gtk.Align.START)
                label.set_ellipsize(Pango.EllipsizeMode.END)
                pos = (j % 3)
                grid.attach(label, pos, i, 1, 1)
                if pos == 2:
                    i += 1
            vbox.add(grid)
        else:
            label.set_markup(
                "<b>" + _("%s will be updated to version") % program.capitalize()
                + f": {info['remote_version']}</b>"
            )
            vbox.add(label)

        scroll.add(vbox)

        buttons = [
            {"name": _("Update"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.update_confirm, program)
        dialog.set_title(_("Update"))

    def update_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Updating {program}")
            self.update_program(self, program)

    def reset_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Recovering hard {program}")
            self.reset_repo(self, program, True)
        if response_id == Gtk.ResponseType.APPLY:
            logging.debug(f"Recovering soft {program}")
            self.reset_repo(self, program, False)

    def reset_repo(self, widget, program, hard):
        if self._screen.updating:
            return
        self._screen.base_panel.show_update_dialog()
        msg = _("Starting recovery for") + f' {program}...'
        self._screen._websocket_callback("notify_update_response",
                                         {'application': {program}, 'message': msg, 'complete': False})
        logging.info(f"Sending machine.update.recover name: {program} hard: {hard}")
        self._screen._ws.send_method("machine.update.recover", {"name": program, "hard": hard})

    def update_program(self, widget, program):
        logging.info(f"Sending machine.update0.{program}")
        # self.gcode_label.set_text("")
        out = subprocess.run(['/home/mks/KlipperScreen/all/git_pull.sh', ''],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True  # Python >= 3.7 also accepts "text=True"
                             )
        logging.info(f"update_program.{out.stdout}")
        out_mes=out.stdout.replace("xpp123","")
        out_mes=out_mes.replace("[sudo] password for mks:", "")
        if "Could not resolve host" in out_mes:
            out_mes = out_mes + "\n         Update Fail! \n        please check network and try again\n"
        elif "HEAD is now at" in out_mes:
            out_mes = out_mes + "\n     Update Success! please reboot\n"

        ###############
        buttons = [
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        label = Gtk.Label(label=_(f"{out_mes}  \n"))
        vbox.add(label)
        scroll.add(vbox)
        self.dialog_wait = self._gtk.Dialog(self._screen, buttons, scroll, self.wait_confirm, '')
        self.dialog_wait.set_title(_("Update"))
        ########
        return
        if self._screen.updating or not self.update_status:
            return

            #logging.info(f"Sending machine.update.{program}")
            #self.add_gcode("response", time.time(), out.stdout)
        if program in self.update_status['version_info']:
            info = self.update_status['version_info'][program]
            logging.info(f"program: {info}")
            if "package_count" in info and info['package_count'] == 0 \
                    or "version" in info and info['version'] == info['remote_version']:
                return
        self._screen.base_panel.show_update_dialog()
        msg = _("Updating") if program == "full" else _("Starting update for") + f' {program}...'
        self._screen._websocket_callback("notify_update_response",
                                         {'application': {program}, 'message': msg, 'complete': False})

        if program in ['klipper', 'moonraker', 'system', 'full']:
            logging.info(f"Sending machine.update.{program}")
            self._screen._ws.send_method(f"machine.update.{program}")
        else:
            logging.info(f"Sending machine.update.client name: {program}")
            self._screen._ws.send_method("machine.update.client", {"name": program})

    def update_program_info(self, p):

        if 'version_info' not in self.update_status or p not in self.update_status['version_info']:
            logging.info(f"Unknown version: {p}")
            return

        info = self.update_status['version_info'][p]

        if p == "system":
            self.labels[p].set_markup("<b>System</b>")
            if info['package_count'] == 0:
                self.labels[f"{p}_status"].set_label(_("Up To Date"))
                self.labels[f"{p}_status"].get_style_context().remove_class('update')
                self.labels[f"{p}_status"].set_sensitive(False)
            else:
                self._needs_update(p, local="", remote=info['package_count'])

        elif 'configured_type' in info and info['configured_type'] == 'git_repo':
            if info['is_valid'] and not info['is_dirty']:
                if info['version'] == info['remote_version']:
                    self._already_updated(p, info)
                    self.labels[f"{p}_status"].get_style_context().remove_class('invalid')
                else:
                    self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}")
                    self._needs_update(p, info['version'], info['remote_version'])
            else:
                logging.info(f"Invalid {p} {info['version']}")
                self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
                self.labels[f"{p}_status"].set_label(_("Invalid"))
                self.labels[f"{p}_status"].get_style_context().add_class('invalid')
                self.labels[f"{p}_status"].set_sensitive(True)
      #  elif 'version' in info and info['version'] == info['remote_version']:
      #      self._already_updated(p, info)
      #  else:
      #      self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}")
      #      self._needs_update(p, info['version'], info['remote_version'])

    def _already_updated(self, p, info):
        logging.info(f"{p} {info['version']}")
        self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
        self.labels[f"{p}_status"].set_label(_("Up To Date"))
        self.labels[f"{p}_status"].get_style_context().remove_class('update')
        self.labels[f"{p}_status"].set_sensitive(False)

    def _needs_update(self, p, local="", remote=""):
        logging.info(f"{p} {local} -> {remote}")
        self.labels[f"{p}_status"].set_label(_("Update"))
        self.labels[f"{p}_status"].get_style_context().add_class('update')
        self.labels[f"{p}_status"].set_sensitive(True)

    def reboot_poweroff_update(self, widget, method):
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        if method == "reboot":
            label = Gtk.Label(label=_("Are you sure you wish to reboot the system?"))
        elif method == "poweroff":
            label = Gtk.Label(label=_("Are you sure you wish to shutdown the system?"))
        elif method == "update":
            label = Gtk.Label(label=_("Perform a full upgrade? this update may take about 5 to 10 minutes"))
        elif method == "recovery":
            label = Gtk.Label(label=_("Recovery to factoring setting? this update may take about 1 minutes"))

        vbox.add(label)
        scroll.add(vbox)
        buttons = [
            #{"name": _("Screen"), "response": Gtk.ResponseType.OK},
            {"name": _("Apply"), "response": Gtk.ResponseType.APPLY},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.reboot_poweroff_update_confirm, method)
        if method == "reboot":
            dialog.set_title(_("Restart"))
        else:
            dialog.set_title(_("Shutdown"))

    def reboot_poweroff_update_confirm(self, dialog, response_id, method):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            subprocess.run([f"/home/mks/mainsail/all/screen_restart.sh"])
            return
            if method == "reboot":
                os.system("systemctl reboot")
            elif method == "poweroff":
                os.system("systemctl poweroff")


        elif response_id == Gtk.ResponseType.APPLY:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
            elif method == "poweroff":
                self._screen._ws.send_method("machine.shutdown")
            elif method == "update":
                GLib.idle_add(self._attach_progress_bar)
                self._screen.show_popup_message("Waiting,this update may take about 5 to 10 minutes", 1, 10)
                GLib.timeout_add_seconds(1, self.process_update, method)

               # GLib.timeout_add_seconds(1, self.get_updates, "true")
                subprocess.Popen(["/home/mks/mainsail/all/git_pull.sh", "&"])
            elif method == "recovery":
                GLib.idle_add(self._attach_progress_bar)
                self._screen.show_popup_message("Recovering, this may take about 1 minute", 1, 10)
                GLib.timeout_add_seconds(1, self.process_update, "recovery")
                subprocess.Popen(["/home/mks/mainsail/all/recovery.sh", "&"])

    def _attach_progress_bar(self):
        if self.grid is not None:
            self.grid.attach(self.progress_bar, 0, 3, 3, 1)
            self.progress_bar.set_show_text(True)
            self.progress_bar.set_text("")
            self.progress_bar.show()
            self.grid.show_all()
        else:
            logging.error("self.grid is None, cannot attach progress bar")

    def process_update(self, action, data):
        if action == "notify_status_update":
            if "display_status" in data and "message" in data["display_status"]:
                message = data['display_status']['message']
                if message is not None:
                    message = message.replace("%20", " ")
                    self.gcode_label.set_text(message)
                    logging.info(f"### Display Status: {message}")
                    if "%" in message or message.startswith("s"):
                        try:
                            if "%" in message:
                                percent_str = message.split("%")[0].strip()
                                if percent_str.isdigit():
                                    percent = float(percent_str) / 100.0
                                else:
                                    raise ValueError(f"Invalid progress value: {percent_str}")
                            elif message.startswith("s") and message[1:].isdigit():
                                percent = float(message[1:]) / 100.0
                            else:
                                raise ValueError(f"Invalid progress value: {message}")
                            logging.info(f"Setting progress bar to {percent}")
                            GLib.idle_add(self.progress_bar.set_fraction, percent)

                        except ValueError as e:
                            logging.error(e)
                else:
                    logging.info("### Display Status message is None")
        elif action == "notify_gcode_response":
            if isinstance(data, str) and "M117" in data:
                message = data.split("M117")[1].strip()
                message = message.replace(" ", "%20")
                self.gcode_label.set_text(message)
                logging.info(f"### G-code Response: {message}")
                if "%" in message:
                    try:
                        percent_str = message.split("%")[0].strip()
                        if percent_str.isdigit():
                            percent = float(percent_str) / 100.0
                            logging.info(f"Setting progress bar to {percent}")
                            GLib.idle_add(self.progress_bar.set_fraction, percent)

                        else:
                            raise ValueError(f"Invalid progress value: {percent_str}")
                    except ValueError as e:
                        logging.error(e)