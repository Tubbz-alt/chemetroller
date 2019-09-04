# -*- coding: utf-8 -*-
"""
Created on Tue Sep  3 12:31:03 2019

@author: Raman
"""

import asyncio
from watchgod import awatch, RegExpWatcher
import classes
import gui 
import tkinter as tk
from pathlib import Path


async def run_tk(root, loop, interval=0.06):
    try:
        while True:
            root.update() 
            await asyncio.sleep(interval)
    except tk.TclError as e:
        if "application has been destroyed" not in e.args[0]:
            raise
        else:
            loop.stop()

async def instep_watcher(path, pred_handler, pid_handler, app, plot_dict):
    watch_kwargs = {'re_files' : r'.+InStepAutoSave\.txt', 
                    're_dirs' : None}
    
    async for changes in awatch(path, watcher_cls=RegExpWatcher, 
                                watcher_kwargs=watch_kwargs, min_sleep = 1000):
        print("InStep Watcher")
        for event, p in changes:
            await pred_handler.on_any_event(p)
            await pid_handler.trigger_PID()
            vol = pid_handler.last()
            
            app.pages["Pump"].dispense_vol(1, vol)
            for plot in plot_dict:
                app.pages[plot].update_plot()
            
            
async def raw_watcher(path, raw_handler):
    watch_kwargs = {'re_files' : r'.+\.txt', 
                        're_dirs' : None}
    async for changes in awatch(path, watcher_cls=RegExpWatcher, 
                                watcher_kwargs=watch_kwargs, min_sleep = 1000):
        print("Raw Watcher")
        for event, p in changes:
            await raw_handler.on_created(p)
            
def init_paths():
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
    
    paths = init_paths()
#    paths = {'instep':'C:/Users/Raman/Desktop/Instep_out', 'raw':'C:/Users/Raman/Desktop/Raman/Input'}
    
    raw_handler = classes.RawHandler()
    
    prediction_plotter = classes.Plotter()
    prediction_plotter.set_ylabel('Concentration (g/L)')
    prediction_handler = classes.PredictionHandler(prediction_plotter)
    
    pid_plotter = classes.Plotter()
    pid_plotter.set_ylabel('Cumulative Vol. (mL)')
    pid_handler = classes.PID_Handler(200, prediction_handler, pid_plotter, 0, 
                                      paths['instep']+'/pid_log.txt')
    
    plot_dict = {'Raman Plot' : prediction_plotter, 'PID Plot' : pid_plotter}
    app = gui.App(plot_dict, pid_handler)
    
    
    loop = asyncio.get_event_loop()
    loop.create_task(run_tk(app, loop))
    loop.create_task(raw_watcher(paths['raw'], raw_handler))
    loop.create_task(instep_watcher(paths['instep'], prediction_handler,
                                    pid_handler, app, plot_dict))
    
    loop.run_forever()
    
if __name__ == '__main__':
    main()