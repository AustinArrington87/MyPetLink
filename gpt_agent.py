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

        # Extract sections more robustly
        sections = analysis.split('\n\n')
        synopsis = ""
        insights = ""
        followup = ""

        current_section = None
        for section in sections:
            section = section.strip()
            if 'SYNOPSIS' in section:
                current_section = 'synopsis'
                synopsis = section.replace('SYNOPSIS', '').strip()
            elif 'INSIGHTS AND ANOMALIES' in section:
                current_section = 'insights'
                insights = section.replace('INSIGHTS AND ANOMALIES', '').strip()
            elif 'FOLLOW-UP ACTIONS' in section:
                current_section = 'followup'
                followup = section.replace('FOLLOW-UP ACTIONS', '').strip()
            elif current_section and section:
                # Append additional content to the current section
                if current_section == 'synopsis':
                    synopsis += "\n" + section
                elif current_section == 'insights':
                    insights += "\n" + section
                elif current_section == 'followup':
                    followup += "\n" + section

        # Skip database operations entirely
        
        # Return the analysis results if we have content
        if synopsis or insights or followup:
            return {
                'success': True,
                'result': {
                    'synopsis': synopsis,
                    'insights_anomalies': insights,
                    'followup_actions': followup
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
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        # Create a thread for the analysis
        thread = client.beta.threads.create()
        
        # Create a message with the image
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
                    "file_id": base64_image
                }
            ]
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id="asst_bYxIi1SefCRrdHSHfByUtNjd"  # Your assistant ID
        )

        # Wait for completion
        while run.status != 'completed':
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run.status == 'failed':
                raise Exception("Analysis failed")
            await asyncio.sleep(1)

        # Get the response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        analysis = messages.data[0].content[0].text.value

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
