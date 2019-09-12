library(Rlabkey)

################################################
# Read in the run properties and results data. #
################################################

#this is a LK function that doesn't require changing unless you plan to handle 
#multiple file types

run.props = labkey.transform.readRunPropertiesFile("${runInfo}")

# Get user security context to allow connecting back to the server to query from list table
${rLabkeySessionId}

current_folder = "${containerPath}"
print(current_folder)

# save the important run.props as separate variables
run.data.upload.file = labkey.transform.getRunPropertyValue(run.props, "runDataUploadedFile")
base.url = labkey.transform.getRunPropertyValue(run.props,"baseUrl")
run.props.output.file = labkey.transform.getRunPropertyValue(run.props,"transformedRunPropertiesFile")
error.file = labkey.transform.getRunPropertyValue(run.props, "errorsFile")

# Query wavenumber list
wavenumber.df = labkey.selectRows(baseUrl=base.url, folderPath = current_folder, schemaName='lists', queryName='Raman_Wavenumbers', colNameOpt='fieldname')

    
# Get a vector of file names in the zip file
file_list = unzip(run.data.upload.file, list = T)[[1]]

# For each file in the file list

txt_file = file_list[grepl('.txt$', file_list)][1] # Get first text file to extract data from

version_num = read.delim(unz(run.data.upload.file, txt_file), header = F, nrows = 22,
                      colClasses = 'character', row.names = 1)['Software Version:',1]

# If this config ID isn't in the list, add it
if (!(version_num %in% wavenumber.df$ConfigID)) {
    # Read raman wavenumbers
    raman_shift = read.delim(unz(run.data.upload.file, txt_file), header = T, skip = 23)[,'RamanShift']
    # Create a row to insert
    row_insert = data.frame(version_num, paste(raman_shift, collapse = ', '), stringsAsFactors = FALSE)
    # Set colnames equal to the list's
    names(row_insert) = colnames(wavenumber.df)
    
    # Insert the new config
    labkey.insertRows(baseUrl=base.url, folderPath = current_folder,
                      schemaName='lists', queryName='Raman_WaveNumbers', toInsert = row_insert)
}

run.props[,2][run.props$name == "Wavenumbers"] = version_num

write.table(run.props, file=run.props.output.file, sep="\t", na="", row.names=FALSE,
            quote=FALSE, col.names = FALSE)
