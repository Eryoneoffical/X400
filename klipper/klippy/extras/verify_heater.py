# Heater/sensor verification code
#
# Copyright (C) 2018  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

HINT_THERMAL = """
See the 'verify_heater' section in docs/Config_Reference.md
for the parameters that control this check.
"""

class HeaterCheck:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:connect",
                                            self.handle_connect)
        self.printer.register_event_handler("klippy:shutdown",
                                            self.handle_shutdown)
        self.heater_name = config.get_name().split()[1]
        self.heater = None
        self.hysteresis = config.getfloat('hysteresis', 5., minval=0.)
        self.max_error = config.getfloat('max_error', 120., minval=0.)
        self.heating_gain = config.getfloat('heating_gain', 2., above=0.)
        default_gain_time = 20.
        if self.heater_name == 'heater_bed':
            default_gain_time = 60.
        self.check_gain_time = config.getfloat(
            'check_gain_time', default_gain_time, minval=1.)
        self.approaching_target = self.starting_approach = False
        self.last_target = self.goal_temp = self.error = 0.
        self.goal_systime = self.printer.get_reactor().NEVER
        self.check_timer = None
    def handle_connect(self):
        if self.printer.get_start_args().get('debugoutput') is not None:
            # Disable verify_heater if outputting to a debug file
            return
        pheaters = self.printer.lookup_object('heaters')
        self.heater = pheaters.lookup_heater(self.heater_name)
        logging.info("Starting heater checks for %s", self.heater_name)
        reactor = self.printer.get_reactor()
        self.check_timer = reactor.register_timer(self.check_event, reactor.NOW)
    def handle_shutdown(self):
        if self.check_timer is not None:
            reactor = self.printer.get_reactor()
            reactor.update_timer(self.check_timer, reactor.NEVER)
    def check_event(self, eventtime):
        temp, target = self.heater.get_temp(eventtime)
        #if "chamber_heater" in self.heater_name and self.error:
        #    self.printer.lookup_object('gcode').respond_info("%.2f C：%.2f" % (temp,self.error))
        if temp >= target - self.hysteresis or target <= 0.:
            # Temperature near target - reset checks
            if self.approaching_target and target:
                logging.info("Heater %s within range of %.3f",
                             self.heater_name, target)
            self.approaching_target = self.starting_approach = False
            if temp <= target + self.hysteresis:
                self.error = 0.
            self.last_target = target
            return eventtime + 1.
        if "chamber_heater" in self.heater_name and ((target - self.hysteresis) - temp) > 15:
            self.error += ((target - self.hysteresis) - temp)/4
        else:
            self.error += (target - self.hysteresis) - temp
        if not self.approaching_target:
            if target != self.last_target:
                # Target changed - reset checks
                if "chamber_heater" in self.heater_name:
                    self.printer.lookup_object('gcode').respond_info("Heater %s approaching new target of %.3f" % (self.heater_name, target))
                logging.info("Heater %s approaching new target of %.3f",
                             self.heater_name, target)
                self.approaching_target = self.starting_approach = True
                self.goal_temp = temp + self.heating_gain
                self.goal_systime = eventtime + self.check_gain_time
            elif self.error >= self.max_error:
                # Failure due to inability to maintain target temperature
                if "chamber_heater" in self.heater_name:
                    gcode = self.printer.lookup_object('gcode')
                    gcode.respond_info("chamber_heater is not heating at expected rate")
                    if eventtime >= self.goal_systime:
                        gcode.respond_info("heating is closed ")
                        self.approaching_target = False
                        gcode.run_script_from_command("SET_HEATER_TEMPERATURE HEATER=chamber_heater TARGET=0")
                        gcode.run_script_from_command("M117 The chamber_heater is not heating at the expected rate and has automatically closed.")
                    self.error = 0.
                    return eventtime + 1.
                return self.heater_fault()
            if "chamber_heater" in self.heater_name:
                if temp >= self.goal_temp:
                    self.error = 0.
                    self.goal_temp = temp + self.heating_gain
                    self.goal_systime = eventtime + self.check_gain_time
        elif temp >= self.goal_temp:
            # Temperature approaching target - reset checks
            self.starting_approach = False
            self.error = 0.
            self.goal_temp = temp + self.heating_gain
            self.goal_systime = eventtime + self.check_gain_time
        elif eventtime >= self.goal_systime:
            # Temperature is no longer approaching target
            self.approaching_target = False
            logging.info("Heater %s no longer approaching target %.3f",
                         self.heater_name, target)
            if "chamber_heater" in self.heater_name:
                self.error = 0.
                self.printer.lookup_object('gcode').run_script_from_command(
                    "M117 The chamber_heater no longer approaching target.")
                self.printer.lookup_object('gcode').respond_info(
                    "Heater %s no longer approaching target  %.3f" % (self.heater_name, target))
        elif self.starting_approach:
            self.goal_temp = min(self.goal_temp, temp + self.heating_gain)
        self.last_target = target
        return eventtime + 1.
    def heater_fault(self):
        msg = "Heater %s not heating at expected rate" % (self.heater_name,)
        logging.error(msg)
        self.printer.invoke_shutdown(msg + HINT_THERMAL)
        return self.printer.get_reactor().NEVER

def load_config_prefix(config):
    return HeaterCheck(config)
