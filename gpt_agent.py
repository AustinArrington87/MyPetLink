from openai import OpenAI
import os
import logging
from dotenv import load_dotenv, find_dotenv
import pytesseract
from pdf2image import convert_from_path
import time
import uuid
import json
from datetime import datetime
from database import get_db_connection
from flask import session

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('PetRecordAnalyzer')

# Load environment variables
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

# Initialize OpenAI client
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    organization=os.environ.get("OPENAI_ORG")
)

# Add error handling if API key is missing
if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key must be set in .env file")

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        images = convert_from_path(file_path)
        text_content = []
        for image in images:
            text = pytesseract.image_to_string(image)
            text_content.append(text)
        return "\n\n".join(text_content)
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def analyze_health_records(file_paths, document_type="vet_record"):
    """Analyze veterinary health records using GPT"""
    try:
        # Extract text from all files
        all_text = []
        for file_path in file_paths:
            try:
                if file_path.lower().endswith('.pdf'):
                    text = extract_text_from_pdf(file_path)
                elif file_path.lower().endswith('.txt'):
                    with open(file_path, 'r') as f:
                        text = f.read()
                elif file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                    text = pytesseract.image_to_string(file_path)
                
                if text:
                    all_text.append(text)
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                continue

        if not all_text:
            return {
                'success': False,
                'error': 'No text could be extracted from the files'
            }

        # Combine all text
        combined_text = "\n\n".join(all_text)

        # Create thread and analyze with GPT
        thread = client.beta.threads.create()
        
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"""Please analyze these veterinary records and provide a structured summary.

Document content:
{combined_text}

Please provide your analysis in this format:
SYNOPSIS
• Key findings and immediate concerns
• Important health metrics
• Medication details

INSIGHTS AND ANOMALIES
• Detailed analysis of any issues
• Trends or patterns
• Recommendations

FOLLOW-UP ACTIONS
• Suggested next steps
• Preventive measures
• Timing for next check-up"""
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
                raise Exception("Analysis failed")

        # Get response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        analysis = messages.data[0].content[0].text.value

        # Extract sections
        sections = analysis.split('\n\n')
        synopsis = ""
        insights = ""
        followup = ""

        for section in sections:
            if section.startswith('SYNOPSIS'):
                synopsis = section
            elif section.startswith('INSIGHTS'):
                insights = section
            elif section.startswith('FOLLOW-UP'):
                followup = section

        # Try to save to database, but don't fail if it errors
        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                
                # Create a new chat session with UUID for user_id
                session_id = str(uuid.uuid4())
                default_user_id = str(uuid.uuid4())  # Generate UUID for user_id
                
                cur.execute("""
                    INSERT INTO chat_sessions (id, user_id, created_at, pet_id, provider_id)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    session_id, 
                    default_user_id, 
                    datetime.now(),
                    default_user_id,  # Using same UUID for pet_id
                    default_user_id   # Using same UUID for provider_id
                ))
                
                conn.commit()
                
                # Store the analysis
                message_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO chat_messages 
                    (id, session_id, role, content, timestamp, request_data, response_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    message_id,
                    session_id,
                    'system',
                    'Veterinary Document Analysis',
                    datetime.now(),
                    json.dumps({'files': file_paths}),
                    json.dumps({
                        'synopsis': synopsis,
                        'insights_anomalies': insights,
                        'followup_actions': followup
                    })
                ))

                conn.commit()
                cur.close()
                conn.close()
                
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}")
            # Continue even if database save fails

        # Return the analysis results
        if not synopsis and not insights and not followup:
            logger.error("No content in analysis sections")
            return {
                'success': False,
                'error': 'Failed to extract content from analysis'
            }

        return {
            'success': True,
            'result': {
                'synopsis': synopsis,
                'insights_anomalies': insights,
                'followup_actions': followup
            }
        }

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return {
            'success': False,
            'error': str(e)
        }
