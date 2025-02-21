#!/bin/bash
#sleep 5

#nmap -p 7125 192.168.2.1/24 -oG /tmp/test.txt  
#
#cat /tmp/test.txt | sed -n '/open/p' | sed 's/^.*Host: //g' | sed 's/ (.*$//g' > /tmp/ip.txt
#cat test.txt | sed -n '/open/p' | sed 's/^.*Host://g' | sed 's/(.*$//g' > ip.txt

##
#nums=$(sed -n '$=' /tmp/ip.txt)
#for ((i=1;i<=nums;i++))
#do
#       echo $i
#       output=$(ls -l)
#       echo $output
 #       line=$i'p'
#       echo $line
  #      ip=$(sed -n $line /tmp/ip.txt)
   #     echo $ip
    #    url=$ip'/all/hostname'
    #   echo $url
    #    name+=`curl -s  $url`','$ip';' #| sed 's/;//g'  
#        echo $name
#done

#echo $name |sed 's/;/\n/g'  > /home/mks/mainsail/all/printers.txt

newversion=`curl -s https://gitee.com/xpp123/KlipperScreen/raw/master/version.md`
echo $newversion

local_version=$(cat /home/mks/KlipperScreen/version.md)
echo $local_version


ver_string="X400"
#to see if it contain the 'X400' else timeout
if [[ $newversion =~ $ver_string ]]
then
    echo "connected"
    if [[ $newversion == $local_version ]]
    then
       echo "the version is same"
    else
       echo "update..."
       update_log=$(/home/mks/mainsail/all/git_pull.sh)
       echo $update_log
    fi

else
    echo "connect timeout"    
fi
