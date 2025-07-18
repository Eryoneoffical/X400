#!/bin/bash

SCRIPTPATH=$(dirname $(realpath $0))
rm $SCRIPTPATH/../all/hostname
ln -s  /etc/hostname $SCRIPTPATH/../all/hostname
if [ -f $SCRIPTPATH/launch_KlipperScreen.sh ]
then
echo "Running "$SCRIPTPATH"/launch_KlipperScreen.sh"
$SCRIPTPATH/launch_KlipperScreen.sh
exit $?
fi

echo "Running KlipperScreen on X in display :0 by default"
/usr/bin/xinit $KS_XCLIENT
