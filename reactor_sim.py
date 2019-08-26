# -*- coding: utf-8 -*-
"""
Created on Thu Aug 22 09:07:24 2019

@author: Raman
"""
import numpy as np

import matplotlib.pyplot as plt
from simple_pid import PID
import time
import pump



vol = .300 # L
reactor_conc = 50 #g/L
makeup_con = 100 #g/L
purge_rate = -1.3e-6 # L/s0
makeup_rate = 0.0004 # L/s
sample_period = 1 #s
pump_rate = 0

pid = PID(0.001, 0.5, 0, setpoint=50, output_limits=(0, .02),
          proportional_on_measurement = False)#, sample_time = sample_period)


dt = 0.1 #s
t_max = 60 #s
t_vector = np.arange(0, t_max, dt)
conc_vector = np.zeros(t_vector.shape)
vol_vector =  np.zeros(t_vector.shape)
conc_vector[0] = reactor_conc
vol_vector[0] = vol
pid_vector = np.zeros(t_vector.shape) #int(dt*t_vector.shape[0]/sample_period)


# g/s
def consum_rate(t):
    return  -0.01 / (1 + np.exp(-0.1 * (t - 30)))

try:
    pump = pump.Pump_Serial('COM4', {13:15})
    pump.assign_speed(1, 'cw', 50)
    
    
    run_pump_time = 0 
    pump_vol = 0
    for i,t in enumerate(t_vector[:-1]):
    #    if run_pump_time > 0:
    #        
    #        pump_rate = makeup_rate
    #        run_pump_time -= dt
    #    else:
    #        pump_rate = 0
        
        
    #    pid_vector[i] = pump_rate
    #    vol_vector[i+1] = vol_vector[i] + dt * (pump_rate+purge_rate)
    #    conc_vector[i+1] = (conc_vector[i]*vol_vector[i] + dt * (consum_rate(t) + 
    #               (pump_rate * makeup_con))) / vol_vector[i+1]
        
        
        pid_vector[i] = pump_vol
        vol_vector[i+1] = vol_vector[i] + dt * (purge_rate) + pump_vol
        conc_vector[i+1] = (conc_vector[i]*vol_vector[i] + dt * consum_rate(t) + 
                   (pump_vol * makeup_con)) / vol_vector[i+1]
        
        pump_vol = 0
        
        if i % (sample_period/dt) == 0:
    #        pump_rate = pid(conc_vector[i])
            pump_vol = pid(conc_vector[i])
            pump.dispense_vol(1, pump_vol * 1e3, 13)
        
        time.sleep(0.1)
    
    
    pump.close()
    
    fig, ax = plt.subplots(4, 1, sharex=True)
    ax[0].plot(t_vector, consum_rate(t_vector))
    ax[0].title.set_text('Sugar Consumption')
    ax[1].plot(t_vector,conc_vector)
    ax[1].title.set_text('Sugar Concentration')
    ax[2].plot(t_vector,vol_vector)
    ax[2].title.set_text('Reactor Volume')
    ax[3].plot(t_vector, pid_vector)
    ax[3].title.set_text('Pump')
    fig.tight_layout()
    
except:
    pump.close()