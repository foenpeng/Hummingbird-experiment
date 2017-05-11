from tkinter.simpledialog import askstring
import tkinter as tk

DEFAULT_INJECTOR_PORT = "COM4"
DEFAULT_FLOWER_PORT = "COM7"
class Gui ( ) :
    """

    """
    def __init__ ( self ) :

        self.root = tk.Tk()
        self.root.title('Hummingbird Experiment GUI')

        self.microinjector_port_label = tk.Label( self.root, text = 'Microinjector Port' )
        self.microinjector_port_label.grid( column = 1, row = 1)

        self.microinjector_port_field = tk.Text ( self.root, height = 1, padx = 5, pady = 10, width = 10 )
        self.microinjector_port_field.grid( column = 2, row = 1 )

        self.flower_port_label = tk.Label( self.root, text = 'Flower Controller Port' )
        self.flower_port_label.grid( column = 1, row = 2 )

        self.flower_port_field = tk.Text( self.root, height = 1, padx = 5, pady = 10, width = 10 )
        self.flower_port_field.grid( column = 2, row = 2 )

        self.stop_event = False
        self.start_event = False

        self.start_button = tk.Button( self.root, text = 'Start', command = self.start_experiment )
        self.start_button.grid( column = 1, row = 3 )


    def update( self ) :
        self.root.update_idletasks()
        self.root.update()

    def start_experiment ( self ) :

        if self.start_button['text'] == "Start" :
            self.start_event = True

            microinjector_port = self.microinjector_port_field.get('0.0', 'end')

            if microinjector_port == '\n' :
                self.microinjector_port_field.insert('0.0', DEFAULT_INJECTOR_PORT)

            flower_port = self.flower_port_field.get('0.0', 'end')

            if flower_port == '\n' :
                self.flower_port_field.insert('0.0', DEFAULT_FLOWER_PORT)

            self.start_button['text'] = "Stop"


        elif self.start_button['text'] == "Stop" :
            print("stop button clicked")
            self.stop_event = True

    def stop ( self ) :
        self.root.destroy()

    def get_flower_port ( self ) :
        return self.flower_port_field.get('0.0', 'end').rstrip('\n')

    def get_microinjector_port ( self ) :
        return self.microinjector_port_field.get('0.0', 'end').rstrip('\n')

# Module unit tests
if __name__ == "__main__" :
    gui = Gui()

    try :
        while not gui.stop_event :
            gui.update()

    except KeyboardInterrupt :
        gui.stop()

    finally :
        print ( bytearray(gui.get_flower_port(), 'ASCII') )
        print ( bytearray(gui.get_microinjector_port(), 'ASCII') )
        pass
