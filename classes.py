# -*- coding: utf-8 -*-
"""
Created on Thu Jul 25 12:50:36 2019

@author: Raman

This module contains classes used to handle various events that occur.

RawFileProcessor:
    Handles processing raw raman spectrum files.
    
Plotter:
    Plots data given to it by a PredictionHandler ora PIDHandler

PredictionHandler:
    Handles reading an InStep autosave file to extract predicted values and store them
    
PIDHandler:
    Handles the PID loop, which is based on values stored in a PredcitionHandler
"""
import datetime
from pathlib import Path
import warnings
import asyncio

import pandas as pd
import numpy as np
from matplotlib.ticker import FuncFormatter
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from simple_pid import PID
from watchgod import Change

warnings.filterwarnings("ignore", category=UserWarning)
np.set_printoptions(threshold=np.inf)

class RawFileProcessor(object):

    '''
    Handles processing raw spectra files into an InStep format.

    This object is called by watchgod in main when a raw spectrum file is created.
    On creation of a file in that directory <par_dir>, it is procesed and written
    to <par_dir>/Output.


    Parameters
    ----------
    None
    '''

    async def on_any_event(self, event_type, event_path):
        '''
        To be called when an event occurs. Determines what action to take,

        If the event is of type <added>, it is passed to on_created(). Otherwise,
        it is ignored.

        Parameters
        ----------
            event_type : watchgod.Change
                watchgod.Change type indicating the type of file event

            event_path : string
                Path to where the event occured

        '''

        if event_type == Change.added:
            await self.on_created(event_path)


    # Method called when a file is created
    async def on_created(self, event_path):

        '''
        Runs when a new raw spectrum file is added. Attempts to process it

        Attempts to process the created file three times before passing. This allows for
        multiple attempts when the file hasn't fully copied or isn't an actual spectra
        instead of throwing an exception.

        Parameters
        ----------
        event_path : string
            A path to the newly created raw spectrum file
        '''

        await asyncio.sleep(.5)      # Allow time for file to fully copy
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
        with output_file.open(mode='w') as file:
            # Dims
            file.write('#d, ' + str(data.shape[0]) + 'x1')
            file.write('\n')

            # Column Names (wavenumbers) - join() fast enough for two lines
            file.write('#c ')
            file.write(', '.join([str(i) for i in data.iloc[:, 0].values]))
            file.write('\n')

            # Dark Subtracted
            file.write('#s, S1, ')
            file.write(', '.join([str(i) for i in data.iloc[:,1].values]))
            file.write('\n')




class PredictionHandler(object):

    '''
    Handles loading and storing InStep predicted outputs.

    Reads a continually updated InStep AutoSave file in the directory watchdog is monitoring
    File must have a comma separated header of predicted value names (in order),
    then rows of tab separated: filename, date, time, <comma sep predicted values>.
    Dates are of format %m/%d/%Y, while time is of format %I:%M:%S %p

    Pattern specifies the pattern of the AutoSave filename to watch for.
    This pattern is looked at upon creation or modifcation. Only the last line is read
    with each update to the file. If plot=True, the data will also be plotted.

    Parameters
    ----------
        plotter : classes.Plotter()
            An instance of a classes.Plotter class. This will be used for handling the
            plot in the gui.

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

        plotter : classes.Plotter()
            An instance of classes.Plotter() that data will be handed to for plotting
            in the gui

        labels : list
            A list of the names of the predicted species - initially None until
            the AutoSave file is read for the first time

    Examples
    --------
    AutoSave Format:
        Glucose, Xylose, Ilactic Acid
        <File Name> \t <Date> \t <Time> \t <gluc_pred, xyl_pred, ilcat_pred>
        <File Name> \t <Date> \t <Time> \t <gluc_pred, xyl_pred, ilcat_pred>
        ...
    '''

    def __init__(self, plotter):
        self.num_event = 0      # Track the number of events that have occured
        self.dates = np.zeros((3000), dtype='datetime64[s]') # Array to store timestamps
        self.ref_dates = np.zeros((3000), dtype='timedelta64[s]') # Stores dates as a float relative to start
        self.pred_values = None # Stores predicted values. Initalized once num of cols is known

        self.plotter = plotter # Data will be handed to this for plotting
        self.labels = None # Stores the names of the predicted compounds (header)

    async def on_any_event(self, event_type, event_path):
        '''
        To be called when an event occurs. Determines what action to take,

        If the event is of type <added>, it is passed to on_created(). Otherwise,
        it is ignored.

        Parameters
        ----------
            event_type : watchgod.Change
                watchgod.Change type indicating the type of file event

            event_path : string
                Path to where the event occured
        '''

        if event_type == Change.added or event_type == Change.modified:
            await self.on_create_mod(event_path)

    # Catch autosave created or modified
    async def on_create_mod(self, event_path):
        '''
        Called when a file matching any pattern is created or modified

        If the file is just created, reads the header and calls plotter.init(),
        passing the now known labels. Also initalizes pred_values to have the correct
        number of columns.

        Upon modification, the last line of the file is read and the data structures are
        updated accordingly at the index corresponding to num_event. Also updates
        the plotter data by calling plotter.anmiate()

        If the file exceeds 3000 entries, the data structures are extended by 3000.
        This is done indefinitely everytime the structure becomes filled

        Catches IndexError, which is a common error in which InStep reports the
        file as missing and doesn't predicted values. In this case, the update is passed.

        Parameters
        ----------
       event_path : string
            A path to the AutoSave file.
        '''

        # If it's the first event caught, read header to get col labels
        if self.num_event < 1:
            with open(event_path, 'r') as file:
                labels = file.readline().split(', ')
                labels[-1] = labels[-1].rstrip() # Remove the \n from the last header
                self.labels = labels

            # Init now that we know how many variables there are
            self.pred_values = np.zeros((3000, len(self.labels)))
            self.plotter.init_plot(self.labels)

        # Try reading the autosave file
        try:
            temp_data = self.read_last_line(event_path) # Get last line

            # Add update dates, ref_dates, and data. All values are initialized to
            # 0, so num_event keeps track of the working index
            self.dates[self.num_event] = np.datetime64(temp_data[0], 's')
            # Store as seconds in UNIX time
            self.ref_dates[self.num_event] = self.dates[self.num_event].astype('timedelta64[s]')

            self.pred_values[self.num_event, :] = temp_data[1]

            self.num_event += 1 # Increment num_event

            await self.plotter.animate(self) # Update the plotter, passing self

            # Check if the preallocated space of 3000 entries has been used.
            # If so, append room for another 3000 entries, indefinitely
            if self.num_event >= self.pred_values.shape[0]:
                self.expand_arrays()

        # Catches a common error where InStep reports the file as missing
        except IndexError:
            print('InStep reported file missing.')


    def expand_arrays(self):
        '''
        Expands data arrays by 3000 if they become full.
        '''
        self.pred_values = np.append(self.pred_values,
                                     np.zeros((3000, self.pred_values.shape[1])),
                                     axis=0)
        self.dates = np.append(self.dates, np.zeros(3000, dtype='datetime64[s]'))
        self.ref_dates = np.append(self.ref_dates, np.zeros(3000))

    def get_values(self):
        '''
        Necessary for plotter. Returns all collected data thus far.

        Returns
        -------
            tuple
                A tuple of the collected ref_dates and the collected predicted values
        '''
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

    def get_labels(self):
        '''
        Returns labels
        '''
        return self.labels


class Plotter(object):
    '''
    Plots data for a handler.

    By passing an instance of Plotter() to one of the handlers, it will plot
    whatever is returned by that handler's get_values() function, with the 0th
    index of the tuple being x values and the 1st index being y values.

    If multiple y lines are being plotted, the rows correspond to x values and
    columns correspond to different lines.

    Unix time is used because matplotlib incorecctly plots datetimes. Therefore, it
    plots the unix time delta and we format the x tick labels to be our choosing
    (absolute time or a time delta to some other point).

    Attributes
    ----------
        fig : matplotlib.Figure()
            a figure to draw on

        ax : matplotlib.axes
            a matplotlib ax within the figure

        lines_array : list of lineplots
            a list of lineplots plotted on the ax. Used to update the plot
            each time animate() is called

        start_time : numpy.timedelta64[s]
            The UNIX time delta in seconds from which elapsed time can be computed from.
            Defaults to 0 (Jan 1 1970) until asigned by another class.

        format_abs : boolean
            True if the plot should be formated in absolute time. False for elapsed time

    '''
    def __init__(self):
        self.fig = Figure(figsize=(6,6)) # 6 inches x 6 inches
        self.ax = self.fig.add_subplot(111) # Only one subplot centered in fig
        self.lines_array = []
        self.start_time = np.timedelta64(0, 's')
        self.format_abs = True


    def init_plot(self, labels):
        '''
        Initalizes the plot when data is first read.

        Sets various plotting parameters and fills lines_array with Line objects,
        using the labels read in the header of the autosave file.

        Parameters
        ----------
        labels : list
            A list of str that lines will be labeled as. Should match the length of
            the columns returned in the y data when a handler's get_values() is called,
            and in the corresponding indicies
        '''

        self.set_x_format(True)

        self.ax.tick_params(axis='x', labelrotation=30, labelsize='small') # Rotate x ticks to fit datetimes

        # Create an empty line object for each column, stored in plot_attr['lines_array']
        for lab in labels:
            line, = self.ax.plot([], [], '-', label=lab,
                                 marker='d', mfc='white')
            self.lines_array.append(line)

        # Create legend
        self.fig.legend()

    def set_ylabel(self, label):
        '''
        Sets the y axis label of the plot.

        Parameters
        ----------
            label : string
                string of the label to display on the y axis
        '''
        self.ax.set_ylabel(label)

    def set_x_format(self, format_abs):
        '''
        Set x axis to be on absolute time (PST) or an elapsed time. Changes axis label

        Parameters
        ----------
            format_abs : boolean
                True if format should be set to absolute time. False for elapsed time
        '''
        # Create formatter and set x axis label
        if format_abs:
            formatter = FuncFormatter(self.x_format_abs)
            self.ax.set_xlabel('Absolute Time (PST)')
        else:
            formatter = FuncFormatter(self.x_format_rel)
            self.ax.set_xlabel('Elapsed Time (hr)')

        # Set formater and the format_abs attribute
        self.ax.xaxis.set_major_formatter(formatter)
        self.format_abs = format_abs

    def x_format_abs(self, x_val, pos, unit='m'):
        '''
        Reformats a Unix time in the x data to a readable datetime string for xticks

        Parameters
        ----------
            x_val : numpy.timedelta64[s]
                Passed by Matplotlib, but assumes the data type

            pos : None
                Required by matplotlib, but un used. Pass none to call manually

            unit : string
                Unit to set the smallest time to. Default is "m" for minutes

        Returns
        -------
            A string formatted as a neat datetime
        '''
        date_str = np.datetime_as_string(x_val.astype('datetime64[s]'), unit=unit)
        return date_str.replace('T', ' ') # Remove a T from numpy's output

    def x_format_rel(self, x_val, pos, decimals=3):
        '''
        Reformats a Unix time in the x data to an elapsed time in hrs using start_time

        Parameters
        ----------
            x_val : numpy.timedelta64[s]
                Passed by Matplotlib, but assumes the data type

            pos : None
                Required by matplotlib, but un used. Pass none to call manually

            decimals : int
                How many decimals to round the hour to. Default is 3.

        Returns
        -------
            A float of the time difference in hours between x_val and start_time
        '''
        # Find difference in seconds, convert to hours, and round
        return np.round((x_val.astype('int') - self.start_time.astype('int')) / 3600,
                        decimals=decimals)

    async def animate(self, update_class):
        '''
        Updates the plot with new data. Call when new data is available

        Should be used async -- call await animate()

        init_plot() should be called first so labels and lines can be initalized

        update_class must have a get_values() method that returns a tuple.
        The first item should be a 1D array containing x values.
        The second item can be a 1D or 2D array with as many rows as the first item.
        It should contain as many columns as labels passed to init_plot() does
        Each column corresponds to a different line to be plotted

        Parameters
        ----------
            update_class : Instance of class containing get_values() method
                This class will have its get_values() method called, which will
                be then used to update the plot.
        '''
        x_values, y_values = update_class.get_values() # Get new x and y data
        for idx, line in enumerate(self.lines_array): # Set values for each line
            line.set_xdata(x_values)

            if len(y_values.shape) == 1: # Handle 1D y array
                line.set_ydata(y_values)
            else:
                line.set_ydata(y_values[:, idx])

        self.fig.canvas.flush_events()
        plt.tight_layout()

        # Set x and y limits to the minimum and maximum values
        self.ax.set_xlim(np.min(x_values.astype('int')) - 60,
                                np.max(x_values.astype('int')) + 60)
        self.ax.set_ylim(np.min(y_values),
                         np.max(y_values))


class PIDHandler(object):
    '''
    Handles the PID loop. Intended to output a volume in mL

    Given a prediction_handler and a plotter, will track one of the values recorded
    by the prediction_handler and feed it to a pid. It stores the values returned
    by the values returned by the PID and hands them to the plotter. Will write info
    to a log file on every call to the PID.

    The handler bases what value it's tracking on the column index of the y_values (2nd item)
    returned by the pred_handler's get_values(). It also uses the pred_handlers dates
    (returned as 1st item in get_values()) to track the time at which the PID was updated,
    instead of keeping its own record.

    The PID has many adjustable parameters - the P, I, D coeffs, the setpoint,
    the lower and upper output limits, a proportional on measurement option, and
    a maximum cumulative output option (will always output zero if reached).

    Parameters
    ----------
        max_vol : float
            The maximum cumulative output of the PID. If the sum of all PID outputs
            reaches this value, each following output will be recorded as 0, no matter
            what the actually has ouput

        pred_handler : classes.PredictionHandler()
            A PredictionHandler instance that will be used to supply input values
            to the PID. Could also be any class that has a get_values() and a
            get labels() method that meet the specifications of PredictionHandler

        plotter : classes.Plotter()
            A Plotter instance that data will be passed to upon recieving a new PID output

        track_idx : int
            The column index of the value to be tracking in the 2nd item returned by
            pred_handler's method get_values().

        log_file : string
            Path to write the log file to, overwritten on every initalization. See
            write_to_log() for details of the log file

    Attributes
    ----------
        vol : numpy.ndarray
            An array to keep track of the output of the PID at every call, typically
            a volume in mL

        pred_handler : classes.PredictionHandler()
            Reference to pred_handler parameter

        pid : simple_pid.PID()
            The PID object that values will be fed to and outputs will be recorded from.
            Read simple_pid docs for a more detailed documentation of parameters.

        plotter : classes.Plotter()
            Reference to plotter parameter

        track_idx : int
            Reference to track_idx parameter

        log_file : string
            Reference to log_file parameter

        max_vol : float
            Reference to max_vol parameter

        num_event : int
            number of times the PID has been called

    Example
    -------
        Suppose pred_handler returned three columns in the second item of get_values(),
        each column corresponding to a different compound being recorded (e.g. Glucose,
        Xylose, Itaconic Acid). If track_idx was set to 0, on each call to trigger_PID(),
        the last value of the glucose column would be fed to the PID an it's output recorded.
        Therefore, the pred_handler should be updated before triggering the PID.
    '''

    def __init__(self, max_vol, pred_handler, plotter, track_idx, log_file):
        self.vol = np.zeros(3000) # Stores pid output values.
        self.pred_handler = pred_handler

        # Default values of the PID can be changed here
        self.pid = PID(0.001, 0.1, 0, setpoint=40, output_limits=(0, 20),
                       proportional_on_measurement=True, auto_mode=False)

        self.plotter = plotter
        self.plotter.init_plot(['Volume (mL)']) # Set label because we know what we're plotting

        self.track_idx = track_idx
        self.log_file = log_file
        self.max_vol = max_vol

        self.num_event = 0


        self.write_header() # Write header to log file, overwritting anything there


    def get_status(self):
        '''
        Get information about the PID settings

        If pred_handler has labels initalized, the tracking item will be a string of
        the corresponding label. If not, it will be track_idx.

        Returns
        -------
        tuple
            Item 1: string
               info on if the PID is enabled or disabled

            Item 2 : string or int
                What value the PID is tracking. See above

            Item 3 : float
                The set point of the PID

            Item 4,5,6 : float
                The P, I, D coeffs of the PID

            Item 7,8 : The lower and upder output limits of the PID

            Item 9 : float
                The max_vol setting

            Item 10 : string
                Info on if Proportional on Measurement is enabled or diabled
        '''
        mode_dict = {True : 'Enabled', False : 'Disabled'}


        return (mode_dict[self.pid.auto_mode], self.get_tracking(),
                self.pid.setpoint) + self.pid.tunings + self.pid.output_limits + \
                (self.max_vol, mode_dict[self.pid.proportional_on_measurement])

    def get_tracking(self):
        '''
        Returns name of tracked index of pred_handler labels are init. Else trac_idx.

        Returns
        -------
        string or int
            String if the pred_handler returns a valid list, i.e. has been initalized.
            Int of the tracked index otherwise
        '''
        try:
            return self.pred_handler.get_labels()[self.track_idx]
        except TypeError:
            return self.track_idx

    def expand_arrays(self):
        '''
        Expands the volume array if needed
        '''
        self.vol = np.append(self.vol, np.zeros(3000))

    async def trigger_PID(self):
        '''
        Using the most recent tracked value, get a new output from the PID and update.

        Call this method once pred_handler has a new value recorded and you want to
        get a new output from the PID based on it. Will record the output, log to the
        log file, and update the plotter
        '''
        # Get most recent value of tracked index
        
        if self.num_event < self.pred_handler.num_event: # Check if pred_handler has updated
            
            # Average of last 4 reads 
            value = np.average(self.pred_handler.get_values()[1][-4:, self.track_idx])
    
            if self.num_event >= self.vol.shape[0]:
                self.expand_arrays()
    
            # Get PID output and round to 2 decimals
            
            if self.pid.auto_mode:
                vol = round(self.pid(value), 2)
            else:
                vol = 0
    
            # Make output zero if the sum of outputs is greater than max_vol
            if vol + np.sum(self.vol) > self.max_vol:
                vol = max(0, (self.max_vol - np.sum(self.vol)))
    
            # Record output and increment num_event
            self.vol[self.num_event] = vol
            self.num_event += 1
    
            # Write this event to the log file
            self.write_to_log(value, vol)
    
            # Wait for the plotter to update with new value
            await self.plotter.animate(self)

    def last(self):
        '''
        Returns the last value output by the PID
        '''
        return self.vol[self.num_event - 1]

    def get_values(self):
        '''
        Returns a tuple as required by classes.Plotter. Y value is cumulative sum of PID outputs.

        Returns
        -------
        tuple (numpy.ndarray, nump.ndarray)
            X values are the same has the pred_handler's, y_values are the cumulative sum's
            of PID outputs stored in vol
        '''
        limit = self.num_event
        return (self.pred_handler.get_values()[0][:limit], np.cumsum(self.vol[:limit]))

    def update_all(self, track, setpoint, coeffs, limits, max_vol):
        '''
        Updates parameters of the PID.

        Parameters
        ----------
            track : string
                The label name or index of the value to track. Will attempt to as a
                label name first, and will use index if pred_handler.labels has not been
                initialized.

            setpoint : float
                New setpoint of the PID

            Coeffs : tuple(float, float, float)
                Tuple of the new P, I, D coefficients

            limits : tuple(float, float)
                Tuple of the new lower and upper output limits

            max_vol : float
                The new max_vol (output) the PID can have
        '''

        try: # See if labels is initalized
            self.track_idx = self.pred_handler.get_labels().index(track)
        except AttributeError: # If not, interpret as index
            self.track_idx = int(track)

        self.pid.setpoint = setpoint
        self.pid.tunings = coeffs
        self.pid.output_limits = limits
        self.max_vol = max_vol

    def write_header(self):
        '''
        Writes the following as a comma separated header, OVERWTIRING any file at log_file
        '''
        header = ['Datetime', 'Elapsed Time', 'Status', 'Tracking', 'Set Point',
                  'Prop.', 'Int', 'Deriv', 'Lower Limit', 'Upper Limit', 'Max Volume',
                  'Input', 'Output', 'Cumulative']

        line = ', '.join(header)
        with open(self.log_file, 'w') as f:
            f.write(line)
            f.write('\n')

    def write_to_log(self, input_val, output_val):
        '''
        Appends current information about the PID to the log file.

        Parameters
        ----------
            input_val : float
                The value that was just input into the PID

            output_val : float
                The value that was just output by the PID

        Format
        ------
        Comma separated values, in order:
            Datetime of last date recorded, same format as plotter's format_abs()

            Elapsed time in hours of the last date in pred_handler. NaN if plotter does
            not have it's start_time initalized

            Comma separated values of everything returned by get_status()

            The input_val parameter

            The output_val parameter

            The sum of the output thus far
        '''
        # Get most recent date and format as datetime
        date = self.plotter.x_format_abs(self.get_values()[0][-1], None, 's')

        # Check if plotter's start time is initialzed. If not, write NaN for elasped time
        if self.plotter.start_time.astype('int') == 0:
            elapsed = 'NaN'
        else:
            # If start_time is initialized, write in plotter's format_rel() format
            elapsed = self.plotter.x_format_rel(self.get_values()[0][-1], None)

        # Combine all values into a single list
        values = [date, elapsed] + list(self.get_status()) +\
                    [input_val, output_val, self.get_values()[1][-1]]

        # Make the list a comma separated string
        line = ', '.join([str(i) for i in values])

        with open(self.log_file, 'a') as f:
            f.write(line)
            f.write('\n')