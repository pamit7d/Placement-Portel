from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from utils.decorators import student_required
from models import PlacementDrive, Application, Student, Company
from extensions import db
from datetime import datetime

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.before_request
@login_required
@student_required
def require_student():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if student and student.is_blacklisted:
        flash('Your account has been blacklisted. Please contact Admin.', 'error')
        from flask_login import logout_user
        logout_user()
        return redirect(url_for('auth.login'))

@student_bp.route('/dashboard')
def dashboard():
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    total_applications = Application.query.filter_by(student_id=student.id).count()
    shortlisted_applications = Application.query.filter_by(student_id=student.id, status='shortlisted').count()
    selected_applications = Application.query.filter_by(student_id=student.id, status='selected').count()
    
    recent_drives = PlacementDrive.query.filter_by(status='approved').order_by(PlacementDrive.created_at.desc()).limit(5).all()
    my_applications = Application.query.filter_by(student_id=student.id).order_by(Application.application_date.desc()).limit(5).all()
    
    return render_template('student_dashboard.html', 
                           student=student,
                           total_applications=total_applications,
                           shortlisted=shortlisted_applications,
                           selected=selected_applications,
                           recent_drives=recent_drives,
                           my_applications=my_applications)

@student_bp.route('/drives')
def browse_drives():
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    search = request.args.get('search', '')
    company_filter = request.args.get('company', '')
    location_filter = request.args.get('location', '')
    
    query = PlacementDrive.query.filter_by(status='approved')
    
    if search:
        query = query.filter(PlacementDrive.job_title.ilike(f'%{search}%'))
    if company_filter:
        query = query.join(Company).filter(Company.company_name.ilike(f'%{company_filter}%'))
    if location_filter:
        query = query.filter(PlacementDrive.location.ilike(f'%{location_filter}%'))
        
    page = request.args.get('page', 1, type=int)
    drives_paginated = query.order_by(PlacementDrive.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    
    # Get IDs of drives the student has already applied to
    applied_drive_ids = [app.drive_id for app in Application.query.filter_by(student_id=student.id).all()]
    
    return render_template('student_browse_drives.html', drives=drives_paginated, applied_drive_ids=applied_drive_ids, student=student)

@student_bp.route('/apply/<int:drive_id>', methods=['POST'])
def apply_to_drive(drive_id):
    student = Student.query.filter_by(user_id=current_user.id).first()
    drive = PlacementDrive.query.get_or_404(drive_id)
    
    if drive.status != 'approved':
        flash('This drive is not currently open for applications.', 'error')
        return redirect(url_for('student.browse_drives'))
        
    # Check if already applied
    existing_application = Application.query.filter_by(student_id=student.id, drive_id=drive.id).first()
    if existing_application:
        flash('You have already applied to this drive.', 'warning')
        return redirect(url_for('student.browse_drives'))
        
    application = Application(
        student_id=student.id,
        drive_id=drive.id,
        status='applied'
    )
    db.session.add(application)
    db.session.commit()
    
    flash(f'Successfully applied to {drive.job_title} at {drive.company_details.company_name}.', 'success')
    return redirect(url_for('student.my_applications'))

@student_bp.route('/applications')
def my_applications():
    student = Student.query.filter_by(user_id=current_user.id).first()
    applications = Application.query.filter_by(student_id=student.id).order_by(Application.application_date.desc()).all()
    
    return render_template('student_application_status.html', applications=applications, student=student)

@student_bp.route('/application/<int:id>')
def view_application(id):
    student = Student.query.filter_by(user_id=current_user.id).first()
    application = Application.query.get_or_404(id)
    if application.student_id != student.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('student.my_applications'))
    return render_template('student_application_detail.html', application=application)

@student_bp.route('/application/<int:id>/withdraw', methods=['POST'])
def withdraw_application(id):
    student = Student.query.filter_by(user_id=current_user.id).first()
    application = Application.query.get_or_404(id)
    if application.student_id != student.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('student.my_applications'))
        
    if application.status != 'applied':
        flash('You can only withdraw applications that are still pending.', 'error')
        return redirect(url_for('student.my_applications'))
        
    application.status = 'withdrawn'
    db.session.commit()
    flash('Application withdrawn successfully.', 'success')
    return redirect(url_for('student.my_applications'))

@student_bp.route('/profile', methods=['GET', 'POST'])
def edit_profile():
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        student.full_name = request.form.get('full_name', student.full_name)
        student.phone = request.form.get('phone', student.phone)
        student.skills = request.form.get('skills', student.skills)
        
        cgpa_str = request.form.get('cgpa')
        if cgpa_str:
            try:
                cgpa = float(cgpa_str)
                if cgpa < 0 or cgpa > 10:
                    flash('CGPA must be between 0 and 10.', 'error')
                    return redirect(url_for('student.edit_profile'))
                student.cgpa = cgpa
            except ValueError:
                flash('Invalid CGPA format.', 'error')
                return redirect(url_for('student.edit_profile'))
        
        # Assume handling resume upload here
        from werkzeug.utils import secure_filename
        import os
        from flask import current_app
        
        resume_file = request.files.get('resume')
        if resume_file and resume_file.filename:
            if not resume_file.filename.lower().endswith('.pdf'):
                flash('Only PDF files are allowed for resumes.', 'error')
                return redirect(url_for('student.edit_profile'))
            
            filename = secure_filename(resume_file.filename)
            upload_dir = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            resume_file.save(os.path.join(upload_dir, filename))
            student.resume_path = 'uploads/' + filename
            
        profile_pic_file = request.files.get('profile_picture')
        if profile_pic_file and profile_pic_file.filename:
            if not profile_pic_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                flash('Only image files are allowed for profile pictures.', 'error')
                return redirect(url_for('student.edit_profile'))
            
            pic_filename = secure_filename(profile_pic_file.filename)
            upload_dir = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            profile_pic_file.save(os.path.join(upload_dir, pic_filename))
            student.profile_picture = 'uploads/' + pic_filename
            
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('student.edit_profile'))
        
    return render_template('student_profile.html', student=student)
