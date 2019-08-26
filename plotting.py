# -*- coding: utf-8 -*-

import datetime
import time
from tkinter import Tk
from tkinter.filedialog import askdirectory
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np

#reftime = np.datetime64(datetime.datetime.today())

#dates = np.zeros((3000), dtype='datetime64[s]')
#data = np.zeros((3000, 3))
#i = 0

#fig = plt.figure() 
#ax = fig.add_subplot(111)

class PlotHandler(PatternMatchingEventHandler):
    
    def __init__(self, pattern='*InStepAutoSave*'):
        self.num_event = 0
        self.dates = np.zeros((3000), dtype='datetime64[s]')
        self.ref_dates = np.zeros(3000)
        
        self.reftime = np.datetime64(datetime.datetime.today())
        
        super().__init__(patterns=pattern, ignore_directories=True)
        
        self.fig = plt.figure() 
        self.ax = self.fig.add_subplot(111)
        
    def init_plot(self, labels):
        plt.ion()
        formatter = FuncFormatter(self.__x_format)
        self.ax.xaxis.set_major_formatter(formatter)
        plt.xticks(rotation = 35)
        plt.tight_layout()
        self.scatter = []
        
        for lab in labels:
            line, = self.ax.plot([], [], '-', label=lab, marker = 'd', mfc = 'white')
            self.scatter.append(line)
        
        plt.legend()
    
    def on_any_event(self, event):
        if self.num_event < 1:
            with open(event.src_path, 'r') as f:
                labels = f.readline().split(', ')
                self.data = np.zeros((3000, len(labels)))
            self.init_plot(labels)
            
        try:
            temp_data = self.read_last_line(event.src_path)
            self.dates[self.num_event] = np.datetime64(temp_data[0])
            self.ref_dates[self.num_event] = (self.dates[self.num_event] - self.reftime).astype('float')
            self.data[self.num_event,:] = temp_data[1]
    
            self.update_plot()
            self.num_event += 1
            
            if self.num_event >= self.data.shape[0]:
                self.data = np.append(self.data, np.zeros((3000, self.data.shape[1])), axis=0)
                self.dates = np.append(self.dates, np.zeros(3000, dtype='datetime64'))
                self.ref_dates = np.append(self.ref_dates, np.zeros(3000))
            
        except IndexError as e:
            print(e)
            
    def read_last_line(self, file_path):
        with open(file_path, 'r') as f:
            for line in f:
                pass
            line = line.split('\t')
        cur_date = datetime.datetime.strptime(line[1] + '-' + line[2], '%m/%d/%Y-%I:%M:%S %p')
        
        return (cur_date, np.array(line[3].split(', ')))
            
    def update_plot(self):
        for idx, sc in enumerate(self.scatter):
            #sc.set_offsets(np.c_[ref_dates[:i+1], data[:i+1, idx]])
            sc.set_xdata(self.ref_dates[:self.num_event+1])
            sc.set_ydata(self.data[:self.num_event+1, idx])
            
        self.ax.set_xlim(np.min(self.ref_dates[:self.num_event+1]), np.max(self.ref_dates[:self.num_event+1]))
        self.ax.set_ylim(np.min(self.data[:self.num_event+1,]), np.max(self.data[:self.num_event+1,]))
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        
        
    def draw_plot(self):
        self.fig.canvas.flush_events()
        plt.pause(0.01)
        
    def __x_format(self, x, pos):
        date_str = np.datetime_as_string(x.astype('timedelta64') + self.reftime, unit = 'm')
        return date_str.replace('T', ' ')
    
#def read_file(file_path):
#    with open(file_path, 'r') as f:
#        line = f.readline().split('\t')
#    cur_date = datetime.datetime.strptime(line[1] + '-' + line[2], '%m/%d/%Y-%I:%M:%S %p')
#    
#    return (cur_date, np.array(line[3].split(', ')))

#def x_format(x, pos):
#    date_str = np.datetime_as_string(x.astype('timedelta64') + reftime, unit = 'm')
#    return date_str.replace('T', ' ')
#formatter = FuncFormatter(x_format)

#def update_plot(dates, data):
#    ref_dates = (dates[:i+1] - reftime).astype('float')
#    for idx, sc in enumerate(scatter):
#        #sc.set_offsets(np.c_[ref_dates[:i+1], data[:i+1, idx]])
#        sc.set_xdata(ref_dates[:i+1])
#        sc.set_ydata(data[:i+1, idx])
#        
#    ax.set_xlim(np.min(ref_dates[:i+1]), np.max(ref_dates[:i+1]))
#    ax.set_ylim(np.min(data[:i+1,]), np.max(data[:i+1,]))
#    fig.canvas.draw()
    
#def prompt_labels():

def main():
    root = Tk()
    scan_path = askdirectory()
    root.withdraw()
    
#    plt.ion()
#    fig = plt.figure() 
#    ax = fig.add_subplot(111)
#    ax.xaxis.set_major_formatter(formatter)
#    plt.xticks(rotation = 35)
#    plt.tight_layout()
#    scatter = []
#    
#    colors = ['aqua', 'orange', 'red']
#    labels = ['Glucose', 'Xylose', 'Ilcatone']
#    for col, lab in zip(colors, labels):
#        line, = ax.plot([], [], '-', mec=col, color=col, label=lab, marker = 'D', mfc = 'white')
#        scatter.append(line)
#    
#    plt.legend()
#    plt.show()
    
    
#    for file in os.listdir('C:\\Users\\Raman\\Desktop\\Instep_out\\'):
#        try:
#            temp_data = read_file('C:\\Users\\Raman\\Desktop\\Instep_out\\' + file)
#            dates[i] = np.datetime64(temp_data[0])
#            data[i,:] = temp_data[1]
#            dates.append(i)
#        
#            update_plot(dates, data)
#            i += 1
#            fig.canvas.draw()
#            fig.canvas.flush_events()
#        except IndexError as e:
#            print(e)
#            print(file)
    
    event_handler = PlotHandler()
    observer = Observer()
    observer.schedule(event_handler, path=scan_path, recursive = False)
    observer.start()
    print('main loop')
    
    try:
        while True:
            time.sleep(1)
            if event_handler.num_event > 0:
                event_handler.draw_plot()
            plt.pause(0.01)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()   

if __name__ == '__main__':
    main()
    
#def on_created(self, event):
#        if self.num_event < 1:
#            
#        try:
#            temp_data = self.read_file(event.src_path)
#            self.dates[self.num_event] = np.datetime64(temp_data[0])
#            self.ref_dates[self.num_event] = (self.dates[self.num_event] - self.reftime).astype('float')
#            self.data[self.num_event,:] = temp_data[1]
#    
#            self.update_plot(self)
#            self.num_event += 1
#        except IndexError as e:
#            print(e)
#    
#def read_file(self, file_path):
#        with open(file_path, 'r') as f:
#            line = f.readline().split('\t')
#        cur_date = datetime.datetime.strptime(line[1] + '-' + line[2], '%m/%d/%Y-%I:%M:%S %p')