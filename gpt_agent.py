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
import base64
import asyncio
import PyPDF2

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
    """Extract text from PDF file with fallback"""
    try:
        # First try with pdf2image/poppler
        try:
            images = convert_from_path(file_path)
            text_content = []
            for image in images:
                text = pytesseract.image_to_string(image)
                text_content.append(text)
            return "\n\n".join(text_content)
        except Exception as poppler_error:
            logger.warning(f"Poppler extraction failed: {poppler_error}, trying fallback method")
            
            # Fallback to direct PDF text extraction
            text_content = []
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text_content.append(page.extract_text())
            
            return "\n\n".join(text_content)
            
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def analyze_health_records(file_paths, document_type="vet_record"):
    """Analyze veterinary health records using GPT"""
    try:
        # Get the pet record analysis prompt template ID
        pet_record_prompt_id = '1df8bf0d-8567-4818-9485-694255d49674'  # Pet Record Analysis

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

Please format your analysis with these sections, using emojis and bold headers:

SYNOPSIS 🏥
**Patient Overview**: Current status and primary concerns
**Health Metrics**: Important measurements and vital signs
**Medications**: Current prescriptions and recent vaccinations

INSIGHTS AND ANOMALIES 🔍
**Clinical Findings**: Notable symptoms and examination results
**Health Patterns**: Observed trends and recurring issues
**Risk Factors**: Potential health concerns and vulnerabilities

FOLLOW-UP ACTIONS ✅
**Next Steps**: Urgent actions and appointments
**Tests**: Recommended diagnostics
**Prevention**: Long-term health recommendations

Please use appropriate emojis for key points (🔴 for urgent concerns, 💊 for medications, 📊 for metrics, etc.)"""
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

        # Extract sections more robustly and clean up formatting
        sections = analysis.split('\n\n')
        synopsis = ""
        insights = ""
        followup = ""

        current_section = None
        for section in sections:
            section = section.strip()
            if 'SYNOPSIS 🏥' in section:
                current_section = 'synopsis'
                # Remove the header and clean up asterisks
                synopsis = section.replace('SYNOPSIS 🏥', '').strip()
            elif 'INSIGHTS AND ANOMALIES 🔍' in section:
                current_section = 'insights'
                insights = section.replace('INSIGHTS AND ANOMALIES 🔍', '').strip()
            elif 'FOLLOW-UP ACTIONS ✅' in section:
                current_section = 'followup'
                followup = section.replace('FOLLOW-UP ACTIONS ✅', '').strip()
            elif current_section and section:
                # Clean up any extra asterisks in the content
                cleaned_section = section.replace('****', '').strip()
                if current_section == 'synopsis':
                    synopsis += "\n" + cleaned_section
                elif current_section == 'insights':
                    insights += "\n" + cleaned_section
                elif current_section == 'followup':
                    followup += "\n" + cleaned_section

        # Skip database operations entirely
        
        # Return the analysis results if we have content
        if synopsis or insights or followup:
            return {
                'success': True,
                'result': {
                    'synopsis': synopsis.replace('---', '').strip(),
                    'insights_anomalies': insights.replace('---', '').strip(),
                    'followup_actions': followup.replace('---', '').strip()
                }
            }
        else:
            logger.error("No content in analysis sections")
            return {
                'success': False,
                'error': 'Failed to extract content from analysis'
            }

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return {
            'success': False,
            'error': str(e)
        }

async def analyze_poop_image(image_path):
    """Analyze pet stool image using GPT-4 Vision"""
    try:
        # Read the image file
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
        
        # First upload the file to OpenAI with retry logic
        logger.info("Uploading image to OpenAI for analysis")
        max_upload_retries = 3
        upload_retry_count = 0
        upload_backoff = 2  # seconds
        
        file_id = None
        while upload_retry_count < max_upload_retries and not file_id:
            try:
                with open(image_path, "rb") as file_obj:
                    file_response = client.files.create(
                        file=file_obj,
                        purpose="assistants"
                    )
                file_id = file_response.id
                logger.info(f"Successfully uploaded image to OpenAI, file_id: {file_id}")
            except Exception as upload_error:
                upload_retry_count += 1
                logger.warning(f"Upload attempt {upload_retry_count}/{max_upload_retries} failed: {upload_error}")
                
                if upload_retry_count >= max_upload_retries:
                    logger.error("Maximum upload retries reached")
                    raise upload_error
                
                # Wait with exponential backoff
                await asyncio.sleep(upload_backoff)
                upload_backoff *= 2

        # Create a thread for the analysis
        thread = client.beta.threads.create()
        
        # Create a message with the image using image_file type instead of file_attachment
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=[
                {
                    "type": "text",
                    "text": "Please analyze this pet stool sample image. Consider color, consistency, and any visible abnormalities. Format the response in three sections: summary, concerns, and recommendations."
                },
                {
                    "type": "image_file",
                    "file_id": file_id
                }
            ]
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id="asst_bYxIi1SefCRrdHSHfByUtNjd"  # Your assistant ID
        )

        # Wait for completion with exponential backoff and longer timeout
        max_retries = 60  # Maximum number of times to check for completion (increased from 30)
        retry_count = 0
        backoff_time = 1  # Starting backoff time in seconds
        max_backoff = 10  # Maximum backoff time in seconds
        
        while retry_count < max_retries:
            try:
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                
                if run.status == 'completed':
                    logger.info(f"Analysis completed successfully after {retry_count} retries")
                    break
                elif run.status == 'failed':
                    error_msg = f"Analysis failed: {run.last_error}" if hasattr(run, 'last_error') else "Analysis failed"
                    raise Exception(error_msg)
                elif run.status in ['queued', 'in_progress']:
                    logger.info(f"Analysis in progress: {run.status}, retry {retry_count+1}/{max_retries}")
                else:
                    logger.warning(f"Unexpected status: {run.status}, continuing to wait")
                
                # Exponential backoff with a maximum
                backoff_time = min(backoff_time * 1.5, max_backoff)
                retry_count += 1
                await asyncio.sleep(backoff_time)
            except Exception as retrieval_error:
                logger.error(f"Error retrieving run status: {retrieval_error}")
                retry_count += 1
                await asyncio.sleep(backoff_time)
                continue

        # Check if we reached max retries without completion
        if retry_count >= max_retries:
            logger.error(f"Analysis timed out after maximum {max_retries} retries")
            return {
                'summary': 'Analysis timed out',
                'concerns': 'The analysis took too long to complete',
                'recommendations': 'Please try again with a clearer image or contact support if the issue persists'
            }
            
        # Get the response with error handling
        try:
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            if not messages.data or not messages.data[0].content:
                raise ValueError("No message content received from OpenAI")
                
            analysis = messages.data[0].content[0].text.value
            logger.info("Successfully retrieved analysis from OpenAI")
        except Exception as message_error:
            logger.error(f"Error retrieving analysis result: {message_error}")
            return {
                'summary': 'Error retrieving analysis',
                'concerns': f'Technical issue: {str(message_error)}',
                'recommendations': 'Please try again later'
            }

        # Parse sections
        sections = analysis.split('\n\n')
        result = {
            'summary': '',
            'concerns': '',
            'recommendations': ''
        }

        for section in sections:
            if section.startswith('Summary:'):
                result['summary'] = section.replace('Summary:', '').strip()
            elif section.startswith('Concerns:'):
                result['concerns'] = section.replace('Concerns:', '').strip()
            elif section.startswith('Recommendations:'):
                result['recommendations'] = section.replace('Recommendations:', '').strip()

        return result

    except Exception as e:
        logger.error(f"Poop analysis error: {str(e)}")
        return {
            'summary': 'Error analyzing image',
            'concerns': 'Unable to process the image',
            'recommendations': 'Please try again with a clearer image'
        }
