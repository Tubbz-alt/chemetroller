# Intro
This package contains data processing tools used for LabKey. This Read Me
contains an overview of what files do what, see the pipeline_basics for
a detailed view.

### `split_zip.py`
A comand line tool used to split a directory of raman files
into zip files of size n for upload to labkey.

### `culture_metadata_creator.py`
A comand line tool to process autosampler files into a culture metadata excel
sheet. Run --help for options. Use from the beginning of the autosampler run as
input. E.g., if you have 120 samples take, start at the first occurance of 
"sample 1." If you later want to add more, use the **same** starting point

### `support_raman_proc.R`
Use in conjuction with `raman_zip_proc.py` to upload zipped raman files to
a labkey assay. See pipeline_basics

### `raman_zip_proc.py`
Use in conjuction with `support_raman_proc.py` to upload zipped raman files to
a labkey assay. See pipeline_basics.

### `raman_join_report.Rmd`
Use a LabKey R Markdown report to join raman data on HPLC data. See pipeline_basics.

### `raman_full_report.Rmd`
Similar to above, use this to get all available raman files in a piroutte 
format without an HPLC data, but to explore the data. See pipeline_basics.
