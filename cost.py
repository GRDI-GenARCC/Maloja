import pandas as pd
import datetime as dt
import math

# year month day hours (24h) minute of local time (not AWS time)
start_date = dt.datetime(2024,3,26,12,8)
end_date = dt.datetime(2024,2,8,14,35)


# the time zone needs to be adjusted forward 5 hours (even though AWS is only offset by 4 hours)
tz_offset = dt.timedelta(hours=5)
start_date = start_date + tz_offset
end_date = end_date + tz_offset

fields = {"id":"lineItem/ResourceId", 
          "cost":"lineItem/UnblendedCost", 
          "time":"identity/TimeInterval", 
          "name":"product/ProductName",
          "family":"product/instanceType",
          "usage": "lineItem/UsageAmount"}
fields_list = list(fields.values())

# read in the report downloaded from AWS, use first row as header, convert all NA or NAN to blank text
report_df = pd.read_csv("./GenericCostAndUsageReport-00001.csv", header=0, keep_default_na=False)
# can also modify this to only read certain columns
# report_df = pd.read_csv("maloja.cache/GenericCostAndUsageReport-00001.csv", header=0, keep_default_na=False, usecols=fields_list)
resources_df = pd.read_csv("maloja.cache/AWS-Snake-Bacteria_resources", header=None)

# newer versions of pandas uses concatenate rather than append. Concat uses lists. Comment this out if using old version of Pandas
df_list = []

# uncomment if using old version of Pandas
# new_df = pd.DataFrame(columns=report_df.columns)

# build the results
for index, i in resources_df.iterrows():
    # # if the substring "instance/i-" is not in the row, skip this row
    # if "instance/i-" not in i[0]: continue

    # this is how you access the string contained within the dataframe
    # print(f'{index}: {i[0]}')

    # create a boolean mask by checking to see if each row in the report dataframe's ID column contains the line of text in the resources dataframe
    bool_mask_line = report_df[fields["id"]].str.contains(i[0])

    # split the row based on a ":" delimeter one time and get the last item in the list
    substring = i[0].rsplit(':',1)[-1]

    if 'instance/i-' in substring: 
        # get the "i-###..." part only of that same string
        substring = substring.rsplit('/',1)[-1]

        # create a boolean mask by checking to see if each row in the report dataframe's ID column contains the line of text in the resources dataframe
        bool_mask_instance = report_df[fields["id"]].str.contains(substring)    

        # add bool masks together (Logical OR operator on panda series objects)
        bool_mask_line = bool_mask_line + bool_mask_instance

    # apply mask to the report dataframe to remove rows without this data
    filtered_df = report_df[bool_mask_line]

    # append these rows to a new dataframe (uncomment if using old version of Pandas)
    # new_df = new_df.append(filtered_df,ignore_index=True)

    # append the filtered dataframe to the list (comment this out if using old version of Pandas)
    df_list.append(filtered_df)

# concatenate the filtered dataframes (comment this out if using old version of Pandas)
new_df = pd.concat(df_list, ignore_index=True)

# Output the two relevant csvs (full details and only relevant details)
# Also making sure pandas does not convert float values into strings of scientific notation
new_df.to_csv("maloja.cache/output_full.csv", index=False, float_format='%.15f')
new_df.to_csv("maloja.cache/output_cropped.csv", index=False, float_format='%.15f', columns=fields_list)

# filter data by date
# total_days = (end_date.date() - start_date.date()).days
date_delta_hours = math.ceil((end_date - start_date).total_seconds()/3600)

# newer versions of pandas uses concatenate rather than append. Concat uses lists. Comment this out if using old version of Pandas
df_list = []

for hour_i in range(date_delta_hours + 1):
    # build the_ new date based on the hour difference (rounded up)
    new_date = start_date + dt.timedelta(hours = hour_i)
    # make a string version of the time formatted as seen in the AWS csv
    filter_time_str = f'{new_date.date()}T{new_date.strftime("%H")}:00:00Z/'
    # create a boolean mask based on if the "time" field contains the above string
    bool_mask_time = new_df[fields["time"]].str.contains(filter_time_str)
    # apply mask to the report dataframe to remove rows without this data
    filtered_df = new_df[bool_mask_time]
    # append the filtered dataframe to the list (comment this out if using old version of Pandas)
    df_list.append(filtered_df)

# concatenate the filtered dataframes (comment this out if using old version of Pandas)
new_df = pd.concat(df_list, ignore_index=True)

new_df2 = new_df.copy()
new_df2["Cpu_hours"] = ""
new_df2["Mem_hours"] = ""
fields_list.append("Cpu_hours")
fields_list.append("Mem_hours")

from convert_instance_to_CoreHours import instance_details 

for index, i in new_df2.iterrows():
    str_cast = str(i[fields["family"]])
    if len(str_cast) > 1:
        print( instance_details(str_cast) )
        new_df2.iloc[index, -1] = instance_details(str_cast)[1]*i[fields["usage"]] #place output of mem_hours here
        new_df2.iloc[index, -2] = instance_details(str_cast)[0]*i[fields["usage"]] #place output of cpu_hours here
new_df2.to_csv("maloja.cache/output_cropped_filtered.csv", index=False, float_format='%.15f', columns=fields_list)
