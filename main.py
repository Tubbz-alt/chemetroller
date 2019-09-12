# -*- coding: utf-8 -*-
"""
Created on Tue Sep  3 12:31:03 2019

@author: Raman

This is the main file to be execeuted, tying all the of the other modules together
and creating the gui. Some important things are hardcoded here:
    
    - The regex's to match the file names of the raw spectra and the InStep autosave to
    
    - The pump that the PID will dispense from to (currently the first one connected to this PC)
    
    - Defaults for the PID:
        These can be changed in the gui:
            - 200mL max volume
            - The index of the Autosave file that is tracked (currently 0)
        
        These must be changed in this file:
            - The location of the pid log_file (currently the same directory as 
                                                the autosave file)
        
"""

import asyncio
from watchgod import awatch, RegExpWatcher
import classes
import gui 
import tkinter as tk
from pathlib import Path


async def run_tk(root, loop, interval=0.06):
    '''
    Async way to run the tkinter main loop. Allows other processes to run for interval.
    
    Not very kosher, but works. Pass this method as a task to the asyncio loop
    and the mainloop for tkinter will exceute asynchronously, allowing time
    for other taks to run. The interval refers to the time in seconds between
    gui updates, reccomended to keep at least below 0.1s (10fps).
    
    If the tkinter root is closed, the event loop is stopped with no error. Otherwise,
    an exception is raised normally.
    
    Parameters
    ----------
        root : tk.Tk subclass
            The root of the tkinter application
            
        loop : asyncio.event_loop
            The asyncio event loop - used to end all tasks in loop when root is closed
            
        interval : float
            Time in seconds between gui updates
    '''
    try:
        while True:
            root.update() 
            await asyncio.sleep(interval)
    except tk.TclError as e:
        if "application has been destroyed" not in e.args[0]:
            raise e
        else:
            loop.stop()

async def instep_watcher(path, regex, pred_handler, pid_handler, app):
    '''
    Async file watcher for InStep autosave files.
    
    Given a path to a directory, watches that path for files matching the regex value
    of the 're_files' key in watch_kwargs. Passes that info to the prediction handler,
    then calls the pid handler to update. It then retrieves the response from the
    pid handler and uses the app to dispense that volume to the pump. Finally, 
    it updates all the plots in the app.
    
    This function is what ties together most of the functionality of the prediction
    control loop. Currently, the PID ordering a specific pump to dispense volume
    is hard-coded here as pump 1.
    
    Parameters
    ----------
        path : string
            full path to directory to watch for InStep autosave files.
            
        regex : string
            A regex that will match the name of the InStep Autosave file
            
        pred_handler : classes.PredictionHandler
            The prediction handler to pass updates of the autosave file to. This should
            be the same prediction handler that the pid_handler is tied to, but
            is left explicit here for clairity.
            
        pid_handler : classes.PIDHandler
            The PIDHandler that will be updating based on the new predicted value.
            
        app : gui.App
            The main app holding all the tabs required.
    '''
    # By changing the value of re_files, the regex to match the name of an
    # autosave file can be changed
    watch_kwargs = {'re_files' : regex, 
                    're_dirs' : None}
    
    # Update every 1000ms
    async for changes in awatch(path, watcher_cls=RegExpWatcher, 
                                watcher_kwargs=watch_kwargs, min_sleep = 1000):
        
        # Handle an event in the directory matching the regex of re_files
        for event, path in changes:
            await pred_handler.on_any_event(event, path) # Let pred_handle update
            await pid_handler.trigger_PID() # Trigger the PID with the new values
            vol = pid_handler.last() # Get the most recent PID output
            
            app.pages["Pump"].dispense_vol(1, vol) # Dispense that to Pump 1
            
            app.update_plots() # Update the plots
            
            
async def raw_watcher(path, regex, raw_handler):
    '''
    Async file watcher for raw raman spectrum files in a directory.
    
    Calls raw_handler when an event matching regex in path occurs
    
    Parameters
    ----------
        path : string
            Full path to directory to watch for raw spectra files
            
        regex : string
            Regex to match raw spectra file names to
            
        raw_handler : classes.RawFileProcessor
            The RawFileProcessor that will process the raw file into an Instep format
    '''
    watch_kwargs = {'re_files' : regex, 
                        're_dirs' : None}
    # Check for events every 1000ms
    async for changes in awatch(path, watcher_cls=RegExpWatcher, 
                                watcher_kwargs=watch_kwargs, min_sleep = 1000):
        # For every change 
        for event, path in changes:
            await raw_handler.on_any_event(event, path) # Pass to raw_handler
            
def init_paths():
    '''
    Prompt user for file paths to the raw in_directory and the Instep autosave directory.
    
    Also creates the directory in_directory/Output to place InStep in files to
    if it does not already exist.
    
    Returns
    -------
        dict{string : string}
            A dictionary in which file paths are stored. 'raw' corresponds to the path
            where raw spectra files will be placed. 'instep' corresponds to the path
            that the InStep autosave file will appear in
    '''
    paths = {}
    
    root = tk.Tk() # Create parent window and hide it
    root.withdraw()
    
    tk.messagebox.showinfo('Python', 'Select the directory where raw spectra will be placed')
    paths['raw'] = tk.filedialog.askdirectory()
    
    output_path = Path(paths['raw']) / 'Output' # Add output folder to that dir if it doesn't exist
    if not output_path.exists():
        output_path.mkdir()
    tk.messagebox.showinfo('Python', f'Set InStep In location to {output_path}')

    # Prompt for directory where InStep will place the autosave file
    tk.messagebox.showinfo('Python', 'Select the directory where the predicted' +
                        ' autosave file will be placed')
    
    paths['instep'] = tk.filedialog.askdirectory()
    
    root.destroy()
    
    return paths
      
def main():
    '''
    Excutes full program. Sets up all handlers and initailzes the gui
    '''
    # Get necessary file paths
    paths = init_paths()
#    paths = {'instep':'C:/Users/Raman/Desktop/Instep_out', 'raw':'C:/Users/Raman/Desktop/Raman/Input'}
    
    raman_regex = r'.+\.txt' # Raman file is any that ends in .txt
    
    # InStepAutosave is any that ends in InStepAutoSave.txt
    instep_regex = r'.+InStepAutoSave\.txt' 
    
    # Create the raw spectrum handler
    raw_handler = classes.RawFileProcessor()
    
    # Create the plotter for the prediction handler, then create the prediction handler
    prediction_plotter = classes.Plotter()
    prediction_plotter.set_ylabel('Concentration (g/L)')
    prediction_handler = classes.PredictionHandler(prediction_plotter)
    
    # Create the plotter for the PID handler, then create the PID handler
    pid_plotter = classes.Plotter()
    pid_plotter.set_ylabel('Cumulative Vol. (mL)')
    
    # Here the log file of the PID handler is set to be in the same directory as
    # the InStep autosave file.
    # Other defaults are set, like the 200mL max volume, and that it's tracking index 0 of
    # the autosave file
    pid_handler = classes.PIDHandler(200, prediction_handler, pid_plotter, 0, 
                                      paths['instep']+'/pid_log.txt')
    
    # Create the plotting_dict and pass it to the App
    plot_dict = {'Raman Plot' : prediction_plotter, 'PID Plot' : pid_plotter}
    app = gui.App(plot_dict, pid_handler)
    
    # Get the current event loop
    loop = asyncio.get_event_loop()
    
    # Add the three async tasks defined above to event loop
    loop.create_task(run_tk(app, loop))
    loop.create_task(raw_watcher(paths['raw'], raman_regex, raw_handler))
    loop.create_task(instep_watcher(paths['instep'], instep_regex, prediction_handler,
                                    pid_handler, app))
    
    # Run the loop forever
    loop.run_forever()
    
if __name__ == '__main__':
    main()