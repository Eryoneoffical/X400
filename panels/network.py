import logging
import os
import gi
import netifaces
import subprocess

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    initialized = False

    def wait_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
        #if response_id == Gtk.ResponseType.CANCEL:
        #    self.update_program(self, program)
    def __init__(self, screen, title):

        super().__init__(screen, title)
        self.show_add = False
        self.networks = {}
        self.interface = None
        self.prev_network = None
        self.update_timeout = None
        self.network_interfaces = netifaces.interfaces()
        self.wireless_interfaces = [iface for iface in self.network_interfaces if iface.startswith('w')]
        self.wifi = None
        self.use_network_manager = os.system('systemctl is-active --quiet NetworkManager.service') == 0
        buttons = [
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        label = Gtk.Label(label=_("Waiting Scanning, don't scan the wifi in short time"))
        vbox.add(label)
        scroll.add(vbox)
       # self.dialog_wait = self._gtk.Dialog(self._screen, buttons, scroll, self.wait_confirm, title)
      #  self.dialog_wait.set_title(_("Update"))
        #self._screen.show_popup_message("Scanning", 1, 10)
        if len(self.wireless_interfaces) > 0:
            logging.info(f"Found wireless interfaces: {self.wireless_interfaces}")
            if self.use_network_manager:
                logging.info("Using NetworkManager")
                from ks_includes.wifi_nm import WifiManager
            else:
                logging.info("Using wpa_cli")
                from ks_includes.wifi import WifiManager
            self.wifi = WifiManager(self.wireless_interfaces[0])
        else:
            self._screen.show_popup_message("No WIFI Hardware!", 1, 8)
            return
        # Get IP Address
        gws = netifaces.gateways()
        if "default" in gws and netifaces.AF_INET in gws["default"]:
            self.interface = gws["default"][netifaces.AF_INET][1]
        else:
            ints = netifaces.interfaces()
            if 'lo' in ints:
                ints.pop(ints.index('lo'))
            if len(ints) > 0:
                self.interface = ints[0]
            else:
                self.interface = 'lo'

        res = netifaces.ifaddresses(self.interface)
        if netifaces.AF_INET in res and len(res[netifaces.AF_INET]) > 0:
            ip = res[netifaces.AF_INET][0]['addr']
        else:
            ip = None

        self.labels['networks'] = {}

        self.labels['interface'] = Gtk.Label()
        self.labels['interface'].set_text(" %s: %s  " % (_("Interface"), self.interface))
        self.labels['interface'].set_hexpand(True)
        self.labels['ip'] = Gtk.Label()
        self.labels['ip'].set_hexpand(True)
        #reload_networks = self._gtk.Button("refresh", None, "color1", 1.5)
        #reload_networks.connect("clicked", self.reload_networks)
        #reload_networks.set_hexpand(False)

        sbox = Gtk.Box()
        sbox.set_hexpand(True)
        sbox.set_vexpand(False)
        sbox.add(self.labels['interface'])
        if ip is not None:
            self.labels['ip'].set_text(f"IP: {ip}  ")
            sbox.add(self.labels['ip'])
        #sbox.add(reload_networks)

        scroll = self._gtk.ScrolledWindow()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)

        self.labels['networklist'] = Gtk.Grid()

        if self.wifi is not None and self.wifi.initialized:
            box.pack_start(sbox, False, False, 5)
            box.pack_start(scroll, True, True, 0)

            GLib.idle_add(self.load_networks)
            scroll.add(self.labels['networklist'])

            self.wifi.add_callback("connected", self.connected_callback)
            self.wifi.add_callback("scan_results", self.scan_callback)
            self.wifi.add_callback("popup", self.popup_callback)
            if self.update_timeout is None:
                self.update_timeout = GLib.timeout_add_seconds(5, self.update_all_networks)
        else:
            self.labels['networkinfo'] = Gtk.Label()
            self.labels['networkinfo'].get_style_context().add_class('temperature_entry')
            box.pack_start(self.labels['networkinfo'], False, False, 0)
            self.update_single_network_info()
            if self.update_timeout is None:
                self.update_timeout = GLib.timeout_add_seconds(5, self.update_single_network_info)

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)
        grid.get_style_context().add_class('system-program-grid')

        eth0_label=Gtk.Label()
        eth0_label.set_text(" %s  " % ip)
        eth0_label.set_hexpand(True)
        eth0_label.set_halign(Gtk.Align.START)

        ebox_wifi = Gtk.Box()
        ebox_wifi.set_hexpand(True)
        ebox_wifi.set_vexpand(False)

        self.entry_ssid = Gtk.Entry()
        self.entry_ssid.set_hexpand(True)
        self.entry_ssid.set_vexpand(False)
        self.entry_ssid.connect("button-press-event", self._screen.show_keyboard)
        self.entry_ssid.connect("focus-in-event", self._screen.show_keyboard)

        self.entry_ssid.connect("activate", self._screen.remove_keyboard)
        self.entry_ssid.grab_focus_without_selecting()

        self.entry_pss = Gtk.Entry()
        self.entry_pss.set_hexpand(True)
        self.entry_pss.set_vexpand(False)
        self.entry_pss.connect("button-press-event", self._screen.show_keyboard)
        self.entry_pss.connect("focus-in-event", self._screen.show_keyboard)
        self.entry_pss.connect("activate", self._screen.remove_keyboard)
        self.entry_pss.grab_focus_without_selecting()

        enter_wifi = self._gtk.Button("resume", " " + _('Connect') + " ", None, .66, Gtk.PositionType.RIGHT, 1)
        enter_wifi.get_style_context().add_class("buttons_slim")

        enter_wifi.set_hexpand(False)
        enter_wifi.connect("clicked", self.connect_wifi)

        #ebox_wifi.add(entry_ssid)
       # ebox_wifi.add(entry_pss)
        #ebox_wifi.add(enter_wifi)
        ###
        null_label = Gtk.Label()
        null_label.set_text(".")
        null_label.set_hexpand(True)
        null_label.set_halign(Gtk.Align.START)
        null_label1 = Gtk.Label()
        null_label1.set_text("Ethernet")
        null_label1.set_hexpand(True)
        null_label1.set_halign(Gtk.Align.START)
        ####
        wifi_label = Gtk.Label()
        wifi_label.set_text("WiFi")
        wifi_label.set_hexpand(True)
        wifi_label.set_halign(Gtk.Align.START)
        ###
        wifi_ssid = Gtk.Label()
        wifi_ssid.set_text("SSID:")
        wifi_ssid.set_hexpand(True)
        wifi_ssid.set_halign(Gtk.Align.START)
        try:
            file1 = open("/etc/wpa_supplicant/wpa_supplicant-wlan0.conf", "r")
            txt_read=file1.read().split('"')
            ssid_default = txt_read[1]
            psk_default = txt_read[3]
            file1.close()
            self.entry_ssid.set_text(ssid_default)
            self.entry_pss.set_text(psk_default)
        except Exception as e:
            pass
        ###
        wifi_pss = Gtk.Label()
        wifi_pss.set_text("PassWord:")
        wifi_pss.set_hexpand(True)
        wifi_pss.set_halign(Gtk.Align.START)
        ###
        #grid.attach(null_label, 0, 0, 2, 2)
        #grid.attach(null_label1, 0, 1, 2, 2)
        #grid.attach(Gtk.Separator(), 0, 1, 1, 1)
        #grid.attach(eth0_label, 1, 1, 1, 1)
        #grid.attach(Gtk.Separator(), 1, 2, 1, 1)

        grid.attach(null_label, 3, 0, 1, 1)
        grid.attach(null_label, 0, 0, 1, 1)
        grid.attach(wifi_label, 0, 3, 1, 1)
        grid.attach(wifi_ssid, 1, 4, 1, 1)
        grid.attach(self.entry_ssid, 1, 5, 1, 1)
        grid.attach(wifi_pss, 1, 6, 1, 1)
        grid.attach(self.entry_pss, 1, 7, 1, 1)
        grid.attach(enter_wifi, 1, 8, 1, 1)
      #  content_box.pack_end(ebox, False, False, 0)
       # self.content.add(eth0_label)

        self.content.add(grid)

       # self.content.add(box)
        self.labels['main_box'] = box
        self.initialized = True

    def connect_wifi(self,*args):
        self._screen.remove_keyboard()
        ssid=self.entry_ssid.get_text()
        psk = self.entry_pss.get_text()
       # logging.info(f"connect_wifi ssid: {ssid}")
       # self.connect_network(self.entry_ssid, ssid, False)

      #  self._screen.remove_keyboard()
       # psk = self.labels['network_psk'].get_text()

        subprocess.call(
            "echo makerbase | sudo -S cp /home/mks/KlipperScreen/all/wpa_supplicant-wlan0.conf  /etc/wpa_supplicant/wpa_supplicant-wlan0.conf",
            shell=True)

        subprocess.call("echo makerbase | sudo -S sed -i '5s/.*/ssid=\""+ssid+"\"/' /etc/wpa_supplicant/wpa_supplicant-wlan0.conf", shell=True)
        subprocess.call("echo makerbase | sudo -S sed -i '6s/.*/psk=\"" + psk + "\"/' /etc/wpa_supplicant/wpa_supplicant-wlan0.conf",shell=True)
        subprocess.call(
            "echo makerbase | sudo -S killall /sbin/wpa_supplicant",
            shell=True)
        subprocess.call(
            "echo makerbase | sudo -S /sbin/wpa_supplicant -c/etc/wpa_supplicant/wpa_supplicant-wlan0.conf -Dnl80211,wext -iwlan0 &",
            shell=True)
        subprocess.run(["sync", ""])
        logging.info("echo makerbase | sudo -S sed '6s/.*/" + psk + "/' /etc/wpa_supplicant/wpa_supplicant-wlan0.conf")
        self._screen.show_popup_message("Connecting to WiFi ...", 1, 30)
        return
        result = self.wifi.add_network(ssid, psk)

        self.close_add_network()

        if result:
            self.connect_network(self.entry_ssid, ssid, False)
        else:
            self._screen.show_popup_message(f"Error adding network {ssid}")

    def load_networks(self):
        return
        networks = self.wifi.get_networks()
        if not networks:
            return
        for net in networks:
            self.add_network(net, False)
        self.update_all_networks()
        self.content.show_all()

        return False

    def add_network(self, ssid, show=True):

        if ssid is None:
            return
        ssid = ssid.strip()
        if ssid in list(self.networks):
            return

        configured_networks = self.wifi.get_supplicant_networks()
        network_id = -1
        for net in list(configured_networks):
            if configured_networks[net]['ssid'] == ssid:
                network_id = net

        display_name = _("Hidden") if ssid.startswith("\x00") else f"{ssid}"
        netinfo = self.wifi.get_network_info(ssid)
        connected_ssid = self.wifi.get_connected_ssid()
        if netinfo is None:
            logging.debug("Couldn't get netinfo")
            if connected_ssid == ssid:
                netinfo = {'connected': True}
            else:
                netinfo = {'connected': False}

        if connected_ssid == ssid:
            display_name += " (" + _("Connected") + ")"

        name = Gtk.Label()
        name.set_markup(f"<big><b>{display_name}</b></big>")
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        info = Gtk.Label()
        info.set_halign(Gtk.Align.START)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)
        labels.add(info)
        labels.set_vexpand(True)
        labels.set_valign(Gtk.Align.CENTER)
        labels.set_halign(Gtk.Align.START)

        connect = self._gtk.Button("load", None, "color3", .66)
        connect.connect("clicked", self.connect_network, ssid)
        connect.set_hexpand(False)
        connect.set_halign(Gtk.Align.END)

        delete = self._gtk.Button("delete", None, "color3", .66)
        delete.connect("clicked", self.remove_wifi_network, ssid)
        delete.set_hexpand(False)
        delete.set_halign(Gtk.Align.END)

        network = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        network.get_style_context().add_class("frame-item")
        network.set_hexpand(True)
        network.set_vexpand(False)

        network.add(labels)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        if network_id != -1 or netinfo['connected']:
            buttons.pack_end(connect, False, False, 0)
            buttons.pack_end(delete, False, False, 0)
        else:
            buttons.pack_end(connect, False, False, 0)
        network.add(buttons)
        self.networks[ssid] = network

        nets = sorted(list(self.networks), reverse=False)
        if connected_ssid in nets:
            nets.remove(connected_ssid)
            nets.insert(0, connected_ssid)
        if nets.index(ssid) is not None:
            pos = nets.index(ssid)
        else:
            logging.info("Error: SSID not in nets")
            return

        self.labels['networks'][ssid] = {
            "connect": connect,
            "delete": delete,
            "info": info,
            "name": name,
            "row": network
        }

        self.labels['networklist'].insert_row(pos)
        self.labels['networklist'].attach(self.networks[ssid], 0, pos, 1, 1)
        if show:
            self.labels['networklist'].show()

    def add_new_network(self, widget, ssid, connect=False):
        self._screen.remove_keyboard()
        psk = self.labels['network_psk'].get_text()
        result = self.wifi.add_network(ssid, psk)

        self.close_add_network()

        if connect:
            if result:
                self.connect_network(widget, ssid, False)
            else:
                self._screen.show_popup_message(f"Error adding network {ssid}")

    def back(self):
        if self.show_add:
            self.close_add_network()
            #self._screen._menu_go_back()
            #self.base_panel.back()
           # return True
        return False

    def check_missing_networks(self):
        networks = self.wifi.get_networks()
        for net in list(self.networks):
            if net in networks:
                networks.remove(net)

        for net in networks:
            self.add_network(net, False)
        self.labels['networklist'].show_all()

    def close_add_network(self):
        if not self.show_add:
            return

        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels['main_box'])
        self.content.show()
        for i in ['add_network', 'network_psk']:
            if i in self.labels:
                del self.labels[i]
        self.show_add = False

    def popup_callback(self, msg):
        self._screen.show_popup_message(msg)

    def connected_callback(self, ssid, prev_ssid):
        logging.info("Now connected to a new network")
        if ssid is not None:
            self.remove_network(ssid)
        if prev_ssid is not None:
            self.remove_network(prev_ssid)

        self.check_missing_networks()

    def connect_network(self, widget, ssid, showadd=True):

        snets = self.wifi.get_supplicant_networks()
        isdef = False
        for netid, net in snets.items():
            if net['ssid'] == ssid:
                isdef = True
                break

        if not isdef:
            if showadd:
                self.show_add_network(widget, ssid)
            return
        self.prev_network = self.wifi.get_connected_ssid()

        buttons = [
            {"name": _("Close"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = self._gtk.ScrolledWindow()
        self.labels['connecting_info'] = Gtk.Label(_("Starting WiFi Association"))
        self.labels['connecting_info'].set_halign(Gtk.Align.START)
        self.labels['connecting_info'].set_valign(Gtk.Align.START)
        scroll.add(self.labels['connecting_info'])
        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self._gtk.remove_dialog)
        dialog.set_title(_("Starting WiFi Association"))
        self._screen.show_all()

        if ssid in list(self.networks):
            self.remove_network(ssid)
        if self.prev_network in list(self.networks):
            self.remove_network(self.prev_network)

        self.wifi.add_callback("connecting_status", self.connecting_status_callback)
        self.wifi.connect(ssid)

    def connecting_status_callback(self, msg):
        self.labels['connecting_info'].set_text(f"{self.labels['connecting_info'].get_text()}\n{msg}")
        self.labels['connecting_info'].show_all()

    def remove_network(self, ssid, show=True):
        if ssid not in list(self.networks):
            return
        for i in range(len(self.labels['networklist'])):
            if self.networks[ssid] == self.labels['networklist'].get_child_at(0, i):
                self.labels['networklist'].remove_row(i)
                self.labels['networklist'].show()
                del self.networks[ssid]
                del self.labels['networks'][ssid]
                return

    def remove_wifi_network(self, widget, ssid):
        self.wifi.delete_network(ssid)
        self.remove_network(ssid)
        self.check_missing_networks()

    def scan_callback(self, new_networks, old_networks):
        return
        for net in old_networks:
            self.remove_network(net, False)
        for net in new_networks:
            self.add_network(net, False)
        self.content.show_all()
        #self._gtk.remove_dialog(self.dialog_wait)

    def show_add_network(self, widget, ssid):
        if self.show_add:
            return

        for child in self.content.get_children():
            self.content.remove(child)

        if "add_network" in self.labels:
            del self.labels['add_network']

        label = self._gtk.Label(_("PSK for") + ' ssid')
        label.set_hexpand(False)
        self.labels['network_psk'] = Gtk.Entry()
        self.labels['network_psk'].set_text('')
        self.labels['network_psk'].set_hexpand(True)
        self.labels['network_psk'].connect("activate", self.add_new_network, ssid, True)
        self.labels['network_psk'].connect("focus-in-event", self._screen.show_keyboard)

        save = self._gtk.Button("sd", _("Save"), "color3")
        save.set_hexpand(False)
        save.connect("clicked", self.add_new_network, ssid, True)

        box = Gtk.Box()
        box.pack_start(self.labels['network_psk'], True, True, 5)
        box.pack_start(save, False, False, 5)

        self.labels['add_network'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.labels['add_network'].set_valign(Gtk.Align.CENTER)
        self.labels['add_network'].set_hexpand(True)
        self.labels['add_network'].set_vexpand(True)
        self.labels['add_network'].pack_start(label, True, True, 5)
        self.labels['add_network'].pack_start(box, True, True, 5)

        self.content.add(self.labels['add_network'])
        self.labels['network_psk'].grab_focus_without_selecting()
        self.content.show_all()
        self.show_add = True

    def update_all_networks(self):
        for network in list(self.networks):
            self.update_network_info(network)
        return True

    def update_network_info(self, ssid):

        info = freq = encr = chan = lvl = ipv4 = ipv6 = ""

        if ssid not in list(self.networks) or ssid not in self.labels['networks']:
            logging.info(f"Unknown SSID {ssid}")
            return
        netinfo = self.wifi.get_network_info(ssid)
        if "connected" in netinfo:
            connected = netinfo['connected']
        else:
            connected = False

        if connected or self.wifi.get_connected_ssid() == ssid:
            stream = os.popen('hostname -f')
            hostname = stream.read().strip()
            ifadd = netifaces.ifaddresses(self.interface)
            if netifaces.AF_INET in ifadd and len(ifadd[netifaces.AF_INET]) > 0:
                ipv4 = f"<b>IPv4:</b> {ifadd[netifaces.AF_INET][0]['addr']} "
                self.labels['ip'].set_text(f"IP: {ifadd[netifaces.AF_INET][0]['addr']}  ")
            if netifaces.AF_INET6 in ifadd and len(ifadd[netifaces.AF_INET6]) > 0:
                ipv6 = f"<b>IPv6:</b> {ifadd[netifaces.AF_INET6][0]['addr'].split('%')[0]} "
            info = '<b>' + _("Hostname") + f':</b> {hostname}\n{ipv4}\n{ipv6}\n'
        elif "psk" in netinfo:
            info = _("Password saved")
        if "encryption" in netinfo:
            if netinfo['encryption'] != "off":
                encr = netinfo['encryption'].upper()
        if "frequency" in netinfo:
            freq = "2.4 GHz" if netinfo['frequency'][0:1] == "2" else "5 Ghz"
        if "channel" in netinfo:
            chan = _("Channel") + f' {netinfo["channel"]}'
        if "signal_level_dBm" in netinfo:
            lvl = f'{netinfo["signal_level_dBm"]} ' + _("dBm")

        self.labels['networks'][ssid]['info'].set_markup(f"{info} <small>{encr}  {freq}  {chan}  {lvl}</small>")
        self.labels['networks'][ssid]['info'].show_all()

    def update_single_network_info(self):

        stream = os.popen('hostname -f')
        hostname = stream.read().strip()
        ifadd = netifaces.ifaddresses(self.interface)
        ipv4 = ""
        ipv6 = ""
        if netifaces.AF_INET in ifadd and len(ifadd[netifaces.AF_INET]) > 0:
            ipv4 = f"<b>IPv4:</b> {ifadd[netifaces.AF_INET][0]['addr']} "
            self.labels['ip'].set_text(f"IP: {ifadd[netifaces.AF_INET][0]['addr']}  ")
        if netifaces.AF_INET6 in ifadd and len(ifadd[netifaces.AF_INET6]) > 0:
            ipv6 = f"<b>IPv6:</b> {ifadd[netifaces.AF_INET6][0]['addr'].split('%')[0]} "
        connected = (
            f'<b>{self.interface}</b>\n\n'
            f'<small><b>' + _("Connected") + f'</b></small>\n'
            + '<b>' + _("Hostname") + f':</b> {hostname}\n'
            f'{ipv4}\n'
            f'{ipv6}\n'
        )

        self.labels['networkinfo'].set_markup(connected)
        self.labels['networkinfo'].show_all()
        return True

    def reload_networks(self, widget=None):

        self.networks = {}
        logging.debug(f" sel22.wifi.initialized:{self.wifi.initialized} ")
        self.labels['networklist'].remove_column(0)
        if self.wifi is not None and self.wifi.initialized:
            logging.debug(f" 33wifi.initialized:{self.wifi.initialized} ")
            #self._screen.show_popup_message("waiting scanning", 1, 6)
            ret=self.wifi.rescan()
            if ret == 0:
                GLib.idle_add(self.load_networks)
            #else:
                #self._screen.show_popup_message("don't scan the wifi in short time", 1, 6)
                #self._gtk.remove_dialog(self.dialog_wait)


    def activate(self):
        if self.initialized:
           # self.reload_networks()
            if self.update_timeout is None:
                if self.wifi is not None and self.wifi.initialized:
                    self.update_timeout = GLib.timeout_add_seconds(5, self.update_all_networks)
                else:
                    self.update_timeout = GLib.timeout_add_seconds(5, self.update_single_network_info)

    def deactivate(self):
        if self.update_timeout is not None:
            GLib.source_remove(self.update_timeout)
            self.update_timeout = None
