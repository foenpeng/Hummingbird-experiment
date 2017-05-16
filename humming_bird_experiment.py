import multiprocessing
import time
import requests
import sys
import traceback
import logging

multiprocessing_logger = multiprocessing.get_logger()
logging.basicConfig ( level = logging.INFO )
log_file_handler = logging.FileHandler('log.txt')
multiprocessing_logger.setLevel(logging.INFO)
multiprocessing_logger.addHandler(log_file_handler)

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


class ChildProcess ( multiprocessing.Process ) :

    def __init__ ( self ) :
        self.exit_event = multiprocessing.Event()
        self.runtime_exception_event = multiprocessing.Event()
        self.log_event = multiprocessing.Event()
        self.parent_connection, self.child_connection = multiprocessing.Pipe()
        self.logger = None
        multiprocessing.Process.__init__ ( self )

    """ Call in the child process to get the logging handle """
    def log_configure ( self ) :
        self.logger = multiprocessing.log_to_stderr()

    """ Send logging level and value to parent process for logging """
    def log ( self, value, level = logging.INFO ) :
        multiprocessing_logger.log ( level, value )

    """ Sends an exception and traceback to the main process via its pipe """
    def raise_exc ( self, exception, traceback ) :
        self.child_connection.send ( (exception, traceback) )
        self.runtime_exception_event.set()

    """ Gets exceptions from the child so they can be logged in the parent and handled """
    def exception_occurred ( self ) :
        if self.runtime_exception_event.is_set() :
            (exception, traceback) = self.parent_connection.recv()
            value = "Exception occurred in process with PID {} \n".format(self.pid) + str ( traceback )
            self.log ( value, level = logging.CRITICAL )
            return exception

class Foo ( ChildProcess ) :

    def __init__ ( self ) :
        ChildProcess.__init__ ( self )

    def run ( self ) :
        self.log_configure()
        try :
            while not self.exit_event.is_set() :
                self.log ( 'Foo {}!'.format(self.pid) )
                time.sleep(1)
                if time.clock() > 10 :
                    raise BaseException ( "Timeout!" )

        except BaseException as e :
            self.raise_exc ( e, traceback.format_exc() )

        finally :
            self.log ( 'Foo {} is terminating'.format(self.pid) )


if __name__ == "__main__" :

    from gui import Gui
    gui = Gui()

    while not gui.start_event :
        gui.update()

    # IPC Objects for signaling and passing data between child processes
    recording = multiprocessing.Event()
    animal_departed = multiprocessing.Event()

    from flower_controller import FlowerController

    port1 = gui.get_flower_port()
    port2 = gui.get_microinjector_port()

    flower_control_process = FlowerController(  recording,
                                                animal_departed,
                                                controller_port = port1,
                                                injector_port = port2   )

    trial_path = flower_control_process.trial_path

    logging.basicConfig ( filename = trial_path + '\\log.txt', level = logging.INFO )
    logger = multiprocessing.log_to_stderr()
    logger.setLevel(logging.INFO)


    from video_detection import Webcam
    webcam_process = Webcam  (recording, animal_departed )


    # Running block - catch exceptions here and then tear down the program.

    flower_control_process.parent_connection.send(round(time.clock(),4))
    logger.info("starting flower control process")
    flower_control_process.start()

    webcam_process.parent_connection.send(round(time.clock(),4))
    webcam_process.parent_connection.send(trial_path)
    logger.info("starting webcam process")
    webcam_process.start()

    while not gui.stop_event :

        gui.update()

        # Checks for runtime exceptions encountered in the child processes
        if flower_control_process.exception_occurred() :
            break

        if webcam_process.exception_occurred() :
            break


    gui.stop()
    exit_event.set()
    comment_file = trial_path  + "/comments.txt"

    webcam_process.join()
    flower_control_process.join()

    write_comment(comment_file)
