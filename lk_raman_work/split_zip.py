#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug  8 09:24:47 2019

@author: lemm905
"""

from zipfile import ZipFile
import os
from os.path import isfile, abspath, join
import argparse
import math

def main():
    parser = argparse.ArgumentParser(description='Split a directory of raman files into zip files.')
    parser.add_argument('directory', help='Path to directory containing raman files')
    parser.add_argument('-n', default=400, type=int, help='Number of files to be placed in each zip')
    args = parser.parse_args()
    
    zip_files(args.directory, args.n)
    

def zip_files(directory, n):
    files = [f for f in os.listdir(directory) if isfile(join(directory, f))]
    files.sort()
    
    for i in range(math.ceil(len(files) / n)):
        with ZipFile(abspath(directory) + f'_{i}.zip', mode='w') as z:
            for j in range(i*n, min((i+1)*n, len(files))):
                z.write(join(directory, files[j]))
                
if __name__ == '__main__':
    main()