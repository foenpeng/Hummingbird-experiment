import multiprocessing
import time
import requests
import sys
import traceback

def send_message(error_message):
    return requests.post(
        "https://api.mailgun.net/v3/YOUR_DOMAIN_NAME/messages",
        auth=("api", "key-2aa750675b64feccadca6cdeefa4ac78"),
        data={"from": "Lab <mailgun@mydomain.com>",
              "to": ["peng.foen@gmail.com", "foen@mydomain.com"],
              "subject": "Error on Hummingbird Experiment",
              "text": error_message})


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

    from gui import Gui
    gui = Gui()

    while not gui.start_event :
        gui.update()

    # IPC Objects for signaling and passing data between child processes
    recording = multiprocessing.Event()
    animal_departed = multiprocessing.Event()
    exit_event = multiprocessing.Event()

    from flower_controller import FlowerController

    port1 = gui.get_flower_port()
    port2 = gui.get_microinjector_port()
    
    print("initializing flower control process")
    flower_control_process = FlowerController(  recording, 
                                                animal_departed,
                                                exit_event,
                                                controller_port = port1,
                                                injector_port = port2   )
                                                
    trial_path = flower_control_process.trial_path

    print("initializing webcam process")
    from video_detection import Webcam
    webcam_process = Webcam(recording, animal_departed, exit_event)


    # Running block - catch exceptions here and then tear down the program.

    flower_control_process.parent_connection.send(round(time.clock(),4))
    print("starting flower control process")
    flower_control_process.start()

    webcam_process.parent_connection.send(round(time.clock(),4))
    webcam_process.parent_connection.send(trial_path)
    print("starting webcam process")
    webcam_process.start()

    while not gui.stop_event :
    
        gui.update()
        sys.stdout.flush()
        
        # Checks for runtime exceptions encountered in the child processes
        if flower_control_process.parent_connection.poll() :
            obj = flower_control_process.parent_connection.recv()
            
            if isinstance( obj, BaseException ) :
                message = "Runtime exception occurred in flower control process\n" + \
                str ( obj ) + "\n"
                print(message)
                break
                
        if webcam_process.parent_connection.poll() :
            obj = webcam_process.parent_connection.recv()
            
            if isinstance( obj, BaseException ) :
                message = "Runtime exception occurred in webcam process\n" + \
                str ( obj ) + "\n"
                print(message)
                break
                
    gui.stop()
    exit_event.set()
    comment_file = trial_path  + "/comments.txt"

    webcam_process.join()
    flower_control_process.join()

    write_comment(comment_file)
