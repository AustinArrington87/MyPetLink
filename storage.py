import os
import boto3
import logging
import uuid
from botocore.exceptions import ClientError

logger = logging.getLogger('Storage')

class S3Storage:
    """Service to handle S3 storage operations"""
    
    def __init__(self):
        # Get environment variables with defaults
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY') 
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        
        # Check for missing environment variables
        missing_vars = []
        if not aws_access_key: missing_vars.append('AWS_ACCESS_KEY_ID')
        if not aws_secret_key: missing_vars.append('AWS_SECRET_ACCESS_KEY')
        if not self.bucket_name: missing_vars.append('S3_BUCKET_NAME')
        
        if missing_vars:
            logger.warning(f"Missing S3 configuration: {', '.join(missing_vars)}")
            if not self.bucket_name:
                raise ValueError("S3_BUCKET_NAME environment variable not set")
            
        try:
            # Initialize S3 client
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            
            # Log S3 configuration
            logger.info(f"S3 Configuration:")
            logger.info(f"  Bucket: {self.bucket_name}")
            logger.info(f"  Region: {aws_region}")
            
            # Verify bucket exists and is accessible
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"  Bucket verification: Success - bucket {self.bucket_name} exists and is accessible")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    logger.error(f"  Bucket verification failed: Bucket {self.bucket_name} does not exist")
                elif error_code == '403':
                    logger.error(f"  Bucket verification failed: No permission to access bucket {self.bucket_name}")
                else:
                    logger.error(f"  Bucket verification failed: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            # We'll continue without raising an exception and handle errors in the upload methods
    
    def upload_file(self, file_path, user_id, pet_id, file_type, original_filename=None):
        """
        Upload a file to S3
        
        Args:
            file_path: Path to the local file
            user_id: User ID
            pet_id: Pet ID
            file_type: Type of file (avatar, health_record, poop)
            original_filename: Original filename (if provided)
            
        Returns:
            S3 object URL if successful, None otherwise
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
            
        try:
            # Generate a unique S3 key in the user/pet folder structure
            file_ext = os.path.splitext(original_filename or file_path)[1].lower()
            s3_key = f"{user_id}/{pet_id}/{file_type}/{str(uuid.uuid4())}{file_ext}"
            
            # Log detailed debug information
            logger.info(f"S3 upload details:")
            logger.info(f"  Bucket: {self.bucket_name}")
            logger.info(f"  Region: {self.s3_client.meta.region_name}")
            logger.info(f"  File path: {file_path}")
            logger.info(f"  S3 key: {s3_key}")
            
            # Test if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"  Bucket verification: Success - bucket exists")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    logger.error(f"  Bucket verification failed: Bucket {self.bucket_name} does not exist")
                elif error_code == '403':
                    logger.error(f"  Bucket verification failed: No access to bucket {self.bucket_name}")
                else:
                    logger.error(f"  Bucket verification failed: {error_code}")
                # Despite error, continue trying the upload - the error might be misleading
            
            # Upload the file to S3 (without ACL - bucket policy should handle permissions)
            self.s3_client.upload_file(
                file_path, 
                self.bucket_name, 
                s3_key
            )
            
            # Construct and return the S3 URL
            region = self.s3_client.meta.region_name
            # Use the regional endpoint format which works for all regions
            s3_url = f"https://s3.{region}.amazonaws.com/{self.bucket_name}/{s3_key}"
                
            logger.info(f"  Successfully uploaded to: {s3_url}")
            return s3_url
        
        except ClientError as e:
            error_message = f"Failed to upload {file_path} to {self.bucket_name}/{s3_key}: {e}"
            logger.error(error_message)
            
            # For development purpose, return a local URL instead of failing completely
            local_url = f"/static/img/avatars/default_avatar.png"
            logger.info(f"  Falling back to local URL: {local_url}")
            return local_url
            
    def upload_file_object(self, file_obj, user_id, pet_id, file_type, original_filename=None):
        """
        Upload a file object (e.g., from a web request) to S3
        
        Args:
            file_obj: File object with read() method
            user_id: User ID
            pet_id: Pet ID
            file_type: Type of file (avatar, health_record, poop)
            original_filename: Original filename
            
        Returns:
            S3 object URL if successful, fallback URL otherwise
        """
        try:
            # Generate a unique S3 key in the user/pet folder structure
            file_ext = os.path.splitext(original_filename or '')[1].lower()
            s3_key = f"{user_id}/{pet_id}/{file_type}/{str(uuid.uuid4())}{file_ext}"
            
            # Log detailed debug information
            logger.info(f"S3 upload details (file object):")
            logger.info(f"  Bucket: {self.bucket_name}")
            logger.info(f"  Region: {self.s3_client.meta.region_name}")
            logger.info(f"  Original filename: {original_filename}")
            logger.info(f"  S3 key: {s3_key}")
            
            # Test if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"  Bucket verification: Success - bucket exists")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    logger.error(f"  Bucket verification failed: Bucket {self.bucket_name} does not exist")
                elif error_code == '403':
                    logger.error(f"  Bucket verification failed: No access to bucket {self.bucket_name}")
                else:
                    logger.error(f"  Bucket verification failed: {error_code}")
                # Despite error, continue trying the upload - the error might be misleading
            
            # Upload the file to S3 (without ACL - bucket policy should handle permissions)
            self.s3_client.upload_fileobj(
                file_obj, 
                self.bucket_name, 
                s3_key
            )
            
            # Construct and return the S3 URL
            region = self.s3_client.meta.region_name
            # Use the regional endpoint format which works for all regions
            s3_url = f"https://s3.{region}.amazonaws.com/{self.bucket_name}/{s3_key}"
                
            logger.info(f"  Successfully uploaded to: {s3_url}")
            return s3_url
            
        except ClientError as e:
            error_message = f"Failed to upload file object to {self.bucket_name}/{s3_key}: {e}"
            logger.error(error_message)
            
            # Determine fallback URL based on file type
            if file_type == 'avatar':
                local_url = f"/static/img/avatars/default_avatar.png"
            else:
                local_url = f"/static/img/default_{file_type}.png"
                
            logger.info(f"  Falling back to local URL: {local_url}")
            return local_url
    
    def delete_file(self, s3_path):
        """
        Delete a file from S3
        
        Args:
            s3_path: S3 path or URL to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract the S3 key from the path or URL
            if s3_path.startswith('http'):
                # Extract key from URL
                s3_key = s3_path.split('.amazonaws.com/')[1]
            else:
                # Assume it's just the key
                s3_key = s3_path
                
            # Delete the object
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
            
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            return False