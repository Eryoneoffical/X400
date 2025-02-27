#!/bin/sh +e

sed -i 's/ERYONE_THR/EECAN/g' /home/mks/printer_data/config/printer.cfg 
sed -i 's/runout1.cfg/runout.cfg/g' /home/mks/printer_data/config/printer.cfg

sed -i 's/runout_p.cfg/runout.cfg/g' /home/mks/printer_data/config/printer.cfg
sed -i 's/EECAN_p.cfg/EECAN.cfg/g' /home/mks/printer_data/config/printer.cfg
sed -i 's/x400_p.cfg/x400.cfg/g' /home/mks/printer_data/config/printer.cfg

sed -i 's/ERYONE_THR/EECAN/g' /home/mks/printer_data/config/canuid.cfg 
sed -i 's/hold_current: 0.5/hold_current: 0.6/g' /home/mks/printer_data/config/printer.cfg 
echo makerbase | sudo -S sed -i 's/txqueuelen 128/txqueuelen 1024/g' /etc/network/interfaces.d/can0

sed   -i '/^.*x400.cfg.*$/,/^.*SAVE_CONFIG.*$/{/^.*x400.cfg.*$/!{/^.*SAVE_CONFIG.*$/!d}}'  /home/mks/printer_data/config/printer.cfg 
sed   -i '/^.*x400_p.cfg.*$/,/^.*SAVE_CONFIG.*$/{/^.*x400_p.cfg.*$/!{/^.*SAVE_CONFIG.*$/!d}}'  /home/mks/printer_data/config/printer.cfg 
#sed  -i '9i [include x400.cfg]' /home/mks/printer_data/config/printer.cfg 

sed -i 's/#\[include KAMP_Settings.cfg\]/[include KAMP_Settings.cfg]/g' /home/mks/printer_data/config/printer.cfg
sed -i 's/ERYONE_EBB36.cfg/ERYONE_36.cfg/g' /home/mks/printer_data/config/printer.cfg

rm /home/mks/klipper -rf
rm /home/mks/mainsail/all -rf
rm /home/mks/printer_data/config/runout.cfg
#rm /home/mks/printer_data/config/KlipperScreen.conf
rm /home/mks/printer_data/config/EECAN.cfg
rm /home/mks/printer_data/config/x400.cfg

#rm /home/mks/printer_data/config/EECAN_p.cfg
#rm /home/mks/printer_data/config/runout_p.cfg
#rm /home/mks/printer_data/config/x400_p.cfg
rm /home/mks/printer_data/config/mainsail.cfg

rm /home/mks/Bed_D* -rf
rm /home/mks/printer_data/config/crowsnest.conf
rm /home/mks/printer_data/config/chamber.cfg

cp /home/mks/KlipperScreen/config/timelapse.cfg  /home/mks/moonraker-timelapse/klipper_macro

#rm /home/mks/moonraker/moonraker/components/update_manager/update_manager.py

#ln -s /home/mks/KlipperScreen/moonraker/moonraker/components/update_manager/update_manager.py  /home/mks/moonraker/moonraker/components/update_manager/update_manager.py

cp  /home/mks/KlipperScreen/klipper/ /home/mks/  -rf
ln -s /home/mks/KlipperScreen/all /home/mks/mainsail/all
cp /home/mks/KlipperScreen/config/runout.cfg  /home/mks/printer_data/config/runout.cfg
cp /home/mks/KlipperScreen/config/EECAN.cfg  /home/mks/printer_data/config/
#ln -s /home/mks/KlipperScreen/config/runout_p.cfg  /home/mks/printer_data/config/
#ln -s /home/mks/KlipperScreen/config/EECAN_p.cfg  /home/mks/printer_data/config/EECAN_p.cfg
#ln -s /home/mks/KlipperScreen/config/x400_p.cfg  /home/mks/printer_data/config/x400_p.cfg
#cp /home/mks/KlipperScreen/config/KlipperScreen.conf /home/mks/printer_data/config/
cp /home/mks/KlipperScreen/config/crowsnest.conf  /home/mks/printer_data/config/

cp /home/mks/KlipperScreen/config/x400.cfg  /home/mks/printer_data/config/
cp /home/mks/KlipperScreen/config/mainsail.cfg  /home/mks/printer_data/config/

#sed -i 's/z_offset/z_offset = -0.12 #/g' /home/mks/printer_data/config/printer.cfg

###
cp /home/mks/KlipperScreen/all/timelapse_install.sh  /home/mks/moonraker-timelapse/scripts/install.sh
cd  /home/mks/moonraker-timelapse/
make install
rm /home/mks/printer_data/config/timelapse.cfg
ln -s /home/mks/moonraker-timelapse/klipper_macro/timelapse.cfg  /home/mks/printer_data/config/timelapse.cfg
cp /home/mks/KlipperScreen/moonraker-timelapse/component/timelapse.py /home/mks/moonraker/moonraker/components/

rm /home/mks/printer_data/config/moonraker.conf
cp  /home/mks/KlipperScreen/config/moonraker.conf  /home/mks/printer_data/config
cp  /home/mks/KlipperScreen/config/chamber.cfg  /home/mks/printer_data/config
###
sync
chmod 777 /home/mks/KlipperScreen/* -Rf
cd /home/mks/KlipperScreen/farm3d
chmod 777 *
chmod 777 /home/mks/KlipperScreen/all/*.sh
./install.sh 
pip3 install opencv-python
pip3 install qrcode[pil]

curl -X POST http://127.0.0.1/printer/gcode/script?script=SAVE_VARIABLE%20VARIABLE=needreboot%20VALUE=1
#curl -X POST http://127.0.0.1/printer/gcode/script?script=SAVE_VARIABLE%20VARIABLE=use_ai%20VALUE=1
#curl -X POST http://127.0.0.1/machine/services/restart?service=cloud_mq.service
#echo makerbase | sudo -S service KlipperScreen restart
#echo makerbase | sudo -S service crowsnest restart
echo makerbase | sudo -S systemctl disable moonraker-obico.service


cd /home/mks/farm3d/
#git fetch --all &&  git reset --hard && git pull
cp /home/mks/KlipperScreen/farm3d/  /home/mks/  -rf
chmod 777 /home/mks/farm3d/*

echo makerbase | sudo -S systemctl  stop cloud_mq.service
echo makerbase | sudo -S systemctl   disable cloud_mq.service
echo makerbase | sudo -S rm /etc/systemd/system/cloud_mq.service

echo makerbase | sudo -S cp /home/mks/farm3d/farm3d.service    /etc/systemd/system/
echo makerbase | sudo -S systemctl  daemon-reload
echo makerbase | sudo -S systemctl   enable farm3d.service
echo makerbase | sudo -S systemctl  restart farm3d.service

sync


exit 0
