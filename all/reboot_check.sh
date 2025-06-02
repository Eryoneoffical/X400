#!/bin/bash

variable_str=$(cat /home/mks/printer_data/config/variable.cfg)
echo $variable_str

ver_string="needreboot = 1"

if [[ $variable_str =~ $ver_string ]]
then
    echo "clear the flag of reboot"
   # sed -i 's/needreboot = 1/needreboot = 0/g' /home/mks/printer_data/config/variable.cfg
   # curl -X POST http://127.0.0.1/printer/gcode/script?script=SAVE_VARIABLE%20VARIABLE=needreboot%20VALUE=0

else
    echo "no need to reboot"
fi
