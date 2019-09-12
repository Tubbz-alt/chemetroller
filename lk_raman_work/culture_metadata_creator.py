#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 11 09:33:22 2019

@author: lemm905
"""

import re
import pandas as pd
import numpy as np

import argparse
from pathlib import Path



def main():

    args = init_argparser().parse_args()
    
    data = read_autosampler(args.AutoSamplerFile)
    
    create(data, args)


def init_argparser():
    parser = argparse.ArgumentParser(description='Create a culture metadata file')
    parser.add_argument('AutoSamplerFile', help='Path to auto sampler file')
    parser.add_argument('StartDate', help='The start of the culture')
    parser.add_argument('--SamplePrefix', default='', help='The prefix to be used for each sample')
    parser.add_argument('--StrainLineID', default='', help='StrainLineID of the culture')
    parser.add_argument('--Experiment', default='', help='The Experiment ID')
    parser.add_argument('--StrainID', default='', help='The StrainId of the culture')
    parser.add_argument('--SampleQuantity', default='', help='The quantity of the sample taking')
    parser.add_argument('--SampleUnits', default='', help='The units of the sample')
    parser.add_argument('--SampleMethod', default='', help='The sampling method')
    
    return parser

def read_autosampler(autosampler_file):
    collected = re.compile(r'deposited in vial position (\d+)')
    date = re.compile(r'\d\d/\d\d/\d\d \d\d:\d\d:\d\d')
    
    data = pd.DataFrame(np.zeros((300,2)), columns=['Sample', 'DateTime'])
    
    sample_line = False
    list_idx = 0
    with open(autosampler_file, 'r') as f:
        for line in f:
            if sample_line:
                sample_line = False
                data.iloc[list_idx, 1] = date.search(line)[0]
                list_idx += 1
            
            if collected.search(line):
                
                sample = collected.search(line)[1]
                
                if sample != '0':
                    sample_line = True
                    data.iloc[list_idx, 0] = collected.search(line)[1]
        

    data.loc[:, 'DateTime'] = pd.to_datetime(data.loc[:, 'DateTime'])
    data.loc[:, 'Sample'] = pd.to_numeric(data.loc[:, 'Sample'])
    
    data.sort_values(by=['DateTime'], inplace=True)
    data = data.loc[data.iloc[:, 0] != 0, :]
    
    for i in range(int(data.shape[0] / 60)):
        end = min((i+2)*60, data.shape[0])
    
        data.iloc[(i+1) * 60:end, 0] = data.iloc[(i+1) * 60:end, 0] + (60 * (i+1))
        
    data = data.set_index('Sample')
                    
    return data

def create(data, args):
    
    data['StrainLineID'] = [args.StrainLineID for i in range(data.shape[0])]
    data['Experiment'] = [args.Experiment for i in range(data.shape[0])]
    data['StrainID'] = [args.StrainID for i in range(data.shape[0])]
    data['SampleQuantity'] = [args.SampleQuantity for i in range(data.shape[0])]
    data['SampleUnits'] = [args.SampleUnits for i in range(data.shape[0])]
    data['SamplingMethod'] = [args.SampleMethod for i in range(data.shape[0])]
    
    start_date = pd.to_datetime(args.StartDate)
    
    timedel = data['DateTime'] - start_date
    data['CultureAge'] = [round(date.total_seconds() / 3600, 3) for date in timedel]
    
    data.index = [f'{args.SamplePrefix}_{int(i):03}' for i in data.index]
    data.index.name = 'SampleID'
    
    data['DateTime'] = data['DateTime'].dt.strftime('%Y/%m/%d %H:%M:%S')
    
    hplc_data = data.loc[:, ['Experiment', 'DateTime']]


    directory = Path(args.AutoSamplerFile).parent
    
    hplc_data.to_excel(f'{directory}/HPLC_template.xlsx')
    data.to_excel(f'{directory}/metadata_template.xlsx')

if __name__ == "__main__":
    main()  
