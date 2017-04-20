import multiprocessing
import time
import requests
import sys

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

    while not gui.start_event : pass

    # IPC Objects for signaling and passing data between child processes
    recording = multiprocessing.Event()
    animal_departed = multiprocessing.Event()
    exit_event = multiprocessing.Event()
    message_queue = multiprocessing.Queue()

    from flower_controller import FlowerController

    port1 = Gui.get_flower_port()
    port2 = Gui.get_microinjector_port()

    flower_control_process = FlowerController(  recording, animal_departed,
                                                exit_event, message_queue,
                                                controller_port = port1,
                                                injector_port = port2   )


    from video_detection import Webcam
    webcam_process = Webcam(recording, animal_departed, exit_event, message_queue)


    # Running block - catch exceptions here and then tear down the program.
    else :

        flower_control_process.parent_connection.send(round(time.clock(),4))
        flower_control_process.start()

        webcam_process.parent_connection.send(round(time.clock(),4))
        webcam_process.start()

        trial_path = flower_control_process.message_queue.get()

        while not gui.stop_event :
            # Checks for runtime exceptions encountered in the child processes
            if flower_control_process.parent_connection.poll(1.e-1) :

                obj = flower_control_process.parent_connection.recv()

                # If a runtime exception occurred, join the other process and exit
                if isinstance( obj, BaseException ) :

                    message = "Runtime exception occurred in flower control process\n" + \
                    str ( obj )
                    send_message(message)

                    flower_control_process.terminate()

                    exit_event.set()
                    webcam_process.join()

                    sys.exit(1)

            else if webcam_process.parent_connection.poll(1.e-1) :

                obj = webcam_process.parent_connection.recv()

                if isinstance( obj, BaseException ) :

                    message = "Runtime exception occurred in webcam process\n" + \
                    str ( obj )
                    send_message(message)

                    webcam_process.terminate()

                    exit_event.set()
                    flower_control_process.join()

                    sys.exit(1)


        exit_event.set()
        comment_file = trial_path  + "/comments.txt"

        webcam_process.join()
        flower_control_process.join()

        write_comment(comment_file)
