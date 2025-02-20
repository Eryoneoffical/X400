import numpy
import cv2

from PIL import Image
import sys 
import requests
import time





win_w = 300
win_h = 300

star_x = 20
star_y = 20

name = '33'
#name =sys.argv[1]
## http://192.168.2.60/webcam/?action=snapshot
#curl http://127.0.0.1/webcam/?action=snapshot -o /tmp/cam.png
#vidcap=cv2.VideoCapture("/dev/video4")
#success,image = vidcap.read()

def check_bed():
    time0 = time.time() 
    url = r'http://127.0.0.1/webcam/?action=snapshot'
    resp = requests.get(url, stream=True).raw
    image = numpy.asarray(bytearray(resp.read()), dtype="uint8")
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
    time1 = time.time() 

    height, width = image.shape[:2]
   # new_size = (width // 2, height // 2)
   # image = cv2.resize(image, new_size, interpolation=cv2.INTER_LINEAR)

#image = cv2.imread(name+'.png') # loads an image from the specified file
# convert an image from one color space to another
    grey_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    invert = cv2.bitwise_not(grey_img) # helps in masking of the image
# sharp edges in images are smoothed while minimizing too much blurring
    blur = cv2.GaussianBlur(invert, (21, 21), 0)
    invertedblur = cv2.bitwise_not(blur)
    sketch = cv2.divide(grey_img, invertedblur, scale=256.0)
#cv2.imwrite(name+"s.png", sketch) # converted image is saved as mentioned name



    image = sketch #cv2.imread(name+'s.png')
#image= cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    se=cv2.getStructuringElement(cv2.MORPH_RECT , (8,8))
    bg=cv2.morphologyEx(image, cv2.MORPH_DILATE, se)
    out_gray=cv2.divide(image, bg, scale=255)
    out_binary=cv2.threshold(out_gray, 0, 255, cv2.THRESH_OTSU )[1]
    cv2.imwrite("/tmp/p.png", out_binary)


    sum = 0



    out_binary=cv2.threshold(out_gray, 0, 1, cv2.THRESH_OTSU )[1]
    time2 = time.time() 
#print(out_binary[0][0:200])
#print (out_binary.shape)
    pos_x = 0
    pos_y = 0

    area = win_w*win_h
#for i in range(0, len(list_1), step) :
    for idx in range(star_y,len(out_binary),20):
        if idx < len(out_binary) - win_h :

            for id in range(star_x,len(out_binary[idx]),20):
                if id < len(out_binary[idx]) - win_w:
                    
                    #sum = rentangle_area(idx,id,out_binary)
                    sum = numpy.sum(out_binary[idx:idx+win_h,id:id+win_w])
                    sum = win_w*win_h - sum
                   # print("x:",idx,"y:",id,"sum:",sum)
                    if area > sum:
                        area = sum
                        pos_x = id
                        pos_y = idx
                    
                    
    print("max pos===x:",pos_x,"y:",pos_y,"sum:",area)
    time3 = time.time() 
    print("time:",time1-time0,"time:",time2-time1,"time:",time3-time2)
    if area > 150:
        requests.get(url="http://127.0.0.1/printer/gcode/script?script=M117 =bed_obj" + str(area))
        requests.get(url="http://127.0.0.1/printer/gcode/script?script=PAUSE")
#http://192.168.2.47/printer/gcode/script?script=M117rt
           # if x==0:
            #    sum = sum + 1
            
        
    
#cv2.imwrite("27gp.png", out_gray)

#while True:
#    time.sleep(2)
check_bed()


