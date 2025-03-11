#!/bin/sh +e



cd  /home/mks/KlipperScreen
rm -f .git/index
git reset
git fetch --all &&  git reset --hard origin/master && git pull
sync
chmod 777 /home/mks/KlipperScreen/* -Rf
chmod 777 /home/mks/KlipperScreen/all/relink_conf.sh
sync
/home/mks/KlipperScreen/all/relink_conf.sh
sync
/home/mks/KlipperScreen/all/install_lib.sh
sync



exit 0
