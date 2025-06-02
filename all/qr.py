import netifaces as ni
import qrcode
ipmac = ni.ifaddresses('eth0')[ni.AF_LINK][0]["addr"]

file1 = open("/etc/hostname", "r")
ipmac = file1.read().replace('\n', '') + ":" + ipmac
file1.close()


img = qrcode.make(ipmac)
img.save("/tmp/qrcode.png")
