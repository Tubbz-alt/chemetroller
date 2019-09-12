## Prep Data
### Raman Files
Raman spectra files are uploaded to *Raman_Transformation* in the form of a zip archive. Every spectra in the file is assumed to have the same run level properties, e.g. *subject ID*, *process ID*, etc. 

LabKey seems to have a limit if one of these archives contains greater than ~500 spectra files, so a large directory will need be broken up into multiple archives. This can be done with `split_zip.py`, a command line python program available under `files/scripts/`. It takes the directory (not archive) of a raman files and the maximum number of spectra files to store in an archive, and creates as many archives as necessary to do so.

To run it, from terminal execute `python [path to split_zip.py] [path to raman_directory] -n [max number of files in archive]`.

The zip archives will be named `<original directory name>_0`, `<original directory name>_1`, etc, for as many as are required, and will be located in the parent directory of the `raman_directory`.

In our example, we have 1478 files, so passing 500 would be processed as two archives containing 500 files and one containing 478.

### Wavenumbers list - Preconfigured

For the script to execute properly, there must be a list named `Raman_WaveNumbers` in the same folder as the assay (hardcoded as LabKey lacks user input). This list has two columns 

1. A text column named *ConfigID* that is the key of the list
2. A multiline text column named WaveNumbers with the *max* option selected under the advanced tab.

In the assay design, this list must be the lookup of the run property *Wavenumbers*

## Upload Data
### Raman
Now you can upload data to the *Raman_Transformation* Assay. Fill in the required Batch and Run Properties. If you had to split a directory containing files from the same experiment, it is recommended to make them all of the same batch and upload them sequentially.

The essential Run Properties are 
1. *SubjectID* - This is used to match the raman experiment to HPLC data in a study. Keep it the same for all raman files and HPLC data from the same experiment.
2. *StartTime* - This is the inoculation date time of the bioreactor in local time. The ElapsedTime for each of the spectra is computed from this, which is then used to match a spectra with a specific HPLC sample in a study.

*Wavenumbers* will be automatically filled in by the script, and the Raman_WaveNumbers list updated if needed. *ProcessID* is a used as a general description of how the experiment was done, e.g. what bioreactor.

If you have multiple archives for one batch, upload the first, then click "Save and Import Another Run" and proceed with the next. **Do not** click the plus button and attempt to import multiple archives at once. The script should take ~15 seconds to run, which includes uploading and processing time.

### HPLC
Currently, the HPLC side isn't automated, only the raman. The HPLC assay has already been imported here, but it's important to understand the layout of it. The HPLC assay has a column named *SampleID* which is a LookUp to the list `Culture_Sampling_Metadata`. This list then has the field *StrainLineID*, which corresponds to the raman's *SubjectID*, and this is what they will be joined on in our study. The HPLC assay also has the column *CultureAge*, which corresponds to the *ElapsedTime* column of the raman.

## Moving to a Study
Create a study, or use the current one. The current convention is to use `SubjectID` as the ParticipantID name. If you create a new study, watch for this, and make sure it is type `continuous`.

### ParticipantID Field
The most essential part of copying to the study is that there is a column of type **Participant (String)**. This is defined in the assay design and should not need to be modified, but if you create more assays or want to change the ParticipantID field, this is how. Furthermore, for a continuous study, you must have a column of type **Date**. 

The raman assay has the *SubjectID* run property defined to be the ParticipantID field. The HPLC assay doesn't have a ParticipantID field directly defined, but the LookUp list `Culture_Sampling_Metadata` *does* have a ParticipantID field - *StrainLineID*. When copying to a study, LabKey knows to reference this field in the LookUp and autopopulate the copy. Once in the study, both of these fields will be referred to as *SubjectID* (or whatever you defined it to be when you created the study), no matter what the original name was. 

## Study - Joining the Data
Once both sets of data have successfully been moved to datasets in the study, you can use the R Report `Raman_HPLC_Join` to join the two datasets and produce a training file for Pirouette based on the joined data.

The report is a RMarkdown file, so it well documented and explained clearly what's happening chunk by chunk. The main things to control are the parameters at the top. These control:

* The name of the dataset containing the raman data
* The name of the dataset containing the HPLC data
* The SubjectID to join on
* The training values that will be pulled from the HPLC table and written to the Pirouette file
* If you want to see table displayed of the join at the top of the report.

### Full Raman To Pirouette
If *all* the raman files are desired to be put in a pirouette format without any corresponding data, this can be done with
another R report - `Raman_Full_to_Pirouette` The use of this is identical to the join report, simply change the parameters

* The name of the dataset containing the raman data
* The SubjectID to join on

as needed.
