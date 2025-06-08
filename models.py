from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Date, Text, LargeBinary, TIMESTAMP, JSON, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime

Base = declarative_base()

def generate_uuid():
    return uuid.uuid4()

class User(Base):
    """User model for storing user related data"""
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    auth0_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    user_type = Column(String(50))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    is_admin = Column(Boolean, default=False)
    avatar_url = Column(String(500))
    bio = Column(Text)
    city = Column(String(100))
    us_state = Column(String(2))
    looking_for = Column(ARRAY(String))

    # Relationships
    pets = relationship("Pet", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id='{self.id}', email='{self.email}')>"
        
    @property
    def name(self):
        """Return full name for backward compatibility"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return ""

class Pet(Base):
    """Pet model for storing pet related data"""
    __tablename__ = 'pets'

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    name = Column(String(100))
    species = Column(String(50))
    breed = Column(String(100))
    age_years = Column(Integer, default=0)
    age_months = Column(Integer, default=0)
    weight = Column(Float)
    health_conditions = Column(Text)
    last_checkup = Column(Date)
    last_vaccination_date = Column(Date)
    state = Column(String(2))
    city = Column(String(100))
    vet_clinic = Column(String(200))
    vet_phone = Column(String(50))
    vet_address = Column(Text)
    avatar_url = Column(String(500))
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="pets")
    files = relationship("PetFile", back_populates="pet", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Pet(id='{self.id}', name='{self.name}', species='{self.species}')>"
    
    @property
    def age(self):
        """Format age as a dictionary for API responses"""
        return {
            'years': self.age_years or 0,
            'months': self.age_months or 0
        }
    
    @property
    def avatar(self):
        """Return avatar URL for frontend compatibility"""
        return self.avatar_url

    def to_dict(self):
        """Convert Pet to dictionary for API responses"""
        return {
            'id': str(self.id),
            'name': self.name,
            'species': self.species,
            'breed': self.breed,
            'age': self.age,
            'weight': self.weight,
            'health_conditions': self.health_conditions,
            'last_checkup': self.last_checkup.isoformat() if self.last_checkup else None,
            'last_vaccination_date': self.last_vaccination_date.isoformat() if self.last_vaccination_date else None,
            'state': self.state,
            'city': self.city,
            'vet_clinic': self.vet_clinic,
            'vet_phone': self.vet_phone,
            'vet_address': self.vet_address,
            'avatar': self.avatar_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }

class PetFile(Base):
    """Model for storing pet file records"""
    __tablename__ = 'pet_files'

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    pet_id = Column(UUID(as_uuid=True), ForeignKey('pets.id'), nullable=False)
    file_type = Column(String(50))  # avatar, health_record, poop
    original_filename = Column(String(255))
    s3_path = Column(String(500))
    local_path = Column(String(500))
    content_type = Column(String(100))
    file_size = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())
    analysis_json = Column(JSON)

    # Relationships
    pet = relationship("Pet", back_populates="files")

    def __repr__(self):
        return f"<PetFile(id='{self.id}', type='{self.file_type}', filename='{self.original_filename}')>"
    
    def to_dict(self):
        """Convert PetFile to dictionary for API responses"""
        return {
            'id': str(self.id),
            'pet_id': str(self.pet_id),
            'file_type': self.file_type,
            'original_filename': self.original_filename,
            's3_path': self.s3_path,
            'content_type': self.content_type,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'has_analysis': self.analysis_json is not None
        }