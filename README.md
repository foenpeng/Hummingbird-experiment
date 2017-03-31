# Hummingbird-experiment
This is the code for outdoor hummingbird experiments with 3D printed flowers. There are three processes, the main process and two child processes: webcam detection of presence or absence of the animal, and the data collection process which collect analog signal from the accelerometer and infrared emitter-detector.

## Main process
User needs to specify the serial ports used to communicate between the computer and the two Arduino boards ("COM3" and "COM6" was default setting). Then user needs to specify the flowr morphology under testing. After the program starts, you can enter anything on the keyboard to exit the program. And at the end of the program, it will prompt to ask for some parameters, like the temperature, humidity, etc.
The usage of the program is `python Hummingbird-experiment.py`

## Video detection
The video detection process will read input from a webcam at a frame rate of 10 fps. The reference image will be obtained when initiating this process. Every new frame will be used to compare with the reference image to infer whether animal is present or not. Once it detect the presence of animal, it will then start compare each subsequent frame to make sure that the signal is not false positive. If continuous false postive signal is generated, it will recalculate the reference image. The video file will be written in avi format and the information of presence/absence of animal along time will also be written into a csv file.

## flower controller
This child process does a lot of things: making a new directory for the new experiment trial, writing the analog input from serial port into disc, analyzing and comparing the nectar level information and making the decision of whether to refill the nectar. 





