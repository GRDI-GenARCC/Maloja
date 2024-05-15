#!/bin/env python

import subprocess
import json
import time
from utilities import import_config
import boto3
import os

config = import_config()

resourceGroups = boto3.client('resource-groups')
pipeline = config["pipeline"]["name"]
username = config["user"]["name"]

pipelineIdentifier = f"{username}-{pipeline}"
sharedIdentifier = "MALOJA-SHARED"

sharedResourceGroup = f"{sharedIdentifier}-resources"
pipelineResourceGroup = f"{pipelineIdentifier}-resources"

#Check for existing group
response = resourceGroups.list_groups()
exists = False
for group in response.get('GroupIdentifiers', []):
    if (group.get('GroupName') == pipelineResourceGroup):
        exists = True

# Create Resource Groups
if (not exists):
    response = resourceGroups.create_group(Name = pipelineResourceGroup, ResourceQuery={"Type":"TAG_FILTERS_1_0","Query":"{\"ResourceTypeFilters\":[\"AWS::AllSupported\"],\"TagFilters\":[{\"Key\":\"PipelineIdentifier\",\"Values\":[\""+ pipelineIdentifier +"\", \""+ sharedIdentifier +"\"]}]}"})

#Confirm if maloja.cache exists
if (not os.path.exists(os.path.join(os.path.curdir, 'maloja.cache'))):
            os.makedirs(os.path.join(os.path.curdir, 'maloja.cache'))

path = os.path.join(os.path.curdir, 'maloja.cache', f'{pipelineIdentifier}_resources')
uniq_resources = []
if (os.path.isfile(path)):
    with open(path) as f:
        uniq_resources = f.read().splitlines()

# Query Resources
while True:
    # Parse resources

    try:
        response = resourceGroups.list_group_resources(Group=pipelineResourceGroup)
        resources = [ resource['ResourceArn'] for resource in response.get('ResourceIdentifiers', []) ]

        # Collect all resources
        uniq_resources = sorted(set(resources + uniq_resources))
        with open(path, "w") as file:
            file.write("\n".join(uniq_resources))

        print("Querying AWS Resources...")
        time.sleep(1)  # Optional: Add a delay to control the polling frequency

    except subprocess.CalledProcessError as e:
        print(f"Error executing AWS CLI command: {e}")
    
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    time.sleep(5)  # Optional: Add a delay between iterations

