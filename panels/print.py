# -*- coding: utf-8 -*-
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
        self.gtk = screen.gtk
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

        buttons = [
            {"name": _("Print"), "response": Gtk.ResponseType.OK},
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

        pixbuf = self.get_file_image(filename, self._screen.width * .9, self._screen.height * .6)
        if pixbuf is not None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.set_vexpand(False)
            grid.attach_next_to(image, label, Gtk.PositionType.BOTTOM, 1, 1)

        dialog = self._gtk.Dialog(self._screen, buttons, grid, self.confirm_print_response, filename)
        dialog.set_title(_("Print"))

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


    def confirm_print_response(self, dialog, response_id, filename):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.CANCEL:
            return
        total, used, free = shutil.disk_usage("/")
        if free / (2**20) < 200:
            self._screen.show_popup_message("No Space left,please delete some files")
            return

        logging.debug("Total: %d GiB" % (total / (2 ** 30)))
        logging.debug("Used: %d GiB" % (used / (2 ** 30)))
        logging.debug("Free: %d MiB" % (free / (2 ** 20)))

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
        logging.debug(f"newfiles: {newfiles}")
        for file in newfiles:
            self.add_file(file)
        logging.debug(f"deletedfiles: {deletedfiles}")
        for file in deletedfiles:
            self.delete_file(file)
        if updatedfiles is not None:
            logging.debug(f"updatefiles: {updatedfiles}")
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
