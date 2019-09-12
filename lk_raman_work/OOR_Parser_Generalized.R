library(Rlabkey)
library(tidyr)

run.props = labkey.transform.readRunPropertiesFile("${runInfo}")

# save the important run.props as separate variables
run.data.file = labkey.transform.getRunPropertyValue(run.props, "runDataFile")
run.output.file = run.props$val3[run.props$name == "runDataFile"]
error.file = labkey.transform.getRunPropertyValue(run.props, "errorsFile")

# read in the results data file content
run.data = read.delim(run.data.file, header=TRUE, sep="\t", stringsAsFactors = FALSE);

#######################
# Transform the data. #
#######################

# Your tranformation code goes here.

#initialize a new column that is the OOR Indicator
cols = colnames(run.data)

for (col in cols){
    run.data = extract(run.data, col, c(paste0(col, "OOR"), col),
                       fill="right", regex="(^\\s?[<>])?(.+)")
}



###########################################################
# Write the transformed data to the output file location. #
###########################################################

#no code changes required here assuming your run.data dataframe is the table you want loaded

# write the new set of run data out to an output file
write.table(run.data, file=run.output.file, sep="\t", na="", row.names=FALSE, quote=FALSE)

# print the ending time for the transform script
writeLines(paste("nProcessing end time:",Sys.time(),sep=" "))