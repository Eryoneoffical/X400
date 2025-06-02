#!/bin/sh +e



cd  /home/mks/KlipperScreen
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%200%
rm -f .git/index
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2010%
git reset
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2030%
git fetch --all &&  git reset --hard origin/master && git pull
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2050%
sync
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2070%
chmod 777 /home/mks/KlipperScreen/* -Rf
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2080%
chmod 777 /home/mks/KlipperScreen/all/relink_conf.sh
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%2090%
sync
curl -X POST http://127.0.0.1/printer/gcode/script?script=M117%20.
/home/mks/KlipperScreen/all/relink_conf.sh
sync
#/home/mks/KlipperScreen/all/install_lib.sh
sync



exit 0
