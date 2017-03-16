import multiprocessing
import time

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
    except KeyboardInterrupt :
        exit_event.set()
        webcam_process.join()
        flower_control_process.join()