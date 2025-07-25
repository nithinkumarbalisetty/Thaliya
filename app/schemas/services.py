from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

# Base schemas for healthcare services
class BaseHealthcareRequest(BaseModel):
    patient_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class BaseHealthcareResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime

# E-Care specific schemas
class ECarePatientData(BaseHealthcareRequest):
    patient_name: str
    medical_record_number: str
    appointment_type: str

class ECareResponse(BaseHealthcareResponse):
    appointment_id: Optional[str] = None
    provider_id: Optional[str] = None

# GeorgeTown specific schemas
class GeorgeTownResearchData(BaseHealthcareRequest):
    study_id: str
    participant_id: str
    data_type: str

class GeorgeTownResponse(BaseHealthcareResponse):
    study_status: Optional[str] = None
    research_data: Optional[Dict[str, Any]] = None

# ChronicCareBridge specific schemas
class ChronicCareData(BaseHealthcareRequest):
    condition_type: str
    care_plan_id: str
    monitoring_data: Dict[str, Any]

class ChronicCareResponse(BaseHealthcareResponse):
    care_plan_status: Optional[str] = None
    next_appointment: Optional[datetime] = None

# Anarcare specific schemas
class AnarcareEmergencyData(BaseHealthcareRequest):
    emergency_type: str
    severity_level: int
    location: str

class AnarcareResponse(BaseHealthcareResponse):
    emergency_id: Optional[str] = None
    response_time: Optional[int] = None
