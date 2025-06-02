import logging
import math
import statistics

from . import bus
from . import filament_switch_sensor

CHECK_RUNOUT_TIMEOUT = 1.0
TIMER_READ_ANGLE = 0.5
AS5600_CHIP_ADDR = 0x36
AS5600_I2C_SPEED = 100000
MAX_LEN = 10
AS5600_REGS = {
    '_zmco'   : 0x00,
    '_zpos_hi' : 0x01,
     '_zpos_lo' : 0x02,
     '_mpos_hi' : 0x03,
     '_mpos_lo' : 0x04,
     '_mang_hi' : 0x05,
     '_mang_lo' : 0x06,
     '_conf_hi' : 0x07,
     '_conf_lo' : 0x08,
     '_raw_ang_hi' : 0x0c,
     '_raw_ang_lo' : 0x0d,
     '_ang_hi' : 0x0e,
     '_ang_lo' : 0x0f,
     '_stat' : 0x0b,
     '_agc' : 0x1a,
     '_mag_hi' : 0x1b,
     '_mag_lo' : 0x1c,
     '_burn' : 0xff
}
class AS5600:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.i2c = bus.MCU_I2C_from_config(config, AS5600_CHIP_ADDR, AS5600_I2C_SPEED)
        self.gcode = self.printer.lookup_object('gcode')
        self.extruder_name = config.get('extruder')
        self.detection_length = config.getfloat(
            'detection_length', 7., above=0.)
        self.enable = 0
        self.angle_list = []
        self.flow_list = []
        self.klipper_flow_list = []
        self.gcode.register_command('ASREAD', self.set_start_pos)
        self.gcode.register_command('ASMOTION', self.cmd_motion_enable)# ASMOTION S=1 ASMOTION S=0
        self.sample_timer = self.reactor.register_timer(self._sample_as5600)
        #self.printer.register_event_handler("klippy:connect",
        #                                    self.handle_connect)
        self.raw_angle = 0
        self.circle_total = 0
        self.angel_offset = 0
        self.runout_helper = filament_switch_sensor.RunoutHelper(config)
        self.get_status = self.runout_helper.get_status
        self.extruder = None
        self.estimated_print_time = None
        # Initialise internal state
        self.filament_runout_pos = None
        # Register commands and event handlers
        self.printer.register_event_handler('klippy:ready',
                                            self._handle_ready)
        self.printer.register_event_handler('idle_timeout:printing',
                                            self._handle_printing)
        self.printer.register_event_handler('idle_timeout:ready',
                                            self._handle_not_printing)
        self.printer.register_event_handler('idle_timeout:idle',
                                            self._handle_not_printing)
    #def handle_connect(self):
        #self.reactor.update_timer(self.sample_timer, self.reactor.NOW)
        self.extruder_pos_old = 0
        self.angel_to_len_old = 0

    def cmd_motion_enable(self, gcmd):
        try:
            self.enable = gcmd.get_int('S', None)
        except Exception as e:
            pass
        if self.enable == 1:
            magStatus, self.angel_offset = self.as5600read(self.gcode)
            self.reactor.update_timer(self.sample_timer, self.reactor.NOW)
        else:
            self.reactor.update_timer(self.sample_timer, self.reactor.NEVER)


    def set_start_pos(self,gcmd):
        raw_h = self.read_register('_raw_ang_hi', 1)[0]
        raw_l = self.read_register('_raw_ang_lo', 1)[0]
        self.start_stop = gcmd.get_int('S', None)
        if self.start_stop == 1:
            self.write_register('_zpos_hi', [raw_h])
            self.write_register('_zpos_lo', [raw_l])
            self.write_register('_burn', [0x80])
        else:
            self.write_register('_mpos_hi', [raw_h])
            self.write_register('_mpos_lo', [raw_l])

    def read_register(self, reg_name, read_len):
        # read a single register
        regs = [AS5600_REGS[reg_name]]
        params = self.i2c.i2c_read(regs, read_len)
        return bytearray(params['response'])

    def write_register(self, reg_name, data):
        if type(data) is not list:
            data = [data]
        reg = AS5600_REGS[reg_name]
        data.insert(0, reg)
        self.i2c.i2c_write(data)
    def as5600read(self, gcmd):
        magStatus = (self.read_register('_stat', 1)[0] & 0x20) >> 5
        self.raw_angle = (self.read_register('_raw_ang_hi', 1)[0] << 8 |
                              self.read_register('_raw_ang_lo', 1)[0])
        angle = self.raw_angle * 0.087
        return magStatus, angle

    def circle_update(self):
        len_angle = len(self.angle_list)
        if len_angle <= 3:
            return
        #self.gcode.respond_info(f"list:%d %d %d" % (self.angle_list[len_angle-3], self.angle_list[len_angle-2],self.angle_list[len_angle-1]))
        if self.angle_list[len_angle-2] > self.angle_list[len_angle-3]:
            if self.angle_list[len_angle-1] < 90 and self.angle_list[len_angle-2] > 180: #270-->360-->0
                self.circle_total += 1
        if self.angle_list[len_angle-2] < self.angle_list[len_angle-3]:
            if self.angle_list[len_angle-1] > 180 and self.angle_list[len_angle-2] < 90: #90-->0-->360
                self.circle_total -= 1

    def compare_float(self, a, b, precision):
        if abs(a - b) <= precision:
            return True
        return False

    def _sample_as5600(self, eventtime):
        magStatus, angle = self.as5600read(self.gcode)
        len_angle = len(self.angle_list)
        measured_time = self.reactor.monotonic()

        if len_angle > 0:
            if self.compare_float(angle, self.angle_list[len_angle - 1], 0.05):
                return measured_time + TIMER_READ_ANGLE
        if len(self.angle_list) >= MAX_LEN:
            self.angle_list.append(angle)
            self.angle_list.pop(0)
        else:
            self.angle_list.append(angle)
        self.circle_update()
        extruder_pos = self._get_extruder_pos(eventtime)
        total_angle = self.circle_total + (angle - self.angel_offset) / 360.0
        angel_to_len = total_angle * math.pi * 10

        if len(self.angle_list) < MAX_LEN:
            self.offset_angle_len = extruder_pos - angel_to_len
        #self.gcode.respond_info(f"D:%d raw:%d {self.angle_list}" % (magStatus, self.raw_angle))


        len_angle = len(self.angle_list)
        klipper_flow = (extruder_pos - self.extruder_pos_old)*math.pi*(1.75/2)*(1.75/2)
        actually_flow = (angel_to_len - self.angel_to_len_old)*math.pi*(1.75/2)*(1.75/2)


        if len(self.flow_list) >= MAX_LEN:
            self.flow_list.append(abs(actually_flow))
            self.klipper_flow_list.append(abs(klipper_flow))
            self.klipper_flow_list.pop(0)
            self.flow_list.pop(0)
        else:
            self.flow_list.append(abs(actually_flow))
            self.klipper_flow_list.append(abs(klipper_flow))
        if len(self.flow_list)>2:
            avaverage_f=0
            for i in self.klipper_flow_list:
                avaverage_f += i
            avaverage_f = avaverage_f/len(self.klipper_flow_list)

            avaverage_a = 0
            for i in self.flow_list:
                avaverage_a += i
            avaverage_a = avaverage_a / len(self.flow_list)

            if abs(avaverage_f) - abs(avaverage_a) < 0.5 and abs(avaverage_f) >= 0.5:
                self.encoder_event(measured_time)
            elif abs(avaverage_f) <= 0.5 and abs(avaverage_a) > 0:
                self.encoder_event(measured_time)
            elif abs(avaverage_f) == 0 and abs(avaverage_a) == 0:
                self.encoder_event(measured_time)
            elif abs(avaverage_a) > 0.5 or abs(avaverage_a) >= abs(avaverage_f):
                self.encoder_event(measured_time)

            try:
                static_data=statistics.stdev(self.flow_list, avaverage_f)
                self.gcode.respond_info(f"Flow/Actual: %.1f/%.1f mm3/s ; Used/Actual: %.1f/%.1f mm ; static_data:%.2f/aver:%0.2f;%.2f "% (klipper_flow, actually_flow,
                                                                       extruder_pos, angel_to_len,static_data,avaverage_f, avaverage_f-avaverage_a))
            except Exception as e:
                pass
      #  self.gcode.respond_info(f"Flow/Actual Flow: %.3f/%.3f mm3/s  ,  P;%.1f;%.1f;offset;%.1f;%.1f; A;%d; C;%d" % (klipper_flow,actually_flow,
       #     extruder_pos, angel_to_len, (extruder_pos - angel_to_len),self.offset_angle_len, self.angle_list[len_angle-1], self.circle_total))
        self.extruder_pos_old = extruder_pos
        self.angel_to_len_old = angel_to_len
        measured_time = self.reactor.monotonic()
        return measured_time + TIMER_READ_ANGLE

    def _update_filament_runout_pos(self, eventtime=None):
        if eventtime is None:
            eventtime = self.reactor.monotonic()
        self.filament_runout_pos = (
                self._get_extruder_pos(eventtime) +
                self.detection_length)
    def _handle_ready(self):
        self.extruder = self.printer.lookup_object(self.extruder_name)
        self.estimated_print_time = (
                self.printer.lookup_object('mcu').estimated_print_time)
        self._update_filament_runout_pos()
        self._extruder_pos_update_timer = self.reactor.register_timer(
                self._extruder_pos_update_event)
    def _handle_printing(self, print_time):
        self.reactor.update_timer(self._extruder_pos_update_timer,
                self.reactor.NOW)
        self.reactor.update_timer(self.sample_timer, self.reactor.NOW)
    def _handle_not_printing(self, print_time):
        self.reactor.update_timer(self._extruder_pos_update_timer,
                self.reactor.NEVER)
        self.reactor.update_timer(self.sample_timer, self.reactor.NEVER)
    def _get_extruder_pos(self, eventtime=None):
        if eventtime is None:
            eventtime = self.reactor.monotonic()
        print_time = self.estimated_print_time(eventtime)
        return self.extruder.find_past_position(print_time)
    def _extruder_pos_update_event(self, eventtime):
        extruder_pos = self._get_extruder_pos(eventtime)
        # Check for filament runout
        if extruder_pos > self.filament_runout_pos:
            self.gcode.respond_info(f"rounout Emotor:%0.1f filament:%0.1f" % (extruder_pos, self.filament_runout_pos))
        self.runout_helper.note_filament_present(
                extruder_pos < self.filament_runout_pos)
        return eventtime + CHECK_RUNOUT_TIMEOUT

    def encoder_event(self, eventtime):
        if self.extruder is not None:
            self._update_filament_runout_pos(eventtime)
            # Check for filament insertion
            # Filament is always assumed to be present on an encoder event
            self.runout_helper.note_filament_present(True)

def load_config(config):
    return AS5600(config)
