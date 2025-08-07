#!/bin/bash
echo ${1}
echo ${2}
#rm /tmp/plr.gcode
#z_s=$(echo ${1})
#z_p=${1} #$("${1}" | sed 's/\./\\./g')
echo -n > /tmp/plr.gcode # clear the file
echo -n > /tmp/pose

echo "date0: $(date +"%Y-%m-%d %H:%M:%S")"
#echo 'START_TEMPS' >> /tmp/plr.gcode
cat "${2}" | sed '/G1 Z'${1}'/q' | sed -ne '/\(M104\|M140\|M109\|M190\)/p' >> /tmp/plr.gcode
echo "date21: $(date +"%Y-%m-%d %H:%M:%S")"

# cat /tmp/plrtmpA.$$ | sed -e '1,/ Z'${1}'[^0-9]*$/ d' | sed -e '/ Z/q' | tac | grep -m 1 ' E' | sed -ne 's/.* E\([^ ]*\)/G92 E\1/p' >> /tmp/plr.gcode
#tac /tmp/plrtmpA.$$ | sed -e '/ Z'${1}'[^0-9]*$/q' | tac | tail -n+2 | sed -e '/ Z[0-9]/ q' | tac | sed -e '/ E[0-9]/ q' | sed -ne 's/.* E\([^ ]*\)/G92 E\1/p' >> /tmp/plr.gcode
BG_EX=`tac "${2}" | sed -e '/G1 Z'${1}'[^0-9]*$/q' | tac | tail -n+2 | sed -e '/ Z[0-9]/ q' | tac | sed -e '/ E[0-9]/ q' | sed -ne 's/.* E\([^ ]*\)/G92 E\1/p'`
# If we failed to match an extrusion command (allowing us to correctly set the E axis) prior to the matched layer height, then simply set the E axis to the first E value present in the resemued gcode.  This avoids extruding a huge blod on resume, and/or max extrusion errors.
if [ "${BG_EX}" = "" ]; then
 BG_EX=`tac "${2}" | sed -e '/G1 Z'${1}'[^0-9]*$/q' | tac | tail -n+2 | sed -ne '/ Z/,$ p' | sed -e '/ E[0-9]/ q' | sed -ne 's/.* E\([^ ]*\)/G92 E\1/p'`
fi
echo "date4: $(date +"%Y-%m-%d %H:%M:%S")"
echo 'G92 E0' >> /tmp/plr.gcode
echo 'M83' >> /tmp/plr.gcode
echo 'G90' >> /tmp/plr.gcode

echo ${BG_EX} >> /tmp/plr.gcode

echo 'SET_KINEMATIC_POSITION Z='$1 >> /tmp/plr.gcode
echo 'G91' >> /tmp/plr.gcode
echo 'G1 Z4' >> /tmp/plr.gcode
echo 'G90' >> /tmp/plr.gcode
echo 'G4 P1000' >> /tmp/plr.gcode
echo 'G28 X Y' >> /tmp/plr.gcode
echo 'G4 P1000' >> /tmp/plr.gcode
echo 'G91' >> /tmp/plr.gcode
echo 'G1 Z-4.03' >> /tmp/plr.gcode
echo 'G90' >> /tmp/plr.gcode
echo 'M83' >> /tmp/plr.gcode
echo 'G92 E0' >> /tmp/plr.gcode
echo 'G1 E2' >> /tmp/plr.gcode
echo 'G1 X350 Y350 F6000' >> /tmp/plr.gcode
echo 'G92 E0' >> /tmp/plr.gcode
echo 'M106 S250' >> /tmp/plr.gcode
echo 'SET_KINEMATIC_POSITION Z='$1 >> /tmp/plr.gcode
echo "date5: $(date +"%Y-%m-%d %H:%M:%S")"
#cat "${2}" | sed -e '1,/G1 Z'${1}'/d' | sed -ne '/ Z/,$ p' >> /tmp/plr.gcode
#tac /tmp/plrtmpA.$$ | sed -e '/ Z'${1}'[^0-9]*$/q' | tac | tail -n+2 | sed -ne '/ Z/,$ p' >> /tmp/plr.gcode

z_p=$(echo ${1} | sed 's/\./\\./g')
position=$(grep -b "G1 Z${z_p}" "${2}" | cut -d':' -f1 | tr '\n' ' ' | cut -d ' ' -f1)
echo ${position} > /tmp/pose
echo $(grep -b "G1 Z${z_p}" ${2})

filename=$(basename "${2}")
echo ${filename}
echo "date6: $(date +"%Y-%m-%d %H:%M:%S")"
sync
#sleep 10

#curl -X POST http://127.0.0.1/printer/gcode/script?script=SDCARD_PRINT_FILE%20FILENAME=${filename}%20P=${position}
