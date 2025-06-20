# Save arbitrary variables so that values can be kept across restarts.
#
# Copyright (C) 2020 Dushyant Ahuja <dusht.ahuja@gmail.com>
# Copyright (C) 2016-2020  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import os, logging, ast, configparser,re

class SaveVariables:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.filename = os.path.expanduser(config.get('filename'))
        self.allVariables = {}
        try:
            if not os.path.exists(self.filename):
                open(self.filename, "w").close()
            self.loadVariables()
        except self.printer.command_error as e:
            raise config.error(str(e))
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('SAVE_VARIABLE', self.cmd_SAVE_VARIABLE,
                               desc=self.cmd_SAVE_VARIABLE_help)
    def loadVariables(self):
        allvars = {}
        varfile = configparser.ConfigParser()
        try:
            varfile.read(self.filename)
            if varfile.has_section('Variables'):
                for name, val in varfile.items('Variables'):
                    if ".gc" not in val:
                        allvars[name] = ast.literal_eval(val)
                    else:
                        allvars[name] = val
        except:
            msg = "Unable to parse existing variable file"
            logging.exception(msg)
            raise self.printer.command_error(msg)
        self.allVariables = allvars
    cmd_SAVE_VARIABLE_help = "Save arbitrary variables to disk"

    def repace_line(self,new_name,gcmd):
        list = []
        matchPattern = re.compile(r'filename = ')
        file = open(self.filename,'r')  
        
        while 1:
            line = file.readline()
            if not line:
                print("Read file End or Error")
                break
            elif matchPattern.search(line):
                pass
            else:
                list.append(line)
        file.close()
         
        list.append("\nfilename = '%s'" % new_name)
        
        file = open(self.filename, 'w')
        for i in list:
            file.write(i)
        file.close()
 
 
 
    def cmd_SAVE_VARIABLE(self, gcmd):
        varname = gcmd.get('VARIABLE')
        value = gcmd.get('VALUE')
        if ".gc" in value:
            self.repace_line(value,gcmd)
            return
            
       # gcmd.respond_info("gcmd.get_command()=%s %s" % (gcmd.get_command_parameters(),self.filename))
        try:
            if ".gc" not in value:
                value = ast.literal_eval(value)
        except ValueError as e:
            raise gcmd.error("Unable to parse '%s' as a literal" % (value,))
        newvars = dict(self.allVariables)
        newvars[varname] = value
        # Write file
        varfile = configparser.ConfigParser()
        varfile.add_section('Variables')
        for name, val in sorted(newvars.items()):
            if ".gc" in repr(val):
                varfile.set('Variables', name, (val))
            else:
                varfile.set('Variables', name, repr(val))
            gcmd.respond_info("gcmd.get_command()=%s %s" % (name,(val)))

        try:
            f = open(self.filename, "w")
            varfile.write(f)
            f.close()
        except:
            msg = "Unable to save variable"
            logging.exception(msg)
            raise gcmd.error(msg)
        #self.repace_line('CFFFP_coil_case.gcode',gcmd)    
       # gcmd.respond_info("cmd_SAVE_VARIABLE1")
        self.loadVariables()
    def get_status(self, eventtime):
        return {'variables': self.allVariables}

def load_config(config):
    return SaveVariables(config)
