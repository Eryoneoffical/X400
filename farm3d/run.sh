#!/usr/bin/env bash
killall monitor.sh
/home/mks/mainsail/all/monitor.sh &
killall python3 mq.py
#uptime | tee -a /home/mks/printer_data/logs/mq.log
sleep 3 
echo makerbase | sudo -S service crowsnest restart
cd ~/farm3d/ 
chmod 777 *
python3 mq.py
