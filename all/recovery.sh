#!/bin/sh +e



cd  /home/mks/KlipperScreen
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2010%
rm -f .git/index
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2030%
git reset
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2050%
git reset --hard origin/master 
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2060%
chmod 777 /home/mks/KlipperScreen/* -Rf
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2090%
chmod 777 /home/mks/KlipperScreen/all/relink_conf.sh
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%20.
/home/mks/KlipperScreen/all/relink_conf.sh
#/home/mks/KlipperScreen/all/install_lib.sh
curl -X POST http://127.0.0.1/printer/gcode/script?script=SAVE_VARIABLE%20VARIABLE=needreboot%20VALUE=1
sync



exit 0
