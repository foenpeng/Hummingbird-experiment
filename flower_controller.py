# This version came after v9.data_acquisition and will be directly updated on github. 2/8/2017

import winsound
import numpy as np
# np.set_printoptions(threshold=np.nan)
import datetime
import os
import sys
import serial as s
import time as t
from datetime import date
from multiprocessing import Process, Event, Queue

DATA_FRAME_SIZE = 12

"""TODO
1 I need to validate the time stamp on x, y, z, n file. 
2 add an injection event whenever the injector is at the starting point and the first two injection at the start of experiment were wired
3 the n value does not change, needs to fix

"""
class FlowerController(Process):

    def __init__(self,  recording, animal_departed, exit_event, message_queue,
                        controller_port,
                        injector_port,
                        accel_sample_freq = 1000):

        #Process setup
        Process.__init__(self)

        # Those are the things need to be passed among processes
        self.recording = recording
        self.animal_departed = animal_departed
        self.exit_event = exit_event

        # IR Sensor hysteresis constants
        self.low_to_high = 220 

        # Declare filenames to write in output folder
        self.Xfilename = "x_data.csv"
        self.Yfilename = "y_data.csv"
        self.Zfilename = "z_data.csv"
        self.Nfilename = "n_data.csv"
        self.Efilename = "e_data.csv"
        self.Ifilename = "i_data.csv"
        self.raw_files = []

        # Initiate parameters
        self.nct_prnt = False
        self.start_time = None
        self.e_time = 0
        self.state = "processing"
        self.controller_port = controller_port
        self.injector_port = injector_port
        self.accel_sample_freq = accel_sample_freq
        
        # Making a directory for the morph and pass its address into a queue
        self.morph = str(input("Which morphology is it?\n")) + "l070r1.5R025v020p000"
        self.morph_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/Data Files/" + self.morph
        if not os.path.exists(self.morph_path):
           os.makedirs(self.morph_path)

        today = date.today()
        now = datetime.datetime.now()
        self.folder = str(today)+ "_" + str(now.hour)+ "_" + str(now.minute) +"_" + self.morph
        self.trial_path = self.morph_path + "/" + self.folder
        self.message_queue = message_queue
        self.message_queue.put(self.trial_path)

    def begin(self):
        
        self.message_queue.put(self.trial_path)

        # Make a working directory to ouput data files
        try:
            os.mkdir(self.trial_path)
        except:
            print("failed to make working directory " + self.trial_path + "\n")

        # Open output files in working directory
        self.Xfilename = self.trial_path + "/" + self.Xfilename
        self.Yfilename = self.trial_path + "/" + self.Yfilename
        self.Zfilename = self.trial_path + "/" + self.Zfilename
        self.Nfilename = self.trial_path + "/" + self.Nfilename
        self.Efilename = self.trial_path + "/" + self.Efilename
        self.Ifilename = self.trial_path + "/" + self.Ifilename

        # Open the two serial ports
        try:
            # Open ports at 1Mbit/sec
            self.controller = s.Serial(self.controller_port,
                                    1000000,
                                    timeout = 1)

            self.injector = s.Serial(self.injector_port,
                                     115200,
                                     timeout = 1)
            success = True

            # Assert Data Terminal Ready signal to reset Arduino
            self.controller.rtscts = True
            self.injector.rtscts = True
            self.controller.dtr = True
            self.injector.dtr = True
            t.sleep(1)
            self.controller.dtr = False
            self.injector.dtr = False
            t.sleep(2)

        except s.SerialException:
            success = False
            print("Failed to open one of the ports")
            raise(s.SerialException)

        if success:
            try:
                # Open output files for writing
                self.Xfile = open(self.Xfilename, 'w')
                self.Yfile = open(self.Yfilename, 'w')
                self.Zfile = open(self.Zfilename, 'w')
                self.Nfile = open(self.Nfilename, 'w')
                self.Efile = open(self.Efilename, 'w')
                self.Ifile = open(self.Ifilename, 'w')

                # Send samples rates and start command
                cmd = bytearray("{0}\n".format(self.accel_sample_freq), 'ascii')
                self.controller.write(cmd)
                success = True

            except BaseException as e:
                success = False
                raise(e)

        if success:
            self.running = True

        else:
            self.running = False

    """
    This function implements the running Loop of the
    FlowerController thread. It waits for 3-byte frames
    of data from the arduino and writes them to a separate
    file based on the first byte, the code, of the data.
    """
    def run(self):

        self.begin()
        self.controller.flushInput()

        if self.start_time is None:
                self.start_time = round(t.clock(),5)

        while True:       
        
            if self.exit_event.is_set():
                break

            data = self.controller.read(24)
            nectar_value = self.parse_nectar_measurement(data)
            self.determine_nectar_state( nectar_value )

            if self.recording.is_set() and self.state == "processing" :
                self.state = "recording"
                self.begin_raw_data_file()

            if self.recording.is_set() and self.state == "recording" :
                self.raw_files[-1]['handle'].write(data)

            if not self.recording.is_set() and self.state == "recording" :
                self.state = "processing"
                self.raw_files[-1]['stop time'] = t.clock()
                self.raw_files[-1]['handle'].close()

            if not self.recording.is_set() and self.state == "processing" :
                if len(self.raw_files) > 0 :
                    self.process_raw_data()

            if self.animal_departed.is_set() and not self.nct_prnt:
                time = self.inject()
                self.nct_prnt = True
                line = "1,{}\n".format(time)
                self.Efile.write(line)
                self.e_time = time
                self.animal_departed.clear()

        self.stop()
        
    def stop(self):
        # Assert Data Terminal Ready to reset Arduino
        self.controller.dtr = True
        t.sleep(1)
        self.controller.dtr = False
        # Close the port
        self.controller.close()
        # Fix the time overflow issue
        self.exit_time = t.clock()

        try:
            commentfile = self.trial_path + "/comments.txt"

            filename = open(commentfile, 'w')
            filename.write("Flower morphology tested: \n")
            filename.write("{0}\n".format(self.morph)) # Flower morphology tested:
            filename.write("Trial starts at: \n")
            filename.write("{0}\n".format(self.start_time)) # Start time
            filename.write("Program lasts (seconds): \n")
            filename.write("{0}\n".format(self.exit_time)) # Program lasts time
            filename.write("The x,y,z sampling frequency: \n")
            filename.write("{0}\n". format(self.accel_sample_freq)) # The x,y,z sampling frequency
            filename.write("Sex of the moth? \n\n")
            filename.write("Proboscis length? \n\n")
            filename.write("How many days after eclosion? \n\n")
            filename.close()
        except OSError as e:
            raise(e)

    """ Parses the last 24 bytes grabbed to try and extract a IR sensor measurement """
    def parse_nectar_measurement(self, data):
        nectar_value = None

        if data is not None:
            for i in range(len(data)):

                # Check for the data code
                if chr(data[i]) == 'N' and i+1 in range(len(data)):

                    if i-3 in range(len(data)):

                        # Check to make sure that the previous value was from Z channel
                        if chr(data[i-3]) == 'Z':
                            nectar_value = data[i+1]
                            break

                    elif i+3 in range(len(data)):

                        # Check to make sure that the following value is form X channel
                        if chr(data[i+3]) == 'X':
                            nectar_value = data[i+1]
                            break

        return nectar_value



    def determine_nectar_state( self, nectar_value ) : 
        """ Determines whether the beam has been blocked or not, based on the ADC value,
            and the two hysteresis thresholds, self.high_to_low and self.low_to_high
        """
        # Determine the nectar state
        if nectar_value is not None:
                toc = round(t.clock(),3)
                if toc - self.e_time > 1:

                    if (self.nct_prnt == True) and (nectar_value > self.low_to_high) :                              #TODO: this has to change, since we are no longer sensing liquid!

                        self.nct_prnt = False
                        print("Nectar emptied at time stamp {0} \n".format(toc))
                        line = "0,{0}\n".format(toc)
                        self.Efile.write(line)
                        self.e_time = toc

                        
    def begin_raw_data_file (self) :   
        """
        Opens a new raw data file for recording to, and appends it to a list of raw data files
        for later processing.
        """
        self.rawfilename = self.trial_path + "/raw_data_{}".format(len(self.raw_files)+1)
        try :
            self.raw_files.append( {
                                    'handle' : open(self.rawfilename, 'wb'),
                                    'size'   : 0,                                                                    #TODO size seems not used.  those info needs to be written somewhere and compare with the video detection program.
                                    'start time' : t.clock(),
                                    'stop time'  : None,
                                    'frame count': 0 } )
        except :
            self.exit_event.set()
            raise ("flower controller failed to open file named '{}' for writing \n"                                 #TODO: this needs to be changed
                    .format(self.rawfilename))

    def process_raw_data ( self ) :

        # If no file is current being processed, open the next file                                                  #TODO: if the file processing was interrupted, this will make the program process the same file one more time from the beginning
        if self.raw_files[0]['handle'].closed :
            self.raw_files[0]['handle'] = open( self.raw_files[0]['handle'].name, 'rb' )

        # Processing the file
        if not self.raw_files[0]['handle'].closed :
            # grap next frame of data
            data = bytearray()
            data += self.raw_files[0]['handle'].read(12)

            if len(data) < 12 : 
                self.close_raw_file()
                return

            while not self.locate_frame ( 0, data ) :
                data.pop(0)
                byte = self.raw_files[0]['handle'].read(1)
                if byte is not "" :
                    data += byte
                else :
                    self.close_raw_file()
                    return

            self.raw_files[0]['frame count'] += 1
            
            # Determine timestamp of this sample
            timestamp = self.raw_files[0]['start time'] + (self.raw_files[0]['frame count'] - 1.) / self.accel_sample_freq

            # Write the X value and timestamp to the CSV file
            value = data[1]
            line = "{0},{1}\n".format(value,timestamp)
            self.Xfile.write(line)

            # Write the Y value and timestamp to the CSV file
            value = data[4]
            line = "{0},{1}\n".format(value,timestamp)
            self.Yfile.write(line)

            # Write the Z value and timestamp to the CSV file
            value = data[7]
            line = "{0},{1}\n".format(value,timestamp)
            self.Zfile.write(line)

            # Write the N value and timestamp to the CSV file
            value = data[10]
            line = "{0},{1}\n".format(value,timestamp)
            self.Nfile.write(line)


    def close_raw_file(self) :
        self.raw_files[0]['handle'].close()
        #os.remove(self.raw_files[0]['handle'].name)
        self.raw_files.pop(0)


    def inject(self):
        self.injector.flushInput()
        cmd = bytearray("inject\n", 'ascii')
        self.injector.write(cmd)
        time = round(t.clock(),3)
        line = "{0}\n".format(time);
        print("Injection requested at time stamp {0} \n".format(time))
        self.Ifile.write(line)
        return time
        
    def locate_frame(self, index, data):
        if data[index] != ord('X'):
            return False
        elif data[index + 3] != ord('Y'):
            return False
        elif data[index + 6] != ord('Z'):
            return False
        elif data[index + 9] != ord('N'):
            return False
        else:
            return True
