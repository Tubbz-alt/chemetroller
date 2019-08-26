# -*- coding: utf-8 -*-

import time
import numpy as np
import pandas as pd
from tkinter import Tk, messagebox
from tkinter.filedialog import askdirectory
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler



np.set_printoptions(threshold = np.inf)

class RawHandler(FileSystemEventHandler):
    def on_created(self, event):
        print(f'Event Type: {event.event_type}\n Path: {event.src_path}')
        time.sleep(.5)
        for i in range(3):
            try:
                self.process_file(event.src_path)
            except:
                print(f'Error reading file... Trying again. {2-i} attempts remaining.')
            else:
                break
         
    def process_file(path):
        input_file = Path(path)
        output_file = input_file.parent / 'Output' / (input_file.name[:-4] + '_proc.dat')
        
        # Read Raman
        with input_file.open(mode='r') as f:
            #data = np.loadtxt(f, skiprows=24, usecols=(1,3))
            data = pd.read_csv(f, sep ='\t', usecols =[1,3], skiprows=23, error_bad_lines = False)
            
            if not any(data.notna()):
                raise ValueError
    
     # Write Raman
        with output_file.open(mode='w') as f:
            # Dims
            f.write('#d, ' + str(data.shape[0]) + 'x1')
            f.write('\n')    
                
            # #C and shifts
            f.write('#c, ' + np.array2string(data.iloc[:,0].values, separator=',', 
                    max_line_width=np.inf, precision = 4, floatmode='fixed')[2:-1])
            f.write('\n')
            # col names
            f.write('#s, S1, ' + np.array2string(data.iloc[:,1].values, separator=',',
                    max_line_width=np.inf, precision = 4, floatmode='fixed')[2:-1])
            f.write('\n')

def main():
    root = Tk()
    messagebox.showinfo('Info', 'Select the directory where raw spectra will be placed:')
    scan_path = askdirectory()
    output_path = Path(scan_path) / 'Output'
    if not output_path.exists():
        output_path.mkdir()

    root.withdraw()
    event_handler = RawHandler()
    observer = Observer()
    observer.schedule(event_handler, path=scan_path)
    observer.start()
    
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    main()