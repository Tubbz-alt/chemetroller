# -*- coding: utf-8 -*-
"""
Created on Mon Aug 26 11:55:50 2019

@author: Raman
"""
import numpy as np
import classes
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import datetime
import time
from watchgod import awatch
import asyncio
import nest_asyncio
from concurrent.futures import ProcessPoolExecutor
import threading

nest_asyncio.apply()

class tester(object):
    def __init__(self):
        self.REFTIME = np.datetime64(datetime.datetime.today())
        self.call_times = 0
        self.ref_dates = np.linspace(0, 15000, 100)
        self.pred_values = np.zeros((100, 2))
        self.pred_values[:,0]= np.linspace(0, 15, 100)
        self.pred_values[:,1] = np.linspace(15, 5, 100)
        
    def get_values(self):
        self.call_times += 1
        return (self.ref_dates[:self.call_times], self.pred_values[:self.call_times,:])
        
    
#path = 'C:/Users/Raman/Desktop'
#test = tester()
##pl = classes.Plotter(test.REFTIME, ['a', 'b'])
#handl = classes.PlotHandler()
#
#plt.ion()


async def pause():
    while True:
        print(1)
        plt.pause(0.001)
        await asyncio.sleep(0.01)

async def watcher1():
    async for changes in awatch(path, min_sleep = 1000):
#        await asyncio.sleep(0.1)
        print("Watcher 1")
        for event, p in changes:
            await handl.on_any_event(p)
            

if __name__ == "__main__":           
    loop = asyncio.get_event_loop()
    loop.create_task(pause())
    loop.create_task(watcher1())
    loop.run_forever()
    #loop.run_until_complete(pause())
