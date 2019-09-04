# -*- coding: utf-8 -*-
"""
Created on Thu Jul 25 12:50:36 2019

@author: Raman
"""
import datetime
import time
from pathlib import Path
from tkinter import Tk, messagebox
from tkinter.filedialog import askdirectory
import pandas as pd
import numpy as np
from watchdog.observers import Observer
from matplotlib.ticker import FuncFormatter
from matplotlib.figure import Figure
import asyncio
from simple_pid import PID
import warnings 
warnings.filterwarnings("ignore", category=UserWarning)

np.set_printoptions(threshold=np.inf)

class RawHandler(object):

    '''
    Handles detecting and processing raw spectra files into an InStep format.

    This object is passed to an Observer schedule from watchdog, which defines
    where the raw spectra files will be looked for. On creation of a file in
    that directory <par_dir>, it is procesed and written to <par_dir>/Output

    Parameters
    ----------
    None
    '''
    

    # Method called when a file is created
    async def on_created(self, event_path):

        '''
        Runs when the Observer passes a FileCreatedEvent. Attempts to process it as a raw spectra

        Attempts to process the created file three times before passing. This allows for
        multiple attempts when the file hasn't fully copied or isn't an actual spectra
        instead of throwing an exception.

        Parameters
        ----------
        event : watchdog.events.FileSystemEvent
            An watchdog Event object (automatically passed by the Observer)
        '''

        time.sleep(.5)      # Allow time for file to fully copy
        for i in range(3):  # Try reading it three times, catching any error
            try:
                self.process_file(event_path)
            except Exception as error:
                print(f'Error reading file... Trying again. {2-i} attempts remaining.')
                print(error)
                await asyncio.sleep(.1)
            else:
                break

    @staticmethod
    def process_file(path):
        '''
        Process a raw raman spectra file at path. Writes an InStep input .dat to ./Output/

        The InStep .dat file is written to a subdirectory, Output/, of the parent
        directory of the passed file. The filename is the same as passed, with
        '_proc' appended.

        It is assumed the data of the spectra file begins on line 24, and that
        Raman Shift and Dark Subtracted are in the 2nd and 4th columns respectively.

        Parameters
        ----------
        path : str
            A str of the full path to the raw spectra file

        Raises
        ------
        ValueError
            If the file read has any NaN values, ValueError is raised. This is most
            likely a result of the file not being fully copied before reading.
        '''
        input_file = Path(path)
        # Output file is a directory in placed in the dir of the input file
        output_file = input_file.parent / 'Output' / (input_file.name[:-4] +
                                                      '_proc.dat')

        # Read Raman - Skip first 23 metadata rows, no header
        # Takes Raman Shift and Dark Subtracted
        with input_file.open(mode='r') as file:
            data = pd.read_csv(file, sep='\t', usecols=[1, 3], skiprows=23,
                               error_bad_lines=False)

            # If pandas starts reading before the file is fully copied, will read
            # a NaN and stop reading. If any NaN's are present, an error is thrown
            # and the file is attempted to be read again in the try loop
            if not any(data.notna()):
                raise ValueError

     # Write Raman
        start = time.time()
        with output_file.open(mode='w') as file:
            # Dims
            file.write('#d, ' + str(data.shape[0]) + 'x1')
            file.write('\n')
            
            file.write('#c ')
            file.write(', '.join([str(i) for i in data.iloc[:, 0].values]))
            file.write('\n')
            
            file.write('#s, S1, ')
            file.write(', '.join([str(i) for i in data.iloc[:,1].values]))
            file.write('\n')

            # #C and shifts
#            file.write('#c, ' + np.array2string(data.iloc[:, 0].values, separator=',',
#                                                max_line_width=np.inf, precision=4,
#                                                floatmode='fixed')[2:-1]) # Trim ends
#            file.write
#            
#            file.write('\n')
#            # Shift values
#            file.write('#s, S1, ' + np.array2string(data.iloc[:, 1].values, separator=',',
#                                                    max_line_width=np.inf, precision=4,
#                                                    floatmode='fixed')[2:-1])
#            file.write('\n')
        end = time.time()
        print(end-start)

    
    
class PredictionHandler(object):

    '''
    Handles loading InStep predicted outputs and plotting them (if desired.)

    Reads a continually updated InStep AutoSave file in the directory passed to the Observer.
    File must have a comma separated header of predicted value names (in order),
    then rows of tab separated: filename, date, time, <comma sep predicted values>.
    Dates are of format %m/%d/%Y, while time is of format %I:%M:%S %p

    Pattern specifies the pattern of the AutoSave filename to watch for.
    This pattern is looked at upon creation or modifcation. Only the last line is read
    with each update to the file. If plot=True, the data will also be plotted.

    Parameters
    ----------
        pattern : list
            A list of pattern strings (usually only one) to specify the name of the file
            autosave file to watch for (e.g. [*InStepAutoSave*])

        plot : bool
            True if realtime plotting of predicted values is desired.

    Attributes
    ----------
        num_event : int
            Number of events that have occured, i.e. how many predictions have been made

        dates : np.array(dtype=datetime64[s])
            An array to store datetimes of the predicted values. Initalized to store
            3000 entries, more are created if needed

        ref_dates : np.array
            An array to store datetimes in a float representation used for plotting

        pred_values : np.array
            A 2 dim array used to store predicted values. Only initialized once the
            number of values needed is known. Rows are entries, columns are variables

        REF_TIME : np.datetime64
            A constant datetime object used to compute ref_dates

        plot_attr : dict
            A dict of plotting attributes

            plot : bool
                True if plotting is desired

            If plot, other values are initalized

            fig : plt.figure

            ax : plt.ax
                ax of subplot of fig

            lines_array : list
                List of line objects corresponding to each predicted variable tracked

    Examples
    --------
    AutoSave Format:
        Glucose, Xylose, Ilcatose
        <File Name> \t <Date> \t <Time> \t <gluc_pred, xyl_pred, ilcat_pred>
        <File Name> \t <Date> \t <Time> \t <gluc_pred, xyl_pred, ilcat_pred>
        ...
    '''

    def __init__(self, plotter):
        self.num_event = 0      # Track the number of events that have occured
        self.dates = np.zeros((3000), dtype='datetime64[s]') # Array to store timestamps
        self.ref_dates = np.zeros(3000) # Stores dates as a float relative to start
        self.pred_values = None # Stores predicted values. Initalized once num of cols is known

        # Reference time to compute plot points. Taken at the start of the program
        # All datetimes will have this value subtracted from them and stored in ref_dates
        self.REF_TIME = np.datetime64(datetime.datetime.today())
        self.plotter = plotter
        self.labels = None

    # Catch autosave created or modified
    async def on_any_event(self, event_path):
        '''
        Called when a file matching any pattern is created or modified

        If the file is just created, reads the header and calls plot_init() if needed.
        Also initalizes preed_values to have the correct number of columns.

        Upon modification, the last line of the file is read and the data structures are
        updated accordingly at the index corresponding to num_event. Updates the plot
        if plot=True.

        If the file exceeds 3000 entries, the data structures are extended by 3000.
        This is done indefinitely everytime the structure becomes filled

        Catches IndexError, which is a common error in which InStep reports the
        file as missing and doesn't predicted values. In this case, the update is passed.

        Parameters
        ----------
        event : watchdog.events.FileSystemEvent
            An watchdog Event object (automatically passed by the Observer)
        '''
        # If it's the first event caught, read header to get col labels
        if self.num_event < 1:
            with open(event_path, 'r') as file:
                labels = file.readline().split(', ')
                labels[-1] = labels[-1].rstrip() # Remove the \n from the last header
                self.labels = labels
                
                # Init data now that we know how many variables there are
            self.pred_values = np.zeros((3000, len(self.labels)))
            self.plotter.init_plot(self.REF_TIME, self.labels)

        # Try reading the autosave file
        try:
            temp_data = self.read_last_line(event_path) # Get last line

            # Add update dates, ref_dates, and data. All values are initialized to
            # 0, so num_event keeps track of the working index
            self.dates[self.num_event] = np.datetime64(temp_data[0])
            self.ref_dates[self.num_event] = (self.dates[self.num_event] -
                                              self.REF_TIME).astype('float')
            self.pred_values[self.num_event, :] = temp_data[1]

            self.num_event += 1 # Increment num_event
            
            await self.plotter.animate(self)

            # Check if the preallocated space of 3000 entries has been used.
            # If so, append room for another 3000 entries, indefinitely
            if self.num_event >= self.pred_values.shape[0]:
                self.expand_arrays()

        # Catches a common error where InStep reports the file as missing
        except IndexError:
            print('InStep reported file missing.')
            
            
    def expand_arrays(self):
        self.pred_values = np.append(self.pred_values,
                                     np.zeros((3000, self.pred_values.shape[1])),
                                     axis=0)
        self.dates = np.append(self.dates, np.zeros(3000, dtype='datetime64'))
        self.ref_dates = np.append(self.ref_dates, np.zeros(3000))
        
    def get_values(self):
        return (self.ref_dates[:self.num_event], self.pred_values[:self.num_event,:])

    # Assumes name in first col, date in 2nd, time in 3rd, then comma sep pred. values
    @staticmethod
    def read_last_line(file_path):
        '''
        Reads the last line of the updated file and returns a tuple of extracted data.

        Parameters
        ----------
        file_path : str
            str describing absolute path to autosave file

        Returns
        -------
        tuple (datetime, np.array)
            First index corresponds to a datetime of the time written
            Second index corresponds to a np.array of the predicted values

        Raises
        ------
        Exception if the file is not of the specified format
        '''
        with open(file_path, 'r') as file:
            # Get through every line in the file
            for line in file:
                pass
            line = line.split('\t')
        # Format as a python datetime.datetime object
        cur_date = datetime.datetime.strptime(line[1] + '-' + line[2],
                                              '%m/%d/%Y-%I:%M:%S %p')
        # Return a tuple of the current date and a np array of the values
        return (cur_date, np.array(line[3].split(', ')))

    def plot(self, labels):
        self.plotter = Plotter(self.REF_TIME, labels)
#        animation.FuncAnimation(self.plotter.fig, self.plotter.animate, 
#                                fargs = (self, ), interval = 1000)

    
    
class Plotter(object):
    def __init__(self):
        self.fig = Figure(figsize=(6,6))
        self.ax = self.fig.add_subplot(111)
        self.lines_array = []
        self.REF_TIME=0
        
        
    def init_plot(self, ref_time, labels):
        '''
        Initalizes the plot when data is first read.

        Sets various plotting parameters and fills lines_array with Line objects,
        using the labels read in the header of the autosave file.

        Parameters
        ----------
        labels : list
            A list of str corresponding to the labels of variables in the header
            of the autosave file
        '''

        # Use method x_format to change time delta back to datetime for xticks
        formatter = FuncFormatter(self.x_format)
        self.ax.xaxis.set_major_formatter(formatter) # Assign formatter
        self.ax.tick_params(axis='x', labelrotation=30, labelsize='small') # Rotate x ticks to fit datetimes

        # Create an empty line object for each column, stored in plot_attr['lines_array']
        for lab in labels:
            line, = self.ax.plot([], [], '-', label=lab,
                                              marker='d', mfc='white')
            self.lines_array.append(line)

        self.fig.legend()
        self.REF_TIME = ref_time
        
    def set_ylabel(self, label):
        self.ax.set_ylabel(label)
        
    # Reformats a ref_time in the x data to a readable datetime string for xticks
    def x_format(self, x_val, pos, unit='m'):
        date_str = np.datetime_as_string(x_val.astype('timedelta64') + self.REF_TIME,
                                         unit=unit)
        return date_str.replace('T', ' ')

    async def animate(self, update_class):
        x_values, y_values = update_class.get_values()
        for idx, line in enumerate(self.lines_array):
            line.set_xdata(x_values)
            # handle 1d array
            if len(y_values.shape) == 1:
                line.set_ydata(y_values)
            else:
                line.set_ydata(y_values[:, idx])
        
        self.fig.canvas.flush_events()
#        plt.draw()
            
        self.ax.set_xlim(np.min(x_values),
                                      np.max(x_values))
        self.ax.set_ylim(np.min(y_values),
                                      np.max(y_values))
        
        
class PID_Handler(object):
    
    def __init__(self, max_vol, pred_handler, plotter, tracking, log_file):
        self.vol = np.zeros(3000) # Stores pid values.
        self.pred_handler = pred_handler
        self.pid = PID(0.001, 0.5, 0, setpoint=60, output_limits=(0, 20),
                       proportional_on_measurement = False)
        
        self.plotter = plotter
        self.plotter.init_plot(self.pred_handler.REF_TIME, ['Volume (mL)'])
        
        self.tracking = tracking
        self.log_file = log_file
        self.max_vol = max_vol
        
        self.write_header()

        
        
    def get_status(self):
        mode_dict = {True:'Enabled', False:'Disabled'}
        try:
            return (mode_dict[self.pid.auto_mode], self.pred_handler.labels[self.tracking], 
                    self.pid.setpoint) + self.pid.tunings + self.pid.output_limits + \
                    (self.max_vol, mode_dict[self.pid.proportional_on_measurement])
        except TypeError:
            return (mode_dict[self.pid.auto_mode], self.tracking, 
                    self.pid.setpoint) + self.pid.tunings + self.pid.output_limits + \
                    (self.max_vol, mode_dict[self.pid.proportional_on_measurement])
                
    def get_tracking(self):
        try:
            return self.pred_handler.labels[self.tracking]
        except TypeError:
            return self.tracking
        
    def expand_arrays(self):
        self.vol = np.append(self.vol, np.zeros(3000))
        
    async def trigger_PID(self):
        
        value = self.pred_handler.pred_values[self.pred_handler.num_event - 1, 
                                              self.tracking]
        
        if self.pred_handler.num_event >= self.vol.shape[0]:
            self.expand_arrays()
            
        vol = round(self.pid(value), 3)
        
        if vol + np.sum(self.vol) > self.max_vol:
            vol = max(0, (self.max_vol - np.sum(self.vol)))
        
        self.vol[self.pred_handler.num_event - 1] = vol
        
        self.write_to_log(value, vol)
        
        await self.plotter.animate(self)
        
    def last(self):
        return self.vol[self.pred_handler.num_event - 1]
    
    def get_values(self):
        limit = self.pred_handler.num_event
        return (self.pred_handler.ref_dates[:limit], np.cumsum(self.vol[:limit]))
    
    def update_all(self, track, setpoint, coeffs, limits, max_vol):        
        try:
            self.tracking = self.pred_handler.labels.index(track)
        except AttributeError:
            self.tracking = int(track)
        
        self.pid.setpoint = setpoint
        self.pid.tunings = coeffs
        self.pid.output_limits = limits
        self.max_vol = max_vol
    
    def write_header(self):
        header = ['Datetime', 'Status', 'Tracking', 'Set Point', 'Prop.', 'Int', 'Deriv', 
                  'Lower Limit', 'Upper Limit', 'Max Volume', 'Input', 'Output', 'Cumulative']
        with open(self.log_file, 'w') as f:
            f.write(', '.join(header))
            f.write('\n')
            
    def write_to_log(self, input_val, output_val):
        last = self.pred_handler.num_event - 1
        date = self.plotter.x_format(self.pred_handler.ref_dates[last], None, 's')
        values = [date] + list(self.get_status()) +\
                    [input_val, output_val, self.get_values()[1][-1]]
            
        line = ', '.join([str(i) for i in values])
        
        with open(self.log_file, 'a') as f: 
            f.write(line)
            f.write('\n')
        
def main():
    ''' Prompts user for directory inputs, then starts monitoring.
    '''
    root = Tk() # Create parent window and hide it
    root.withdraw()
    # Prompt for directory to where raw spectra will be placed
    messagebox.showinfo('Python', 'Select the directory where raw spectra will be placed')
    raw_path = askdirectory()
    output_path = Path(raw_path) / 'Output' # Add output folder to that dir if it doesn't exist
    if not output_path.exists():
        output_path.mkdir()
    messagebox.showinfo('Python', f'Set InStep In location to {output_path}')

    # Prompt for directory where InStep will place the autosave file
    messagebox.showinfo('Python', 'Select the directory where the predicted' +
                        ' autosave file will be placed')
    processed_path = askdirectory()

    # Ask if you want to plot
    plot_realtime = messagebox.askyesno('Python', 'Would you like to plot the' +
                                        ' predicted results in real time?')

    observer = Observer()   # Passes events to handler
    raw_handler = RawHandler() # Handles raw spectra.
    # Tell observer to give events it sees in raw_path to the raw_handler
    observer.schedule(raw_handler, path=raw_path)

    # Pattern arg ensures that other files aren't handled, only the autosave
    processed_handler = PredictionHandler(pattern=['*InStepAutoSave*'], plot=plot_realtime)
    observer.schedule(processed_handler, path=processed_path, recursive=False)
    observer.start() # Start the oberver

    # Observer and program will run indefinitely until keyboard interupt
    try:
        while True:
            time.sleep(1) # Sleep for 1 second

#            plt.pause(0.001)    # NECESSARY IN MAIN LOOP for plot to not freeze
    except KeyboardInterrupt:
        observer.stop()
    observer.join() # Kill observer thread

# Call main if the script is executed
if __name__ == '__main__':
    main()
