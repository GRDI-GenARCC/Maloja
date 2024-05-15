The tutorial goes over a detailed list of steps for using Maloja to deploy a snakemake pipeline.
The following figure summarizes the four high level steps of deploying a pipeline.

![Use-Case-Diagram](https://github.com/hodgsonw/Maloja/assets/44032294/41811363-1fec-4860-b00d-aee154d663f3)

## Steps
1. Make sure local working direcory is `Maloja`
2. Activate the conda environment 
    ```shell
    conda activate snakemake_automator
    ```
3. Copy and paste the access tokens **from the AWS access portal's** `access keys` into the terminal. The tokens should look like this:
    ```shell
    export AWS_ACCESS_KEY_ID=
    export AWS_SECRET_ACCESS_KEY=
    export AWS_SESSION_TOKEN=
    ```
    - You also have to export your region to the terminal:
        ```shell
        export AWS_DEFAULT_REGION=ca-central-1
        ```
4. Update the amzn.yaml:
    - For the Metaworks pipeline:
    ```yaml
    pipeline:
        jobDefinition: AWS-Snake
        pipeline_url: https://github.com/terrimporter/MetaWorks
        pipeline_path: MetaWorks_v1.12.0
        name: Metaworks
        dockerFile: Dockerfile.metaworks_cloud
        landingZoneSize: m4.2xlarge
        local_build: local_pipelines/
    ```
    - Include your public IP. If you are on a VPN, use your VPN's public IP address. You can also use subnet masking (e.g. `/31` at the end of the IP address). To view your public IP address, type this command into your Linux terminal:
    ```shell
    curl ifconfig.me
    ```
5. If you wish to record cost details about your pipeline and the resources required to run the pipeline, do the following:
    - Record your current date and time now 
    - Open a new Linux terminal session
    - Paste the `export` commands from **step 3** (including the region) into this new terminal 
    - Activate the conda environment in the new terminal
        ```shell
        conda activate snakemake_automator
        ```
    - Run this command in the new terminal session:
        ```python
        python query_resource_groups.py
        ```
        - This will create a local `maloja.cache` folder (if it does not already existy), under the `cloud-poc-snakemake-manager` folder, with a file that has the following naming convention based on your `amzn.yaml` file: `[user:name]-[pipeline:name]_resources`
    - Let this script continue run in the new terminal as it is collecting AWS resource and pipeline information
6. In the original Linux terminal, enter these commands in the following order. Wait for one command to finish before entering the next command. This whole process can take roughly 30 minutes to complete:
    ```python
    python setup_environment.py infrastructure
    ```
    - **Only run this if it is your first time creating resources, or if the Maloja resources have been torn down** 
    - This will create `vpc` (3 minutes), `batch` (2 minutes), and `imageInfrastructure` (1 minute) resources on AWS with the stackname as `MALOJA-SHARED-[resource name]`
    - Resources can be viewed if you search for and open `cloud formation` in AWS
    ```python
    python setup_environment.py pipeline
    ```
    - This will create `storage`, `imagePipeline`, and `landingZone` resource with the naming convention as amzn.yaml's `[user:name]-[pipeline:name]-[resource name]`
    - The process will also build the image which can take up to roughly 45 minute
    - You should see messages in the terminal that look like this:
        ```shell
        > File uploaded successfully to s3:...Snakemake.tar.gz
        > File uploaded successfully to s3:...BuildDeps.tar.gz
        > Started image pipeline execution. Build version ARN: arn:aws:imagebuilder:ca-central-1:.../1.0.0/1
        > Waiting for image build to complete. This may take some time.
        > Waiting for 120 seconds before next check.
        > Waiting for 120 seconds before next check.
        ...
        > Image build completed successfully.
        ```

    ```python
    python setup_environment.py finalize
    ```
    - This creates a `jobdef` in AWS `cloud formation` with the naming convention as amzn.yaml's `[user:name]-[pipeline:name]-[resource name]`

You have now created all the required resources on AWS to run your pipeline. The next step is to access the `landingzone` you created, pull the Docker image, prepare the environment, and run the pipeline. 


We show here how to access the `landingzone` by means of `SSH`. But there are a number of ways to access the landing zone. 

7. To `SHH` into the landing zone, perform these steps in the following order:
    - Navigate to AWS `cloud formation`
    - Click on `[user:name]-[pipeline:name]-landingZone`
    - Click on the `Resources` tab
    - Click the landingZone `Physical ID` hyperlink
    - Click on the `Instance ID` link
    - Click `Connect` (in the top-right) to get the SSH command
        - This is where you can choose your preferred method to connect to the landing zone. Your options are `EC2 Instance Connect`, `Session Manager`, `SSH client`, and `EC2 serial console`
    - Click `SSH client` 
        - Follow the instruction on screen
        - Copy the `example` command at the bottom of the window
        - You may need to modify the `SnakemakeKey-xxxx.pem` part of the command to match where your local `id_rsa` file is instead
        - You may also need to specify your desired port in the `SSH` command
        - Some of the pipeline setup commands can take a while to finish executing. As such, it is recommended that you append `-o ServerAliveInterval=240` to the `SSH` command to prevent the client from kicking you out due to prolonged inactivity
        - Note: There will be a new address in this command each time you create a new landing zone
    - Enter your `SSH` command into your original Linux terminal
        - If the terminal ask you if you want to proceed, select `yes`

You should now be connected to the `landingZone` head node.

8. To set up the `landingZone` with your pipeline's docker image, do the following in order:
    - Enter the `Export` commands from **step 3** (including the region) again into the `SSH` session terminal
    - You now need to tell the `SSH` session to log into Docker. You can do this by entering the following command into the `SSH` terminal:
        ```ssh
        aws ecr get-login-password --region ca-central-1 | docker login --username AWS --password-stdin xxxx.dkr.ecr.ca-central-1.amazonaws.com
        ```
        - Where `xxxx` is your AWS account ID (without any spaces or dashes)
    - Obtain the `URI` of the pipeline by navigating on AWS to the `Elastic Container Registry` and copying the string of text under the `URI` column.
    - Enter the following command in the `SSH` terminal:
        ```shell
        docker pull [URI]
        ```
        - Where `[URI]` is the `URI` you obtained from the `Elastic Container Registry`
    - Wait for the downloads to finish. This can take a while
    - Run Docker with the following command:
        ```shell
        docker run --mount type=bind,source="$HOME"/mountpoint,target=/mnt/efs/snakemake -it --entrypoint="/bin/sh" [URI]
        ```
        - Where `[URI]` is the `URI` you obtained from the `Elastic Container Registry`

You will now be in an interactive docker session. 

9. Now initial data for the pipeline needs to be transferred from the image to the shared mount.
    ```bash
    cp -R /root/Snakemake/* /mnt/efs/snakemake
    ```
    - This command can take up to 20 minutes or more to complete depending on the size of the `/root/Snakemake/` directory

10. Enter the `Export` commands from **step 3** (including the region) one last time and additionally set the default region through 
	'export AWS_DEFAULT_REGION=[your-preferred-region]'

	Where [your-preferred-region] is something like us-east-2. This region should be geographically near to you to make data transfer less expensive.

11. 

At this point, you can make changes to the MetaWorks pipeline within the /mnt/efs/snakemake/ directory.

Some configurations need to be made to allow Maloja to allocate the appropriate resources for each job.

First, the default configured memory to the RDP tool needs to be increased from 8Gb to 16Gb.
In config_testing_COI_data.yaml, replace 'Xmx8g' with 'Xmx16g' on line 120.

Secondly, the snakefile needs definitions for memory size that Maloja can recognize.
For taxonomic assignment, we can add the following to the assignment rules on 335 and 272.

```
resources:
	mem_mb=16000
```

12. Cost Capturing

For evaluating the cost of an already run pipeline, Maloja uses AWS Resource Tagging to identify the relevant expenses to a specific pipeline.

Gathering the details from a resource tag involves the following steps.

	1. Before running the snakemake pipeline from the landing zone instance, take note of the time and date and then run the cost gathering script.
```
query_resource_groups.py
```
	2. Wait until the snakemake pipeline finishes running on AWS Batch
	3. Kill the python process running the cost gathering script.
	4. Take note of the time and date that the pipeline finished at.

The resource details will be written to a file named after your pipeline configuration, and inside the maloja.cache directory. If there doesn't exist a maloja.cache directory, one will be created in your current working directory.

	4. Accessing the Amazon Web Console will let you download a Cost and Usage report which contains the exact pricing information for all the costs accrued in your Amazon account. Depending on how you set up the Cost and Usage reports, the reports will be generated at recurring times as CSV files in a specified private S3 bucket within your account.
	
	5. Download the latest CSV file and modify the cost.py script to point to your pipeline's 'Resources' file located in maloja.cache, and to your latest Cost and Usage report, finally change the start and end date to match the start and end of your pipeline. Running cost.py will then output a simplified table relevant to your pipeline's cost in the maloja.cache directory.

13. Teardown

	Since Maloja is completely deployed using cloudformation templates, a teardown for the most part involves accessing the cloudformation service from the AWS Web Console and manually deleting stacks.

	The Maloja deployment itself will have 3 stacks that cannot be deleted until all pipeline specific stacks have been deleted.

	To teardown a pipeline you will need to delete the matching jobDef, imagePipeline, landingZone, and storage stacks. These stacks will be prefixed with your configured user and pipeline name.

	1. Delete the jobDef stack
	2. Ensure that ECR resource under the imagePipeline stack does not have any container images associated with it, this may involve deleting existing container images.
	3. Delete the imagePipeline stack
	4. Ensure the S3 bucket defined in the storage stack has nothing in it, this may involve deleting files from the bucket.
	5. delete the storage stack.
	6. delete the landing zone stack.

	Once there remain no pipeline stacks, you can delete the 'SHARED' Maloja stacks

	1. Delete the ImageInfrastructure stack
	2. Delete the Batch stack
	3. Delete the VPC stack

	The teardown is now complete.
	
14. Logging

	Logging related to Maloja can be found accross three AWS Services.

	The first source of logging is related to the building of a pipeline docker image.
	To view the docker build logs, navigate to AWS ImageBuilder, find the appropriate ...

	Logging the execution of a snakemake job is done by reviewing the appropriate Job that matches the JobID of the snakemake task. This is done by navigating the AWS Web Console to AWS Batch, and under Jobs, filtering for the relevant Job ID.

	Logging of the entire pipeline can also be viewed from the landing zone instance within the docker container that launched the pipeline. The snakemake folder located on the EFS will provide logging information for this.


15. Reestablishing Connection

	Sometimes the SSH client fails to maintain a connection between your local computer and the landing zone. When this happens, you will have to repeat the following steps to reconnect to the environment from which you launched the pipeline.

	1. SSH back to the ec2 instance.
	2. connect to the already running docker instance managing the snakemake execution.
	```
	docker start -ai [image name]
	```
	





