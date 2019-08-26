# -*- coding: utf-8 -*-
"""
Created on Mon Jul 22 11:01:38 2019

@author: Raman
"""
import time
import shutil
import os
r_files = r'C:\Users\Raman\Downloads\B30.35 (2)\B30.35\Raman Data\20190320_B30.35'
dest = r'C:\Users\Raman\Desktop\Raman\Input'

for f in os.listdir(r_files):
    shutil.copy(r_files + '\\' + f, dest)
    time.sleep(5)