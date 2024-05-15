#!/usr/bin/env python3
import fileinput

def instance_details(x):
    # gather vcpu and ram details from instance type string
    # vcpu, mem
    if(x == 't3.medium'):
        return (2, 4)
    if(x == 't3.large'):
        return (2, 8)
    if(x == 't3.xlarge'):
        return (4, 16)
    if(x == 't3.2xlarge'):
        return (8, 32)
    if(x == 'r4.xlarge'):
        return (4, 30.5)
    if(x == 'r4.2xlarge'):
        return (8, 61)
    if(x == 'r4.16xlarge'):
        return (64, 488)
    if(x == 'm4.large'):
        return (2, 8)
    if(x == 'm4.xlarge'):
        return (4, 16)
    if(x == 'm4.2xlarge'):
        return (8, 32)
    if(x == 'm4.4xlarge'):
        return (16, 64)
    if(x == 'm4.16xlarge'):
        return (64, 256)
    if(x == 'c4.large'):
        return (2, 3.75)
    if(x == 'c4.large'):
        return (2, 3.75)
    if(x == 'c4.xlarge'):
        return (4, 7.5)
    return (0, 0)

if __name__ == "__main__":
    core_hours = 0.0
    GB_hours = 0.0
    for line in fileinput.input():
        instance = line.split(",")[0].strip()
        #turn percentage usage into minutes of an hour
        usage = float(line.split(",")[1].strip())

        core_hours += instance_details(instance)[0] * usage
        GB_hours += instance_details(instance)[1] * usage

    print("Core Hours:", core_hours, " | GB Hours:,", GB_hours)
