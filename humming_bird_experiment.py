import multiprocessing
import time

def write_comment( comment_file ) :
    try:
        filename = open(comment_file, "a")

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
        comments = input("Comments on this trial?\n").strip()
        filename.write(comments)
        filename.close()
    except OSError as e:
        raise(e)

if __name__ == "__main__" :

    recording = multiprocessing.Event()
    animal_departed = multiprocessing.Event()
    exit_event = multiprocessing.Event()
    message_queue = multiprocessing.Queue()
    # The following two pipes were used to send the time of main process to childs
    mtime1, ftime_pipe = multiprocessing.Pipe()
    mtime2, vtime_pipe = multiprocessing.Pipe()

    from flower_controller import FlowerController
    port1 = input("Please enter COM port for flower controller: ") or "COM3"
    port2 = input("Please enter COM port for microinjector: ") or "COM6"
    flower_control_process = FlowerController(recording, animal_departed, exit_event, message_queue,ftime_pipe, controller_port = port1, injector_port = port2)


    from video_detection import Webcam
    webcam_process = Webcam(recording, animal_departed, exit_event, message_queue, vtime_pipe)
 
    mtime1.send(time.clock())
    flower_control_process.start()
    
    mtime2.send(time.clock())
    webcam_process.start()
    
    trial_path = flower_control_process.message_queue.get()

    try :
        input("Enter anything to exit: \n")
        exit_event.set()
        comment_file = trial_path  + "/comments.txt"
        webcam_process.join()
        flower_control_process.join()
        write_comment(comment_file)

    except KeyboardInterrupt :
        exit_event.set()
        comment_file = flower_control_process.message_queue.get()
        print("joining video detection process...")
        webcam_process.join()
        print("joining flower controller process...")
        flower_control_process.join()
        write_comment(comment_file)
