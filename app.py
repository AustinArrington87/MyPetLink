from flask import Flask, render_template, request, jsonify, session, url_for, send_file
from werkzeug.utils import secure_filename
import os
from datetime import datetime
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
import uuid
import json
from database import get_db_connection
from PIL import Image
import io
import time
import pyheif
import asyncio
from functools import partial
import base64
from email.mime.text import MIMEText
from google.oauth2 import service_account
from googleapiclient.discovery import build

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

# Initialize OpenAI client
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    organization=os.environ.get("OPENAI_ORG")
)
translation_api_key=os.environ.get("TRANSLATION_API_KEY")
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('HealthAnalysisApp')

app = Flask(__name__)
app.secret_key = 'dev-secret-key-123'  # Required for session management

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'heic', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_gmail_service():
    """Get Gmail service using credentials.json"""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )
        
        # Add user impersonation
        delegated_credentials = credentials.with_subject('austin@plantgroup.co')
        
        return build('gmail', 'v1', credentials=delegated_credentials)
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

@app.route('/')
def home():
    # Get user name from session, default to "Guest" if not found
    user_name = session.get('user_name', 'Guest')
    return render_template('home.html', user_name=user_name)

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        logger.info("Upload endpoint hit")
        if 'files[]' not in request.files:
            logger.error("No files in request")
            return jsonify({'success': False, 'error': 'No files uploaded'}), 400

        files = request.files.getlist('files[]')
        logger.info(f"Received {len(files)} files")
        
        if not files:
            logger.error("Empty files list")
            return jsonify({'success': False, 'error': 'No files selected'}), 400

        file_paths = []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                logger.info(f"Processing file: {filename}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    logger.info(f"Saving file to: {file_path}")
                    file.save(file_path)
                    file_paths.append(file_path)
                    logger.info(f"File saved successfully: {file_path}")
                except Exception as e:
                    logger.error(f"Error saving file {filename}: {str(e)}")
                    return jsonify({'success': False, 'error': f'Error saving file {filename}: {str(e)}'}), 400

        logger.info(f"Analyzing files: {file_paths}")
        result = analyze_health_records(file_paths, document_type='vet_record')
        logger.info(f"Analysis result: {result}")

        # Clean up files
        for file_path in file_paths:
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up file {file_path}: {e}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/profile')
def profile():
    # Get pet profile from session or use empty dict
    pet_data = session.get('pet_profile', {})
    return render_template('profile.html', pet=pet_data)

@app.route('/update_pet_profile', methods=['POST'])
def update_pet_profile():
    try:
        data = request.json
        
        # Store in session for now (can add database storage later)
        session['pet_profile'] = {
            'name': data.get('pet_name'),
            'species': data.get('species'),
            'breed': data.get('breed'),
            'age': data.get('age'),
            'weight': data.get('weight'),
            'health_conditions': data.get('health_conditions'),
            'last_checkup': data.get('last_checkup'),
            'state': data.get('state')
        }
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
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
async def analyze_poop():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image uploaded'})

        image = request.files['image']
        if not image.filename:
            return jsonify({'success': False, 'error': 'No image selected'})

        # Save the image temporarily
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(image.filename))
        image.save(temp_path)

        try:
            # Run the analysis in an async context
            loop = asyncio.get_event_loop()
            analysis = await analyze_poop_image(temp_path)
            
            return jsonify({
                'success': True,
                'result': {
                    'summary': analysis.get('summary', ''),
                    'concerns': analysis.get('concerns', ''),
                    'recommendations': analysis.get('recommendations', '')
                }
            })
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logger.error(f"Error analyzing poop image: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/breeds/<pet_type>')
def get_breeds(pet_type):
    # Add your breed lists here
    breeds = {
        'dog': [
            'Labrador Retriever', 'German Shepherd', 'Golden Retriever', 'French Bulldog', 'Bulldog',
            'Poodle', 'Yorkshire Terrier', 'Boxer', 'Dachshund', 'Siberian Husky',
            'Great Dane', 'Doberman Pinscher', 'Australian Shepherd', 'Shih Tzu', 'Chihuahua',
            'Rottweiler', 'Cocker Spaniel', 'Boston Terrier', 'Miniature Schnauzer', 'Cavalier King Charles Spaniel',
            'Basset Hound', 'Border Collie', 'Akita', 'Maltese', 'Bernese Mountain Dog',
            'Newfoundland', 'Weimaraner', 'English Springer Spaniel', 'Papillon', 'St. Bernard',
            'West Highland White Terrier', 'Rhodesian Ridgeback', 'Pomeranian', 'Alaskan Malamute', 'Whippet'
        ],
        'cat': [
            'Persian', 'Maine Coon', 'Siamese', 'British Shorthair', 'Ragdoll',
            'Sphynx', 'Bengal', 'Scottish Fold', 'Abyssinian', 'Russian Blue',
            'Norwegian Forest Cat', 'Savannah', 'Turkish Angora', 'Birman', 'Oriental Shorthair',
            'American Shorthair', 'Tonkinese', 'Himalayan', 'Chartreux', 'Devon Rex'
        ],
        'bird': [
            'Parakeet', 'Cockatiel', 'Canary', 'Cockatoo', 'African Grey',
            'Macaw', 'Lovebird', 'Budgerigar', 'Finch', 'Eclectus Parrot',
            'Amazon Parrot', 'Conure', 'Quaker Parrot', 'Lorikeet', 'Parrotlet',
            'Indian Ringneck', 'Pionus Parrot', 'Green Cheek Conure', "Bourke's Parrot", 'Senegal Parrot'
        ],
        'reptile': [
            'Bearded Dragon', 'Ball Python', 'Leopard Gecko', 'Corn Snake', 'Green Iguana',
            'Red-Eared Slider', 'Crested Gecko', 'Blue-Tongue Skink', 'King Snake', 'Chameleon',
            'Uromastyx', 'Tokay Gecko', 'Milk Snake', 'Tegu', 'Savannah Monitor',
            'Boa Constrictor', 'Chinese Water Dragon', 'Anole', 'Garter Snake', 'Sulcata Tortoise'
        ],
        'fish': [
            'Betta', 'Goldfish', 'Angelfish', 'Guppy', 'Neon Tetra',
            'Oscar', 'Koi', 'Discus', 'Molly', 'Platy',
            'Swordtail', 'Clownfish', 'Zebra Danio', 'Plecostomus', 'Cichlid'
        ],
        'rabbit': [
            'Holland Lop', 'Netherland Dwarf', 'Flemish Giant', 'Mini Rex', 'Lionhead',
            'English Lop', 'American Fuzzy Lop', 'Harlequin', 'English Angora', 'Silver Marten'
        ],
        'ferret': [
            'Standard Ferret', 'Albino Ferret', 'Black Sable Ferret', 'Champagne Ferret', 'Cinnamon Ferret'
        ],
        'farm animal': [
            'Goat', 'Sheep', 'Pig', 'Cow', 'Horse',
            'Donkey', 'Alpaca', 'Llama', 'Chicken', 'Duck'
        ]
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

@app.route('/report-rescue', methods=['POST'])
def report_rescue():
    logger.info("Received rescue report request")
    
    try:
        data = request.json
        
        body = f"""
        🆘 Rescue Animal Report

        Location: {data['location']}
        Species: {data['species']}
        Breed: {data['breed'] or 'Not specified'}
        
        Health Issues/Situation:
        {data['description']}
        
        Reporter Email: {data['email'] or 'Not provided'}
        
        Reported on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        try:
            message = MIMEText(body)
            message['to'] = 'austin@plantgroup.co'
            message['from'] = 'austin@plantgroup.co'
            message['subject'] = f"🆘 New Rescue Animal Report - {data['species'].title()}"
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            service = get_gmail_service()
            service.users().messages().send(userId='me', body={'raw': raw}).execute()
            
            logger.info("Rescue report email sent successfully")
            
            return jsonify({
                'success': True,
                'message': 'Your rescue report has been submitted successfully. Thank you for helping!'
            })
            
        except Exception as email_error:
            logger.error(f"Email error: {str(email_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to submit report. Please try again or contact support.'
            }), 500
            
    except Exception as e:
        logger.error(f"Request processing error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to submit report. Please try again or contact support.'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001, use_reloader=True)
