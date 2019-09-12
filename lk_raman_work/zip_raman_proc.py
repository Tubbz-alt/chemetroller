# -*- coding: utf-8 -*-

import zipfile
import re
import datetime
from pathlib import Path


def main():
    run_prop_path = '${runInfo}'
    
    # Extract run properties from file
    with open(run_prop_path) as file:
        for line in file:
            line_delim = line.split('\t')
            if line_delim[0] == 'runDataFile':
                modified_run_path = line_delim[3].rstrip()
                
            elif line_delim[0] == 'runDataUploadedFile':
                upload_path = line_delim[1].rstrip()
                
            elif line_delim[0] == 'StartTime':
                start_date = _parse_times(line_delim[1])
                
    process_zip(upload_path, modified_run_path, start_date)
    
# Given a zip file in_path, an out_path to write to, and a starting datetime,
# will read each file in the archive and process them, writing line by line to 
# the out file tsv.
def process_zip(in_path, out_path, start_date):
    file_regex = re.compile(r'\.txt$') # Match end of file name to be .txt
    
    header = ['FileName', 'ElapsedTime', 'Date', 'IntegrationTime',
          'AverageOf', 'LaserPower', 'Intensities']

    header_keys = ['file_name', 'elapsed', 'Date:', 'Integration time (ms):',
               'Averages:', 'Laser Power (mW):']

    # Replace parens with \( for regex matching and encode
    meta = [re.sub(r'\((.*)\)', r'\\(\1\\)', x).encode('utf-8') for x in header_keys]
    
    # Match metadata
    meta_regex = re.compile(b"(" + b")|(".join(meta) + b")")
    
    with zipfile.ZipFile(in_path, mode='r') as raman_zipped:
        # Get list of filenames 
        names_list = [i for i in raman_zipped.namelist() if file_regex.search(i)]
        
        
        # Assert that there are txt files in the zip archive
        assert len(names_list) > 0, 'No .txt files found in zip file'
        
        with open(out_path, mode='w') as out_file:
            out_file.write('\t'.join(header))
            out_file.write('\n')
            
            for name in names_list:
                 with raman_zipped.open(name) as file:
                     _process_spectra(file, out_file, name, start_date,
                                      header_keys, meta_regex)
                
                
# Process an individual file
def _process_spectra(in_file, out_file, file_name, start_date, header_keys, meta_regex):
    # Use Path to extract only the file name, rather than the full path
    meta_dict = {'file_name' : Path(file_name).name}

    # ASSUMES FIRST 24 LINES CONTAIN METADATA
    for i in range(24):
        line = in_file.readline()
        # Search the line to see if it matches a regex
        if meta_regex.search(line):
            # Split label and value by tab
            delim = line.split(b'\t')
            # Store label and value as an entry in meta_dict
            # Read as raw bytes from zip, so must be decoded
            meta_dict[delim[0].decode("utf-8")] = delim[1].decode("utf-8").rstrip()
            
    # Parse the datetime string as a datetime object
    meta_dict['Date:'] = _parse_times(meta_dict['Date:'])
    # Calculate and store hours since elapsed time
    meta_dict['elapsed'] = str(timedel_to_hr(meta_dict['Date:'] - start_date))
        
    # Re-store date as a string in this format
    meta_dict['Date:'] = meta_dict['Date:'].strftime('%Y-%m-%d %H:%M:%S')
    
    # Write the metadata to the file in the same order as header_keys
    for key in header_keys:
        out_file.write(meta_dict[key])
        out_file.write('\t')

    # Write the column of index 3 (4th col) to the out_file
    _write_col(in_file, out_file, 3)        
    
    out_file.write('\n')

# Assumes file line positioned at first entry
def _write_col(in_file, out_file, col_num):
    
    # Process first entry for correct comma sep
    out_file.write(in_file.readline().split(b'\t')[col_num].decode('utf-8').rstrip())
    
    for row in in_file:
        out_file.write(', ')
        # Split based on tab, take the column of index col_num, decode, and strip whitespace
        out_file.write(row.split(b'\t')[col_num].decode('utf-8').rstrip())
        

def _parse_times(date_string):
    date_string = date_string.replace('-', '/')
    for fmt in ['%m/%d/%Y %H:%M:%S', '%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y %H:%M', 
                '%m/%d/%Y %I:%M %p', '%Y/%m/%d %I:%M %p', '%Y/%m/%d %H:%M']:
        try:
            return datetime.datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    raise ValueError
    
def timedel_to_hr(time_del):
    return round((time_del.seconds / 3600 + time_del.days * 24), 3)

if __name__ == '__main__':
    main()
    print('Script complete')
