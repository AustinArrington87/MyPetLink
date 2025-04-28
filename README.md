# MyPetLink

A pet health management application that helps pet owners track their pets' health, analyze medical records, and get insights about their pets' wellbeing.

## Features

- **Multi-pet Management**: Support for multiple pets per user with easy switching between pet profiles
- **Health Record Analysis**: Upload veterinary records for AI-powered analysis
- **Poop Analysis**: Upload images of pet waste for health analysis
- **User Authentication**: Secure login via Auth0
- **Database Integration**: PostgreSQL for data storage with SQLAlchemy ORM
- **File Storage**: S3 integration for secure file storage with organized structure
- **User-friendly Interface**: Clean and intuitive UI with pet avatars and health data visualization

## Architecture

- **Backend**: Flask (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **File Storage**: AWS S3
- **Authentication**: Auth0
- **AI Integration**: OpenAI API

## S3 Storage Structure

Files are stored in S3 with the following folder structure:
- `{user_id}/{pet_id}/avatar/` - Pet avatars
- `{user_id}/{pet_id}/health_record/` - Health records (PDF, images)
- `{user_id}/{pet_id}/poop/` - Poop images for analysis

## Environment Variables

The application requires the following environment variables:

```
# App configuration
APP_SECRET_KEY=your-secret-key
FLASK_APP=app.py
FLASK_ENV=development

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/mydatabase

# OpenAI API
OPENAI_API_KEY=your-openai-api-key
OPENAI_ORG=your-openai-org-id

# Auth0
AUTH0_CLIENT_ID=your-auth0-client-id
AUTH0_CLIENT_SECRET=your-auth0-client-secret
AUTH0_DOMAIN=your-auth0-domain
AUTH0_CALLBACK_URL=http://localhost:5001/callback

# AWS S3
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name
```

## Getting Started

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Set up environment variables in a `.env` file
6. Run the application: `flask run --port=5001`

## Database Migrations

Database migrations are handled with Alembic:

```
# Initialize migrations
alembic init migrations

# Generate a migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head
```