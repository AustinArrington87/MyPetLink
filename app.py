from flask import Flask, render_template, request, jsonify, session, url_for, send_file, redirect
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
from gpt_agent import analyze_health_records, analyze_poop_image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from config import default_config
import logging
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import urllib.parse
import uuid
import json
from PIL import Image
import io
import time
import pyheif
import asyncio
from functools import partial, lru_cache
import base64
from email.mime.text import MIMEText
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re
import requests
from authlib.integrations.flask_client import OAuth
from werkzeug.security import generate_password_hash, check_password_hash
from jose import jwt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('HealthAnalysisApp')

# Load environment variables
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
    logger.info("Environment variables loaded from .env file")
else:
    logger.warning("No .env file found, using environment variables from system")

# Import after environment is loaded
from database import get_db_connection

# Initialize OpenAI client
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    organization=os.environ.get("OPENAI_ORG")
)
translation_api_key=os.environ.get("TRANSLATION_API_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", 'dev-secret-key-123')  # Required for session management

# Auth0 configuration
oauth = OAuth(app)
auth0 = oauth.register(
    'auth0',
    client_id=os.environ.get("AUTH0_CLIENT_ID"),
    client_secret=os.environ.get("AUTH0_CLIENT_SECRET"),
    api_base_url=f'https://{os.environ.get("AUTH0_DOMAIN")}',
    access_token_url=f'https://{os.environ.get("AUTH0_DOMAIN")}/oauth/token',
    authorize_url=f'https://{os.environ.get("AUTH0_DOMAIN")}/authorize',
    jwks_uri=f'https://{os.environ.get("AUTH0_DOMAIN")}/.well-known/jwks.json',
    server_metadata_url=f'https://{os.environ.get("AUTH0_DOMAIN")}/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid profile email',
    },
)

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'heic', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Store token and expiry globally (for demo; for production, use a better cache)
petfinder_token = None
petfinder_token_expiry = 0

def get_petfinder_token():
    global petfinder_token, petfinder_token_expiry
    if petfinder_token and time.time() < petfinder_token_expiry:
        return petfinder_token

    url = "https://api.petfinder.com/v2/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": os.environ.get("PETFINDER_CLIENT_ID"),
        "client_secret": os.environ.get("PETFINDER_CLIENT_SECRET")
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    token_data = resp.json()
    petfinder_token = token_data["access_token"]
    petfinder_token_expiry = time.time() + token_data["expires_in"] - 60  # buffer
    return petfinder_token

@lru_cache(maxsize=1)
def get_gmail_service():
    """Get Gmail service using credentials.json with caching"""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )
        
        # Add user impersonation
        delegated_credentials = credentials.with_subject('austin@plantgroup.co')
        
        return build(
            'gmail', 
            'v1', 
            credentials=delegated_credentials, 
            cache_discovery=False,
            # Add these parameters for better timeout handling
            static_discovery=False,
            num_retries=3
        )
    except Exception as e:
        logger.error(f"Error creating Gmail service: {str(e)}")
        raise

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class UserVitals:
    def __init__(self, data):
        self.blood_pressure = data.get('blood_pressure')
        self.bmi = data.get('bmi')
        self.height = data.get('height')
        self.weight = data.get('weight')

class User:
    def __init__(self, name, vitals_data, user_type='patient'):
        self.name = name
        self.vitals = UserVitals(vitals_data)
        self.type = user_type

def get_current_user():
    """Get current user data from session"""
    user_name = session.get('user_name', 'Guest')
    first_name, last_name = user_name.split(' ', 1) if ' ' in user_name else (user_name, '')
    
    # Get vitals from session or use defaults
    vitals_data = session.get('user_vitals', {
        'blood_pressure': '120/80',
        'bmi': '21.5',
        'height': "5'10\"",
        'weight': '150'
    })
    
    # Get user type from session or default to patient
    user_type = session.get('user_type', 'patient')

    return User(user_name, vitals_data, user_type)

# Auth0 routes
@app.route('/login')
def login():
    return auth0.authorize_redirect(redirect_uri=os.environ.get("AUTH0_CALLBACK_URL"))

@app.route('/callback')
def callback_handling():
    token = auth0.authorize_access_token()
    resp = auth0.get('userinfo')
    userinfo = resp.json()
    
    # Store user info in session
    session['jwt_payload'] = userinfo
    session['profile'] = {
        'user_id': userinfo['sub'],
        'name': userinfo.get('name', ''),
        'picture': userinfo.get('picture', ''),
        'email': userinfo.get('email', '')
    }
    
    # Extract first and last name for compatibility with existing code
    full_name = userinfo.get('name', 'Guest')
    session['user_name'] = full_name
    
    # Parse name for database storage
    name_parts = full_name.split(' ', 1) if ' ' in full_name else [full_name, '']
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ''
    
    # Store user in database
    from models import User
    from database import get_db_session, close_db_session
    
    db = get_db_session()
    try:
        # Check if user exists
        user = db.query(User).filter(User.auth0_id == userinfo['sub']).first()
        
        if not user:
            # Create new user
            user = User(
                auth0_id=userinfo['sub'],
                email=userinfo.get('email', ''),
                first_name=first_name,
                last_name=last_name,
                user_type='patient'  # Default user type
            )
            db.add(user)
            db.commit()
        
        # Store user ID in session for database operations (convert UUID to string)
        session['db_user_id'] = str(user.id)
    except Exception as e:
        db.rollback()
        logger.error(f"Error storing user in database: {e}")
    finally:
        close_db_session(db)
    
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    
    # Check environment to determine if we should force HTTPS
    env = os.environ.get("ENVIRONMENT", "development")
    
    # Get base URL - either from request or with url_for
    if env != "development" and request.host and not request.host.startswith('localhost'):
        # In production: Force HTTPS in the returnTo URL
        base_url = f"https://{request.host}"
        return_to = f"{base_url}/"
    else:
        # In development: Use whatever protocol was in the request
        return_to = url_for('home', _external=True)
    
    params = {
        'returnTo': return_to,
        'client_id': os.environ.get("AUTH0_CLIENT_ID")
    }
    
    logout_url = auth0.api_base_url + '/v2/logout?' + '&'.join([f'{key}={urllib.parse.quote(value)}' for key, value in params.items()])
    return redirect(logout_url)

def requires_auth(f):
    """Decorator to check if user is authenticated"""
    def decorated(*args, **kwargs):
        if 'profile' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

@app.route('/')
def home():
    # Get user name from session, default to "Guest" if not found
    user_name = session.get('user_name', 'Guest')
    is_authenticated = 'profile' in session
    
    # Get pet information for authenticated users
    pets = []
    active_pet = {}
    
    if is_authenticated:
        from models import Pet
        from database import get_db_session, close_db_session
        import uuid
        
        user_id = session.get('db_user_id')
        
        if user_id:
            # Convert string user_id to UUID for database
            try:
                user_id_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid UUID format in session.db_user_id: {user_id}")
                return redirect('/logout')  # Logout to reset session if ID is invalid
                
            db = get_db_session()
            try:
                # Get all pets for the user
                db_pets = db.query(Pet).filter(Pet.user_id == user_id_uuid).all()
                pets = [pet.to_dict() for pet in db_pets]
                
                # Get active pet
                active_pet_id = session.get('active_pet_id')
                
                if active_pet_id:
                    # Find active pet in the list (both IDs will be strings here)
                    for pet in pets:
                        if pet['id'] == active_pet_id:
                            active_pet = pet
                            break
                
                # If no active pet selected but pets exist, use the first one
                if not active_pet and pets:
                    active_pet = pets[0]
                    session['active_pet_id'] = active_pet['id']  # Store as string
                    
                    # Also update database to mark this pet as active
                    try:
                        # Convert back to UUID for database query
                        pet_id_uuid = uuid.UUID(active_pet['id'])
                        active_db_pet = db.query(Pet).filter(Pet.id == pet_id_uuid).first()
                        
                        if active_db_pet:
                            # Set all pets to inactive
                            db.query(Pet).filter(Pet.user_id == user_id_uuid).update({"is_active": False})
                            # Set selected pet to active
                            active_db_pet.is_active = True
                            db.commit()
                    except Exception as e:
                        logger.error(f"Error updating active pet: {e}")
            except Exception as e:
                logger.error(f"Error retrieving pets from database: {e}")
            finally:
                close_db_session(db)
    
    return render_template('home.html', 
                          user_name=user_name, 
                          is_authenticated=is_authenticated,
                          pets=pets,
                          active_pet=active_pet)

@app.route('/upload', methods=['POST'])
@requires_auth
def upload_file():
    db = None
    try:
        logger.info("Upload endpoint hit")
        if 'files[]' not in request.files:
            logger.error("No files in request")
            return jsonify({'success': False, 'error': 'No files uploaded'}), 400

        # Get user ID and active pet ID from session
        user_id = session.get('db_user_id')
        active_pet_id = session.get('active_pet_id')
        
        if not user_id or not active_pet_id:
            logger.error("Missing user_id or active_pet_id in session")
            return jsonify({'success': False, 'error': 'User or pet not found'}), 401

        files = request.files.getlist('files[]')
        logger.info(f"Received {len(files)} files")
        
        if not files:
            logger.error("Empty files list")
            return jsonify({'success': False, 'error': 'No files selected'}), 400

        # Import necessary modules
        from models import PetFile
        from database import get_db_session, close_db_session
        from storage import S3Storage
        
        # Initialize S3 storage client
        s3_storage = S3Storage()
        
        file_paths = []
        uploaded_files = []
        
        # Process files first (save locally and upload to S3)
        processed_files = []
        
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                logger.info(f"Processing file: {filename}")
                
                try:
                    # Save locally for AI processing
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    logger.info(f"Saving file to local filesystem: {file_path}")
                    file.save(file_path)
                    
                    # Get file size and content type
                    file_size = os.path.getsize(file_path)
                    content_type = file.content_type if hasattr(file, 'content_type') else 'application/octet-stream'
                    
                    # Upload to S3
                    logger.info(f"Uploading file to S3: {filename}")
                    file.seek(0)  # Rewind file for S3 upload
                    
                    s3_result = s3_storage.upload_file_object(
                        file,
                        user_id,
                        active_pet_id,
                        'health_record',
                        filename
                    )
                    
                    if s3_result:
                        processed_files.append({
                            'filename': filename,
                            'file_path': file_path,
                            's3_path': s3_result,
                            'content_type': content_type,
                            'file_size': file_size
                        })
                        file_paths.append(file_path)
                except Exception as file_error:
                    logger.error(f"Error processing file {filename}: {str(file_error)}")
                    return jsonify({'success': False, 'error': f'Error processing file {filename}: {str(file_error)}'}), 400
        
        # If no files were processed successfully, return an error
        if not processed_files:
            return jsonify({'success': False, 'error': 'No files were processed successfully'}), 400
        
        # Now save to database - each file in a separate transaction
        file_records = []
        
        for file_info in processed_files:
            # Get a fresh database session for each file to avoid transaction timeouts
            db = get_db_session()
            try:
                # Create database record
                pet_file = PetFile(
                    pet_id=active_pet_id,
                    file_type='health_record',
                    original_filename=file_info['filename'],
                    s3_path=file_info['s3_path'],
                    local_path=file_info['file_path'],
                    content_type=file_info['content_type'],
                    file_size=file_info['file_size']
                )
                
                db.add(pet_file)
                db.commit()
                file_records.append(pet_file)
                logger.info(f"Created database record for file: {file_info['filename']}")
            except Exception as db_error:
                if db:
                    db.rollback()
                logger.error(f"Database error saving file {file_info['filename']}: {str(db_error)}")
                # Continue with other files even if one fails to save to DB
            finally:
                if db:
                    close_db_session(db)
                    db = None
        
        # Now analyze the files
        logger.info(f"Analyzing files: {file_paths}")
        
        try:
            result = analyze_health_records(file_paths, document_type='vet_record')
            logger.info(f"Analysis result: {result}")
            
            # Update file records with analysis results - one at a time
            for pet_file in file_records:
                db = get_db_session()
                try:
                    # Fetch the record again to ensure it's still valid
                    updated_file = db.query(PetFile).filter(PetFile.id == pet_file.id).first()
                    if updated_file:
                        updated_file.analysis_json = result
                        db.commit()
                except Exception as analysis_db_error:
                    if db:
                        db.rollback()
                    logger.error(f"Database error updating analysis: {str(analysis_db_error)}")
                finally:
                    if db:
                        close_db_session(db)
                        db = None
            
            return jsonify(result)
        except Exception as analysis_error:
            logger.error(f"Error analyzing files: {str(analysis_error)}")
            # Return a success message with the issue
            return jsonify({
                'success': True, 
                'message': 'Files uploaded successfully but could not be analyzed',
                'error': str(analysis_error)
            })
            
    except Exception as e:
        if db:
            db.rollback()
            close_db_session(db)
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/profile')
@requires_auth
def profile():
    # Get user profile data
    user_profile = session.get('profile', {})
    user_id = session.get('db_user_id')
    
    if not user_id:
        return redirect('/login')  # Redirect if no user ID in session
    
    from models import Pet
    from database import get_db_session, close_db_session
    import uuid
    
    # Get pets and active pet from database
    pets = []
    active_pet = {}
    is_first_pet = True
    
    # Convert string user_id to UUID for database query
    try:
        user_id_uuid = uuid.UUID(user_id)
    except ValueError:
        logger.error(f"Invalid UUID format in session.db_user_id: {user_id}")
        return redirect('/logout')  # Logout to reset session if ID is invalid
    
    db = get_db_session()
    try:
        # Get all pets for the user
        db_pets = db.query(Pet).filter(Pet.user_id == user_id_uuid).all()
        pets = [pet.to_dict() for pet in db_pets]
        is_first_pet = len(pets) == 0
        
        # Get active pet
        if not is_first_pet:
            # First try to get pet marked as active in DB
            active_db_pet = db.query(Pet).filter(Pet.user_id == user_id_uuid, Pet.is_active == True).first()
            
            # If no active pet in DB but we have pets, mark the first one as active
            if not active_db_pet and db_pets:
                active_db_pet = db_pets[0]
                # Set all pets to inactive
                db.query(Pet).filter(Pet.user_id == user_id_uuid).update({"is_active": False})
                # Set first pet to active
                active_db_pet.is_active = True
                db.commit()
            
            if active_db_pet:
                active_pet = active_db_pet.to_dict()
                session['active_pet_id'] = active_pet['id']  # ID is already a string from to_dict()
    except Exception as e:
        logger.error(f"Error getting pets from database: {e}")
    finally:
        close_db_session(db)
    
    # For backward compatibility, also check old pet_profile format
    if is_first_pet and session.get('pet_profile'):
        old_pet = session.get('pet_profile', {})
        if old_pet:
            # We'll handle this migration when saving the pet profile
            is_migrating_old_pet = True
            active_pet = old_pet
                
    return render_template('profile.html', 
                          active_pet=active_pet,
                          pets=pets,
                          is_first_pet=is_first_pet,
                          user_profile=user_profile)

@app.route('/update_pet_profile', methods=['POST'])
@requires_auth
def update_pet_profile():
    try:
        # Get user ID from session
        user_id = session.get('db_user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not found'}), 401
        
        # Import requirements
        from models import Pet, PetFile
        from database import get_db_session, close_db_session
        import uuid
        
        # Convert string user_id to UUID for database operations
        try:
            user_id_uuid = uuid.UUID(user_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid user ID format'}), 400
            
        data = request.json
        
        # Get pet_id from request or generate new one
        pet_id = data.get('pet_id')
        is_new = not pet_id or pet_id == ''
        
        db = get_db_session()
        try:
            # Find existing pet or create a new one
            if is_new:
                # Process avatar if it's a base64 image
                avatar_data = data.get('avatar')
                avatar_url = None
                
                if avatar_data and isinstance(avatar_data, str) and avatar_data.startswith('data:'):
                    try:
                        # Import necessary modules for image processing
                        import base64
                        import io
                        from PIL import Image
                        import os
                        from storage import S3Storage
                        
                        # Extract image data from base64 string
                        image_format = avatar_data.split(';')[0].split('/')[1]
                        base64_data = avatar_data.split(',')[1]
                        
                        # Decode base64 data
                        image_data = base64.b64decode(base64_data)
                        
                        # Create a temporary file
                        temp_filename = f"temp_avatar_{uuid.uuid4()}.{image_format}"
                        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
                        
                        # Save image to temp file
                        with open(temp_path, 'wb') as f:
                            f.write(image_data)
                        
                        # Initialize S3 storage
                        s3_storage = S3Storage()
                        
                        # Create placeholder pet_id for S3 path
                        temp_pet_id = str(uuid.uuid4())
                        
                        # Upload to S3
                        s3_result = s3_storage.upload_file(
                            temp_path,
                            user_id,
                            temp_pet_id,  # We'll update this after pet creation
                            'avatar',
                            f"{data.get('pet_name', 'pet')}_avatar.{image_format}"
                        )
                        
                        # Get S3 URL
                        avatar_url = s3_result
                        
                        # Remove temp file
                        os.remove(temp_path)
                    except Exception as avatar_error:
                        logger.error(f"Error processing avatar image: {avatar_error}")
                        avatar_url = None
                elif avatar_data and not avatar_data.startswith('data:'):
                    # It's already a URL
                    avatar_url = avatar_data
                
                # Create new pet
                pet = Pet(
                    user_id=user_id_uuid,
                    name=data.get('pet_name', ''),
                    species=data.get('species', ''),
                    breed=data.get('breed', ''),
                    age_years=data.get('age', {}).get('years', 0) if data.get('age') else 0,
                    age_months=data.get('age', {}).get('months', 0) if data.get('age') else 0,
                    weight=data.get('weight'),
                    health_conditions=data.get('health_conditions', ''),
                    last_checkup=data.get('last_checkup'),
                    state=data.get('state', ''),
                    city=data.get('city', ''),
                    vet_clinic=data.get('vet_clinic', ''),
                    vet_phone=data.get('vet_phone', ''),
                    vet_address=data.get('vet_address', ''),
                    avatar_url=avatar_url,
                    is_active=True
                )
                
                # Set all pets to inactive
                db.query(Pet).filter(Pet.user_id == user_id_uuid).update({"is_active": False})
                
                # Add the new pet
                db.add(pet)
                db.commit()
                
                # Get the ID of the newly created pet (as string for JSON)
                pet_id = str(pet.id)
                
                # If we processed an avatar, create a PetFile record for it
                if avatar_url and pet_id:
                    try:
                        # Create pet file record
                        pet_file = PetFile(
                            pet_id=pet.id,  # Use the UUID object directly
                            file_type='avatar',
                            original_filename=f"{pet.name}_avatar.{image_format if 'image_format' in locals() else 'jpg'}",
                            s3_path=avatar_url,
                            content_type=f"image/{image_format if 'image_format' in locals() else 'jpeg'}"
                        )
                        db.add(pet_file)
                        db.commit()
                    except Exception as file_error:
                        logger.error(f"Error creating pet file record: {file_error}")
                        # Continue anyway since the pet was created successfully
            else:
                # Convert pet_id to UUID for database query
                try:
                    pet_id_uuid = uuid.UUID(pet_id)
                except ValueError:
                    return jsonify({'success': False, 'error': 'Invalid pet ID format'}), 400
                    
                # Find the existing pet
                pet = db.query(Pet).filter(Pet.id == pet_id_uuid, Pet.user_id == user_id_uuid).first()
                
                if not pet:
                    return jsonify({'success': False, 'error': 'Pet not found'}), 404
                
                # Update pet properties
                pet.name = data.get('pet_name', pet.name)
                pet.species = data.get('species', pet.species)
                pet.breed = data.get('breed', pet.breed)
                pet.age_years = data.get('age', {}).get('years', pet.age_years) if data.get('age') else pet.age_years
                pet.age_months = data.get('age', {}).get('months', pet.age_months) if data.get('age') else pet.age_months
                pet.weight = data.get('weight', pet.weight)
                pet.health_conditions = data.get('health_conditions', pet.health_conditions)
                pet.last_checkup = data.get('last_checkup', pet.last_checkup)
                pet.state = data.get('state', pet.state)
                pet.city = data.get('city', pet.city)
                pet.vet_clinic = data.get('vet_clinic', pet.vet_clinic)
                pet.vet_phone = data.get('vet_phone', pet.vet_phone)
                pet.vet_address = data.get('vet_address', pet.vet_address)
                
                # Only update avatar if provided and it's a base64 image
                avatar_data = data.get('avatar')
                if avatar_data and isinstance(avatar_data, str) and avatar_data.startswith('data:'):
                    try:
                        # Import necessary modules for image processing
                        import base64
                        import io
                        from PIL import Image
                        import os
                        from storage import S3Storage
                        
                        # Extract image data from base64 string
                        image_format = avatar_data.split(';')[0].split('/')[1]
                        base64_data = avatar_data.split(',')[1]
                        
                        # Decode base64 data
                        image_data = base64.b64decode(base64_data)
                        
                        # Create a temporary file
                        temp_filename = f"temp_avatar_{uuid.uuid4()}.{image_format}"
                        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
                        
                        # Save image to temp file
                        with open(temp_path, 'wb') as f:
                            f.write(image_data)
                        
                        # Initialize S3 storage
                        s3_storage = S3Storage()
                        
                        # Upload to S3
                        s3_result = s3_storage.upload_file(
                            temp_path,
                            user_id,
                            pet_id,
                            'avatar',
                            f"{pet.name or 'pet'}_avatar.{image_format}"
                        )
                        
                        # Get S3 URL
                        avatar_url = s3_result
                        
                        # Remove temp file
                        os.remove(temp_path)
                        
                        # Update pet's avatar URL
                        pet.avatar_url = avatar_url
                        
                        # Create pet file record
                        pet_file = PetFile(
                            pet_id=pet_id_uuid,
                            file_type='avatar',
                            original_filename=f"{pet.name or species}_avatar.{image_format}",
                            s3_path=avatar_url,
                            content_type=f"image/{image_format}"
                        )
                        
                        # Add file record to be committed with other changes
                        db.add(pet_file)
                    except Exception as avatar_error:
                        logger.error(f"Error processing avatar image: {avatar_error}")
                        # Continue with other updates even if avatar processing fails
                
                # Set all pets to inactive
                db.query(Pet).filter(Pet.user_id == user_id_uuid).update({"is_active": False})
                
                # Set this pet to active
                pet.is_active = True
                
                db.commit()
            
            # Update session with active pet ID
            session['active_pet_id'] = pet_id
            
            # Count the number of pets for this user
            pet_count = db.query(Pet).filter(Pet.user_id == user_id).count()
            
            return jsonify({
                'success': True,
                'pet_id': pet_id,
                'is_first_pet': pet_count == 1
            })
        except Exception as e:
            db.rollback()
            logger.error(f"Database error updating pet profile: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            close_db_session(db)
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_pets', methods=['GET'])
@requires_auth
def get_pets():
    try:
        user_id = session.get('db_user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not found'}), 401
            
        from models import Pet
        from database import get_db_session, close_db_session
        
        db = get_db_session()
        try:
            # Get all pets for the user
            db_pets = db.query(Pet).filter(Pet.user_id == user_id).all()
            pets = [pet.to_dict() for pet in db_pets]
            
            active_pet_id = session.get('active_pet_id')
            
            return jsonify({
                'success': True,
                'pets': pets,
                'active_pet_id': active_pet_id
            })
        except Exception as e:
            logger.error(f"Database error fetching pets: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            close_db_session(db)
    except Exception as e:
        logger.error(f"Error fetching pets: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
        
@app.route('/get_pet_files/<pet_id>', methods=['GET'])
@requires_auth
def get_pet_files(pet_id):
    try:
        user_id = session.get('db_user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not found'}), 401
            
        file_type = request.args.get('type', None)  # Optional file type filter
            
        from models import Pet, PetFile
        from database import get_db_session, close_db_session
        import uuid
        
        # Convert string IDs to UUIDs for database operations
        try:
            user_id_uuid = uuid.UUID(user_id)
            pet_id_uuid = uuid.UUID(pet_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid ID format'}), 400
        
        db = get_db_session()
        try:
            # First verify that the pet belongs to the user
            pet = db.query(Pet).filter(Pet.id == pet_id_uuid, Pet.user_id == user_id_uuid).first()
            
            if not pet:
                return jsonify({'success': False, 'error': 'Pet not found or not authorized'}), 404
                
            # Query files for the pet
            query = db.query(PetFile).filter(PetFile.pet_id == pet_id_uuid)
            
            # Apply file type filter if provided
            if file_type:
                query = query.filter(PetFile.file_type == file_type)
                
            # Sort by creation date, newest first
            query = query.order_by(PetFile.created_at.desc())
            
            # Execute query and convert to dictionaries
            files = [pet_file.to_dict() for pet_file in query.all()]
            
            return jsonify({
                'success': True,
                'files': files,
                'count': len(files)
            })
        except Exception as e:
            logger.error(f"Database error fetching pet files: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            close_db_session(db)
    except Exception as e:
        logger.error(f"Error fetching pet files: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
        
@app.route('/set_active_pet/<pet_id>', methods=['POST'])
@requires_auth
def set_active_pet(pet_id):
    try:
        user_id = session.get('db_user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not found'}), 401
        
        from models import Pet
        from database import get_db_session, close_db_session
        import uuid
        
        # Convert string IDs to UUIDs for database operations
        try:
            user_id_uuid = uuid.UUID(user_id)
            pet_id_uuid = uuid.UUID(pet_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid ID format'}), 400
        
        db = get_db_session()
        try:
            # Verify the pet belongs to the user
            pet = db.query(Pet).filter(Pet.id == pet_id_uuid, Pet.user_id == user_id_uuid).first()
            
            if not pet:
                return jsonify({'success': False, 'error': 'Pet not found'}), 404
            
            # Set all user's pets to inactive
            db.query(Pet).filter(Pet.user_id == user_id_uuid).update({"is_active": False})
            
            # Set this pet to active
            pet.is_active = True
            db.commit()
            
            # Update session (store as string)
            session['active_pet_id'] = str(pet_id_uuid)
            
            return jsonify({'success': True})
        except Exception as e:
            db.rollback()
            logger.error(f"Database error setting active pet: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            close_db_session(db)
            
    except Exception as e:
        logger.error(f"Error setting active pet: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/generate_pet_avatar', methods=['POST'])
@requires_auth
def generate_pet_avatar():
    try:
        data = request.json
        species = data.get('species', '')
        breed = data.get('breed', '')
        pet_name = data.get('pet_name', '')
        pet_id = data.get('pet_id', '')
        avatar_data = data.get('avatar', '')  # This may be a base64 image
        
        # Get user ID from session
        user_id = session.get('db_user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not found'}), 401
        
        # Import necessary modules
        import uuid
        import base64
        import io
        from PIL import Image
        import os
        from models import PetFile, Pet
        from database import get_db_session, close_db_session
        from storage import S3Storage
        
        # Convert user_id to UUID
        try:
            user_id_uuid = uuid.UUID(user_id)
            pet_id_uuid = uuid.UUID(pet_id) if pet_id else None
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid ID format'}), 400

        # Default avatar if no custom avatar is provided
        placeholder_avatars = {
            'dog': '/static/img/avatars/dog_avatar.png',
            'cat': '/static/img/avatars/cat_avatar.png',
            'bird': '/static/img/avatars/bird_avatar.png',
            'reptile': '/static/img/avatars/reptile_avatar.png',
            'fish': '/static/img/avatars/fish_avatar.png',
            'rabbit': '/static/img/avatars/rabbit_avatar.png',
            'ferret': '/static/img/avatars/ferret_avatar.png',
            'farm animal': '/static/img/avatars/farm_avatar.png'
        }
        
        # Default to a placeholder if no avatar data is provided
        if not avatar_data or not avatar_data.startswith('data:'):
            avatar_path = placeholder_avatars.get(species.lower(), '/static/img/avatars/default_avatar.png')
            avatar_url = avatar_path
            return jsonify({
                'success': True,
                'avatar_url': avatar_url
            })
        
        # Process base64 image data
        try:
            # Extract image data from base64 string
            # Format is typically: data:image/jpeg;base64,/9j/4AAQ...
            image_format = avatar_data.split(';')[0].split('/')[1]
            base64_data = avatar_data.split(',')[1]
            
            # Decode base64 data
            image_data = base64.b64decode(base64_data)
            
            # Create a temporary file
            temp_filename = f"temp_avatar_{uuid.uuid4()}.{image_format}"
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
            
            # Save image to temp file
            with open(temp_path, 'wb') as f:
                f.write(image_data)
            
            # Initialize S3 storage
            s3_storage = S3Storage()
            
            # Upload to S3
            s3_result = s3_storage.upload_file(
                temp_path,
                user_id,
                pet_id if pet_id else 'temp',
                'avatar',
                f"{pet_name or 'pet'}_avatar.{image_format}"
            )
            
            # Get S3 URL
            avatar_url = s3_result
            
            # Remove temp file
            os.remove(temp_path)
            
            # Update database if pet_id is provided
            if pet_id_uuid:
                db = get_db_session()
                try:
                    # Create pet file record
                    pet_file = PetFile(
                        pet_id=pet_id_uuid,
                        file_type='avatar',
                        original_filename=f"{pet_name or species}_avatar.{image_format}",
                        s3_path=avatar_url,
                        content_type=f"image/{image_format}"
                    )
                    
                    # Add file record
                    db.add(pet_file)
                    
                    # Update pet's avatar URL
                    pet = db.query(Pet).filter(Pet.id == pet_id_uuid).first()
                    if pet:
                        pet.avatar_url = avatar_url
                        
                    db.commit()
                except Exception as db_error:
                    db.rollback()
                    logger.error(f"Database error saving avatar: {db_error}")
                    return jsonify({'success': False, 'error': 'Database error'}), 500
                finally:
                    close_db_session(db)
            
            return jsonify({
                'success': True,
                'avatar_url': avatar_url
            })
            
        except Exception as e:
            logger.error(f"Error processing avatar image: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
            
    except Exception as e:
        logger.error(f"Avatar generation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/update_profile', methods=['POST'])
def update_profile():
    try:
        data = request.json
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        user_type = data.get('user_type', 'patient')
        
        # Combine names and store in session
        full_name = f"{first_name} {last_name}".strip()
        session['user_name'] = full_name
        session['user_type'] = user_type
        
        # Store vitals in session
        session['user_vitals'] = {
            'blood_pressure': data.get('vitals', {}).get('blood_pressure', '120/80'),
            'bmi': data.get('vitals', {}).get('bmi', '21.5'),
            'height': data.get('vitals', {}).get('height', "5'10\""),
            'weight': data.get('vitals', {}).get('weight', '150')
        }
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/export-pdf', methods=['POST'])
def export_pdf():
    try:
        data = request.json
        
        # Create a BytesIO buffer to receive PDF data
        buffer = BytesIO()
        
        # Create the PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        heading_style = styles['Heading2']
        normal_style = styles['Normal']
        
        # Create the document content
        content = []
        
        # Add title
        content.append(Paragraph("Health Record Analysis", title_style))
        content.append(Spacer(1, 20))
        
        # Add date
        date_str = datetime.now().strftime("%B %d, %Y")
        content.append(Paragraph(f"Generated on {date_str}", normal_style))
        content.append(Spacer(1, 20))
        
        # Add synopsis
        content.append(Paragraph("Synopsis", heading_style))
        content.append(Paragraph(data.get('synopsis', ''), normal_style))
        content.append(Spacer(1, 20))
        
        # Add insights and anomalies
        content.append(Paragraph("Insights and Anomalies", heading_style))
        content.append(Paragraph(data.get('insights_anomalies', ''), normal_style))
        content.append(Spacer(1, 20))
        
        # Add citations if available
        if data.get('citations'):
            content.append(Paragraph("Citations", heading_style))
            content.append(Paragraph(data.get('citations', ''), normal_style))
        
        # Build the PDF document
        doc.build(content)
        
        # Move to the beginning of the buffer
        buffer.seek(0)
        
        return send_file(
            buffer,
            download_name='health-analysis.pdf',
            as_attachment=True,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"PDF generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate PDF'}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message')
        
        if not user_message:
            return jsonify({'success': False, 'error': 'No message provided'}), 400

        # Get the default health chat prompt template ID
        default_prompt_id = '3c135563-13cd-452b-85a7-678209c961cb'  # Health Chat Default

        # Create a thread for the chat
        thread = client.beta.threads.create()
        
        # Add the user's message
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id="asst_bYxIi1SefCRrdHSHfByUtNjd"
        )

        # Wait for completion
        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run.status == 'completed':
                break
            elif run.status == 'failed':
                raise Exception("Chat response failed")

        # Get the assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        response = messages.data[0].content[0].text.value

        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                
                session_id = str(uuid.uuid4())
                default_user_id = str(uuid.uuid4())
                
                cur.execute("""
                    INSERT INTO chat_sessions 
                    (id, user_id, created_at, prompt_template_id, provider) 
                    VALUES (%s, %s, %s, %s, NULL)
                    RETURNING id
                """, (session_id, default_user_id, datetime.now(), default_prompt_id))
                
                conn.commit()
                
                # Store the messages
                cur.execute("""
                    INSERT INTO chat_messages 
                    (id, session_id, role, content, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    session_id,
                    'user',
                    user_message,
                    datetime.now()
                ))

                cur.execute("""
                    INSERT INTO chat_messages 
                    (id, session_id, role, content, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    session_id,
                    'assistant',
                    response,
                    datetime.now()
                ))

                conn.commit()
                cur.close()
                conn.close()
                
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}")
            # Continue even if database save fails

        return jsonify({
            "success": True,
            "response": response
        })

    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/save_intake_form', methods=['POST'])
def save_intake_form():
    try:
        form_data = request.get_json()
        
        # For now, just store in session (we can add database storage later)
        if 'intake_form' not in session:
            session['intake_form'] = {}
        
        session['intake_form'] = form_data
        
        # TODO: Add database storage here
        # db.session.add(...)
        # db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Form saved successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/get_intake_form', methods=['GET'])
def get_intake_form():
    try:
        form_data = session.get('intake_form', {})
        return jsonify({
            'success': True,
            'form_data': form_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/search_providers', methods=['GET'])
def search_providers():
    try:
        search_term = request.args.get('term', '').strip()
        state = request.args.get('state', '').strip()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Base query with column alias
        query = "SELECT provider as name, location, url FROM providers WHERE 1=1"
        params = []
        
        # Add search term condition if provided
        if search_term:
            query += " AND provider ILIKE %s"
            params.append(f'%{search_term}%')
        
        # Add state condition if provided
        if state:
            query += " AND location ILIKE %s"
            params.append(f'%{state}%')
        
        cur.execute(query, params)
        providers = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({'providers': providers})
        
    except Exception as e:
        print(f"Error searching providers: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_provider_url', methods=['GET'])
def get_provider_url():
    try:
        provider_name = request.args.get('provider')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Update query to use provider column
        cur.execute("SELECT url FROM providers WHERE provider = %s", (provider_name,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if result:
            return jsonify({'url': result['url']})
        else:
            return jsonify({'error': 'Provider not found'}), 404
            
    except Exception as e:
        print(f"Error getting provider URL: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyze_poop', methods=['POST'])
@requires_auth
def analyze_poop():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image uploaded'})

        # Get user ID and active pet ID from session
        user_id = session.get('db_user_id')
        active_pet_id = session.get('active_pet_id')
        
        if not user_id or not active_pet_id:
            logger.error("Missing user_id or active_pet_id in session")
            return jsonify({'success': False, 'error': 'User or pet not found'}), 401

        image = request.files['image']
        if not image.filename:
            return jsonify({'success': False, 'error': 'No image selected'})

        # Import necessary modules
        from models import PetFile
        from database import get_db_session, close_db_session
        from storage import S3Storage

        # Initialize S3 storage client
        s3_storage = S3Storage()

        # Secure filename
        filename = secure_filename(image.filename)
        
        # Save the image temporarily for analysis
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(temp_path)
        
        # Get file size and content type
        file_size = os.path.getsize(temp_path)
        content_type = image.content_type if hasattr(image, 'content_type') else 'image/jpeg'
        
        # Upload to S3
        logger.info(f"Uploading poop image to S3: {filename}")
        # Rewind file for S3 upload
        image.seek(0)
        
        s3_result = s3_storage.upload_file_object(
            image,
            user_id,
            active_pet_id,
            'poop',
            filename
        )
        
        # Create database record
        db = get_db_session()
        pet_file = None
        
        try:
            # Create file record
            pet_file = PetFile(
                pet_id=active_pet_id,
                file_type='poop',
                original_filename=filename,
                s3_path=s3_result,  # S3 URL
                local_path=temp_path,
                content_type=content_type,
                file_size=file_size
            )
            
            db.add(pet_file)
            db.commit()
            pet_file_id = pet_file.id
            logger.info(f"Created database record for poop image: {filename}")
            
            # Create a new event loop for running the async analysis
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            
            try:
                # Run the async function using run_until_complete
                analysis = new_loop.run_until_complete(analyze_poop_image(temp_path))
                
                # Update database record with analysis results
                pet_file = db.query(PetFile).filter(PetFile.id == pet_file_id).first()
                if pet_file:
                    pet_file.analysis_json = analysis
                    db.commit()
                
                return jsonify({
                    'success': True,
                    'result': {
                        'summary': analysis.get('summary', ''),
                        'concerns': analysis.get('concerns', ''),
                        'recommendations': analysis.get('recommendations', '')
                    },
                    'file_id': str(pet_file_id)  # Convert UUID to string for JSON
                })
            except Exception as analysis_error:
                logger.error(f"Analysis error: {str(analysis_error)}")
                # If analysis fails, still return success for the upload
                return jsonify({
                    'success': True,
                    'message': 'Image uploaded successfully but analysis failed',
                    'error': str(analysis_error)
                })
            finally:
                # Close the event loop
                new_loop.close()
                # We keep the file on the server for future reference
                # For production, you might want to implement a cleanup job
                
        except Exception as db_error:
            if db:
                db.rollback()
            logger.error(f"Database error: {str(db_error)}")
            return jsonify({'success': False, 'error': f'Database error: {str(db_error)}'}), 500
        finally:
            if db:
                close_db_session(db)

    except Exception as e:
        logger.error(f"Error analyzing poop image: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/breeds/<pet_type>')
def get_breeds(pet_type):
    # Comprehensive breed lists organized alphabetically
    breeds = {
        'dog': sorted([
            'Affenpinscher', 'Afghan Hound', 'Airedale Terrier', 'Akita', 'Alaskan Malamute',
            'American Bulldog', 'American Eskimo Dog', 'American Pit Bull Terrier', 'American Staffordshire Terrier',
            'Australian Cattle Dog', 'Australian Shepherd', 'Australian Terrier',
            'Basenji', 'Basset Hound', 'Beagle', 'Bearded Collie', 'Belgian Malinois',
            'Bernese Mountain Dog', 'Bichon Frise', 'Bloodhound', 'Border Collie', 'Border Terrier',
            'Boston Terrier', 'Boxer', 'Boykin Spaniel', 'Brittany', 'Brussels Griffon', 'Bull Terrier',
            'Bulldog', 'Bullmastiff',
            'Cairn Terrier', 'Cane Corso', 'Cavalier King Charles Spaniel', 'Chesapeake Bay Retriever',
            'Chihuahua', 'Chinese Crested', 'Chinese Shar-Pei', 'Chow Chow', 'Cocker Spaniel', 'Collie',
            'Corgi (Cardigan)', 'Corgi (Pembroke)', 'Dachshund', 'Dalmatian', 'Doberman Pinscher',
            'English Bulldog', 'English Setter', 'English Springer Spaniel',
            'French Bulldog',
            'German Shepherd', 'German Shorthaired Pointer', 'Giant Schnauzer', 'Golden Retriever',
            'Gordon Setter', 'Great Dane', 'Great Pyrenees', 'Greater Swiss Mountain Dog', 'Greyhound',
            'Havanese', 'Irish Setter', 'Irish Wolfhound', 'Italian Greyhound',
            'Jack Russell Terrier', 'Japanese Chin', 'Japanese Spitz',
            'Keeshond', 'Kerry Blue Terrier', 'Komondor', 'Kuvasz',
            'Labrador Retriever', 'Leonberger', 'Lhasa Apso',
            'Maltese', 'Mastiff', 'Miniature Pinscher', 'Miniature Schnauzer',
            'Newfoundland', 'Norfolk Terrier', 'Norwegian Elkhound', 'Norwich Terrier',
            'Old English Sheepdog', 'Papillon', 'Pekingese', 'Pharaoh Hound',
            'Pointer', 'Pomeranian', 'Poodle (Standard)', 'Poodle (Miniature)', 'Poodle (Toy)',
            'Portuguese Water Dog', 'Pug',
            'Rat Terrier', 'Rhodesian Ridgeback', 'Rottweiler',
            'Saint Bernard', 'Saluki', 'Samoyed', 'Schipperke', 'Scottish Terrier',
            'Shetland Sheepdog', 'Shiba Inu', 'Shih Tzu', 'Siberian Husky',
            'Silky Terrier', 'Smooth Fox Terrier', 'Soft Coated Wheaten Terrier',
            'Staffordshire Bull Terrier',
            'Standard Schnauzer',
            'Tibetan Mastiff', 'Tibetan Spaniel', 'Tibetan Terrier',
            'Toy Fox Terrier',
            'Vizsla',
            'Weimaraner', 'Welsh Springer Spaniel', 'West Highland White Terrier',
            'Whippet',
            'Wire Fox Terrier',
            'Yorkshire Terrier'
        ]),
        'cat': sorted([
            'Abyssinian', 'American Bobtail', 'American Curl', 'American Shorthair', 'American Wirehair',
            'Balinese', 'Bengal', 'Birman', 'Bombay', 'British Longhair', 'British Shorthair', 'Burmese',
            'Chartreux', 'Chausie', 'Cornish Rex', 'Cyprus',
            'Devon Rex', 'Egyptian Mau', 'European Shorthair', 'Exotic Shorthair',
            'Havana Brown', 'Himalayan',
            'Japanese Bobtail',
            'Korat',
            'LaPerm', 'Maine Coon', 'Manx', 'Munchkin',
            'Norwegian Forest Cat',
            'Ocicat', 'Oriental Longhair', 'Oriental Shorthair',
            'Persian',
            'Ragamuffin', 'Ragdoll', 'Russian Blue',
            'Savannah', 'Scottish Fold', 'Selkirk Rex', 'Siamese', 'Siberian', 'Singapura',
            'Snowshoe', 'Somali', 'Sphynx',
            'Thai', 'Tonkinese', 'Turkish Angora', 'Turkish Van'
        ]),
        'bird': sorted([
            'African Grey Parrot', 'Amazon Parrot', 'Australian King Parrot',
            'Budgerigar (Budgie)',
            'Caique', 'Canary', 'Cockatiel', 'Cockatoo (Umbrella)', 'Cockatoo (Sulfur-crested)',
            'Conure (Green Cheek)', 'Conure (Sun)', 'Conure (Blue-crowned)',
            'Diamond Dove',
            'Eclectus Parrot',
            'Finch (Zebra)', 'Finch (Society)', 'Finch (Gouldian)',
            'Indian Ringneck Parakeet',
            'Lovebird (Peach-faced)', 'Lovebird (Fischer\'s)', 'Lovebird (Masked)',
            'Macaw (Blue and Gold)', 'Macaw (Scarlet)', 'Macaw (Green-winged)', 'Macaw (Hyacinth)',
            'Meyer\'s Parrot',
            'Pacific Parrotlet',
            'Pionus Parrot',
            'Quaker Parrot',
            'Rainbow Lorikeet', 'Red-factor Canary',
            'Senegal Parrot',
            'White-capped Pionus',
            'Yellow-naped Amazon'
        ]),
        'reptile': sorted([
            'African Fat-tailed Gecko', 'African Spurred Tortoise',
            'Ball Python', 'Bearded Dragon', 'Blue-tongued Skink', 'Boa Constrictor',
            'California Kingsnake', 'Carpet Python', 'Chameleon (Veiled)', 'Chameleon (Panther)',
            'Corn Snake', 'Crested Gecko',
            'Eastern Box Turtle', 'Emerald Tree Boa',
            'Fire Skink',
            'Garter Snake', 'Gecko (Mediterranean)', 'Green Anole', 'Green Iguana',
            'Hermann\'s Tortoise',
            'Jackson\'s Chameleon',
            'Kenyan Sand Boa', 'King Snake',
            'Leopard Gecko', 'Leopard Tortoise',
            'Mali Uromastyx',
            'Painted Turtle',
            'Red-eared Slider', 'Red-footed Tortoise', 'Rosy Boa', 'Russian Tortoise',
            'Savannah Monitor',
            'Tegu (Argentine Black and White)', 'Tokay Gecko',
            'Water Dragon', 'Western Hognose Snake'
        ]),
        'fish': sorted([
            'Angelfish', 'Arowana',
            'Barb (Tiger)', 'Betta', 'Black Moor Goldfish', 'Black Skirt Tetra', 'Blue Gourami',
            'Cardinal Tetra', 'Clownfish', 'Corydoras Catfish',
            'Danio (Zebra)', 'Discus', 'Dwarf Gourami',
            'Fancy Guppy', 'Firemouth Cichlid',
            'German Blue Ram', 'Goldfish',
            'Harlequin Rasbora',
            'Jack Dempsey Cichlid',
            'Killifish', 'Koi',
            'Lionfish',
            'Molly (Black)', 'Molly (Sailfin)',
            'Neon Tetra',
            'Oscar',
            'Platy', 'Plecostomus',
            'Rainbow Shark', 'Rainbowfish',
            'Siamese Algae Eater', 'Silver Dollar', 'Swordtail',
            'Tiger Barb',
            'White Cloud Mountain Minnow'
        ]),
        'rabbit': sorted([
            'American Fuzzy Lop', 'American Sable',
            'Belgian Hare', 'Beveren',
            'Californian',
            'Dutch',
            'English Angora', 'English Lop', 'English Spot',
            'Flemish Giant', 'Florida White', 'French Angora', 'French Lop',
            'Giant Angora', 'Giant Chinchilla',
            'Harlequin', 'Havana', 'Holland Lop', 'Hotot',
            'Jersey Wooly',
            'Lilac',
            'Mini Lop', 'Mini Rex', 'Mini Satin',
            'Netherland Dwarf', 'New Zealand',
            'Polish',
            'Rex',
            'Satin', 'Silver Fox', 'Silver Marten',
            'Standard Chinchilla',
            'Tan', 'Thrianta'
        ]),
        'ferret': sorted([
            'Albino', 'Black', 'Black Sable', 'Champagne',
            'Chocolate', 'Cinnamon', 'Dark-Eyed White',
            'Panda', 'Point', 'Sable',
            'Silver', 'Standard (Sable)', 'White'
        ]),
        'farm animal': sorted([
            'Alpaca',
            'Chicken (Ameraucana)', 'Chicken (Australorp)', 'Chicken (Brahma)', 'Chicken (Leghorn)', 'Chicken (Orpington)', 'Chicken (Plymouth Rock)', 'Chicken (Rhode Island Red)', 'Chicken (Silkie)', 'Chicken (Sussex)', 'Chicken (Wyandotte)',
            'Cow (Angus)', 'Cow (Holstein)', 'Cow (Jersey)',
            'Donkey',
            'Duck (Pekin)', 'Duck (Rouen)', 'Duck (Runner)',
            'Goat (Alpine)', 'Goat (Boer)', 'Goat (LaMancha)', 'Goat (Nigerian Dwarf)', 'Goat (Nubian)',
            'Horse (American Quarter)', 'Horse (Arabian)', 'Horse (Morgan)', 'Horse (Paint)', 'Horse (Thoroughbred)',
            'Llama',
            'Pig (Berkshire)', 'Pig (Duroc)', 'Pig (Hampshire)', 'Pig (Potbelly)', 'Pig (Yorkshire)',
            'Sheep (Dorper)', 'Sheep (Hampshire)', 'Sheep (Merino)', 'Sheep (Suffolk)'
        ])
    }
    return jsonify(breeds.get(pet_type, []))

@app.route('/get_training_tips', methods=['POST'])
def get_training_tips():
    try:
        data = request.json
        species = data.get('species')
        breed = data.get('breed')
        
        if not species or not breed:
            return jsonify({'success': False, 'error': 'Species and breed are required'}), 400

        # Create a more specific prompt
        prompt = f"""As a veterinary expert, please provide detailed training and care tips for a {breed} {species}. 
        If you're not familiar with this specific breed, provide general tips for {species} while incorporating any known traits of similar breeds.

        Please format your response with these sections:

        Training Tips:
        • Basic Training: Focus on essential commands and techniques specific to {breed}s
        • Behavioral Tips: Common {breed} traits and how to manage them
        • Training Methods: Most effective approaches for this breed

        Exercise & Play:
        • Exercise Needs: Daily requirements based on {breed} energy levels
        • Play Activities: Best games and toys for this breed
        • Exercise Tips: Special considerations for {breed}s

        Enrichment Activities:
        • Mental Stimulation: Puzzle and learning activities suited for {breed}s
        • Environmental Enrichment: Creating an engaging space
        • Social Enrichment: Interaction needs and socialization tips

        Please be specific to the breed when possible, and provide general {species} advice when breed-specific information is limited."""

        # Create thread and send to GPT
        thread = client.beta.threads.create()
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id="asst_bYxIi1SefCRrdHSHfByUtNjd"
        )

        # Wait for completion
        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run.status == 'completed':
                break
            elif run.status == 'failed':
                raise Exception("Failed to generate training tips")

        # Get the response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        response = messages.data[0].content[0].text.value

        # Parse sections
        sections = response.split('\n\n')
        result = {
            'training': '',
            'play': '',
            'enrichment': ''
        }

        current_section = None
        for section in sections:
            if 'Training Tips:' in section:
                current_section = 'training'
                result['training'] = section
            elif 'Exercise & Play:' in section:
                current_section = 'play'
                result['play'] = section
            elif 'Enrichment Activities:' in section:
                current_section = 'enrichment'
                result['enrichment'] = section
            elif current_section:
                result[current_section] += '\n' + section

        return jsonify({
            'success': True,
            'result': result
        })

    except Exception as e:
        logger.error(f"Training tips error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add this helper function to extract zipcode
def extract_zipcode(address):
    """Extract zipcode from address string. Returns None if no zipcode found."""
    # Look for 5-digit number at the end of the address
    zipcode_match = re.search(r'\b\d{5}\b(?![\d-])', address)
    if zipcode_match:
        return zipcode_match.group(0)
    return None

@app.route('/report-rescue', methods=['POST'])
def report_rescue():
    logger.info("Received rescue report request")
    
    try:
        data = request.json
        logger.info(f"Received data: {data}")
        
        # Generate UUID for ticket
        ticket_id = str(uuid.uuid4())
        
        # Get current date
        current_date = datetime.now().date()
        logger.info(f"Creating ticket for date: {current_date}")
        
        # Extract zipcode from location
        zipcode = extract_zipcode(data['location'])
        logger.info(f"Extracted zipcode: {zipcode}")
        
        # Store in database
        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                
                # Get species and breed directly from form data
                species = data.get('species', '')  # Remove 'Unknown' fallback
                breed = data.get('breed', '')      # Remove 'Unknown Breed' fallback
                ticket_name = f"{species} - {breed}" if species and breed else "Unspecified Animal"
                
                logger.info(f"Creating ticket with species: {species}, breed: {breed}")
                
                cur.execute("""
                    INSERT INTO rescue_tickets 
                    (id, zipcode, description, ticket_name, contact_email, contact_name, 
                     contact_phone, contact_address, date, species, breed)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    ticket_id,
                    zipcode,
                    data.get('description', ''),
                    ticket_name,
                    data.get('email', ''),
                    data.get('name', ''),
                    data.get('phone', ''),
                    data.get('location', ''),
                    current_date,
                    species,    # Add species to database
                    breed      # Add breed to database
                ))
                
                conn.commit()
                cur.close()
                conn.close()
                
                logger.info(f"Rescue ticket {ticket_id} stored in database with species: {species}, breed: {breed}")
                
                # Return success immediately after database write
                return jsonify({
                    'success': True,
                    'message': 'Your rescue report has been submitted successfully. Thank you for helping!',
                    'ticket_id': ticket_id
                })
                
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to store report. Please try again.'
            }), 500
            
    except Exception as e:
        logger.error(f"Request processing error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to submit report. Please try again or contact support.'
        }), 500

# Note: Gmail code has been removed. If you want to re-enable it later, 
# it can be added back after the database operation succeeds.

@app.route('/search-rescues', methods=['GET'])
def search_rescues():
    try:
        zipcode = request.args.get('zipcode', '').strip()
        
        if not zipcode or not zipcode.isdigit() or len(zipcode) != 5:
            return jsonify({
                'success': False,
                'error': 'Please provide a valid 5-digit zipcode'
            }), 400
        
        conn = get_db_connection()
        if conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT id, species, breed, description, date, ticket_name, 
                       contact_name, contact_phone, contact_email, contact_address, zipcode
                FROM rescue_tickets 
                WHERE zipcode = %s
                ORDER BY date DESC
            """, (zipcode,))
            
            rescues = cur.fetchall()
            
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'rescues': rescues
            })
            
    except Exception as e:
        logger.error(f"Error searching rescues: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to search rescues. Please try again.'
        }), 500

@app.route('/api/petfinder/organizations', methods=['GET'])
def petfinder_organizations():
    zipcode = request.args.get('zipcode', '').strip()
    if not zipcode or not zipcode.isdigit() or len(zipcode) != 5:
        return jsonify({'success': False, 'error': 'Please provide a valid 5-digit zipcode'}), 400

    try:
        token = get_petfinder_token()
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "location": zipcode,
            "distance": 50,  # miles, adjust as needed
            "limit": 5
        }
        resp = requests.get("https://api.petfinder.com/v2/organizations", headers=headers, params=params)
        resp.raise_for_status()
        orgs = resp.json().get("organizations", [])
        return jsonify({'success': True, 'organizations': orgs})
    except Exception as e:
        logger.error(f"PetFinder API error: {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch organizations from PetFinder.'}), 500

# US Cities data (abbreviated list for common cities)
US_CITIES = {
    'AL': ['Birmingham', 'Montgomery', 'Huntsville', 'Mobile', 'Tuscaloosa'],
    'AK': ['Anchorage', 'Fairbanks', 'Juneau', 'Sitka', 'Wasilla'],
    'AZ': ['Phoenix', 'Tucson', 'Mesa', 'Chandler', 'Scottsdale'],
    'AR': ['Little Rock', 'Fort Smith', 'Fayetteville', 'Springdale', 'Jonesboro'],
    'CA': ['Los Angeles', 'San Francisco', 'San Diego', 'Sacramento', 'San Jose'],
    'CO': ['Denver', 'Colorado Springs', 'Aurora', 'Fort Collins', 'Boulder'],
    'CT': ['Hartford', 'New Haven', 'Stamford', 'Bridgeport', 'Waterbury'],
    'DE': ['Wilmington', 'Dover', 'Newark', 'Middletown', 'Smyrna'],
    'FL': ['Miami', 'Orlando', 'Tampa', 'Jacksonville', 'Tallahassee'],
    'GA': ['Atlanta', 'Savannah', 'Augusta', 'Athens', 'Macon'],
    'HI': ['Honolulu', 'Hilo', 'Kailua', 'Kaneohe', 'Waipahu'],
    'ID': ['Boise', 'Nampa', 'Meridian', 'Idaho Falls', 'Pocatello'],
    'IL': ['Chicago', 'Springfield', 'Peoria', 'Rockford', 'Champaign'],
    'IN': ['Indianapolis', 'Fort Wayne', 'Evansville', 'South Bend', 'Bloomington'],
    'IA': ['Des Moines', 'Cedar Rapids', 'Davenport', 'Sioux City', 'Iowa City'],
    'KS': ['Wichita', 'Kansas City', 'Topeka', 'Olathe', 'Lawrence'],
    'KY': ['Louisville', 'Lexington', 'Bowling Green', 'Owensboro', 'Covington'],
    'LA': ['New Orleans', 'Baton Rouge', 'Shreveport', 'Lafayette', 'Lake Charles'],
    'ME': ['Portland', 'Lewiston', 'Bangor', 'South Portland', 'Auburn'],
    'MD': ['Baltimore', 'Annapolis', 'Frederick', 'Rockville', 'Gaithersburg'],
    'MA': ['Boston', 'Worcester', 'Springfield', 'Cambridge', 'Lowell'],
    'MI': ['Detroit', 'Grand Rapids', 'Ann Arbor', 'Lansing', 'Flint'],
    'MN': ['Minneapolis', 'St. Paul', 'Rochester', 'Duluth', 'Bloomington'],
    'MS': ['Jackson', 'Gulfport', 'Southaven', 'Hattiesburg', 'Biloxi'],
    'MO': ['Kansas City', 'St. Louis', 'Springfield', 'Columbia', 'Independence'],
    'MT': ['Billings', 'Missoula', 'Great Falls', 'Bozeman', 'Helena'],
    'NE': ['Omaha', 'Lincoln', 'Bellevue', 'Grand Island', 'Kearney'],
    'NV': ['Las Vegas', 'Reno', 'Henderson', 'Carson City', 'Sparks'],
    'NH': ['Manchester', 'Nashua', 'Concord', 'Dover', 'Rochester'],
    'NJ': ['Newark', 'Jersey City', 'Paterson', 'Elizabeth', 'Trenton'],
    'NM': ['Albuquerque', 'Santa Fe', 'Las Cruces', 'Rio Rancho', 'Roswell'],
    'NY': ['New York City', 'Buffalo', 'Rochester', 'Syracuse', 'Albany'],
    'NC': ['Charlotte', 'Raleigh', 'Greensboro', 'Durham', 'Winston-Salem'],
    'ND': ['Fargo', 'Bismarck', 'Grand Forks', 'Minot', 'West Fargo'],
    'OH': ['Columbus', 'Cleveland', 'Cincinnati', 'Toledo', 'Akron'],
    'OK': ['Oklahoma City', 'Tulsa', 'Norman', 'Broken Arrow', 'Edmond'],
    'OR': ['Portland', 'Salem', 'Eugene', 'Gresham', 'Hillsboro'],
    'PA': ['Philadelphia', 'Pittsburgh', 'Allentown', 'Erie', 'Reading'],
    'RI': ['Providence', 'Warwick', 'Cranston', 'Pawtucket', 'East Providence'],
    'SC': ['Columbia', 'Charleston', 'Greenville', 'Myrtle Beach', 'Rock Hill'],
    'SD': ['Sioux Falls', 'Rapid City', 'Aberdeen', 'Brookings', 'Watertown'],
    'TN': ['Nashville', 'Memphis', 'Knoxville', 'Chattanooga', 'Clarksville'],
    'TX': ['Houston', 'Dallas', 'Austin', 'San Antonio', 'Fort Worth'],
    'UT': ['Salt Lake City', 'West Valley City', 'Provo', 'West Jordan', 'Orem'],
    'VT': ['Burlington', 'South Burlington', 'Rutland', 'Essex Junction', 'Bennington'],
    'VA': ['Virginia Beach', 'Richmond', 'Norfolk', 'Chesapeake', 'Newport News'],
    'WA': ['Seattle', 'Spokane', 'Tacoma', 'Vancouver', 'Bellevue'],
    'WV': ['Charleston', 'Huntington', 'Morgantown', 'Parkersburg', 'Wheeling'],
    'WI': ['Milwaukee', 'Madison', 'Green Bay', 'Kenosha', 'Racine'],
    'WY': ['Cheyenne', 'Casper', 'Laramie', 'Gillette', 'Rock Springs'],
    'DC': ['Washington']
}

@app.route('/api/cities/<state>')
def get_cities(state):
    """Get cities for a given state"""
    if state not in US_CITIES:
        return jsonify([])
    return jsonify(sorted(US_CITIES[state]))

if __name__ == '__main__':
    app.run(debug=True, port=5001, use_reloader=True)
