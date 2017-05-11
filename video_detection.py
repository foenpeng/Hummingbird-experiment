import cv2
import time as t
import datetime
import numpy as np
import copy
import sys
from multiprocessing import Process, Event, Pipe

class Webcam(Process):

    def __init__(self, recording, animal_departed, exit_event):
        self.recording = recording
        self.animal_departed = animal_departed
        self.exit_event = exit_event
        self.parent_connection, self.child_connection = Pipe()
        self.animal_prnt = False
        self.firstFrame = None
        self.previous_image = None
        self.current_image = None
        self.AbsentFrame = 0
        self.frame_count = 0
        self.error_adjust = 0
        self.fps = 10
        self.consective_parameter = [10,10] # parameter used in consecutive analysis [every # frame to run analysis, threshold to make new ref_frame]
        self.image_threshold = 50 # color difference after image convert to black-white
        self.min_area = 1500 # the minimum amount of different pixels in simple processing to do furthre analysis
        self.ROI = [300,300,150] # circle parameters [x,y,r] to define the region of interest
        self.InjectionDelay = 2 # how many seconds after the animal left the region to refill nectar
        Process.__init__(self)



    def begin(self):
        t.clock()
        self.start_time = self.child_connection.recv()
        print("Video process starts at {}".format(self.start_time))
        sys.stdout.flush()

        # frame rate
        self.trial_path = self.child_connection.recv()
        self.Mfile=open(self.trial_path + "/m_data.csv",'w')
        self.cam = cv2.VideoCapture(0)
        self.video  = cv2.VideoWriter(self.trial_path + "/video.avi",cv2.VideoWriter_fourcc('X','V','I','D'), self.fps, (640, 480), True)
        t.sleep(1.5) # allow enough time for the camera to adjust to the light condition before fetch ref frame
        self.reference_image = self.get_ref_frame()
        cv2.imshow('ref',self.reference_image)

        # this function is to get a reference image, when the image is stable (there is less than 50 pixels have color difference)
    def get_ref_frame(self):
        while(True):
            if self.exit_event.is_set() :
                break
            ret,frame1 = self.cam.read()
            self.gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            if self.firstFrame is None:
                self.firstFrame = self.gray1
                continue
            subt1 = cv2.absdiff(self.firstFrame,self.gray1)
            self.firstFrame = self.gray1
            position =  np.matrix(np.where(subt1 > self.image_threshold))
            if position.shape[1] < 50:
                break
        if self.exit_event.is_set() :
            self.stop()
        return self.firstFrame

    def consecutive_analysis(self, i1, i2, number):
        sub2 = cv2.absdiff(i1, i2)
        ret,thresh2 = cv2.threshold(sub2,self.image_threshold,255,cv2.THRESH_BINARY)
        if thresh2.sum()/255 < 50:
            return 1
        else:
            return 0

    def simple_processing(self, img):
        self.original_image = img
        self.current_image = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        diff = cv2.absdiff(self.current_image, self.reference_image)
        ret,thresh = cv2.threshold(diff,
                                   self.image_threshold,
                                   255,
                                   cv2.THRESH_BINARY)
        moving_pixels = thresh.sum()/255
        if moving_pixels > self.min_area:
            self.AbsentFrame = 0
            self.frame_count += 1
            if self.previous_image is None:
                self.previous_image = self.current_image
            if self.frame_count >= self.consective_parameter[0]:
                detection_conflict = self.consecutive_analysis(self.current_image, self.previous_image, moving_pixels)
                if detection_conflict :
                    self.error_adjust += 1
                else :
                    self.error_adjust = 0
                self.previous_image = self.current_image
                self.frame_count = 0

            if self.error_adjust >= self.consective_parameter[1]:
                print("Reference image adjusted at {}".format(str(round((t.clock()-self.start_time),2))))
                sys.stdout.flush()
                self.reference_image = self.get_ref_frame()
                cv2.imshow('ref',self.reference_image)
                self.error_adjust = 0
            else:
                self.further_processing(thresh)
                self.recording.set()
                self.animal_departed.clear()
        else:
            self.AbsentFrame += 1
            cv2.destroyWindow('thresh')
            cv2.destroyWindow('bird cam')

        if self.AbsentFrame > self.fps * self.InjectionDelay and not self.animal_departed.is_set():
            self.animal_departed.set()
            self.recording.clear()
            #self.animal_prnt = False
            print("animal is gone at: {}".format(str(round((t.clock()-self.start_time),2))))
            sys.stdout.flush()

    def further_processing(self, thresh):
        self.display_image = copy.deepcopy(self.original_image)
        centroid_x,centroid_y= 0,0
        biggest_cnt = 0
        num_biggest_cnt = None
        toc = round((t.clock()-self.start_time),3)
        thresh_dilate = cv2.dilate(thresh, None, iterations=2)
        _, cnts, _ = cv2.findContours(thresh_dilate, cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)

        # find the biggest contour in the image
        for c in cnts:
            contourArea = cv2.contourArea(c)
            # if the contour is too small, ignore it
            if contourArea < self.min_area:
                continue
            if contourArea > biggest_cnt:
                biggest_cnt = contourArea
                num_biggest_cnt = c

        # find the centroid of the biggest contour
        if num_biggest_cnt is not None:
            M = cv2.moments(num_biggest_cnt)
            centroid_x = int(M['m10']/M['m00'])
            centroid_y = int(M['m01']/M['m00'])
            cv2.circle(self.display_image, (centroid_x,centroid_y), 5, (0,0,0), -1) # draw the centroid in the video


        # Determine whether the moving object is inside a defined area
        if (self.ROI[0]-centroid_x)**2 + (self.ROI[1]-centroid_y)**2 < self.ROI[2]**2: # judge if the centroid is inside the circle
            cv2.circle(self.display_image, (self.ROI[0], self.ROI[1]), self.ROI[2], (255, 255, 255), 2)
            cv2.putText(self.display_image, "Animal Present", (250, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
            self.animal_prnt = True

            self.AbsentFrame = 0
            line = "{0},{1}\n".format(1,toc)
            self.Mfile.write(line)
        else:
            cv2.circle(self.display_image, (self.ROI[0], self.ROI[1]), self.ROI[2], (0, 0, 0), 2)
            cv2.putText(self.display_image, "Animal Absent", (250, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
            self.AbsentFrame += 1
            line = "{0},{1}\n".format(0,toc)
            self.Mfile.write(line)

        cv2.putText(self.display_image, datetime.datetime.now().strftime("%A %d %B %Y %I:%M:%S%p"),(10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
        cv2.putText(self.display_image, "Time Elapsed: {}".format(str(toc)),(250, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
        cv2.imshow('bird cam', self.display_image)
        cv2.imshow('thresh', thresh)
        self.video.write(self.display_image)


    def run(self):
        try :
            self.begin()
            t3 = 0
            
            while True:
                t0 = t.clock()
                if self.exit_event.is_set():
                    break
                re1,img1 = self.cam.read()
                t1 = t.clock()
                self.simple_processing(img1)
                t2 = t.clock()
                while(t.clock() - t0 < 1/self.fps - 20e-3):
                    cv2.waitKey(20)
                while(t.clock() - t0 < 1/self.fps):
                    pass

                t3 = t0

        except BaseException as e :
            self.child_connection.send ( e )
            raise
            
        finally :
            self.stop()

    def stop(self):
        self.Mfile.close()
        self.cam.release()
        self.video.release()
        cv2.destroyAllWindows()


def main():
    animal_departed = Event()
    exit_event = Event()
    video = Webcam(animal_departed, exit_event);
    try:
        video.start()
        input("Press Enter to Exit: ")
        video.exit_event.set()
        video.join()
        print("Program ends, goodbye!")

    except KeyboardInterrupt:
        video.exit_event.set()
        video.join()
        print("Exited due to keyboard interrupt.")

if __name__ == '__main__':
    main()
