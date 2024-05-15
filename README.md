# Maloja
This project provides a command line interface for automating the deployment, management and usage of cloud infrastructure for multiple different high performance pipelines in a single AWS account. As an output of the GenARCC project, Maloja is developed and tested for use with bioinformatics software. It should however be able to deploy any Snakemake pipeline. Future steps for the project may include supporting Nextflow pipelines.

Because AWS cost and usage analyzer only provides cost summaries to the account, Maloja also provides methods for tracking the costing information for seperate pipelines in an account to allow users to analyze the unique cost of a pipeline.

## Detailed Overview
The project leverages AWS Batch for providing autoscaling compute resources to meet the hardware requirements of the currently active jobs. Temporary shared filesystem storage can be mounted through the AWS EFS service, and input and outputs to the pipelines are stored in S3 buckets.
Software environments are provided through docker images which are defined locally. The dockerfiles are uploaded to AWS and built using the ImageBuilder service.

Coordination of these resources is done through local configurations and processes associated with the install of this tool.
The main utility is the maloja python script, which provides a command line interface for initializing the AWS environment with all the resources required to run a pipeline.

**Note :** Currently no support for GPU acceleration

![Architecture-Diagram](AWS-Cloud-Architecture.png)

## Install Instructions
All dependencies are resolved through conda on conda-forge.

Install the 'snakemake_automator' environment with:
``` 
conda env create -f snakemake_automator_env.yaml
```

## Configuration
Pipelines can be configured and run by any user within the account, but the initial deployment and configuration of the system is done by a priveleged user. Both the priveleged user and regular user roles are distinct from the account owner. The permissions of the priveleged user are not yet restricted in any way, but the expected permissions of the regular user are defined in the '/roles/DataScientist' directory.

Configuration of the tool is done through the file 'amzn.yaml' or via command line options. An example configuration exists in 'amzn.yaml.template' which can be copied and filled with details about the user, pipeline, and account.

A further and more detailed breakdown of the usage of Maloja can be found [under TUTORIAL.md](./TUTORIAL.md) where a step by step account is given of running the metabarcoding pipeline [MetaWorks](https://github.com/terrimporter/MetaWorks).

## Contributions
**Disclaimer:** This project is completed and developers may not be able to resolve submitted issues in any specific timeframe.

Any issues with the project can be submitted to this repository for review and are greatly appreciated.

## License
Maloja is released under the Apache 2 [License](./LICENSE).
