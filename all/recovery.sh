#!/bin/bash
str_cfg=$(cat /home/mks/printer_data/config/printer.cfg)
ver_string="x400.cfg"
if [[ $str_cfg =~ $ver_string ]]
then
    echo "printer.cfg is not null"
else
    echo "printer.cfg is null, recoveryng..."
    cp /home/mks/KlipperScreen/config/printer.cfg /home/mks/printer_data/config/
    cp /home/mks/KlipperScreen/config/variable.cfg /home/mks/printer_data/config/    
fi
exit 0
