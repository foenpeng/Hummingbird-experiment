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


"""TODO
1 we dont' send time stamp from arduino
2 add an injection event whenever the injector is at the starting point
3 optional: activate/deactivate arduino based on animal presence
4 start writing data when animal comes and stop when it is gone. and convert them to csv when animal is gone.


"""

                
class FlowerController(Process):

    def __init__(self,  animal_gone, exit_event,
                        accel_sample_freq = 1000, 
                        controller_port = "COM3", 
                        injector_port = "COM4",):
                        
        #Process setup
        Process.__init__(self)
        self.animal_gone = animal_gone
        self.exit_event = exit_event
        
        # IR Sensor hysteresis constants
        self.high_to_low = 190 #magic numbers, GET RID OF THEM
        self.low_to_high = 220 #
        
        # Declare filenames to write in output folder
        self.Xfilename = "x_data.csv"
        self.Yfilename = "y_data.csv"
        self.Zfilename = "z_data.csv"
        self.Nfilename = "n_data.csv"
        self.Efilename = "e_data.csv"
        self.Ifilename = "i_data.csv"
        self.rawfilename = "raw_data"
        
        self.path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.nct_prnt = False
        self.start_time = None
        self.e_time = 0      

        self.controller_port = controller_port
        self.injector_port = injector_port

        self.accel_sample_freq = accel_sample_freq
        
        self.morph = str(input("Which morphology is it?\n")) + "l070r1.5R025v020p000"
        
        self.message_queue = Queue()
        
        
    def begin(self):
    
        # Get the morphology to name the output folder
        os.chdir(os.path.join(self.path, "Data Files"))
        
        if not os.path.exists((os.path.join(os.getcwd(), self.morph))):
           os.makedirs((os.path.join(os.getcwd(), self.morph)))
           
        os.chdir(os.path.join(os.getcwd(), self.morph))
        
        today = date.today()
        
        now = datetime.datetime.now()
        
        # Get the date, also used to name output folder
        self.folder = str(today)+ "_" + str(now.hour)+ "_" + str(now.minute) +"_" + self.morph
        
        # change working directory to data files
        try:
            os.mkdir(self.folder)
        except:
            print("failed to make working directory " + self.folder + "\n")
            
        # Open output files in working directory
        self.Xfilename = self.folder + "/" + self.Xfilename
        self.Yfilename = self.folder + "/" + self.Yfilename
        self.Zfilename = self.folder + "/" + self.Zfilename
        self.Nfilename = self.folder + "/" + self.Nfilename
        self.Efilename = self.folder + "/" + self.Efilename
        self.Ifilename = self.folder + "/" + self.Ifilename
        self.rawfilename = self.folder + "/" + self.rawfilename
    
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
                self.raw_data = open(self.rawfilename, 'wb')
                
                # Send samples rates and start command
                cmd = bytearray("{0}\n".format(self.accel_sample_freq), 'ascii')
                self.controller.write(cmd)
                success = True
                
            except BaseException:                                                                  #### e?
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
        self.nct_prnt = False
        
        if self.start_time is None:
                self.start_time = round(t.clock(),5)
                
        while True:
            if self.exit_event.is_set():
                break
       
            data = self.retrieve_data()
            
            nectar_value = self.parse_nectar_measurement(data)
            self.determine_nectar_state( nectar_value ) #TODO: this has to change, since we are no longer sensing liquid!
            
            if self.animal_gone.is_set() and not self.nct_prnt:
                self.inject()
                self.nct_prnt = True
                toc = round(t.clock(),3)
                print("Nectar refilled at time stamp {} \n".format(toc))
                line = "1,{}\n".format(toc)
                self.Efile.write(line)
                self.e_time = toc 
                self.animal_gone.clear()

        self.stop()
        
    """ Reads 24 bytes, to try and grab 2 frames of data """    
    def retrieve_data(self) :
        #while(self.controller.in_waiting):
        data = self.controller.read(24)
        if data is not None: 
            self.raw_data.write(data)
        return data

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
                        
                        
    """ Determines whether the beam has been blocked or not, based on the ADC value,
        and the two hysteresis thresholds, self.high_to_low and self.low_to_high
    """
    def determine_nectar_state( self, nectar_value ) : #TODO: this has to change, since we are no longer sensing liquid!
       
       # Determine the nectar state
        if nectar_value is not None:
        
                toc = round(t.clock(),3)
                
                if toc - self.e_time > 1:
                
                    if(self.nct_prnt == True and (nectar_value > self.low_to_high)) :
                        self.nct_prnt = False
                        print("Nectar emptied at time stamp {0} \n".format(toc))
                        line = "0,{0}\n".format(toc)
                        self.Efile.write(line)
                        self.e_time = toc

        
    def inject(self):
        self.injector.flushInput()                                                     
        cmd = bytearray("inject\n", 'ascii')
        self.injector.write(cmd)
        toc = round(t.clock(),3)
        time = str(toc)
        line = "{0}\n".format(time);
        print("Injection requested at time stamp {0}".format(time))
        self.Ifile.write(line)
        return toc                        
                        
    def stop(self):
        # Assert Data Terminal Ready to reset Arduino
        self.controller.dtr = True
        t.sleep(1)
        self.controller.dtr = False
        # Close the port
        self.controller.close()
        # Unpack the data
        self.unpack_data()
        # Fix the time overflow issue
        self.exit_time = t.clock()
        try:

            self.update_time(self.Xfilename, 4 * self.accel_sample_freq)
            self.update_time(self.Yfilename, 4 * self.accel_sample_freq)
            self.update_time(self.Zfilename, 4 * self.accel_sample_freq)
            self.update_time(self.Nfilename, 4 * self.accel_sample_freq)

            pass
        except OSError as e:
            raise(e)
   
        try:
            commentfile = self.folder + "/comments.txt"

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
            
            self.message_queue.put(commentfile)

        except OSError as e:
            raise(e)
            
        

    """
    This function reads from the raw binary data file and separates each
    data frame, where a frame consists of one read from each analog input channel
    and its corresponding timestamp.

    After collecting the frames, it will compute the amount of bytes lost in
    transmission, and then write the data to appropriate files (one for each channel)
    """
    def unpack_data(self):
        # Close the raw_data file, since it was open for writing previously
        self.raw_data.close()
        # Open the raw data file for reading
        self.raw_data = open(self.rawfilename, 'rb')
        data = bytearray()

        # Iterate over the file, reading each byte and appending to an array
        while True:
            byte = self.raw_data.read(1)
            if byte:
                data += byte
            else:
                break

        index = 0                           # iteration index
        frames = []                         # Location of frames in the data array

        while(index + 11 < len(data)):      # Verify that there is a full frame yet to be processed
            if locate_frame(index,data):
                frames.append(index)        # Append this index to a list of indexes pointing to valid frames
                index += 12                 # Increment by the size of one frame in bytes
            else:
                index += 1                  # Increment by one byte
        
        self.frame_count = len(frames)
        print("frame count", self.frame_count)
        print("bytes received", len(data))
        bytes_lost = len(data) - len(frames) * 12
        print("bytes lost", bytes_lost)
        print("loss ratio " + str(round(100 * bytes_lost / float(len(data)),4)) + " percent" )


        for frame in frames:
            # Write the X value and timestamp to the CSV file
            value = data[frame+1]
            timestamp = data[frame+2]
            line = "{0},{1}\n".format(value,timestamp)
            self.Xfile.write(line)

            # Write the Y value and timestamp to the CSV file
            value = data[frame+4]
            timestamp = data[frame+5]
            line = "{0},{1}\n".format(value,timestamp)
            self.Yfile.write(line)

            # Write the Z value and timestamp to the CSV file
            value = data[frame+7]
            timestamp = data[frame+8]
            line = "{0},{1}\n".format(value,timestamp)
            self.Zfile.write(line)

            # Write the N value and timestamp to the CSV file
            value = data[frame + 10]
            timestamp = data[frame + 11]
            line = "{0},{1}\n".format(value,timestamp)
            self.Nfile.write(line)

        # Close the output files
        self.Xfile.close()
        self.Yfile.close()
        self.Zfile.close()
        self.Nfile.close()
        self.Efile.close()
        self.Ifile.close()

    """
    This function is used to adjust the time stamps sent by
    the flower controller after the data has been unpacked and sorted
    into separate files.

    For example, the sequence of time stamps
    0, 1, ..., 2^16-1, 0, 1, ... 2^16-1 is converted into
    0, 1, ..., 2^16-1, 2^16, 2^16+1, ..., 2^17-1
    """
    def update_time(self, filename, frequency):
        print("Updating " + filename)
        
        # open the file for reading
        try:
            in_file = open(filename, 'r')
        except OSError:
            raise OSError("Error opening " + filename + "for reading!")
            
        # Loop over the file contents, and then process
        lines = list()
        offset = 0;
        last_time = 0;
        modulus = pow(2,8)
        time_unit = (self.exit_time - self.start_time)/self.frame_count
        time_line = self.start_time
        
        for line in in_file:
            # split the data into (data,time_stamp)
            (data, sep, time_stamp) = line.partition(',')
            time_line = time_line + time_unit
            time_stamp = str(round(time_line,4))
            
            # Rejoin the parts to a new line, and write to file
            if('' == data):
                lines.append(time_stamp+'\n')
            else:
                lines.append("".join((data,sep,time_stamp))+'\n')
        in_file.close()
        
        # Open the file for writing
        try:
            out_file = open(filename,'w')
            
        # OSError caught incase the file does not exist or this
        # script does not have permissions to write
        except OSError:
            print("Error opening " + filename + " for writing!")
            raise OSError
            
        # Write the data to the file
        for line in lines:
            out_file.write(line)

        # All done with this file
        out_file.close()
    
def locate_frame(index,data): 
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