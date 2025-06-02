#!/bin/sh +e

rm /home/mks/KlipperScreen/ -rf
git clone https://gitcode.com/xpp012/KlipperScreen.git /home/mks/KlipperScreen
sync
chmod 777 /home/mks/KlipperScreen/* -Rf
chmod 777 /home/mks/KlipperScreen/all/relink_conf.sh
sync
/home/mks/KlipperScreen/all/relink_conf.sh
sync

exit 0
