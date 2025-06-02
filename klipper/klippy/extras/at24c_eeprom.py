import math

from . import bus

class at24cxx:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        address = config.getint('address', 0)
        speed = config.getint('speed', 0)
        self.i2c = bus.MCU_I2C_from_config(config, address, speed)
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command('M406', self.cmd_write)
        self.gcode.register_command('M407', self.cmd_read_wirte_variable)
        self.printer.register_event_handler('klippy:ready',
                                            self._handle_ready)
        self.variables = []

    def _handle_ready(self):
        #self.extruder =get_status
        eventtime = self.reactor.monotonic()
        self.variables = self.printer.lookup_object('save_variables').get_status(eventtime)["variables"]
        raw = self.read_register(0x00, 2)
        eeprom_z = raw[0] | (raw[1] << 8)
        if 'power_resume_z' in  self.variables:
            if math.fabs(eeprom_z / 10.0 - self.variables['power_resume_z']) > 0.01:
                z_str = str(eeprom_z / 10.0)
                if z_str.rfind('.0') != -1:
                    z_str = z_str[:-2]
            #if z_str.find('0.') == 0:
            #    z_str = z_str[1:]
                self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=power_resume_z VALUE=" + z_str)

    def read_register(self, address, read_len):
        # read a single register
        params = self.i2c.i2c_read([address], read_len)
        return bytearray(params['response'])

    def write_register(self, address, data):
        if type(data) is not list:
            data = [data]
        data.insert(0, address)
        self.i2c.i2c_write(data)
    def cmd_read(self, gcmd):
        address = gcmd.get_int('A')
        raw = self.read_register(0x00, 2)
        self.gcode.respond_info(f"addr: {address} , read data: {raw}")


    def cmd_write(self, gcmd):
        data = gcmd.get_int('D')
        data = [data&0xff,(data>>8)&0xff]
        self.write_register(0x00, data)
        self.gcode.respond_info(f"write data: {data}")
    def cmd_read_wirte_variable(self, gcmd):
        address = gcmd.get('A')
        raw = self.read_register(0x00, 2)
        eeprom_z = raw[0]| (raw[1]<<8)
        if 'power_resume_z' in self.variables:
            self.gcode.respond_info(f"raw %d %d eeprom_z:%d  %f"%(raw[0],raw[1],eeprom_z,self.variables['power_resume_z']))
       # if math.fabs(eeprom_z / 10.0 - self.variables['power_resume_z']) > 0.01:
        z_str = str(eeprom_z / 10.0)
        self.gcode.respond_info(z_str)
        self.gcode.respond_info(f"{z_str.find('0.')}")
        if z_str.rfind('.0') != -1:
            z_str = z_str[:-2]
        if z_str.find('0.') == 0:
            z_str = z_str[1:]
        self.gcode.respond_info(z_str)
def load_config(config):
    return at24cxx(config)