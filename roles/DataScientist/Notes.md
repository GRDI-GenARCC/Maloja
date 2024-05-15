changes were made to these JSON during export from the amazon environment to remove the Amazon Account Number.
It would be important to check if it still works.

In DataScientist-Policy the AWS Account number was removed from lines 92 and 93, which pertain to elastic filesystem permissions. This was replaced with an '*' to indicate that any EFS is accessible to the user.

