#!/bin/bash

#input= cat /usr/share/X11/xorg.conf.d/10-evdev.conf
#echo input
echo makerbase | sudo -S mount -o remount,ro /boot

input=$(sed -n '/ Option/'p /usr/share/X11/xorg.conf.d/10-evdev.conf |wc -l)
echo $input
#if[ ! $# == 2 ]; then
if [ $input -eq 1 ] ; then
  xrandr -display :0.0 -q --verbose -o inverted
else
  echo ""normal
fi

#while [ 1 ]
#do
#    sleep 3
#    log_t=$(/home/mks/mainsail/all/check_version.sh)
#    echo $log_t
#done
#killall monitor.sh
#/home/mks/mainsail/all/monitor.sh &
#killall python3 mq.py
#cd /home/mks/KlipperScreen/mqtt
#chmod 777 *
#python3 mq.py &
python3 /home/mks/mainsail/all/qr.py
/home/mks/mainsail/all/reboot_check.sh
echo makerbase | sudo -S service moonraker-obico stop
exit 0
