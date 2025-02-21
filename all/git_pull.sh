#!/bin/sh +e

#xrandr -display :0.0 -q --verbose -o inverted
#cd /home/mks/KlipperScreen
#git pull
#rm  /home/mks/KlipperScreen  -rf
#cd  /home/mks/
#git clone 
#echo makerbase | sudo -S service KlipperScreen restart


#rm  /home/mks/KlipperScreen  -rf
#cd  /home/mks/
#git clone  https://gitee.com/everyone3d/KlipperScreen.git
cd  /home/mks/KlipperScreen
git fetch --all &&  git reset --hard origin/master && git pull
chmod 777 /home/mks/KlipperScreen/all/relink_conf.sh
/home/mks/KlipperScreen/all/relink_conf.sh
sync



exit 0
