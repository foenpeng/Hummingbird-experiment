import multiprocessing
import time
import requests
import sys
import os
import traceback
import logging

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

""" Sets up the multiprocessing logger to have a stream handler to stdout, as well as log to a file.
    This is used in both the main process, and child processes
"""
def configure_logger () :
    logger = multiprocessing.get_logger()
    logger.setLevel(logging.INFO)
    log_file_handler = logging.FileHandler('log.txt')
    log_stream_handler = logging.StreamHandler(sys.stdout)
    log_formatter = logging.Formatter('[%(levelname)s][%(processName)s][%(process)d][%(asctime)s] %(message)s')
    log_stream_handler.setFormatter(log_formatter)
    log_file_handler.setFormatter(log_formatter)
    logger.addHandler(log_stream_handler)
    logger.addHandler(log_file_handler)
    return logger



class ChildProcess ( multiprocessing.Process ) :

    def __init__ ( self ) :
        self.exit_event = multiprocessing.Event()
        self.runtime_exception_event = multiprocessing.Event()
        self.parent_connection, self.child_connection = multiprocessing.Pipe()
        self.logger = None
        self.log_file_path = ""
        multiprocessing.Process.__init__ ( self )

    """ Send logging level and value to parent process for logging """
    def log ( self, value, level = logging.INFO ) :
        if os.getpid() == self.pid :
            if self.logger is None :
                self.logger = configure_logger()
            self.logger.log ( level, value )

    """ Sends an exception and traceback to the main process via its pipe """
    def raise_exc ( self, exception, traceback ) :
        self.child_connection.send ( (exception, traceback) )
        self.runtime_exception_event.set()
        value = "Exception occurred in process with PID {} \n".format(self.pid) + str ( traceback )
        self.log ( value, level = logging.CRITICAL )

    """ Gets exceptions from the child so they can be logged in the parent and handled """
    def exception_occurred ( self ) :
        if self.runtime_exception_event.is_set() :
            (exception, traceback) = self.parent_connection.recv()
            return exception


if __name__ == "__main__" :

    root_logger = configure_logger()

    from gui import Gui
    gui = Gui()

    while not gui.start_event :
        gui.update()

    # IPC Objects for signaling and passing data between child processes
    recording = multiprocessing.Event()
    animal_departed = multiprocessing.Event()

    from flower_controller import FlowerController

    port = gui.get_flower_port()

    flower_control_process = FlowerController(  recording,
                                                animal_departed,
                                                controller_port = port )

    trial_path = flower_control_process.trial_path
    root_logger.info('Trial data will be saved at "{}"'.format(trial_path))

    from video_detection import Webcam
    webcam_process = Webcam  (recording, animal_departed )

    flower_control_process.parent_connection.send(round(time.clock(),4))
    flower_control_process.start()

    webcam_process.parent_connection.send(round(time.clock(),4))
    webcam_process.parent_connection.send(trial_path)
    webcam_process.start()

    while not gui.stop_event :

        gui.update()

        # Checks for runtime exceptions encountered in the child processes
        if flower_control_process.exception_occurred() :
            root_logger.critical('exception occurred!')
            break

        if webcam_process.exception_occurred() :
            root_logger.critical('exception occurred!')
            break

    root_logger.info('terminating GUI')
    gui.stop()
    flower_control_process.exit_event.set()
    webcam_process.exit_event.set()
    comment_file = trial_path  + "/comments.txt"

    webcam_process.join()
    flower_control_process.join()

    write_comment(comment_file)
