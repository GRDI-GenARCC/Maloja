#!/usr/bin/env python3

import argparse
import subprocess
import warnings
import sys

import json

from snakemake.utils import read_job_properties

jobscript = sys.argv[1]
job_properties = read_job_properties(jobscript)
DEFAULT_NAME = "snakemake_job"

DEFAULT_QUEUE = "{{cookiecutter.queue_arn}}"

DEFAULT_JOBDEF_NAME = "{{cookiecutter.jobdef}}"



command = ["conda", "run", "--no-capture-output", "-n", "{{cookiecutter.conda}}", jobscript] 

if job_properties["type"] == "single":
    name = job_properties["rule"]
elif job_properties["type"] == "group":
    name = job_properties["groupid"]
else:
    raise NotImplementedError(
        f"Don't know what to do with job_properties['type']=={job_properties['type']}"
    )

#Build container Overrides
if ("threads" in job_properties["resources"] and "mem_mb" not in job_properties["resources"]):
    override = {
            "command": command,
            "vcpus": job_properties["resources"]["threads"]
            }
elif ("mem_mb" in job_properties["resources"] and "threads" not in job_properties["resources"]):
    override = {
            "command": command,
            "memory": job_properties["resources"]["mem_mb"]
            }
elif ("threads" in job_properties and "mem_mb" in job_properties["resources"]):
    override = {
            "command": command,
            "vcpus": job_properties["resources"]["threads"],
            "memory": job_properties["resources"]["mem_mb"]
            }
else:
    override = { "command": command }

## do a try catch here in case the default region is not set
cmd = ["aws", "batch", "submit-job", "--job-name", name, "--job-queue", DEFAULT_QUEUE, "--job-definition", DEFAULT_JOBDEF_NAME, "--container-overrides", json.dumps(override)]

res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
res = json.loads(res.stdout.decode())

jobId = res["jobId"]
print(jobId)
