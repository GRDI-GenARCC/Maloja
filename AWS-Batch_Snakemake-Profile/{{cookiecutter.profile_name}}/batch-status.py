#!/usr/bin/env python

import json
import sys
import subprocess

jobid = sys.argv[1]


STATUS_ATTEMPTS = 20
#Try to get status 20 times
for i in range(STATUS_ATTEMPTS):
    try:
        cmd = "aws batch describe-jobs --jobs {}".format(jobid)
        res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        res = json.loads(res.stdout.decode())
        
        status= res["jobs"][0]["status"]
        break
    except subprocess.CalledProcessError as e:
        ## test to see if this prints out an error for if the default region is not set
        if i >= STATUS_ATTEMPTS - 1:
            print("failed")
            exit(0)
        print("aws batch error: ", e.stdout, file=sys.stderr)
        raise e
    else:
        time.sleep(5)

if status == "SUBMITTED":
    print("running")
if status == "PENDING":
    print("running")
if status == "RUNNABLE":
    print("running")
if status == "STARTING":
    print("running")
if status == "RUNNING":
    print("running")
if status == "SUCCEEDED":
    print("success")
if status == "FAILED":
    print("failed")
