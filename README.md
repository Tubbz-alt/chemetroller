# Introduction

This package is used to interface a Marqmetrix Raman Spectrometer's output with
a multiple regression prediction model developed in Chemometrix's InStep. It can then use
those predicted values to control a Cole-Parmer Pump via serial connection with a PID loop
to keep one of them at a setpoint.

# Setup
Use conda to install required packages. Run  
`conda env create`
then 
`conda activate pred_pid`
to activate the environment

# Usage
Run `python example/path/to/main.py` from the command prompt with the enviroment activated, or 
setup a batch file to do so automatically. Upon launching for the first time, there may be a 
delay as Python compiles the packages that run in C, however, this should only occur once.

## File Selection
You will be prompted to select the directory that the raw spectrum files will be placed in.
A message will appear telling you where to set the "In" folder of InStep.

You will then be prompted to select the directory than InStep will place it's AutoSave file in.
This is the same directory that the PID log file will be placed in.

## Activate InStep
From InStep, click File -> Start Processing

## Pump Setup
Now the main app will appear. Connect all pumps to the PC using a RS-232 cable. If any of the pumps
were used by this program, turn them off, then back on again to reset them. 

Now navigate to the "Pump" tab.
Click "Update Available Ports" to refresh the available serial ports.
Select the correct serial port to use via the dropdown menu and
click "Connect to Pumps." If no pumps were connected, you will be informed. If connection was
successful, you will see information displayed about each pump and the serial port selection
will become locked.

Before using a Pump, it is required that you set some parameters. They are as follows:

1. The volume in mL per revolution. This is something **you** must calibrate.
2. The RPM to run the pump at
3. The direction of the pump (clockwise or counterclockwise) - Select from the dropdown

Click "Update" to apply this configuration to the pump.

## PID Setup
The PID reads a value from the InStep Autosave file and controls a pump (by default, the first
pump connected) to attempt to keep that value at the setpoint. Its output is in terms of mL that the
pump should dispense, and there are safeguards to ensure it doesn't dispense too much. Each time the
AutoSave file updates, the PID is fed the latest tracked value and determines how much volume to
dispense in response to it.

Navigate to the PID Control tab. Here you can control all the parameters of the PID control loop.

* Tracking - Initially refers to the index of the column of the predicted values put out by InStep.
However, will update to the names in the header once the AutoSave file has been created.

* Setpoint - What the PID tries to keep the tracked value at.
* Prop, Int, Deriv - The three coefficients of the PID (change defaults in `classes.PIDHandler`
* Lower limit - The minimum value the PID can output. Should always be zero, unless the pump should
continually run.
* Upper Limit - The maximum value the PID can output on any update to it. Use this as a safeguard to
prevent too much volume from being dispensed at one time
* Max Cumulative Volume - The maximum total amount of volume the PID can output. Use as a safeguard to 
prevent overfilling your vessel. If the PID reaches this value, no more volume will be dispensed, no
matter what the tracked value is. If it becomes safe to add more volume, increase this amount.
* Proportional on Measurement - Turns on proportional on measurement instead of on error. Useful if
the PID's output effects the rate of change of the tracked value.

Click "Update" to set these values. Note that every box must be filled in to update.

## Mark a Time
You can navigate to the "Mark Time" tab to mark a specific time. Simply click the "Mark Time" button,
the current time will be recorded and displayed. From the time the button was pressed, data can be 
optionally be graphed as *Elapsed Time*, which is time in hours since the mark. The button 
"Switch to Elapsed Time" will be shown on both graphing tabs, and you can now cycle between absolute
time and Elapsed Time. For each trigger of the PID, Elapsed Time will be recorded in addition to
absolute time.

**WARNING:** If you want to reset the marked time, you can, but there is no current implementation
to update the PID log file if you set a new time. **It is your responsibility** to take note of 
the time change. It is therefore recommended that you only do so if absolutely necessary, or if
you do so before the processing starts. A warning dialogue will appear when the "Reset Marked Time"
button is pressed informing you of this as well.

## Begin Processing
Ensure all the above steps have been followed. You can now begin the raman spectrometer and processing
-> prediction -> PID -> pump will automatically begin as soon as the first spectrum file is created.

# Format

## Spectrum Files
Spectrum files are assumed to have a specific format such that

1. The spectral data begins on line 24
2. The second and forth columns are Raman Shift and Dark Subtracted respectively.
See classes.RawFileProcessor if this needs to change.

By default, the only assumption is that files end in `.txt`, but a regex identifier can be
set in `main.py`.

## InStep Files

### Processed In Files
Processed spectra that are ready to be fed to InStep are placed in a directory *Output*, which is
created in the directory that raw spectrum files are read from. A place holder sample name is used.

Set the "In" folder for InStep's file watcher to `raw_raman_dir/Output` 

### AutoSave Out File
InStep should be set to produce one continuous output autosave file. It should have the
name `InStepAutoSave.txt` (the default for InStep), however a regex identifier can be defined
in `main.py`. The format should be as follows:

* Header - A comma separated line of the names of the predicted values (e.g. Glucose, Xylose, Itaconic Acid)

* Body - Four tab separated values
	* File Name (not used, could be any filler)
	* Date
	* Time
	* A comma separated list of predicted values, in the same order as the header

The PID is set to track pred_value_0 by default (that in the 0th column of the comma separated values),
but this can be changed in the gui

Example:
	
	name_value_0, name_value_1, name_value_2, ...
	File_Name \t Date \t Time \t pred_value_0, pred_value_1, pred_value_2
	File_Name \t Date \t Time \t pred_value_0, pred_value_1, pred_value_2
	...

See `classes.PredictionHandler` if this needs to change

## PID Log
The PID log is written in the same directory as the InStepAutoSave file. The name of it is 
"pid_log_datetime of program launch.txt" Each row corresponds to a
trigger of the PID loop by the a new predicted value. It has a comma separated format of:

1. Date Time
2. Elapsed Time (NaN if no time marked in the gui
3. Info on if the PID is enabled or disabled
4. What value the PID is tracking in the AutoSave file (can be index or name)
5. The setpoint of the PID
6. Proportional Coeff 
7. Integral Coeff
8. Derivative Coeff
9. The lower output limit of the PID
10. The upper output limit of the PID
11. The maximum volume that can be dispensed
12. Info if proportional on measurement is enabled or disabled
13. The input value for this entry
14. The PID's output for this entry
15. The total volume dispensed thus far
