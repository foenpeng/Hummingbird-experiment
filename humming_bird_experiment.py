import multiprocessing
import time

def write_comment( comment_file ) :    
    try:

        filename = open(comment_file, 'w')
        filename.write("Flower morphology tested: \n")
        filename.write("{0}\n".format(self.morph)) # Flower morphology tested: 
        filename.write("Trial starts at: \n")
        filename.write("{0}\n".format(self.start_time)) # Start time
        #filename.write("Video starts at time: {0}\n".format(v.start_time))
        #filename.write("Sensor starts at time: {0}\n".format(self.start_time))
        #toc = round(t.clock(),3)
        filename.write("Program lasts (seconds): \n")
        filename.write("{0}\n".format(self.exit_time)) # Program lasts time
        filename.write("The x,y,z sampling frequency: \n")
        filename.write("{0}\n". format(self.accel_sample_freq)) # The x,y,z sampling frequency
        temp = input("Temperature? \n").strip()
        filename.write("Temperature? \n")
        filename.write("{0}\n".format(temp))
        hum = input("Humidity? \n").strip()
        filename.write("Humidity? \n")
        filename.write("{0}\n".format(hum))
        filename.write("Sex of the moth? \n\n")
        weight = input("Body Weight? \n").strip()
        filename.write("Body Weight?\n")
        filename.write("{0}\n".format(weight))
        filename.write("Body length? \n\n")
        filename.write("Proboscis length? \n\n")
        filename.write("How many days after eclosion? \n\n")
        filename.write("Program exit condition?\n")
        filename.write(exit_text +"\n")
        comments = input("Comments on this trial?\n").strip()
        filename.write(comments)
        filename.close()
    except OSError as e:
        raise(e)

if __name__ == "__main__" :

    animal_gone = multiprocessing.Event()

    exit_event = multiprocessing.Event()

    from video_detection import Webcam
    webcam_process = Webcam(animal_gone, exit_event)

    from flower_controller import FlowerController
    port1 = input("enter COM port for flower controller")
    port2 = input("enter COM port for microinjector")
    flower_control_process = FlowerController(animal_gone, exit_event, controller_port = port1, injector_port = port2)

    webcam_process.start()
    flower_control_process.start()


    try :
        while True:
            input("enter anything to exit")
            exit_event.set()
            webcam_process.join()
            flower_control_process.join()
            comment_file = flower_control_process.message_queue.get()
            print("received comment file {}".format(comment_file))
            write_comment(comment_file)
     
    except KeyboardInterrupt :
        exit_event.set()
        print("joining video detection process...")
        webcam_process.join()
        print("joining flower controller process...")
        flower_control_process.join()
        comment_file = flower_control_process.message_queue.get()
        print("received comment file {}".format(comment_file))
        write_comment(comment_file)
     