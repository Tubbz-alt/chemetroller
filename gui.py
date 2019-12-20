# -*- coding: utf-8 -*-
"""
Created on Tue Aug 27 08:35:27 2019

@author: Isaiah Lemmon isaiah.lemmon@pnnl.gov

This module contains classes used to set up the gui. Many things are hardcoded
here, but they are well documented. Take care when attempting to reorganize the
gui's layout

App:
    The main application that will be created
    
PlottingTab:
    A tab to display a classes.Plotter's plot
    
PumpTab:
    A tab to control pumps through a pump.Pump_Serial connection
    
PIDTab
    A tab to control a PID loop
    
MarkTab
    A tab that allows the marking of a datetime to compute elapsed time from
    for the plots
"""

import matplotlib
import asyncio
from functools import partial
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from pump import Pump_Serial
import numpy as np
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import serial.tools.list_ports as list_ports
global COM_PORT
COM_PORT = 'COM4'


class App(tk.Tk):
    '''
    Root of the gui. Inherits from tkinter.Tk (standard root) to do so
    
    Parameters
    ----------
        plotter_dict : dict{string : classes.Plotter()}
            The key is a string of what a plotting tab should be named, and the value
            is a the Plotter object tied to that tab.
            
        pid : classes.PIDHandler
            The PIDHandler. Used to update parameters in the PID Control tab.
            
        *args, **kwargs
            Passed to tk.TK()
            
    Attributes
    ----------
        plotter_dict : dict{string : classes.Plotter()}
            Reference to plotter_dict parameter
            
        pages : dict{string : tk.Frame subclass}
            A dictionary of pages (tabs) that are within the notebook. Pages are anything
            that can be added to a notebook
    '''
    def __init__(self, plotter_dict, pid, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        
        # Create notebook as the top level display
        notebook = ttk.Notebook(self)
        notebook.pack(side="top", fill="both", expand=True) # Fill whole window
        notebook.grid_rowconfigure(0, weight=1) # Config tab sizes
        notebook.grid_columnconfigure(0, weight=1)
        
        self.plotter_dict = plotter_dict
        self.pages = {}
        
        # Create a plotting page for each item in plotter_dict
        for key, value in plotter_dict.items():
            self.pages[key] = PlottingTab(notebook, value)
            notebook.add(self.pages[key], text=key)
            
        # Create Pump tab
        self.pages["Pump"] = PumpTab(notebook)
        notebook.add(self.pages["Pump"], text="Pump")
        
        # Create PID Control tab
        self.pages["PID Control"] = PIDTab(notebook, pid, self)
        notebook.add(self.pages["PID Control"], text="PID Control")
        
        # Create Mark Time tab
        self.pages["Mark Time"] = MarkTab(notebook, self)
        notebook.add(self.pages["Mark Time"], text="Mark Time")
        
        # Geometrically pack the notebook (make everything fit)
        notebook.pack(expand=1, fill="both")
        
    def set_mark(self, mark_time):
        '''
        Given a time, sets the start_time of each Plotter passed in plotter_dict to it.
        
        Parameters
        ----------
            mark_time : numpy.timedelta64[s]
        '''
        for key, value in self.plotter_dict.items():
            value.start_time = mark_time
            self.pages[key].elapsed_time_init()
            
    def update_plots(self):
        '''
        Updates the graphs of all plotters in plotter_dict
        '''
        for key in self.plotter_dict:
            self.pages[key].update_plot() 

class PlottingTab(tk.Frame):
    '''
    Given a classes.Plotter, displays the Plotter in tk.Frame
    
    Parameters
    ----------
        parent : tk.Frame subclass
            The parent of this frame, e.g., the notebook.
        
        plotter : classes.Plotter
            The plotter that will have it's figure displayed
    '''
    def __init__(self, parent, plotter):
        tk.Frame.__init__(self, parent)
        
        # Get the Figure
        self.plotter = plotter
        plotter_fig = self.plotter.fig
        
        # Create the figure, draw it, and pack
        self.canvas = FigureCanvasTkAgg(plotter_fig, self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        # Create the toolbar, update it, and pack
        toolbar = NavigationToolbar2Tk(self.canvas, self)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill = tk.BOTH, expand=True)
        
        # Create the button to switch to elapsed time, initially disabled
        self.elapsed_button = tk.Button(self, text='Switch to Elapsed Time',
                                        command=lambda: self.set_x_ax(),
                                        state=tk.DISABLED)
        self.elapsed_button.pack(side=tk.TOP, fill = tk.BOTH, expand=True)
        
    def update_plot(self):
        '''
        Redraw the plot with the current state of plotter's fig 
        '''
        self.canvas.draw()
        
    def elapsed_time_init(self):
        '''
        Enable elasped_button when called.
        '''
        self.elapsed_button.config(state=tk.NORMAL)
        
    def set_x_ax(self):
        '''
        Set the format of the x axis and change button next, alternating with on press
        '''
        if self.plotter.format_abs:
            self.elapsed_button.config(text='Switch to Absolute Time')
        else:
            self.elapsed_button.config(text='Switch to Elapsed Time')
            
        self.plotter.set_x_format(not self.plotter.format_abs)
        self.update_plot()
            
class LabelManager(object):
    '''
    A helper class to keep a reference to things stored with tk's grid geometry
    
    Parameters
    ----------
        size : list[int, int] or tuple(int, int)
            # of rows, # of columns to allocate for grid
            
    Attributes
    ----------
        grid_matrix : numpy.ndarray(dtype=object)
            A 2d matrix used to store reference to an object set at a location int k's grid
    '''
    def __init__(self, size):
        self.grid_matrix = np.zeros(size, dtype=object) # Allocate space
        
        
    def set_obj(self, obj, pos, rowspan=1, columnspan=1, padx=5, pady=5, grid=True):
        '''
        Given an object, store it at pos and optionally set it to the grid at pos
        
        Parameters
        ----------
            obj : object
                The object to be stored in grid_matrix
                
            pos : list[int, int] or tuple(int, int)
                The row, column to store the object at, and optionally grid it to. Zero indexed
                
            grid : boolean
                True if objected should be grided. If False, it's just stored.
                
            Others
                Passed to tk's grid
        '''
        self.grid_matrix[pos[0], pos[1]] = obj
        if grid:
            obj.grid(row=pos[0], column=pos[1], rowspan=rowspan, columnspan=columnspan,
                     padx=padx, pady=pady)
    
    def get_obj(self, pos):
        '''
        Return the object at this position
        '''
        return self.grid_matrix[pos[0], pos[1]]
        

class PumpTab(tk.Frame):
    '''
    Tab to control connecting to pumps and adjusting parameters of the pumps
    
    This tab invokes pump.Pump_Serial, displaying the pumps its connected to.
    It provides options for viewing information and status of connected pumps,
    as well as setting their required parameters such as vol/rev, speed, and direction.
    
    Many buttons and labels have their positions hardcoded in due to time constraints.
    If anything needs to be changed, pay careful attention to their positions on the grid
    
    Parameters
    ----------
        parent : tk.Frame subclass
            The parent of this frame, e.g., the notebook.
            
    Attributes
    ----------
        parent : tk.Frame subclass
            Reference to parent parameter
        
        grid : gui.LabelManager
            Used to store references to tk objects (buttons, labels) that are generated and gridded
            
        ports : dict{string : string}
            A dictionary of available COM ports. Human readable names are keys, while the actual
            port name are the values
        
        connection : pump.Pump_Serial()
            A Pump_Serial object used to communicate and track pumps. Initalized in init_pumps()
    '''
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        
        self.parent = parent
        self.connection = None
        self.grid = LabelManager((10,15))
        self.num_pumps = 0
        
        # Create button to connect to pumps at 0, 0. Calls init_pumps() on press
        self.grid.set_obj(tk.Button(self, text = 'Connect to Pumps', 
                                    command = lambda: self.init_pumps()),
                                    (0,0), columnspan=2)
        
        # Create button to disconnect pumps at 0, 2. Calls disconnect_pumps() on press
        self.grid.set_obj(tk.Button(self, text = 'Disconnect all Pumps',
                                    command = lambda: self.disconnect_pumps(),
                                    state=tk.DISABLED), (0,2), columnspan=2)
        
        # Get current COM ports
        self.ports = self.available_comports()
        # Variable connected to the COM port option menu
        self.grid.set_obj(tk.StringVar(self), (0, 5), grid=False)
        self.grid.get_obj((0, 5)).set(list(self.ports.keys())[0]) # Set to an available port
        
        # Create the option menu, connected to the variable. Has the keys of ports as options
        self.grid.set_obj(tk.OptionMenu(self, self.grid.get_obj((0, 5)), *self.ports.keys()), 
                          (0, 4), columnspan=2)
        
        # Create a button to update the COM port option menu
        self.grid.set_obj(tk.Button(self, text = 'Update Available Ports', 
                                    command = lambda: self.update_ports()), (0, 6))
        
        self.grid.set_obj(tk.Button(self, text = 'Create a Virtual Pump', 
                                    command = lambda: self.create_vpump(), state=tk.DISABLED), 
                         (0, 7))

    def available_comports(self):
        '''
        Get a dictionary of currently available COM ports.
        
        If no ports are avaiable, the dictionary will only have {'No Available Ports' : None}.
        Furthermore, the connection button will be disabled.
        
        Otherwise, the keys will be a human readable description of the port, while the
        values will be the exact name of the COM port. The connection button will be
        enabled
        
        Returns
        -------
            dict : {string : string}
                Keys are a human readable description of the port which is to be displayed.
                Values are the exact name of the port, e.g. COM4
        '''
        # Check ports with pyserial
        comports_info_list = list_ports.comports()
        if len(comports_info_list) == 0:
            # Disable connect button if no ports
            self.grid.get_obj((0, 0)).config(state=tk.DISABLED)
            return {'No Available Ports': None}
        else:
            # Enable connect button if there are ports
            self.grid.get_obj((0, 0)).config(state=tk.NORMAL)
            return {port[1] : port[0] for port in comports_info_list}
    
    def update_ports(self):
        '''
        Refreshes the list of avaiable COM ports in the menu
        
        Gets a new dict of ports from avaiable_comports(). Then checks to see if the
        COM port that is currently selected is still avaiable. If not, a new one is chosen
        to display.
        '''
        # Variable that is read when we want to read the value
        str_var = self.grid.get_obj((0, 5))
        menu = self.grid.get_obj((0, 4))["menu"]
        menu.delete(0, "end") # Delete all items in the menu
        
        self.ports = self.available_comports() # Update ports dictionary
        current_port = str_var.get()
        
        # If the current selected port is not available, set a new one
        if current_port not in self.ports:
            str_var.set(list(self.ports.keys())[0])
        
        # Add the updated ports back to the menu and connect to str_var
        for port in self.ports.keys():
            menu.add_command(label=port, command=tk._setit(str_var, port))
                             
        
    def init_pumps(self):
        '''
        Connect to pumps and initalize the labels/information
        
        Tries to connect to the pumps. Raises a message box if pump.Pump_Serial can't
        access the specified COM port, or if it finds no pumps at that port.
        
        If connection is successful, the connect/disconnect buttons switch states,
        the header labels are generated, and information about each pump is gotten.
        The tools to select a COM port are also frozen until the pump is disconnected
        '''
        # Try connecting
        selected_port_key = self.grid.get_obj((0, 5)).get()
        port_value = self.ports[selected_port_key]
        
        try:
            self.connection = Pump_Serial(port_value)
            self.grid.get_obj((0, 0)).config(state=tk.DISABLED)
            self.grid.get_obj((0, 2)).config(state=tk.NORMAL)
            
            
            
            # Create header labels
            labels = ['Pump ID', 'Vol (mL/rev)', 'Total Volume\nDispensed (mL)', 'RPM',
                      'Direction', 'Connection', 'Status', 'Errors', 'Vol (mL/rev)', 
                      'RPM', 'Direction']
            for i, text in enumerate(labels):
                tk.Label(self, text=text).grid(row=1, column=i)  
            
            # Get new information about pumps
            self.update_pump_labels()
            
            # Disable COM PORT selection
            self.grid.get_obj((0, 4)).config(state=tk.DISABLED)
            self.grid.get_obj((0, 6)).config(state=tk.DISABLED)
            
            self.num_pumps = len(self.connection.pump_dict)
            
            if self.num_pumps > 1:
                # Add option for virtual pump
                self.grid.get_obj((0,7)).config(state=tk.NORMAL)
            
            
        # Catch these exceptions and raise in messagebox
        except (RuntimeError, PermissionError) as e:
            tk.messagebox.showinfo("Python", e)
            
        
    def update_pump_labels(self):
        '''
        Create/update the information and parameter labels for each pump in connection
        
        Checks to see if a pump has had it's labels made or not by checking the first
        column of its row. Creates the labels if needed, otherwise just updates them.
        If new labels were created everytime this update was called, there would soon
        be hundreds stacked ontop of each other, significantly slowing tkinter down.
        Instead, the labels are created once and a reference to them is kept. The text they're
        displaying can be then be edited directly. This is the purpose of LabelManager
        '''
        # Call only if there is a connection
        if self.connection != None:
            
            # Loop through each Pump, starting on row index 2
            # Check status of only real pumps
            real_pumps = [(pump_id, pump) for pump_id, pump in self.connection.pump_dict.items() if "VP" not in str(pump_id)]
            
            for i, (ID, pump) in enumerate(real_pumps, 2):
                # Get info about this pump
                status = self.connection.full_info(ID)
                    
                # Used to determine if the labels/textboxes need to be created, or just changed
                if self.grid.get_obj((i, 0)) == 0:
                    
                    # Create each label and set its text
                    for j, info in enumerate((ID,) + status):
                        self.grid.set_obj(tk.Label(self, text=info), (i, j))
                    
                    # Text boxes to read
                    self.grid.set_obj(tk.Text(self, height=1, width=5), (i, j+1)) # Vol / Rev
                    self.grid.set_obj(tk.Text(self, height=1, width=5), (i, j+2)) # RPM
                    
                    # Create dropdown for RPM
                    # The StringVar used to read from the OptionMenu, so it is stored
                    # but not gridded. The OptionMenu doesn't have to be referenced again,
                    # so it is not stored and gridded manually
                    self.grid.set_obj(tk.StringVar(self), (i, j+3), grid=False)
                    self.grid.get_obj((i, j+3)).set('CW')
                    tk.OptionMenu(self, self.grid.get_obj((i, j+3)), 'CW', 'CCW').grid(row=i, 
                                 column=j+3, padx=5, pady=5)
                    
                    # Set update button. Calls set_pump_values and passes starting location of 
                    # the new parameters and the pump ID
                    # Since the args to the commands are changing everytime we loop, we
                    # need to use partial() instead of a lambda
                    self.grid.set_obj(tk.Button(self, text = 'Update', 
                                           command=partial(self.set_pump_values, i, j+1, pump.ID)),
                                           (i, j+4))
                    
                    self.grid.set_obj(tk.Button(self, text = 'Calibrate', 
                                           command=partial(self.calibrate, pump.ID)),
                                           (i, j+5)) 
                
                # If labels are already created for this pump, just update them
                else:
                    for j, info in enumerate((ID,) + status):
                        self.grid.get_obj((i, j)).config(text=info)
                    
            # Reschedule to update again after 2000ms       
            self.parent.after(2000, self.update_pump_labels)
            
    def calibrate(self, pump_num):
        response = tk.messagebox.askyesno('Warning',
                                           'You are about to dispense 5 revolutions of volume. Track how much \
                                           volume was dispensed and divide by 5 to calibrate the vol/rev parameter. \
                                           Are you ready?',
                                           icon = 'warning')
        if response:
            try:
                self.connection.assign_rev(pump_num, 5)
            except (AttributeError, ValueError) as e:
                tk.messagebox.showinfo("Python", e)

            
    def set_pump_values(self, row, start_col, pump_num):
        '''
        Read the parameter inputs and update the pump accordingly
        
        Parameters
        ----------
            row : int
                The index of the row the pump is assigned to
            
            start_col : int
                The index of the column where the vol / rev box resides
                
            pump_num : int
                The ID of the pump to update to in connection
        '''
        vol_per_rev = self.grid.get_obj((row, start_col)).get('1.0', tk.END)
        rpm = self.grid.get_obj((row, start_col+1)).get('1.0', tk.END)
        direction = self.grid.get_obj((row, start_col+2)).get()
        
        # Try assigning the read values
        try:
            self.connection.set_vol_per_rev(pump_num, vol_per_rev)
            self.connection.assign_speed(pump_num, direction, rpm)
            
        # Catch if a bad type is entered, e.g. a string in the RPM box, and raise a 
        # message box
        except ValueError as e:
            tk.messagebox.showinfo("Python", e)
            
    def create_vpump(self):
        
        
        row = 2 + self.num_pumps
        
        vpump_id = f"VP{self.num_pumps+1}"
        
        self.grid.set_obj(tk.Label(self, text=vpump_id), (row, 0))
        
        available_pumps = list(self.connection.pump_dict.keys())
        
        # Create selection for first pump
        self.grid.set_obj(tk.StringVar(self), (row, 2), grid=False)
        self.grid.get_obj((row, 2)).set(available_pumps[0])
        
        self.grid.set_obj(tk.OptionMenu(self, self.grid.get_obj((row, 2)),
                                        *available_pumps), 
                          (row, 1), columnspan=2)
        
        # Create selection for second pump
        self.grid.set_obj(tk.StringVar(self), (row, 4), grid=False)
        self.grid.get_obj((row, 4)).set(available_pumps[1])
        
        self.grid.set_obj(tk.OptionMenu(self, self.grid.get_obj((row, 4)),
                                        *available_pumps), 
                          (row, 3), columnspan=2)
        
        self.grid.set_obj(tk.Label(self, text="Ratio: N/A"), (row, 5))
        
        self.grid.set_obj(tk.Button(self, text = 'Update', 
                                    command=partial(self.set_vpump_values, row, vpump_id)),
                         (row, 6))
            
        self.grid.set_obj(tk.Scale(self, from_=0, to=100, orient=tk.HORIZONTAL), 
                          (row, 7), columnspan=2)

        self.num_pumps += 1
        
    def set_vpump_values(self, row, vpump_id):
        
        # Get pumps and ratio; turn from strings into numbers
        pump_num_1 = int(self.grid.get_obj((row, 2)).get())
        pump_num_2 = int(self.grid.get_obj((row, 4)).get())
        ratio = int(self.grid.get_obj((row, 7)).get())
        
        self.grid.get_obj((row, 5)).config(text=f"Ratio (Pump 1:Pump 2): {ratio}")
        
        ratio /= 100
        
        # Check if this virtual pump hasn't been created yet
        if vpump_id not in self.connection.pump_dict.keys():
            self.connection.add_vpump(pump_num_1, pump_num_2, ratio)
        
        else:
            self.connection.set_vpump(vpump_id, pump_num_1, pump_num_2, ratio)
            
        
    
    def disconnect_pumps(self):
        '''
        Switch the connect/disconnect buttton states and call connection.close()
        
        Also restores function to the COM port selection
        '''
        self.grid.get_obj((0, 0)).config(state=tk.NORMAL)
        self.grid.get_obj((0, 2)).config(state=tk.DISABLED)
        self.grid.get_obj((0, 4)).config(state=tk.NORMAL)
        self.grid.get_obj((0, 6)).config(state=tk.NORMAL)
        self.grid.get_obj((0, 7)).config(state=tk.DISABLED)
        
        self.connection.close()
        
        
    async def dispense_vol(self, pump_num, vol):
        '''
        Dispense a volume to a pump. Helper method to catch bad inputs
        
        Parameters
        ----------
            pump_num : int
                The pump to dispense from
                
            vol : float
                The volume to dispense. See pump.Pump_Serial for units
        '''
        try:
           await self.connection.dispense_vol(pump_num, vol)
        
        # Catch if there is no connection, vol/rev not assigned, or if 
        # pump_num / volume is invalid
        except (AttributeError, ValueError) as e:
            tk.messagebox.showinfo("Python", e)
            
    def get_pump_ids(self):
        if self.connection is not None:
            return self.connection.pump_dict.keys()
        else:
            return None
        
    def get_ratio(self, pump_id):
        if self.connection is not None:
            return self.connection.get_ratio(pump_id)
        else:
            return None
            
    
class PIDTab(tk.Frame):
    '''
    Tab to control PID parameters and state
    
    Allows ccontrol over a classes.PIDHandler by adjusting parameters such as
    the coeffs, max volume, tracking, etc.
    
    Many buttons and labels have their positions hardcoded in due to time constraints.
    If anything needs to be changed, pay careful attention to their positions on the grid
    
    Parameters
    ----------
        parent : tk.Frame subclass
            The parent of this frame, e.g., the notebook.
        
        pid_handler : classes.PIDHandler
            The PIDHandler that this tab will be controlling
            
    Attributes
    ----------
        parent : tk.Frame subclass
            Reference to parent parameter
            
        pid_handler : classes.PIDHandler
            Refernce to pid_handler parameter
        
        grid : gui.LabelManager
            Used to store references to tk objects (buttons, labels) that are generated and gridded
            
        tracking_labels_int : boolean
            True if the labels the PID is tracking have been initalized. False otherwise.
            Used to know if a dropdown of label names or indicies should be displayed
    '''
    
    def __init__(self, parent, pid_handler, app):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.pid_handler = pid_handler
        self.app = app
        self.grid = LabelManager((4,15))
        self.tracking_labels_init = False

        
        # Enable and Disable buttons, similar to PumpTab
        self.grid.set_obj(tk.Button(self, text = 'Enable PID', 
                                    command = lambda: self.enable_pid()),
                                    (0,0), columnspan=2)
                                    
        
        self.grid.set_obj(tk.Button(self, text = 'Disable PID',
                                    command = lambda: self.disable_pid(),
                                    state=tk.DISABLED), (0,2), columnspan=2)
        
        # Create Headers
        labels = ['Pump', 'Status', 'Tracking\n(Index)', 'Set Point', 'Prop.', 'Int', 'Deriv', 
                  'Lower Limit\n(mL)', 'Upper Limit\n(mL)', 'Max Cumulative\nVol (mL)',
                  'Proportional\non Measurement']
        for col, text in enumerate(labels):
            self.grid.set_obj(tk.Label(self, text=text), (1, col))
            
        # Create prop-on-meas button
        self.grid.set_obj(tk.Button(self, text='Disable Proportional\non Measurement',
                                    command=lambda: self.proportional_on()),
                          (0, col), columnspan=2)
            
        self.update_labels()
        
        
    
    def update_labels(self):
        '''
        Create/Update the PID labels
        
        If there is no object stored in grid at 2, 0, then it is assumed labels
        and input boxes need to be initalized. See the function in PumpTab for details.
        
        Also deals with the pred_handler of the pid_handler not having its labels initialized.
        If they are not avaiable, then the indexes 0, 1, 2 are listed in the dropdown 
        to be selected for tracking. Once the labels are initialzed, the dropdown changes
        to the specific labels, so the index isn't dealt with by the user.
        '''
        # If labels have not been made 
        if self.grid.get_obj((2,1)) == 0:
            # Get the status from pid_handler and create labels
            for col, info in enumerate(self.pid_handler.get_status(), 1):
                self.grid.set_obj(tk.Label(self, text=info), (2, col))
                
            # Create variable for tracking drop down
            self.grid.set_obj(tk.StringVar(self), (3, 2), grid=False)
            self.grid.get_obj((3, 2)).set(self.pid_handler.get_tracking()) # Assign to current
            
            # Create tracking drop down - won't need to be updated more than once
            tk.OptionMenu(self, self.grid.get_obj((3, 2)), *[0, 1, 2]).grid(row=3,
                          column=2, padx=5, pady=5)
            
            # Create variable for pump drop down
            self.grid.set_obj(tk.StringVar(self), (3, 0), grid=False)
            self.grid.get_obj((3, 0)).set('') # Assign to nothing
            
            # Set pump label
            self.grid.set_obj(tk.Label(self, text=self.grid.get_obj((3, 0)).get()), (2, 0))
            
            # Create pump drop down. Will need to be updated
            self.pump_menu = tk.OptionMenu(self, self.grid.get_obj((3, 0)), *[''])
            self.pump_menu.grid(row=3, column=0, padx=5, pady=5)
                
            # Make 7 textboxes
            text_boxes = [tk.Text(self, height=1, width=6) for i in range(7)]
            # Store and assign their positions
            for col, text in enumerate(text_boxes, 3):
                self.grid.set_obj(text, (3, col))
            
            # Create button to update
            self.grid.set_obj(tk.Button(self, text = 'Update', command = lambda: self.update_pid()),
                              (3, col+1)) 
        
        else:
            #update pump label
            self.grid.get_obj((2, 0)).config(text=self.grid.get_obj((3, 0)).get())
            
            # Update labels with pid_handler's get status
            for i, info in enumerate(self.pid_handler.get_status(), 1):
                self.grid.get_obj((2, i)).config(text=info)
                
            # Update pump drop down
            if self.app.pages["Pump"].get_pump_ids() is not None:
                pump_ids = self.app.pages["Pump"].get_pump_ids()
                menu = self.pump_menu['menu']
                var = self.grid.get_obj((3,0))
                
                menu.delete(0, 'end')
                for name in pump_ids:
                    menu.add_command(label=name, command=lambda name=name: var.set(name))
            
            # If the labels are not initialized yet
            if not self.tracking_labels_init:
                # Try to set them, see if they have been initialized
                try:
                    tk.OptionMenu(self, self.grid.get_obj((3, 2)), 
                                  *self.pid_handler.pred_handler.labels).grid(row=3, 
                                 column=2, padx=5, pady=5)
                    self.grid.get_obj((3, 2)).set(self.pid_handler.get_tracking())
                    self.grid.get_obj((1, 2)).config(text='Tracking\n(Label)')
                    
                    self.tracking_labels_init = True
                    
                # If still not initialized, pass.
                except TypeError:
                    pass
            
        # Reschedule update_labels to be called in 2000ms
        self.parent.after(2000, self.update_labels)
        
    
    def proportional_on(self):
        '''
        Alternate prop. on measurement state and button state on call
        '''
        button = self.grid.get_obj((0,10))
        prop = self.pid_handler.pid.proportional_on_measurement
        if prop:
            button.config(text='Enable Proportional\non Measurement')
        else:
            button.config(text='Disable Proportional\non Measurement')
        self.pid_handler.pid.proportional_on_measurement = not prop

        
    def update_pid(self):
        '''
        Try to update pid with values entered in the text boxes. Raise a messagebox if incompatible
        
        Hardcoded positions of each text box, please be careful if you plan on adjusting
        the layout
        '''
        track = self.grid.get_obj((3, 2)).get()
        try:
            setpoint = float(self.grid.get_obj((3, 3)).get('1.0', tk.END))
            coeffs = tuple([float(self.grid.get_obj((3, i)).get('1.0', tk.END)) for i in range(4, 7)])
            limits = tuple([float(self.grid.get_obj((3, i)).get('1.0', tk.END)) for i in range(7, 9)])
            max_vol = float(self.grid.get_obj((3, 9)).get('1.0', tk.END))
            self.pid_handler.update_all(track, setpoint, coeffs, limits, max_vol)
        except ValueError as e:
            tk.messagebox.showinfo("Python", e)
        
        
        
    def enable_pid(self):
        '''
        Enable the PID loop, allowing values to be output and alternate button states
        '''
        pump = self.grid.get_obj((3, 0)).get() #Current pump
        
        if pump == '':
            tk.messagebox.showinfo("Python", "Pump not assigned")
        
        else:
            self.grid.get_obj((0, 0)).config(state=tk.DISABLED)
            self.grid.get_obj((0, 2)).config(state=tk.NORMAL)
            self.pid_handler.pid.set_auto_mode(True)
        
    def disable_pid(self):
        '''
        Disable the PID loop, stopping values from being output and alternate button states.
        '''
        self.grid.get_obj((0, 0)).config(state=tk.NORMAL)
        self.grid.get_obj((0, 2)).config(state=tk.DISABLED)
        self.pid_handler.pid.set_auto_mode(False)
        
    def get_selected_pump(self):
        pump = self.grid.get_obj((3, 0)).get() #Current pump
        
        try:
            pump_id = int(pump)
        except ValueError: # Handle if virtual pump
            pump_id = pump
        
        return pump_id
        
class MarkTab(tk.Frame):
    '''
    Simple tab to mark a start time of the experiment so that elapsed time can be calculated.
    
    Once time is marked, it is your responsibility to take all necessary measures if you
    decide to reset and mark a different time. There is currently no feature to log such
    an event.
    
    When the mark_time button is pressed, the datetime at that instance is recorded
    and is passed to the plotter's where it is set to be their start_time
    
    Parameters
    ----------
        parent : tk.Frame subclass
            The parent of this frame, e.g., the notebook.
        
        app : tk.Tk subclass
            The overall root, used to call set_mark to reference the plotting tabs
            
    Attributes
    ----------
        parent : tk.Frame subclass
            Reference to the parent parameter
            
        app : tk.Tk subclass
            Reference to the app parameter
            
        mark_button : tk.Button
            Button used to set the mark time
            
        reset_button : tk.Button
            Button used to reset the marked time
            
        time_label : tk.Label
            Label displaying the marked time once set
    '''
    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.app = app
        
        # Button to set mark
        self.mark_button = tk.Button(self, text='Mark Start Time', command=lambda: self.set_mark())
        # Pack is used to let tk figure out how to arange things
        self.mark_button.pack(side=tk.TOP, fill = tk.BOTH, expand=False)
        
        # Button to reset mark. Disabled initially
        self.reset_button = tk.Button(self, text='Reset', command=lambda: self.reset(),
                                      state=tk.DISABLED)
        self.reset_button.pack(side=tk.TOP, fill = tk.BOTH, expand=False)
        
        # Label to display marked time. Initially empty
        self.time_label = tk.Label(self, text='')
        self.time_label.pack(side=tk.TOP, fill = tk.BOTH, expand=True)
        
        
    def set_mark(self):
        '''
        Marks the time of the call. Disables mark_button and enabled reset_button.
        
        On press
        '''
        # Using datetime because it reads local time zone
        current_time = datetime.now()
        
        # timedelta64[s] is the format required by the plotters
        # Convert from datetime -> numpy's datetime -> numpy's timedelta
        time_stamp = np.datetime64(current_time, 's').astype('timedelta64[s]')
        
        # Show marked time. Change format displayed here in strftime
        self.time_label.config(text='Start Time: ' + \
                                   current_time.strftime('%Y-%m-%d %H:%M:%S %Z'))
        
        # Disable buttons 
        self.mark_button.config(state=tk.DISABLED)
        self.reset_button.config(state=tk.NORMAL)
        
        # Pass the timedelta64[s] values to the app to be assigned
        self.app.set_mark(time_stamp)
        
    def reset(self):
        '''
        Resets the marked time. Doesn't immediately change it, but enables the mark_button,
        which will set a new time when pressed.
        
        Prompts a warning. Nothing is done to log the resetting of a marked time. If it
        changes in the middle of an experiment, all elapsed time values will suddenly be
        off. Understand that you have responsibility of noting this
        '''
        # Prompt if user is sure
        response = tk.messagebox.askyesno('Warning',
                                           'Are you sure you want to reset the start time?\n' \
                                           'If so, it is your responsibility to modify the PID log.',
                                           icon = 'warning')
        
        # If they're sure, enable the mark_button
        if response:
             self.mark_button.config(state=tk.NORMAL)
             self.reset_button.config(state=tk.DISABLED)
             self.time_label.config(text='')
             

                