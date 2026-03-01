from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False) # admin, company, student
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    hr_name = db.Column(db.String(100))
    hr_email = db.Column(db.String(120))
    hr_phone = db.Column(db.String(20))
    website = db.Column(db.String(120))
    description = db.Column(db.Text)
    logo_path = db.Column(db.String(200))
    approval_status = db.Column(db.String(20), default='pending') # pending, approved, blacklisted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('company_profile', uselist=False), cascade='all, delete')
    drives = db.relationship('PlacementDrive', backref='company_details', lazy='dynamic', cascade='all, delete-orphan')

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    roll_no = db.Column(db.String(20), unique=True, index=True, nullable=False)
    branch = db.Column(db.String(50))
    year = db.Column(db.String(10))
    cgpa = db.Column(db.Float)
    phone = db.Column(db.String(20))
    skills = db.Column(db.Text) # JSON or comma separated
    resume_path = db.Column(db.String(200))
    profile_picture = db.Column(db.String(200))
    is_blacklisted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('student_profile', uselist=False), cascade='all, delete')
    applications = db.relationship('Application', backref='student_details', lazy='dynamic', cascade='all, delete-orphan')

class PlacementDrive(db.Model):
    __tablename__ = 'placement_drives'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    eligibility = db.Column(db.Text)
    required_skills = db.Column(db.Text)
    ctc_range = db.Column(db.String(50))
    location = db.Column(db.String(100))
    deadline = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending') # pending, approved, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship('Application', backref='drive_details', lazy='dynamic', cascade='all, delete-orphan')

class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    drive_id = db.Column(db.Integer, db.ForeignKey('placement_drives.id'), nullable=False)
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='applied') # applied, shortlisted, selected, rejected, withdrawn
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'drive_id', name='uq_student_drive'),
    )
