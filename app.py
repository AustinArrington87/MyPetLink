from flask import Flask, render_template, request, jsonify, session, url_for, send_file
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from gpt_agent import analyze_health_records
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
    # Get user name from session or use default
    user_name = session.get('user_name', 'Michelle G')
    first_name, last_name = user_name.split(' ', 1) if ' ' in user_name else (user_name, '')
    
    # Mock data for demonstration
    user_data = {
        'name': {'first': first_name, 'last': last_name},
        'vitals': {
            'blood_pressure': '120/80',
            'pulse_rate': '72',
            'height': "5'10\"",
            'weight': '150',
            'bmi': '21.5',
            'respiratory_rate': '16'
        }
    }
    return render_template('profile.html', user=user_data)

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
        data = request.get_json()
        user_message = data.get('message', '')
        
        # Get intake form context if available
        intake_context = ""
        if session and 'intake_form' in session:
            intake_data = session.get('intake_form', {})
            medical_context = []
            
            # Medical History (non-PII only)
            if intake_data.get('takingMedications') == 'yes' and intake_data.get('medications'):
                medical_context.append(f"Current Medications: {intake_data['medications']}")
            
            if intake_data.get('chronicConditions'):
                conditions = intake_data['chronicConditions']
                if isinstance(conditions, list):
                    medical_context.append(f"Chronic Conditions: {', '.join(conditions)}")
                else:
                    medical_context.append(f"Chronic Condition: {conditions}")
            
            # Current Health
            if intake_data.get('primaryReason'):
                medical_context.append(f"Current Health Concern: {intake_data['primaryReason']}")
            
            if intake_data.get('painLevel'):
                medical_context.append(f"Pain Level: {intake_data['painLevel']}/10")
            
            # Lifestyle
            if intake_data.get('exercise'):
                medical_context.append(f"Exercise Frequency: {intake_data['exercise']}")
            
            if intake_data.get('stressLevel'):
                medical_context.append(f"Stress Level: {intake_data['stressLevel']}")
            
            if medical_context:
                intake_context = "\nPatient Background:\n• " + "\n• ".join(medical_context) + "\n\n"

        # Update system message to include medical error detection
        system_message = """You are an AI Health Assistant. Use the following patient background information to provide more personalized responses.
{intake_context}

CRITICAL INSTRUCTIONS:
1. Always review medications listed in the patient background
2. Flag any potential connections between medications and reported symptoms
3. Note if medications like Xanax could be relevant to symptoms
4. Recommend consulting a healthcare provider about medication side effects
5. Be especially attentive to mental health medications and their effects
6. IMPORTANT: If you detect any potential medical errors (such as outdated prescriptions, 
   contraindicated medications, or concerning symptoms), include "[MEDICAL_ERROR_RISK]" 
   at the start of your response.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

I understand your concern about [symptom]. Let me address this while considering your current medications.


MEDICATION CONSIDERATIONS

- Note any medication effects relevant to the symptoms

- Highlight potential medication interactions or side effects


RECOMMENDED STEPS

- First recommendation with clear explanation

- Second recommendation with clear explanation


IMPORTANT REMINDERS

- Key safety points about medications and symptoms

- When to consult healthcare providers

I hope this helps. Please discuss any medication concerns with your healthcare provider.

FORMATTING RULES:
- Use UPPERCASE for section headers
- Leave TWO blank lines between sections
- Use simple dashes (-) for bullet points
- Never use **, ##, or ### characters
- Keep paragraphs short and well-spaced
- Use plain text only, no special formatting"""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        # Get chat history from session and add to messages
        chat_history = session.get('chat_history', [])
        messages.extend(chat_history)

        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        # Get the assistant's response
        assistant_response = response.choices[0].message.content

        # Check for medical error risk
        medical_error_risk = '[MEDICAL_ERROR_RISK]' in assistant_response
        # Remove the flag from the displayed response
        assistant_response = assistant_response.replace('[MEDICAL_ERROR_RISK]', '').strip()

        # Update chat history in session
        chat_history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_response}
        ])
        session['chat_history'] = chat_history

        return jsonify({
            "success": True,
            "response": assistant_response,
            "medical_error_risk": medical_error_risk
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

@app.route('/analyze-poop', methods=['POST'])
def analyze_poop():
    try:
        logger.info("Starting poop analysis")
        if 'image' not in request.files:
            logger.error("No image file in request")
            return jsonify({'error': 'No image uploaded'}), 400
            
        image = request.files['image']
        logger.info(f"Received image: {image.filename}")
        
        # Read image data
        try:
            image_data = image.read()
            logger.info(f"Successfully read image data, size: {len(image_data)} bytes")
        except Exception as e:
            logger.error(f"Error reading image data: {str(e)}")
            return jsonify({'error': 'Error reading image file'}), 400
        
        # Create a thread for the analysis
        try:
            thread = client.beta.threads.create()
            logger.info(f"Created thread: {thread.id}")
            
            # Upload the image
            image_file = client.files.create(
                file=io.BytesIO(image_data),
                purpose='assistants'
            )
            logger.info(f"Uploaded image to OpenAI: {image_file.id}")
            
            # Create a message with the image
            message = client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=[{
                    "type": "text",
                    "text": "Please analyze this pet stool sample image for any health concerns. Consider color, consistency, and any visible abnormalities."
                }, {
                    "type": "image_file",
                    "file_id": image_file.id
                }]
            )
            logger.info("Created message with image")
            
            # Run the assistant
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id="asst_bYxIi1SefCRrdHSHfByUtNjd"
            )
            logger.info("Started assistant run")
            
            # Wait for completion
            while run.status != 'completed':
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                if run.status == 'failed':
                    logger.error(f"Run failed: {run.last_error}")
                    raise Exception("Analysis failed")
                time.sleep(1)
            
            logger.info("Analysis completed")
            
            # Get the assistant's response
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            analysis = messages.data[0].content[0].text.value if hasattr(messages.data[0].content[0].text, 'value') else str(messages.data[0].content[0].text)
            
            logger.info("Successfully retrieved analysis")
            return jsonify({
                'success': True,
                'analysis': analysis
            })
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Poop analysis error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/breeds/<pet_type>')
def get_breeds(pet_type):
    # Add your breed lists here
    breeds = {
        'dog': ['Labrador Retriever', 'German Shepherd', 'Golden Retriever', 'French Bulldog', 'Bulldog'],
        'cat': ['Persian', 'Maine Coon', 'Siamese', 'British Shorthair', 'Ragdoll'],
        'bird': ['Parakeet', 'Cockatiel', 'Canary', 'Cockatoo', 'African Grey'],
        'reptile': ['Bearded Dragon', 'Ball Python', 'Leopard Gecko', 'Corn Snake', 'Green Iguana']
    }
    return jsonify(breeds.get(pet_type, []))

if __name__ == '__main__':
    app.run(debug=True, port=5001)
