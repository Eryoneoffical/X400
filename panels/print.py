# -*- coding: utf-8 -*-
import configparser
import hashlib
import json
import logging
import os
from threading import Thread
import subprocess

import gi,time
import shutil
import shutil


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from datetime import datetime
from ks_includes.screen_panel import ScreenPanel


class ProgressBarWindow(Gtk.Window):
    def __init__(self,screen):
        super().__init__(title="ProgressBar Demo")
        #self.set_border_width(100)
        self.entry_z = None
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)
        
        label = Gtk.Label(label="  ")
        vbox.pack_start(label, True, True, 0)
        
        self.progressbar = Gtk.ProgressBar()
        vbox.pack_start(self.progressbar, True, True, 0)

        self.timeout_id = GLib.timeout_add(1, self.on_timeout, None)
        self.activity_mode = False

        width, height = screen.get_size()
        self.set_default_size(width, height)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.label = Gtk.Label(label=" ")
        vbox.pack_start(self.label, True, True, 0)
        label = Gtk.Label(label="  ")
        vbox.pack_start(label, True, True, 0)

    def on_timeout(self, user_data):
        """
        Update value on the progress bar
        """
        #self.win.hide()



        # As this is a timeout function, return True so that it
        # continues to get called
        return True
class Panel(ScreenPanel):
    cur_directory = "gcodes"
    dir_panels = {}
    filelist = {'gcodes': {'directories': [], 'files': []}}

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.entry_z = None
        self.gtk = screen.gtk
        self.distance = 0.05
        sortdir = self._config.get_main_config().get("print_sort_dir", "name_asc")
        sortdir = sortdir.split('_')
        if sortdir[0] not in ["name", "date"] or sortdir[1] not in ["asc", "desc"]:
            sortdir = ["name", "asc"]
        self.sort_current = [sortdir[0], 0 if sortdir[1] == "asc" else 1]  # 0 for asc, 1 for desc
        self.sort_items = {
            "name": _("Name"),
            "date": _("Date")
        }
        self.sort_icon = ["arrow-up", "arrow-down"]
        self.scroll = self._gtk.ScrolledWindow()
        self.files = {}
        self.directories = {}
        self.labels['directories'] = {}
        self.labels['files'] = {}
        self.source = ""
        self.time_24 = self._config.get_main_config().getboolean("24htime", True)
        logging.info(f"24h time is {self.time_24}")

        sbox = Gtk.Box(spacing=0)
        sbox.set_vexpand(False)
        for i, (name, val) in enumerate(self.sort_items.items(), start=1):
            s = self._gtk.Button(None, val, f"color{i % 4}", .5, Gtk.PositionType.RIGHT, 1)
            s.get_style_context().add_class("buttons_slim")
            if name == self.sort_current[0]:
                s.set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]], self._gtk.img_scale * self.bts))
            s.connect("clicked", self.change_sort, name)
            self.labels[f'sort_{name}'] = s
            sbox.add(s)

        deAll = self._gtk.Button("delete", style="color1", scale=self.bts)
        deAll.get_style_context().add_class("buttons_slim")
        deAll.connect('clicked', self._deAll_files)
        sbox.add(deAll)

        refresh = self._gtk.Button("refresh", style="color4", scale=self.bts)
        refresh.get_style_context().add_class("buttons_slim")
        refresh.connect('clicked', self._refresh_files)
        sbox.add(refresh)


        sbox.set_hexpand(True)
        sbox.set_vexpand(False)

        pbox = Gtk.Box(spacing=0)
        pbox.set_hexpand(True)
        pbox.set_vexpand(False)
        self.labels['path'] = Gtk.Label()
        pbox.add(self.labels['path'])
        self.labels['path_box'] = pbox

        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main.set_vexpand(True)
        self.main.pack_start(sbox, False, False, 0)
        self.main.pack_start(pbox, False, False, 0)
        self.main.pack_start(self.scroll, True, True, 0)

        self.dir_panels['gcodes'] = Gtk.Grid()

        GLib.idle_add(self.reload_files)

        self.scroll.add(self.dir_panels['gcodes'])
        self.content.add(self.main)
        self._screen.files.add_file_callback(self._callback)
        self.showing_rename = False
        self.win = ProgressBarWindow(screen)
        self.win.connect("destroy", Gtk.main_quit)

    def queue_confirm_c(self, dialog, response_id, filename):

        if response_id == Gtk.ResponseType.CANCEL:
            self._gtk.remove_dialog(dialog)
            return
        out = subprocess.run(['curl', '-s','-d', '/server/job_queue/start','http://127.0.0.1/server/job_queue/start'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True  # Python >= 3.7 also accepts "text=True"
                             )
        logging.debug(out.stdout)
        time.sleep(1)
        self._gtk.remove_dialog(dialog)
        #self.back()
    def activate(self):
        out = subprocess.run(['curl', '-s', 'http://127.0.0.1/server/job_queue/status'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True  # Python >= 3.7 also accepts "text=True"
                             )
        job_queue = json.loads(out.stdout)
        logging.debug(out.stdout)
        logging.debug(len(job_queue['result']['queued_jobs']))
        if len(job_queue['result']['queued_jobs']) > 0:
            first_file = job_queue['result']['queued_jobs'][0]['filename']
            buttons = [
                {"name": _("Print"), "response": Gtk.ResponseType.OK},
                {"name": _("Later"), "response": Gtk.ResponseType.CANCEL}
            ]
            scroll = self._gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            vbox.set_halign(Gtk.Align.CENTER)
            vbox.set_valign(Gtk.Align.CENTER)
            label = Gtk.Label('有打印任务：')
            vbox.add(label)
            label = Gtk.Label('')
            vbox.add(label)
            index = 0
            for item in job_queue['result']['queued_jobs']:
                label = Gtk.Label(f"            {index} : {item['filename']}")
                index = index + 1
                logging.debug(item['filename'])
                vbox.add(label)
                label = Gtk.Label('')
                vbox.add(label)
            scroll.add(vbox)
            self.dialog_wait = self._gtk.Dialog(self._screen, buttons, scroll, self.queue_confirm_c, first_file)
            self.dialog_wait.set_title(_("Update"))


        if self.cur_directory != "gcodes":
            self.change_dir(None, "gcodes")
        self._refresh_files()

    def deactivate(self):
        self.win.hide()
        #subprocess.run(["sync", ""])

    def add_directory(self, directory, show=True):
        parent_dir = os.path.dirname(directory)
        if directory not in self.filelist:
            self.filelist[directory] = {'directories': [], 'files': [], 'modified': 0}
            self.filelist[parent_dir]['directories'].append(directory)

        if directory not in self.labels['directories']:
            self._create_row(directory)
        reverse = self.sort_current[1] != 0
        dirs = sorted(
            self.filelist[parent_dir]['directories'],
            reverse=reverse, key=lambda item: self.filelist[item]['modified']
        ) if self.sort_current[0] == "date" else sorted(self.filelist[parent_dir]['directories'], reverse=reverse)

        pos = dirs.index(directory)

        self.dir_panels[parent_dir].insert_row(pos)
        self.dir_panels[parent_dir].attach(self.directories[directory], 0, pos, 1, 1)
        if show is True:
            self.dir_panels[parent_dir].show_all()

    def add_file(self, filepath, show=True):
        fileinfo = self._screen.files.get_file_info(filepath)
        if fileinfo is None:
            return
        filename = os.path.basename(filepath)
        if filename.startswith("."):
            return
        directory = os.path.dirname(os.path.join("gcodes", filepath))
        d = directory.split(os.sep)
        for i in range(1, len(d)):
            curdir = os.path.join(*d[:i])
            newdir = os.path.join(*d[:i + 1])
            if newdir not in self.filelist[curdir]['directories']:
                if d[i].startswith("."):
                    return
                self.add_directory(newdir)

        if filename not in self.filelist[directory]['files']:
            for i in range(1, len(d)):
                curdir = os.path.join(*d[:i + 1])
                if curdir != "gcodes" and fileinfo['modified'] > self.filelist[curdir]['modified']:
                    self.filelist[curdir]['modified'] = fileinfo['modified']
                    if self.time_24:
                        time = f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %H:%M}</b>'
                    else:
                        time = f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %I:%M %p}</b>'
                    info = _("Modified") + time
                    info += "\n" + _("Size") + f':<b>  {self.format_size(fileinfo["size"])}</b>'
                    self.labels['directories'][curdir]['info'].set_markup(info)
            self.filelist[directory]['files'].append(filename)

        if filepath not in self.files:
            self._create_row(filepath, filename)
        reverse = self.sort_current[1] != 0
        files = sorted(
            self.filelist[directory]['files'],
            reverse=reverse,
            key=lambda item: self._screen.files.get_file_info(f"{directory}/{item}"[7:])['modified']
        ) if self.sort_current[0] == "date" else sorted(self.filelist[directory]['files'], reverse=reverse)

        pos = files.index(filename)
        pos += len(self.filelist[directory]['directories'])

        self.dir_panels[directory].insert_row(pos)
        self.dir_panels[directory].attach(self.files[filepath], 0, pos, 1, 1)
        if show is True:
            self.dir_panels[directory].show_all()
        return False

    def _create_row(self, fullpath, filename=None):
        name = Gtk.Label()
        name.get_style_context().add_class("print-filename")
        if filename:
            name.set_markup(f'<big><b>{os.path.splitext(filename)[0].replace("_", " ")}</b></big>')
        else:
            name.set_markup(f"<big><b>{os.path.split(fullpath)[-1]}</b></big>")
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.CHAR)

        info = Gtk.Label()
        info.set_hexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("print-info")

        delete = self._gtk.Button("delete", style="color1", scale=self.bts)
        delete.set_hexpand(False)
        rename = self._gtk.Button("files", style="color2", scale=self.bts)
        rename.set_hexpand(False)

        if filename:
            action = self._gtk.Button("print", style="color3")
            action.connect("clicked", self.confirm_print, fullpath)
            info.set_markup(self.get_file_info_str(fullpath))
            icon = Gtk.Button()
            icon.connect("clicked", self.confirm_print, fullpath)
            delete.connect("clicked", self.confirm_delete_file, f"gcodes/{fullpath}")
            rename.connect("clicked", self.show_rename, f"gcodes/{fullpath}")
            GLib.idle_add(self.image_load, fullpath)
        else:
            action = self._gtk.Button("load", style="color3")
            action.connect("clicked", self.change_dir, fullpath)
            icon = self._gtk.Button("folder")
            icon.connect("clicked", self.change_dir, fullpath)
            delete.connect("clicked", self.confirm_delete_directory, fullpath)
            rename.connect("clicked", self.show_rename, fullpath)
        icon.set_hexpand(False)
        action.set_hexpand(False)
        action.set_halign(Gtk.Align.END)

        delete.connect("clicked", self.confirm_delete_file, f"gcodes/{fullpath}")

        row = Gtk.Grid()
        row.get_style_context().add_class("frame-item")
        row.set_hexpand(True)
        row.set_vexpand(False)
        row.attach(icon, 0, 0, 1, 2)
        row.attach(name, 1, 0, 3, 1)
        row.attach(info, 1, 1, 1, 1)
        row.attach(rename, 2, 1, 1, 1)
        row.attach(delete, 3, 1, 1, 1)

        if not filename or (filename and os.path.splitext(filename)[1] in [".gcode", ".g", ".gco"]):
            row.attach(action, 4, 0, 1, 2)

        if filename is not None:
            self.files[fullpath] = row
            self.labels['files'][fullpath] = {
                "icon": icon,
                "info": info,
                "name": name
            }
        else:
            self.directories[fullpath] = row
            self.labels['directories'][fullpath] = {
                "info": info,
                "name": name
            }
            self.dir_panels[fullpath] = Gtk.Grid()

    def image_load(self, filepath):
        pixbuf = self.get_file_image(filepath, small=True)
        if pixbuf is not None:
            self.labels['files'][filepath]['icon'].set_image(Gtk.Image.new_from_pixbuf(pixbuf))
        else:
            self.labels['files'][filepath]['icon'].set_image(self._gtk.Image("file"))
        return False

    def confirm_delete_file(self, widget, filepath):
        logging.debug(f"Sending delete_file {filepath}")
        params = {"path": f"{filepath}"}
        self._screen._confirm_send_action(
            None,
            _("Delete File?") + "\n\n" + filepath,
            "server.files.delete_file",
            params
        )

    def confirm_delete_directory(self, widget, dirpath):
        logging.debug(f"Sending delete_directory {dirpath}")
        params = {"path": f"{dirpath}", "force": True}
        self._screen._confirm_send_action(
            None,
            _("Delete Directory?") + "\n\n" + dirpath,
            "server.files.delete_directory",
            params
        )

    def back(self):
        if self.showing_rename:
            self.hide_rename()
            return True
        if os.path.dirname(self.cur_directory):
            self.change_dir(None, os.path.dirname(self.cur_directory))
            return True
        return False

    def change_dir(self, widget, directory):
        if directory not in self.dir_panels:
            return
        logging.debug(f"Changing dir to {directory}")

        for child in self.scroll.get_children():
            self.scroll.remove(child)
        self.cur_directory = directory
        self.labels['path'].set_text(f"  {self.cur_directory[7:]}")

        self.scroll.add(self.dir_panels[directory])
        self.content.show_all()

    def change_sort(self, widget, key):
        if self.sort_current[0] == key:
            self.sort_current[1] = (self.sort_current[1] + 1) % 2
        else:
            oldkey = self.sort_current[0]
            logging.info(f"Changing sort_{oldkey} to {self.sort_items[self.sort_current[0]]}")
            self.labels[f'sort_{oldkey}'].set_image(None)
            self.labels[f'sort_{oldkey}'].show_all()
            self.sort_current = [key, 0]
        self.labels[f'sort_{key}'].set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]],
                                                             self._gtk.img_scale * self.bts))
        self.labels[f'sort_{key}'].show()
        GLib.idle_add(self.reload_files)

        self._config.set("main", "print_sort_dir", f'{key}_{"asc" if self.sort_current[1] == 0 else "desc"}')
        self._config.save_user_config_options()

    def confirm_print(self, widget, filename):
        logging.debug(f"type: {Gtk.ResponseType}")
        buttons = [
            {"name": _("Print"), "response": Gtk.ResponseType.OK},
           # {"name": _("Resume"), "response": Gtk.ResponseType.ACCEPT},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

        label = Gtk.Label()
        label.set_markup(f"<b>{filename}</b>\n")
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = Gtk.Grid()
        grid.set_vexpand(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        grid.add(label)

        buttonz0 = self._gtk.Button(label=_("Resume"))
        buttonz0.set_direction(Gtk.TextDirection.LTR)
        buttonz0.connect("clicked", self.resume_print_confirm, filename)


        pixbuf = self.get_file_image(filename, self._screen.width * .9, self._screen.height * .4)
        if pixbuf is not None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.set_vexpand(False)
            grid.attach_next_to(image, label, Gtk.PositionType.BOTTOM, 1, 1)
            grid.attach(buttonz0, 3, 0, 1, 1)

        self.dialog_p = self._gtk.Dialog(self._screen, buttons, grid, self.confirm_print_response, filename)
        self.dialog_p.set_title(_("Print"))

    def copy_callback(self,copied):
        if copied == 100:
            copied = 99
        self.win.progressbar.set_text("%d"%copied)
        self.win.progressbar.set_show_text(True) 
        self.win.progressbar.set_fraction(copied/100)
        

    def copyfileobj(self,fsrc, fdst, callback, length=0):
        #subprocess.run(["sync", ""])
        fsrc.seek(0, os.SEEK_END)
        total_len=fsrc.tell()
        fsrc.seek(0, os.SEEK_SET)

        if not length:
            length = 1024*64#shutil.COPY_BUFSIZE

        fsrc_read = fsrc.read
        fdst_write = fdst.write
        fdst.seek(0, os.SEEK_SET)
        copied = 0
        procress_len_old = 0
        #self._screen.show_popup_message(f"Copy file ... {copied * 100 / total_len}")
        while True:
            buf = fsrc_read(length)
            if not buf:
                break
            fdst_write(buf)
            copied += len(buf)
            procress_len = int(copied*100/total_len)
            if procress_len_old != procress_len and procress_len % 10 < 1:
                logging.info("copied=%d %d" % (procress_len, procress_len % 10))
                callback(procress_len)
                procress_len_old = procress_len

        #self.win.hide()
        #subprocess.run(["sync", ""])
            #logging.info("copied=%d"%copied)

    def threaded_function(self, args):
        #self.win.progressbar.set_text("0")
        #self.win.progressbar.set_show_text(True)

        self.win.progressbar.set_text("0")
        self.win.progressbar.set_show_text(True)
        self.win.label.set_text("Copy file " + args)

        # wait 1 sec in between each thread
        #time.sleep(1)
        p_n = args.rfind("/")
        name = args[p_n+1:]
        src_md5 = hashlib.md5(open("/home/mks/printer_data/gcodes/"+args, 'rb').read()).hexdigest()

        logging.info(f"copy file from usb: {args}==>{name} md5: {src_md5}")
        fo_dst = open("/home/mks/printer_data/gcodes/"+name, "w")
        fo_src = open("/home/mks/printer_data/gcodes/"+args, "r")
        #self.win.label.set_text("Copy file "+args+" to " +name )

        self.copyfileobj(fo_src,fo_dst,self.copy_callback)

        src_md5_1 = hashlib.md5(open("/home/mks/printer_data/gcodes/" + name, 'rb').read()).hexdigest()
        logging.info(f"print start:{name} , md5_1:{src_md5_1}")

        if src_md5_1 != src_md5:
            #self._screen.show_popup_message("copy file failed,please try again", level=1)
            self.copyfileobj(fo_src, fo_dst, self.copy_callback)

            src_md5_1 = hashlib.md5(open("/home/mks/printer_data/gcodes/" + name, 'rb').read()).hexdigest()
            logging.info(f"print start:{name} , md5_1:{src_md5_1}")
            if src_md5_1 != src_md5:
                self.win.hide()
                return
        #self.win.hide()
        subprocess.run(["sync", ""])
        self._screen._ws.klippy.print_start(name)

    @staticmethod
    def validate_temp(temp):
        try:
            return float(temp)
        except ValueError:
            return 0
    def update_entry(self, widget, digit):
        text = self.labels['entry'].get_text()
        if digit == 'B':
            if len(text) < 1:
                return
            self.labels['entry'].set_text(text[:-1])
        elif digit == 'E':
            #self.change_temp(temp)
            #self.labels['entry'].set_text("")
           # self.labels["keypad"].set_visible(True)
            logging.debug("update_entry")
            self.keygrid.remove(self.labels["keypad"])
            self.keygrid.remove(self.button_entry_ok)
            self.keygrid.attach(self.adjust_z, 1, 1, 1, 1)

            logging.debug("update_entry--")

        elif len(text + digit) > 8:
            return
        else:
            self.labels['entry'].set_text(text + digit)
        self.resume_z = self.labels['entry'].get_text()
        #self.pid.set_sensitive(self.validate_temp(self.labels['entry'].get_text()) > 9)

    def show_numpad(self, widget, device):
        logging.debug("update_entry- show")
        self.keygrid.attach(self.labels["keypad"], 1, 1, 1, 1)
        self.keygrid.attach(self.button_entry_ok, 2, 0, 1, 1)
        self.keygrid.remove(self.adjust_z)

    def hide_numpad(self, widget, device):
        logging.debug("update_entry- hide-")
        self.keygrid.remove(self.labels["keypad"])
        self.keygrid.remove(self.button_entry_ok)
        self.keygrid.attach(self.adjust_z, 1, 1, 1, 1)

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        if distance == 5:
            self.buttonz_05.get_style_context().remove_class("distbutton_active")
            self.buttonz_5.get_style_context().add_class("distbutton_active")
        else:
            self.buttonz_5.get_style_context().remove_class("distbutton_active")
            self.buttonz_05.get_style_context().add_class("distbutton_active")
        self.distance = distance
    def adjust_nozzle(self, widget, up_down):
        logging.info(f"### adjust_nozzle {up_down}{self.distance}")

        self._screen._ws.klippy.gcode_script("SET_KINEMATIC_POSITION Z=10")
        self._screen._ws.klippy.gcode_script("G91")
        self._screen._ws.klippy.gcode_script(f"G1 Z{up_down}{self.distance}")
        self._screen._ws.klippy.gcode_script("G90")


    def resume_print_confirm(self, widget, filename):
        self._gtk.remove_dialog(self.dialog_p)
        buttons = [
            {"name": _("Print"), "response": Gtk.ResponseType.YES},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]



        label = Gtk.Label()
        label.set_markup(f"<b>{filename}</b>\n")
        label.set_hexpand(False)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(False)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = Gtk.Grid()
        grid.set_hexpand(False)
        grid.set_vexpand(False)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        #grid.set_homogeneous(True)
        grid.set_row_spacing(1)
        grid.set_column_spacing(1)
        #grid.set_size_request(self.gtk.content_width / 10, self.gtk.keyboard_height / 10)
       # grid.add(label)


        #grid.add(self.entry_z)
        #####
        self.labels = {}
        numpad = Gtk.Grid() #self._gtk.HomogeneousGrid()
        numpad.set_size_request(100, 100)
        numpad.set_hexpand(False)
        numpad.set_vexpand(False)
        numpad.set_direction(Gtk.TextDirection.LTR)
        numpad.get_style_context().add_class('numpad')
        numpad.set_halign(Gtk.Align.CENTER)
        numpad.set_valign(Gtk.Align.CENTER)

        keys = [
            ['1', 'numpad_right'],
            ['2', 'numpad_right'],
            ['3', 'numpad_right'],
            ['4', 'numpad_right'],
            ['5', 'numpad_right'],
            ['6', 'numpad_right'],
            ['7', 'numpad_right'],
            ['8', 'numpad_right'],
            ['9', 'numpad_right'],
            ['0', 'numpad_right'],
            ['.', 'numpad_right'],
            ['B', 'numpad_right'],
           # ['E', 'numpad_right']
        ]
        for i in range(len(keys)):
            k_id = f'button_{str(keys[i][0])}'
            if keys[i][0] == "B":
                self.labels[k_id] = self._gtk.Button("backspace", scale=0.6)
            elif keys[i][0] == "E":
                self.labels[k_id] = self._gtk.Button("complete", scale=0.7)
            else:
                self.labels[k_id] = Gtk.Button(label=keys[i][0])
            self.labels[k_id].connect('clicked', self.update_entry, keys[i][0])
            self.labels[k_id].get_style_context().add_class(keys[i][1])
            numpad.attach(self.labels[k_id], i % 6, i / 6, 1, 1)
        self.keygrid = grid
        self.labels["keypad"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['entry'] = Gtk.Entry()
        self.labels['entry'].props.xalign = 0.5
        self.labels['entry'].set_can_focus(False)

        self.labels["keypad"] = numpad

        #### read default height in variables.cfg
        config = configparser.ConfigParser()
        config.read('/home/mks/printer_data/config/variable.cfg')
        logging.debug(f"All sections:{config['Variables']}")
        if 'Variables' in config:
            power_resume_z = config.get('Variables', 'power_resume_z', fallback=None)
            if power_resume_z is not None:
                power_resume_z = config['Variables']['power_resume_z']
                self.resume_z = power_resume_z
                self.labels['entry'].set_text(f"{power_resume_z}")
                logging.debug(f"power_resume_z:{power_resume_z}" )

        ###

       # self.labels['entry'].connect("activate", self.hide_numpad)
        self.labels['entry'].connect("focus-in-event", self.hide_numpad)
        self.labels['entry'].connect("button-press-event", self.show_numpad)

       # self.pid = self._gtk.Button('heat-up', _('Calibrate') + ' PID', None, .66, Gtk.PositionType.LEFT, 1)
       # self.pid.connect("clicked", self.update_entry, "PID")
        #self.pid.set_sensitive(False)
       # self.pid.set_no_show_all(True)

        label_en = Gtk.Label()
        label_en.set_markup(_("Start") + " " + _("Height:") + "(mm)")


        #grid.add(self.labels['entry'])
        #grid.add(grid2)

        grid.attach(label, 0, 0, 1, 1)

        label_nozzle = Gtk.Label()
        label_nozzle.set_markup(_("Adjust") +" "+ _("Nozzle:") )
        self.adjust_z = Gtk.Grid()
        self.adjust_z.set_hexpand(False)
        self.adjust_z.set_vexpand(False)
        self.adjust_z.set_direction(Gtk.TextDirection.LTR)
        self.adjust_z.get_style_context().add_class('numpad')
        self.adjust_z.set_halign(Gtk.Align.CENTER)
        self.adjust_z.set_valign(Gtk.Align.CENTER)
        buttonz0 = self._gtk.Button(label=_("Raise Nozzle"), scale=1)
        buttonz1 = self._gtk.Button(label=_("Lower Nozzle"), scale=1)
        self.buttonz_05 = self._gtk.Button(label="0.05", scale=1)
        self.buttonz_5 = self._gtk.Button(label="5", scale=1)
        self.buttonz_05.set_direction(Gtk.TextDirection.LTR)
        self.buttonz_5.set_direction(Gtk.TextDirection.LTR)
        buttonz0.connect("clicked", self.adjust_nozzle, "")
        buttonz1.connect("clicked", self.adjust_nozzle, "-")
        self.buttonz_05.connect("clicked", self.change_distance, 0.05)
        self.buttonz_5.connect("clicked", self.change_distance, 5)

        self.distance = 0.05
        self.buttonz_5.get_style_context().remove_class("distbutton_active")
        self.buttonz_05.get_style_context().add_class("distbutton_active")

        #adjust_z.attach(self.labels['entry'], 0, 0, 1, 1)
       # self.adjust_z.attach(label_nozzle, 0, 0, 1, 1)
       # self.adjust_z.attach(label_nozzle, 1, 0, 1, 1)
        self.adjust_z.attach(buttonz0, 0, 0, 1, 1)
        self.adjust_z.attach(buttonz1, 1, 0, 1, 1)
        self.adjust_z.attach(self.buttonz_05, 0, 1, 1, 1)
        self.adjust_z.attach(self.buttonz_5, 1, 1, 1, 1)

        self.entry_z = Gtk.Grid()
        self.entry_z.set_hexpand(False)
        self.entry_z.set_vexpand(False)
        self.entry_z.set_direction(Gtk.TextDirection.LTR)
        self.entry_z.get_style_context().add_class('numpad')
        self.entry_z.set_halign(Gtk.Align.CENTER)
        self.entry_z.set_valign(Gtk.Align.CENTER)
        self.entry_z.attach(label_en, 0, 0, 1, 1)
        self.entry_z.attach(self.labels['entry'], 1, 0, 1, 1)


        grid.attach(self.entry_z, 1, 0, 1, 1)
       # grid.attach(self.labels['entry'], 1, 0, 1, 1)

        self.button_entry_ok = self._gtk.Button("complete", scale=0.7)
        self.button_entry_ok.connect('clicked', self.update_entry, 'E')
        grid.attach(self.button_entry_ok, 2, 0, 1, 1)

       # grid.attach_next_to(numpad, self.labels['entry'], Gtk.PositionType.BOTTOM, 1, 1)
       # grid.add(self.labels["keypad"])

        #grid.attach(self.labels['entry'], 0, 0, 1, 1)

        grid.attach(self.adjust_z, 1, 1, 1, 1)
        grid.attach(self.labels["keypad"], 1, 1, 1, 1)
        #self.keygrid.attach(self.labels["keypad"], 1, 2, 1, 1)

        #grid.remove(self.labels["keypad"])
        #grid.attach(numpad, 1, 0, 1, 1)

        #grid.labels["keypad"] = numpad
        ############

        pixbuf = self.get_file_image(filename, 200, 200)
        if pixbuf is not None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.set_vexpand(False)
            #grid.attach_next_to(image, label, Gtk.PositionType.BOTTOM, 1, 1)
            grid.attach(image, 0, 1, 1, 1)

        dialog = self._gtk.Dialog(self._screen, buttons, grid, self.confirm_print_response, filename)
        dialog.set_title(_("Print"))
        self.hide_numpad(None, None)


    def search_large_file(self, file_path, keyword1, keyword2, keyword3):
        buttons = [
            {"name": _("OK"), "response": Gtk.ResponseType.CANCEL}
        ]
        labels = Gtk.Label()
        labels.set_markup(
            f"\n\n\n\nThe height value is incorrect!\n\nthere is no that height in the gcode file!\n\nmaybe out of range or "
            f" {round(float(self.resume_z)-0.1,1)} or {round(float(self.resume_z)+0.1,1)} ")

        with open(file_path, 'r', encoding='utf-8') as file:
            for line_number, line in enumerate(file, 1):
                if keyword1 in line or keyword2 in line:
                    logging.debug(f"Line {line_number}: {line.strip()}")
                    return True
                elif keyword3 in line:
                    if len(line) > 1:
                        labels.set_markup(
                            f"\n\n\n\nThe height value is incorrect!\n\n Please Try:   {line.split('Z')[1]}")
                    break

        labels.set_hexpand(False)
        labels.set_halign(Gtk.Align.CENTER)
        labels.set_vexpand(False)
        labels.set_valign(Gtk.Align.CENTER)
        labels.set_line_wrap(True)
        labels.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        dialog2 = self._gtk.Dialog(self._screen, buttons, labels, self.check_confirm)
        dialog2.set_title(_("Print"))
        return False

    def height_check(self, filename):
        logging.debug(f"filename: {filename}")
        if len(self.resume_z)<=0:
            return False
        if self.resume_z[-1] == '0' and '.' in self.resume_z:
            self.resume_z = self.resume_z[:-1]
        if self.resume_z[-1] == '.':
            self.resume_z = self.resume_z[:-1]
        if self.resume_z[0] == '0' and self.resume_z[1] == '.':
            self.resume_z = self.resume_z[1:]

        check_flag = self.search_large_file("/home/mks/printer_data/gcodes/" + filename,
                                                          "G1 Z" + self.resume_z+"\n","G1 Z" + self.resume_z + " ","G1 Z" + self.resume_z)

        logging.debug(f"height {check_flag}")
        return check_flag
    def resume_print(self, widget, filename):

        logging.debug(f"filename: {filename}")
        if self.resume_z[-1] == '0' and '.' in  self.resume_z:
            self.resume_z = self.resume_z[:-1]
        if self.resume_z[0] == '0' and self.resume_z[1] == '.':
            self.resume_z = self.resume_z[1:]

        file_name = filename.split('/')[-1].replace(" ","%20")
        self._screen._ws.klippy.gcode_script(f"PRINT_CONTINUE Z={self.resume_z} FILE={file_name}")
       
        self._screen.show_popup_message(_("Processing ..."), 1, 30)

    def check_confirm(self, dialog, response_id):
        self._gtk.remove_dialog(dialog)
        return
    def confirm_print_response(self, dialog, response_id, filename):

        if response_id == Gtk.ResponseType.YES:
            if self.height_check(filename):
                self._gtk.remove_dialog(dialog)
                self.resume_print(dialog, filename)
            else:
                logging.debug(f"height wrong11")

                #self._screen.show_popup_message("Height wrong!", level=1)
            return

        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.CANCEL:
            return
        if response_id == Gtk.ResponseType.ACCEPT:
            self.resume_print_confirm(dialog, filename)
            return

        total, used, free = shutil.disk_usage("/")
        if free / (2**20) < 200:
            self._screen.show_popup_message("No Space left,please delete some files")
            return

        logging.debug("Total: %d GiB" % (total / (2 ** 30)))
        logging.debug("Used: %d GiB" % (used / (2 ** 30)))
        logging.debug("Free: %d MiB" % (free / (2 ** 20)))
        #subprocess.run(["rm /tmp/klippy.log.20*", ""])
        logging.info(f"Starting print---------: {filename}")
       # self.change_dir(None, "/media/usb")
        if filename.find("usb/")==0 or filename.find("usb0/")==0 or filename.find("usb1/")==0 or filename.find("usb2/") == 0:
            self._screen.show_popup_message("Waiting.", level=1)
            self.win.show_all()
            #
            thread = Thread(target = self.threaded_function, args=[filename,])
            thread.start()
            #thread.join()
            #self._screen.show_popup_message("Waiting", level=1)
            return
        self._screen._ws.klippy.print_start(filename)

    def delete_file(self, filename):
        directory = os.path.join("gcodes", os.path.dirname(filename)) if os.path.dirname(filename) else "gcodes"
        if directory not in self.filelist or os.path.basename(filename).startswith("."):
            return
        try:
            self.filelist[directory]["files"].pop(self.filelist[directory]["files"].index(os.path.basename(filename)))
        except Exception as e:
            logging.exception(e)
        dir_parts = directory.split(os.sep)
        i = len(dir_parts)
        while i > 1:
            cur_dir = os.path.join(*dir_parts[:i])
            if len(self.filelist[cur_dir]['directories']) > 0 or len(self.filelist[cur_dir]['files']) > 0:
                break
            parent_dir = os.path.dirname(cur_dir)

            if self.cur_directory == cur_dir:
                self.change_dir(None, parent_dir)

            del self.filelist[cur_dir]
            self.filelist[parent_dir]['directories'].pop(self.filelist[parent_dir]['directories'].index(cur_dir))
            self.dir_panels[parent_dir].remove(self.directories[cur_dir])
            del self.directories[cur_dir]
            del self.labels['directories'][cur_dir]
            self.dir_panels[parent_dir].show_all()
            i -= 1

        try:
            self.dir_panels[directory].remove(self.files[filename])
        except Exception as e:
            logging.exception(e)
        self.dir_panels[directory].show_all()
        self.files.pop(filename)

    def get_file_info_str(self, filename):

        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo is None:
            return
        info = _("Uploaded")
        if self.time_24:
            info += f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %H:%M}</b>\n'
        else:
            info += f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %I:%M %p}</b>\n'

        if "size" in fileinfo:
            info += _("Size") + f':  <b>{self.format_size(fileinfo["size"])}</b>\n'
        if "estimated_time" in fileinfo:
            info += _("Print Time") + f':  <b>{self.format_time(fileinfo["estimated_time"])}</b>'
        return info

    def reload_files(self, widget=None):
        self.filelist = {'gcodes': {'directories': [], 'files': []}}
        for dirpan in self.dir_panels:
            for child in self.dir_panels[dirpan].get_children():
                self.dir_panels[dirpan].remove(child)

        flist = sorted(self._screen.files.get_file_list(), key=lambda item: '/' in item)
        for file in flist:
            GLib.idle_add(self.add_file, file)
        return False

    def update_file(self, filename):
        if filename not in self.labels['files']:
            logging.debug(f"Cannot update file, file not in labels: {filename}")
            return

        logging.info(f"Updating file {filename}")
        self.labels['files'][filename]['info'].set_markup(self.get_file_info_str(filename))

        # Update icon
        GLib.idle_add(self.image_load, filename)

    def _callback(self, newfiles, deletedfiles, updatedfiles=None):
        #logging.debug(f"newfiles: {newfiles}")
        for file in newfiles:
            self.add_file(file)
        #logging.debug(f"deletedfiles: {deletedfiles}")
        for file in deletedfiles:
            self.delete_file(file)
        if updatedfiles is not None:
           # logging.debug(f"updatefiles: {updatedfiles}")
            for file in updatedfiles:
                self.update_file(file)
        return False

    def _refresh_files(self, widget=None):
        self._files.refresh_files()
        return False

    def wait_confirm(self, dialog, response_id, program):

        if response_id == Gtk.ResponseType.APPLY:
            result = subprocess.run(["rm /home/mks/printer_data/gcodes/*.gc*", ""], shell=True, capture_output=True,
                                    text=True)
            logging.debug("result:" + result.stdout)
        try:
            #subprocess.run(["rm /home/mks/printer_data/gcodes/*.gc*", ""])
            self.gtk.remove_dialog(dialog)
        except Exception as e:
            logging.debug(f"wait_confirm error:\n{e}")
            #subprocess.run(["echo makerbase | sudo -S service KlipperScreen restart", ""])
            python = sys.executable
            os.execl(python, python, *sys.argv) #reboot
            pass

        #self.show_panel("menu", disname, panel_name=name, items=menuitems)
    def show_dialog_message(self,message):
        buttons = [
            {"name": _("Accept"), "response": Gtk.ResponseType.APPLY},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = self.gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        label = Gtk.Label(label=_(message))
        vbox.add(label)

        scroll.add(vbox)
        self.dialog_wait = self.gtk.Dialog(self._screen, buttons, scroll, self.wait_confirm, "Update")
        self.dialog_wait.set_title(_("Update"))
    def _deAll_files(self, widget=None):
        self.show_dialog_message('Delete ALL Files?')
      #
    def show_rename(self, widget, fullpath):
        self.source = fullpath
        logging.info(self.source)

        for child in self.content.get_children():
            self.content.remove(child)

        if "rename_file" not in self.labels:
            self._create_rename_box(fullpath)
        self.content.add(self.labels['rename_file'])
        self.labels['new_name'].set_text(fullpath[7:])
        self.labels['new_name'].grab_focus_without_selecting()
        self.showing_rename = True

    def _create_rename_box(self, fullpath):
        lbl = self._gtk.Label(_("Rename/Move:"))
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(False)
        self.labels['new_name'] = Gtk.Entry()
        self.labels['new_name'].set_text(fullpath)
        self.labels['new_name'].set_hexpand(True)
        self.labels['new_name'].connect("activate", self.rename)
        self.labels['new_name'].connect("focus-in-event", self._screen.show_keyboard)

        save = self._gtk.Button("complete", _("Save"), "color3")
        save.set_hexpand(False)
        save.connect("clicked", self.rename)

        box = Gtk.Box()
        box.pack_start(self.labels['new_name'], True, True, 5)
        box.pack_start(save, False, False, 5)

        self.labels['rename_file'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.labels['rename_file'].set_valign(Gtk.Align.CENTER)
        self.labels['rename_file'].set_hexpand(True)
        self.labels['rename_file'].set_vexpand(True)
        self.labels['rename_file'].pack_start(lbl, True, True, 5)
        self.labels['rename_file'].pack_start(box, True, True, 5)

    def hide_rename(self):
        self._screen.remove_keyboard()
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.main)
        self.content.show()
        self.showing_rename = False

    def rename(self, widget):
        params = {"source": self.source, "dest": f"gcodes/{self.labels['new_name'].get_text()}"}
        self._screen._send_action(
            widget,
            "server.files.move",
            params
        )
        self.back()
        GLib.timeout_add_seconds(2, self._refresh_files)
