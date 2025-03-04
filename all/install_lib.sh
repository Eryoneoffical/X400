#!/bin/sh +e

##install timelapse
cp /home/mks/KlipperScreen/all/timelapse_install.sh  /home/mks/moonraker-timelapse/scripts/install.sh
cd  /home/mks/moonraker-timelapse/
make install
rm /home/mks/printer_data/config/timelapse.cfg
ln -s /home/mks/moonraker-timelapse/klipper_macro/timelapse.cfg  /home/mks/printer_data/config/timelapse.cfg
cp /home/mks/KlipperScreen/moonraker-timelapse/component/timelapse.py /home/mks/moonraker/moonraker/components/

###install farm3d
cp /home/mks/KlipperScreen/farm3d/  /home/mks/  -rf
chmod 777 /home/mks/farm3d/*
cd /home/mks/KlipperScreen/farm3d
chmod 777 *
./install.sh 
pip3 install opencv-python
pip3 install qrcode[pil]

exit 0
