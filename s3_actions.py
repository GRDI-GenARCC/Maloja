#!/bin/env python

import boto3

def upload_file_to_s3(bucket_name, local_file_path, s3_file_key):
    """
    Upload a file to an Amazon S3 bucket.

    Parameters:
        bucket_name (str): The name of the S3 bucket to upload the file to.
        local_file_path (str): The local file path of the file to be uploaded.
        s3_file_key (str): The key or name of the file in the S3 bucket.

    Returns:
        bool: True if the upload is successful, False otherwise.
    """
    try:
        # Create an S3 client
        s3 = boto3.client('s3')

        # Upload the file to the S3 bucket
        s3.upload_file(local_file_path, bucket_name, s3_file_key)

        print(f"File uploaded successfully to s3://{bucket_name}/{s3_file_key}")
        return True

    except Exception as e:
        print(f"Error uploading file to S3: {e}")
        return False


def download_file_from_s3(bucket_name, s3_file_key, local_file_path):
    """
    Download a single file from an Amazon S3 bucket.

    Parameters:
        bucket_name (str): The name of the S3 bucket.
        s3_file_key (str): The key or name of the file in the S3 bucket.
        local_file_path (str): The local file path to save the downloaded file.

    Returns:
        bool: True if the download is successful, False otherwise.
    """
    try:
        # Create an S3 client
        s3 = boto3.client('s3')

        # Download the file from the S3 bucket
        s3.download_file(bucket_name, s3_file_key, local_file_path)

        print(f"File downloaded successfully from s3://{bucket_name}/{s3_file_key} to {local_file_path}")
        return True

    except Exception as e:
        print(f"Error downloading file from S3: {e}")
        return False
