#!/bin/env python

import click
import boto3
import logging
import json
import time
import re
import os
import yaml
import shutil
from string import Template
from utilities import import_config, load_file, windows_to_linux_line_end, enforce_cidr
from s3_actions import upload_file_to_s3, download_file_from_s3
from cfn_tools import load_yaml as cfn_load_yaml
from botocore.exceptions import ClientError
from sys import platform
from contextlib import closing

# Global configuration, loaded below
CONFIG = None

# Define constants
SHARED_RESOURCE_PREFIX = "MALOJA-SHARED"
TEMPLATE_DIR = "cloudformation"


def create_cloudformation_client():
    return closing(boto3.client('cloudformation'))


def embed_config(config, to_embed, shared=False):
    if shared:
        return f"{SHARED_RESOURCE_PREFIX}-{to_embed}"
    else:
        pipeline_name = config["pipeline"]["name"]
        user_name = config["user"]["name"]
        return f"{user_name}-{pipeline_name}-{to_embed}"


def load_template(template_name):
    template_location = os.path.join(TEMPLATE_DIR, f"{template_name}.yaml")
    with open(template_location, 'r') as content_file:
        return cfn_load_yaml(content_file)


def stack_exists(cf_client, name):
    try:
        cf_client.describe_stacks(StackName=name)
        return True
    except ClientError:
        return False


def wait_for_stack(cf_client, stack_name, shared=False):
    while True:
        time.sleep(5)
        if not stack_exists(cf_client, stack_name):
            logging.error(f"{stack_name} does not exist.")
            break
        status = cf_client.describe_stacks(StackName=stack_name)['Stacks'][0]['StackStatus']
        if status == "CREATE_COMPLETE":
            logging.info(f"{stack_name} successfully deployed.")
            break
        elif status != "CREATE_IN_PROGRESS":
            logging.error(f"{stack_name} failed to deploy with status: {status}")
            break


def deploy_stack(cf_client,stack_name, template_body, parameters=[], capabilities=[], shared=False):
    #cf_client = create_cloudformation_client()
    try:
        stack_name = embed_config(CONFIG, stack_name, shared)
        cf_client.create_stack(
            StackName=stack_name,
            TemplateBody=json.dumps(template_body),
            Parameters=parameters,
            Capabilities=capabilities
        )
        logging.debug(f"Stack {stack_name} creation initiated.")
        wait_for_stack(cf_client, stack_name, shared)
    except ClientError as error:
        logging.error(error)
    #finally:
    #    cf_client.close()


def deploy_roles(cf_client,config):
    stack_name = "roles"
    template_body = load_template(stack_name)
    parameters = [
        {'ParameterKey': 'NamePrefix', 'ParameterValue': SHARED_RESOURCE_PREFIX},
        {'ParameterKey': 'AccountId', 'ParameterValue': str(CONFIG["user"]["account"])}
    ]
    capabilities = ['CAPABILITY_NAMED_IAM']
    deploy_stack(cf_client,stack_name, template_body, parameters, capabilities, shared=True)


def deploy_network(cf_client,config):
    stack_name = "vpc"
    template_body = load_template(stack_name)
    parameters = [
        {'ParameterKey': 'PipelineIdentifier', 'ParameterValue': SHARED_RESOURCE_PREFIX},
        {'ParameterKey': 'UserName', 'ParameterValue': CONFIG["user"]["name"]},
        {'ParameterKey': 'EcsInstanceRole', 'ParameterValue': CONFIG["roles"]["ecsInstanceRole"]}
        ]
    deploy_stack(cf_client,stack_name, template_body, parameters, shared=True)
    
def deploy_batch(cf_client,config):
    stack_name = "batch"
    template_body = load_template(stack_name)
    parameters = [
        {
            'ParameterKey': 'VpcStack',
            'ParameterValue': embed_config(config, "vpc", shared=True)
        },
        {
            'ParameterKey': 'PipelineIdentifier',
            'ParameterValue': SHARED_RESOURCE_PREFIX },
        {
            'ParameterKey': 'InstanceRole',
            'ParameterValue': config["roles"]["batchInstanceProfile"]
        },
        {
            'ParameterKey': 'ServiceRole',
            'ParameterValue': config["roles"]["batchServiceRole"]
        }
    ]
    deploy_stack(cf_client,stack_name, template_body, parameters, shared=True)
    
def deploy_jobDef(cf_client, config):
    stack_name = "jobDef"
    cache_dir = "maloja.cache"
    pipeline_name = config["pipeline"]["name"].lower()

    # Load the Job Definition name from a file
    with open(os.path.join(os.path.curdir, cache_dir, f'{pipeline_name}_build', 'jobDefName'), 'r') as f:
        jobDef_name = f.read().strip()
    
    # Describe the 'imagePipeline' stack to retrieve the stack ID
    
    response = cf_client.describe_stacks(StackName=embed_config(config, "imagePipeline"))
    
    stack_id = re.findall("[a-z0-9]+$", response["Stacks"][0]["StackId"])[0]

    account = config["user"]["account"]
    region = config["infrastructure"]["region"]
    ecsExecutionRole = config["roles"]["ecsExecutionRole"]
    pipelineIdentifier = f'{config["user"]["name"]}-{config["pipeline"]["name"]}'

    # Load template and deploy
    template_body = load_template(stack_name)
    parameters = [
        {'ParameterKey': 'BatchStack', 'ParameterValue': embed_config(config, "batch", shared=True)},
        {'ParameterKey': 'DockerImage', 'ParameterValue': f"{account}.dkr.ecr.{region}.amazonaws.com/{pipeline_name}-{stack_id}"},
        {'ParameterKey': 'JobName', 'ParameterValue': jobDef_name},
        {'ParameterKey': 'PipelineIdentifier', 'ParameterValue': pipelineIdentifier},
        {'ParameterKey': 'EcsExecutionRole', 'ParameterValue': ecsExecutionRole}
    ]
    deploy_stack(cf_client,stack_name, template_body, parameters)


def deploy_landingZone(cf_client,config):
    stack_name = "landingZone"
    template_body = load_template(stack_name)
    public_key = config["infrastructure"]["publicKey"]
    pipelineIdentifier = f'{config["user"]["name"]}-{config["pipeline"]["name"]}'
    whitelist_ip = enforce_cidr(config["user"]["whitelistIp"])
    lz_size = config["pipeline"]["landingZoneSize"]

    parameters = [
        {'ParameterKey': 'VpcStack', 'ParameterValue': embed_config(config, "vpc", shared=True)},
        {'ParameterKey': 'BatchStack', 'ParameterValue': embed_config(config, "batch", shared=True)},
        {'ParameterKey': 'PublicKeyContent', 'ParameterValue': load_file(public_key)},
        {'ParameterKey': 'PipelineIdentifier', 'ParameterValue': pipelineIdentifier},
        {'ParameterKey': 'WhitelistIP', 'ParameterValue': whitelist_ip},
        {'ParameterKey': 'InstanceType', 'ParameterValue': lz_size}
    ]
    deploy_stack(cf_client,stack_name, template_body, parameters)
    
def deploy_storage(cf_client,config):
    stack_name = "storage"
    template_body = load_template(stack_name)
    pipelineIdentifier = f'{config["user"]["name"]}-{config["pipeline"]["name"]}'

    parameters = [
        {
            'ParameterKey': 'Project',
            'ParameterValue': config["pipeline"]["name"].lower()
        },{
            'ParameterKey': 'PipelineIdentifier',
            'ParameterValue': pipelineIdentifier
        }
    ]
    deploy_stack(cf_client, stack_name, template_body, parameters)


def deploy_imageInfrastructure(cf_client, config):
    stack_name = "imageInfrastructure"
    template_body = load_template(stack_name)
    instance_role = config["roles"]["imageBuilderInstanceProfileName"]
    pipelineIdentifier = f'{config["user"]["name"]}-{config["pipeline"]["name"]}'
    
    parameters = [
        {
            'ParameterKey': 'VpcStack',
            'ParameterValue': embed_config(config, "vpc", shared=True)
        },
        {
            'ParameterKey': 'PipelineIdentifier',
            'ParameterValue': pipelineIdentifier
        },
        {
            'ParameterKey': 'ImageBuilderInstanceRole',
            'ParameterValue': instance_role
        }
    ]
    deploy_stack(cf_client, stack_name, template_body, parameters, shared=True)


def deploy_imagePipeline(cf_client, config):
    stack_name = "imagePipeline"
    template_body = load_template(stack_name)
    
    prepareComputeEnv(CONFIG)
    
    # Get Bucket name for SnakemakeComponent
    s3_stack_name = embed_config(config, "storage")
    
    response = cf_client.describe_stacks(StackName=s3_stack_name)
    output = response["Stacks"][0]["Outputs"]
    response_val = [value for value in output if value["OutputKey"] == "Bucket"]
    bucket_name = response_val[0]["OutputValue"]


    logging.info(f"Bucket Name: {bucket_name}")
    
    # Read Dockerfile content
    with open(config["pipeline"]["dockerFile"], 'r') as dockerfile:
        dockerfile_content = dockerfile.read()

    pipelineIdentifier = f'{config["user"]["name"]}-{config["pipeline"]["name"]}'
    parameters = [
        {
            'ParameterKey': 'Dockerfile',
            'ParameterValue': dockerfile_content
        },
        {
            'ParameterKey': 'ImageStack',
            'ParameterValue': embed_config(config, "imageInfrastructure", shared=True)
        },
        {
            'ParameterKey': 'ECRname',
            'ParameterValue': config["pipeline"]["name"].lower()
        },
        {
            'ParameterKey': 'PipelineBucket',
            'ParameterValue': bucket_name
        },
        {
            'ParameterKey': 'PipelineIdentifier',
            'ParameterValue': pipelineIdentifier
        },
        {
            'ParameterKey': 'Region',
            'ParameterValue': config["infrastructure"]["region"]
        }
    ]
    deploy_stack(cf_client, stack_name, template_body, parameters)
    
def get_cloudformation_output_value(cloudFormation, stack_name, output_key):
    response = cloudFormation.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0]["Outputs"]
    return next((output["OutputValue"] for output in outputs if output["OutputKey"] == output_key), None)

def get_cloudformation_output(cf_client,name, shared):
    stack_name = embed_config(CONFIG, name, shared)
    response = cf_client.describe_stacks(StackName=stack_name)
    stack_outputs = response['Stacks'][0]['Outputs']
    click.echo(click.style("Paste these values under the roles section in your configuration file", fg='green'))
    for output in stack_outputs:
        click.echo(f"{output['OutputKey']}: {output['OutputValue']}")


def write_role_output(cf_client, name, shared, config_file):
    stack_name = embed_config(CONFIG, name, shared)
    response = cf_client.describe_stacks(StackName=stack_name)
    stack_outputs = response['Stacks'][0]['Outputs']
    
    # If the YAML configuration file exists, update it
    if os.path.exists(config_file):
        with open(config_file, 'r') as file:
            config = yaml.load(file, Loader=yaml.SafeLoader)
        
        # Update the roles section with stack outputs
        roles_dict = {output['OutputKey']: output['OutputValue'] for output in stack_outputs}
        config['roles'] = roles_dict

        # Write the updated configuration back to the YAML file
        with open(config_file, 'w') as file:
            yaml.dump(config, file, Dumper=yaml.SafeDumper, default_flow_style=False)
        
        click.echo(click.style("Updated roles in configuration file.", fg='green'))

    # If the YAML configuration file does not exist, output the values to the console
    else:
        click.echo(click.style("Configuration file not found. Outputting values:", fg='yellow'))
        for output in stack_outputs:
            click.echo(f"{output['OutputKey']}: {output['OutputValue']}")
    

def prepareComputeEnv(config):
    # Embed stack names
    batch_stack = embed_config(config, "batch", shared=True)
    s3_stack = embed_config(config, "storage")
    jobDef_name = config["pipeline"]["jobDefinition"]
    pipeline_path = config["pipeline"]["pipeline_path"]
    pipeline = config["pipeline"]["name"].lower()
    cache_dir = "maloja.cache"
    build_dir = f"{pipeline}_build"
    local_build = config["pipeline"]["local_build"]

    with create_cloudformation_client() as cloudFormation:
        # Get Queue ID and Bucket Name from CloudFormation outputs
        queue_id = get_cloudformation_output_value(cloudFormation, batch_stack, "Queue")
        bucket_name = get_cloudformation_output_value(cloudFormation, s3_stack, "Bucket")

    logging.info(f"Queue ID: {queue_id}")
    logging.info(f"Bucket Name: {bucket_name}")

    # Custom AWS profile using Cookiecutter
    from string import Template
    
    template_param = {
        'queue_id': queue_id,
        'jobDefinition_name': jobDef_name,
        'pipeline_path': pipeline_path
    }
    
    location = os.path.join(os.path.curdir, 'AWS-Batch_Snakemake-Profile', 'cookiecutter.json')
    with open(f"{location}.template") as file:
        content = Template(file.read()).substitute(template_param)
    
    with open(location, "w") as file:
        file.write(content)

    os.system('cookiecutter --no-input AWS-Batch_Snakemake-Profile')

    profile_path = os.path.join(os.path.curdir, cache_dir, build_dir, '.config', 'snakemake', 'aws-batch')
    if (not os.path.exists(profile_path)):
        shutil.copytree('aws-batch', profile_path)

    region = config["infrastructure"]["region"]
    config_path = os.path.join(os.path.curdir, cache_dir, build_dir, '.aws')
    if (not os.path.exists(config_path)):
        os.makedirs(config_path)

    with open(os.path.join(config_path, 'config'), 'w') as f:
        f.write('[default]\nregion = {}'.format(region))
        f.close()

# Here we are storing the Job Definition Name to a file in the maloja.cache (uniquely appended with the UUID)
# It is later used in the deploy_jobDef function to deploy a jobdef with the exact same UUID
    with open(os.path.join(os.path.curdir, cache_dir, build_dir, 'jobDefName'), 'w') as f:
        f.write(jobDef_name)
        f.close()

    if platform == "win32":
        windows_to_linux_line_end(os.path.join(os.path.curdir, cache_dir, build_dir, '.aws', 'config'))
        windows_to_linux_line_end(os.path.join(os.path.curdir, cache_dir, build_dir, '.config', 'snakemake', 'aws-batch', 'batch-jobscript.sh'))
        windows_to_linux_line_end(os.path.join(os.path.curdir, cache_dir, build_dir, '.config', 'snakemake', 'aws-batch', 'batch-status.py'))
        windows_to_linux_line_end(os.path.join(os.path.curdir, cache_dir, build_dir, '.config', 'snakemake', 'aws-batch', 'batch-submit.py'))
        windows_to_linux_line_end(os.path.join(os.path.curdir, cache_dir, build_dir, '.config', 'snakemake', 'aws-batch', 'config.yaml'))

    # Bundle config into ZIP and upload to AWS S3
    shutil.make_archive(os.path.join(cache_dir, build_dir, 'Snakemake'), 'gztar', root_dir=os.path.join(os.path.curdir, cache_dir, build_dir), base_dir='.config')
    upload_file_to_s3(bucket_name, os.path.join(cache_dir, build_dir, 'Snakemake.tar.gz'), 'Snakemake.tar.gz')

    # Bundle local build dependencies into ZIP and upload to AWS S3
    if (local_build):
        shutil.make_archive(os.path.join(cache_dir, local_build), 'gztar', root_dir=os.path.join(local_build))
        upload_file_to_s3(bucket_name, f"{os.path.join(cache_dir, local_build)}.tar.gz", 'BuildDeps.tar.gz')
    else:
        local_build = "empty_build"
        os.makedirs(os.path.join(cache_dir, local_build), exist_ok=True)
        shutil.make_archive(os.path.join(cache_dir, local_build), 'gztar', root_dir=os.path.join(cache_dir, local_build))
        upload_file_to_s3(bucket_name, f"{os.path.join(cache_dir, local_build)}.tar.gz", 'BuildDeps.tar.gz')

    logging.info("Compute environment is ready.")
    
def run_aws_image_pipeline(pipeline_arn):
    # Create an Imagebuilder client
    imagebuilder = boto3.client('imagebuilder')

    try:
        # Start an image pipeline execution
        response = imagebuilder.start_image_pipeline_execution(
            imagePipelineArn=pipeline_arn
        )
        # The response contains the image build version ARN
        image_build_version_arn = response['imageBuildVersionArn']
        click.echo(f"Started image pipeline execution. Build version ARN: {image_build_version_arn}")
        
         # Wait for the image build to complete
        wait_for_image_build(imagebuilder, image_build_version_arn)

    except ClientError as error:
        click.echo(click.style(f"Failed to start image pipeline execution", fn='red'))
        logging.error(f"Failed to start image pipeline execution: {error}")


def wait_for_image_build(imagebuilder, image_build_version_arn, interval=120):
    click.echo("Waiting for image build to complete. This may take some time.")
    
    while True:
        # Get the current status of the image build
        response = imagebuilder.get_image(imageBuildVersionArn=image_build_version_arn)
        
        status = response['image']['state']['status']
            
        # Check if the status is a terminal state
        if status == 'AVAILABLE':
            click.echo("Image build completed successfully.")
            break
        elif status in ['CANCELLED', 'FAILED']:
            click.echo(f"Image build did not complete successfully. Status: {status}")
            if 'statusReason' in response['image']['state']:
                click.echo(f"Reason: {response['image']['state']['statusReason']}")
            break
    
        # Wait before polling again
        click.echo(f"Waiting for {interval} seconds before next check.")
        time.sleep(interval)

# Function to get the latest ECR image URI from an image pipeline
def get_latest_ecr_image_uri(imagebuilder,pipeline_arn):
    try:
        
        # Get the details of the Image Builder image version
        image_version_response = imagebuilder.get_image(imageBuildVersionArn=pipeline_arn)

        repository_name = image_version_response['image']['distributionConfiguration']['distributions'][0]['containerDistributionConfiguration']['targetRepository']['repositoryName']
        image_tag = 'latest'

        # Now, use the ECR client to get the repository URI
        ecr_client = boto3.client('ecr')

        # Get the repository details from ECR
        repository_response = ecr_client.describe_repositories(
            repositoryNames=[
                repository_name,
            ]
        )

        # Extract the repository URI
        repository_uri = repository_response['repositories'][0]['repositoryUri']

        # Construct the full ECR image URI
        ecr_image_uri = f"{repository_uri}:{image_tag}"
        click.echo(click.style(f"Docker image uri: {ecr_image_uri}",fg='green'))
        return None
    except ClientError as e:
            logging.error(f"An error occurred getting the ECR image URI: {e}")
            click.echo(click.style(f"An error occurred getting the ECR image URI", fg='red'))
            return None

@click.group()
def deploy():
    global CONFIG
    CONFIG = import_config()

def deploy_and_wait(cf_client,stack_name, deploy_func, shared=False, **kwargs):
    try:
        deploy_func(cf_client, CONFIG, **kwargs)
        # Assuming there's a function to print outputs or that the deploy functions handle it internally
    except ClientError as error:
        logging.error(error)
        click.echo(click.style("Error creating stack, please check the logs", fg='red'))

@click.command()
def roles():
    with create_cloudformation_client() as cf_client:
      deploy_and_wait(cf_client, "roles", deploy_roles, shared=True)
      write_role_output(cf_client,"roles",shared=True,config_file="amzn.yaml")

@click.command()
@click.option("-i", "--identity", "public_key", type=str)
def infrastructure(public_key):
    if public_key:
        CONFIG["infrastructure"]["publicKey"] = public_key
    
    with create_cloudformation_client() as cf_client:
      deploy_and_wait(cf_client,"vpc", deploy_network, shared=True)
      deploy_and_wait(cf_client,"batch", deploy_batch, shared=True)
      deploy_and_wait(cf_client,"imageInfrastructure", deploy_imageInfrastructure, shared=True)

@click.command()
@click.option("-t", "--instance-type", "instance_type", type=str)
@click.option("--local-deploy", "directory", type=str)
def pipeline(instance_type, directory):
    if instance_type:
        CONFIG["pipeline"]["landingZoneSize"] = instance_type
    if directory:
        CONFIG["pipeline"]["local_build"] = directory
    
    with create_cloudformation_client() as cf_client:
        deploy_and_wait(cf_client,"storage", deploy_storage)
        deploy_and_wait(cf_client,"imagePipeline", deploy_imagePipeline)
        deploy_and_wait(cf_client,"landingZone", deploy_landingZone)
        
        # Get the arn for the image and run it
        stack_name = embed_config(CONFIG, "imagePipeline")
        arn = get_cloudformation_output_value(cf_client, stack_name,"imagePipeline")
        run_aws_image_pipeline(arn)

@click.command()
def finalize():
    with create_cloudformation_client() as cf_client:
        deploy_jobDef(cf_client, CONFIG)

@click.command()
def clean():
    cookiecutter = os.path.join(".", "AWS-Batch_Snakemake-Profile", "cookiecutter.json")
    if (os.path.isdir("aws-batch")):
        shutil.rmtree("aws-batch")
    if (os.path.isfile(cookiecutter)):
        os.remove(cookiecutter)
    if (os.path.isdir("maloja.cache")):
        shutil.rmtree("maloja.cache")

@click.command()
@click.argument('bucket')
@click.argument('localfile')
@click.argument('remotefile')
def download(bucket, localfile, remotefile):
    bucket_name = bucket
    local_file_path = localfile
    s3_file_key = remotefile

    result = download_file_from_s3(bucket_name, s3_file_key, local_file_path)
    if result:
        click.echo("File download successful!")
    else:
        click.echo("File download failed.")

@click.command()
@click.argument('bucket')
@click.argument('localfile')
@click.argument('remotefile')
def upload(bucket, localfile, remotefile):
    bucket_name = bucket
    local_file_path = localfile
    s3_file_key = remotefile

    result = upload_file_to_s3(bucket_name, local_file_path, s3_file_key)
    if result:
        click.echo("File upload successful!")
    else:
        click.echo("File upload failed.")

deploy.add_command(roles)
deploy.add_command(infrastructure)
deploy.add_command(pipeline)
deploy.add_command(finalize)
deploy.add_command(clean)

deploy.add_command(upload)
deploy.add_command(download)

#@click.command()
#def clean_infrastructure():


#@click.command()
#def dry_run():


#try to define a god deployStack which takes input parameters, and also follows dependencies
deploy()
