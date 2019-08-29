# -*- coding: utf-8 -*-
"""
Created on Tue Aug 27 08:35:27 2019

@author: Raman
"""

from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib
import tkinter as tk
from tkinter import ttk
import classes
from pump import Pump_Serial
import numpy as np
matplotlib.use("TkAgg")
#from test import tester
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from serial import SerialException

from simple_pid import PID

import asyncio
from watchgod import awatch


class App(tk.Tk):
    def __init__(self, plotter_dict, pid, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        
        notebook = ttk.Notebook(self)
        notebook.pack(side="top", fill="both", expand=True)
        notebook.grid_rowconfigure(0, weight=1)
        notebook.grid_columnconfigure(0, weight=1)
        
        
        self.pages = {}
        for key, value in plotter_dict.items():
            self.pages[key] = Plotting_Tab(notebook, value)
            notebook.add(self.pages[key], text=key)
            
        self.pages["Pump"] = Pump_Tab(notebook)
        notebook.add(self.pages["Pump"], text="Pump")
        
        self.pages["PID Control"] = PID_Tab(notebook, pid)
        notebook.add(self.pages["PID Control"], text="PID Control")
        notebook.pack(expand=1, fill="both")
        

class Plotting_Tab(tk.Frame):
    
    def __init__(self, parent, plotter):
        tk.Frame.__init__(self, parent)

        plotter_fig = plotter.fig
        
        self.canvas = FigureCanvasTkAgg(plotter_fig, self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        toolbar = NavigationToolbar2Tk(self.canvas, self)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill = tk.BOTH, expand=True)
        
        self.labels = []
        
    def update_plot(self):
        self.canvas.draw()
        
class Pump_Tab(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        
        self.parent = parent
        
        self.grid = Label_Manager((10,15))
        
        self.grid.set_obj(tk.Button(self, text = 'Connect to Pumps', 
                                    command = lambda: self.init_pumps()),
                                    (0,0), columnspan=2)
        
        self.grid.set_obj(tk.Button(self, text = 'Disconnect all Pumps',
                                    command = lambda: self.disconnect_pumps(),
                                    state=tk.DISABLED), (0,2), columnspan=2)
                
        self.grid_matrix = np.zeros((10,10), dtype=object)
        self.volume_buttons = {}
        
        self.init_pumps()
        
        
    def init_pumps(self):
        try:
            self.connection = Pump_Serial('COM4')
            self.grid.get_obj((0, 0)).config(state=tk.DISABLED)
            self.grid.get_obj((0, 2)).config(state=tk.NORMAL)
            
            labels = ['Pump ID', 'Vol (mL)\n/rev', 'Total Volume\nDispensed (mL)', 'RPM',
                      'Direction', 'Connection', 'Status', 'Errors', 'Vol (mL)/rev', 
                      'RPM', 'Direction']
            for i, text in enumerate(labels):
                tk.Label(self, text=text).grid(row=1, column=i)
            
            
            self.update_pump_labels()
            
            
        except RuntimeError as e:
            tk.messagebox.showinfo("Python", e)
            
        
    def update_pump_labels(self):
        
        if self.connection != None:
            
            for i, (ID, pump) in enumerate(self.connection.pump_dict.items(), 2):
                
                status = self.connection.full_info(ID)
                    
                if self.grid.get_obj((i, 0)) == 0:
                    
                    for j, info in enumerate((ID,) + status):
                        self.grid.set_obj(tk.Label(self, text=info), (i, j))
                    
                    self.grid.set_obj(tk.Text(self, height=1, width=5), (i, j+1))
                    self.grid.set_obj(tk.Text(self, height=1, width=5), (i, j+2))
                    
                    self.grid.set_obj(tk.StringVar(self), (i, j+3), grid=False)
                    self.grid.get_obj((i, j+3)).set('CW')
                    tk.OptionMenu(self, self.grid.get_obj((i, j+3)), 'CW', 'CCW').grid(row=i, 
                                 column=j+3, padx=5, pady=5)
                    
                    self.grid.set_obj(tk.Button(self, text = 'Update', 
                                           command=lambda: self.set_pump_values(i, j+1, pump.ID)),
                                           (i, j+4)) 
            
                else:
                    for j, info in enumerate((ID,) + status):
                        self.grid.get_obj((i, j)).config(text=info)
                    
                    
            self.parent.after(2000, self.update_pump_labels)
            
    def set_pump_values(self, row, start_col, pump_num):
        
        vol_per_rev = self.grid.get_obj((row, start_col)).get('1.0', tk.END)
        rpm = self.grid.get_obj((row, start_col+1)).get('1.0', tk.END)
        direction = self.grid.get_obj((row, start_col+2)).get()
        
        try:
            self.connection.set_vol_per_rev(pump_num, vol_per_rev)
            self.connection.assign_speed(pump_num, direction, rpm)
        except ValueError as e:
            tk.messagebox.showinfo("Python", e)
        
    def set_vol_per_rev(self, row, col, pump_num):
        value = self.grid.get_obj((row, col)).get('1.0', tk.END)
#        self.grid.get_obj((row, col)).delete('1.0', tk.END)
        try:
            self.connection.set_vol_per_rev(pump_num, value)
        except ValueError as e:
            tk.messagebox.showinfo("Python", e)
    
    def disconnect_pumps(self):
        self.grid.get_obj((0, 0)).config(state=tk.NORMAL)
        self.grid.get_obj((0, 2)).config(state=tk.DISABLED)
        
        self.connection.close()
        
    def dispense_vol(self, pump_num, vol):
        try:
            self.connection.dispense_vol(pump_num, vol)
        except (AttributeError, ValueError) as e:
            tk.messagebox.showinfo("Python", e)
            
class Label_Manager(object):
    
    def __init__(self, size):
        self.grid_matrix = np.zeros(size, dtype=object)
        
        
    def set_obj(self, obj, pos, rowspan=1, columnspan=1, padx=5, pady=5, grid=True):
        self.grid_matrix[pos[0], pos[1]] = obj
        if grid:
            obj.grid(row=pos[0], column=pos[1], rowspan=rowspan, columnspan=columnspan,
                     padx=padx, pady=pady)
    
    def get_obj(self, pos):
        return self.grid_matrix[pos[0], pos[1]]
    
class PID_Tab(tk.Frame):
    
    def __init__(self, parent, pid_handler):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.pid_handler = pid_handler
        self.grid = Label_Manager((3,10))
        
        self.grid.set_obj(tk.Button(self, text = 'Enable PID', 
                                    command = lambda: self.enable_pid(),
                                    state=tk.DISABLED), (0,0), columnspan=2)
                                    
        
        self.grid.set_obj(tk.Button(self, text = 'Disable PID',
                                    command = lambda: self.disable_pid()),
                                    (0,2), columnspan=2)
        
        labels = ['Status', 'Tracking', 'Prop.', 'Int', 'Deriv']
        for i, text in enumerate(labels):
            tk.Label(self, text=text).grid(row=1, column=i)
            
        try:
            self.update_labels()
        except TypeError as e:
            print(e)
            self.parent.after(2000, self.update_labels)
        
    
    def update_labels(self):
        try:
            if self.grid.get_obj((2,0)) == 0:
                for i, info in enumerate(self.pid_handler.get_status()):
                    self.grid.set_obj(tk.Label(self, text=info), (2, i))
                    
                
                
            else:
                for i, info in enumerate(self.pid_handler.get_status()):
                    self.grid.get_obj((2, i)).config(text=info)
                    
            self.parent.after(2000, self.update_labels)
        except TypeError as e:
            print(e)
            self.parent.after(2000, self.update_labels)
        
        
        
    def enable_pid(self):
        self.grid.get_obj((0, 0)).config(state=tk.DISABLED)
        self.grid.get_obj((0, 2)).config(state=tk.NORMAL)
        self.pid_handler.pid.set_auto_mode(True)
        
    def disable_pid(self):
        self.grid.get_obj((0, 0)).config(state=tk.NORMAL)
        self.grid.get_obj((0, 2)).config(state=tk.DISABLED)
        self.pid_handler.pid.set_auto_mode(False)
        
class PID_Handler(object):
    
    def __init__(self, pred_handler, plotter, tracking):
        self.vol = np.zeros(3000) # Stores predicted values. Initalized once num of cols is known
        self.pred_handler = pred_handler
        self.pid = PID(0.01, 0.5, 0, setpoint=60, output_limits=(0, 20),
          proportional_on_measurement = False)
        
        self.plotter = plotter
        self.plotter.init_plot(self.pred_handler.REF_TIME, ['Volume (mL)'])
        
        self.tracking = tracking
        
    def get_status(self):
        mode_dict = {True:'Enable', False:'Disabled'}
        return (mode_dict[self.pid.auto_mode], self.pred_handler.labels[self.tracking]) + \
                self.pid.tunings
        
    def expand_arrays(self):
        self.vol = np.append(self.vol, np.zeros(3000))
        
    async def trigger_PID(self):
        
        value = self.pred_handler.pred_values[self.pred_handler.num_event - 1, 
                                              self.tracking]
        
        if self.pred_handler.num_event >= self.vol.shape[0]:
            self.expand_arrays()
            
        vol = self.pid(value)
        self.vol[self.pred_handler.num_event] = vol
        
        await self.plotter.animate(self)
        
    def last(self):
        return self.vol[self.pred_handler.num_event - 1]
    
    def get_values(self):
        limit = self.pred_handler.num_event
        return (self.pred_handler.ref_dates[:limit], np.sum(self.vol[:limit]))
    
    def update_pid_setpoint(self, value):
        self.pid.setpoint = value
    
    def update_pid_lims(self, lower, upper):
        self.pid.output_limits = (lower, upper)
        
    def update_pid_tunings(self, Kp, Ki, Kd):
        self.pid.tunings = (Kp, Ki, Kd)
        
        




path = 'C:/Users/Raman/Desktop'
prediction_plotter = classes.Plotter()
prediction_handler = classes.PlotHandler(prediction_plotter)

pid_plotter = classes.Plotter()
pid_handler = PID_Handler(prediction_handler, pid_plotter, 0)

plot_dict = {'Raman Plot':prediction_plotter, 'PID Plot':pid_plotter}
app = App(plot_dict, pid_handler)

async def run_tk(root, interval=0.06):
    try:
        while True:
            root.update()
            
            await asyncio.sleep(interval)
    except tk.TclError as e:
        if "application has been destroyed" not in e.args[0]:
            raise
        else:
            loop.stop()


async def watcher1():
    async for changes in awatch(path, min_sleep = 1000):
#        await asyncio.sleep(0.1)
        print("Watcher 1")
        for event, p in changes:
            
            await prediction_handler.on_any_event(p)
            await pid_handler.trigger_PID()
            vol = pid_handler.last()
            
            app.pages["Pump"].dispense_vol(1, vol)
            for plot in plot_dict:
                app.pages[plot].update_plot()
            


loop = asyncio.get_event_loop()
loop.create_task(run_tk(app))
loop.create_task(watcher1())
loop.run_forever()

