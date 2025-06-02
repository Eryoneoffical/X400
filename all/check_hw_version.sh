#!/bin/bash


local_version=$(cat /home/mks/printer_data/config/printer.cfg )
#echo $local_version


ver_string="v1_"
#to see if it contain the 'v1_' else timeout
if [[ $local_version =~ $ver_string ]]
then
    echo "has hardware version"

else
    echo "no hardware version"    
    sed -i '2a\[include v1_1.cfg]' /home/mks/printer_data/config/printer.cfg
fi
