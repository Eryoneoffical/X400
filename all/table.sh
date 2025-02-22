#!/bin/bash
#output=`ls -l`
#echo $output
nums=$(sed -n '$=' /tmp/ip.txt)
for ((i=1;i<=nums;i++))
do
#	echo $i
#	output=$(ls -l)
#	echo $output
	line=$i'p'
#	echo $line
	ip=$(sed -n $line /tmp/ip.txt)
#        echo $ip
        url=$ip'/all/hostname'
#	echo $url
	name+=`curl -s  $url`','$ip';' #| sed 's/;//g'  
	echo $name
done

echo $name |sed 's/;/\n/g'  > /home/mks/mainsail/all/printers.txt

