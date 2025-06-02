#!/bin/sh

df
echo makerbase | sudo -S cp /home/mks/klipper/out/klipper.uf2 /media/usb1/
#cd /home/mks/klipper/
#make flash FLASH_DEVICE=0483:df11
python3 /home/mks/CanBoot/scripts/flash_can.py -d  /dev/serial/by-id/$(ls /dev/serial/by-id/)  -f /home/mks/klipper/out/klipper.bin
sleep 2
sudo -S rm /media/usb1/klipper.uf2

sync

