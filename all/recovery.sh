#!/bin/sh +e



cd  /home/mks/KlipperScreen
rm -f .git/index
git reset
git reset --hard origin/master 
chmod 777 /home/mks/KlipperScreen/* -Rf
chmod 777 /home/mks/KlipperScreen/all/relink_conf.sh
/home/mks/KlipperScreen/all/relink_conf.sh
#/home/mks/KlipperScreen/all/install_lib.sh
curl -X POST http://127.0.0.1/printer/gcode/script?script=SAVE_VARIABLE%20VARIABLE=allcalibrate%20VALUE=1
sync



exit 0
