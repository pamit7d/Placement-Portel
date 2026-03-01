from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from utils.decorators import company_required
from models import PlacementDrive, Application, Company, User
from extensions import db
from datetime import datetime

company_bp = Blueprint('company', __name__, url_prefix='/company')

@company_bp.before_request
@login_required
@company_required
def require_company():
    pass

@company_bp.route('/dashboard')
def dashboard():
    company = Company.query.filter_by(user_id=current_user.id).first()
    if company.approval_status != 'approved':
        flash('Your company profile is pending approval or blacklisted. You cannot create drives.', 'error')
        
    total_drives = PlacementDrive.query.filter_by(company_id=company.id).count()
    total_applications = Application.query.join(PlacementDrive).filter(PlacementDrive.company_id == company.id).count()
    shortlisted_applications = Application.query.join(PlacementDrive).filter(PlacementDrive.company_id == company.id, Application.status == 'shortlisted').count()
    
    my_drives = PlacementDrive.query.filter_by(company_id=company.id).order_by(PlacementDrive.created_at.desc()).all()
    
    return render_template('company_dashboard.html', 
                           drives=total_drives, 
                           applications=total_applications, 
                           shortlisted=shortlisted_applications,
                           my_drives=my_drives,
                           company=company)

@company_bp.route('/drive/create', methods=['GET', 'POST'])
def create_drive():
    company = Company.query.filter_by(user_id=current_user.id).first()
    if company.approval_status != 'approved':
        flash('You must be approved by an Admin to create placement drives.', 'error')
        return redirect(url_for('company.dashboard'))
        
    if request.method == 'POST':
        job_title = request.form.get('job_title')
        description = request.form.get('description')
        eligibility = request.form.get('eligibility')
        required_skills = request.form.get('required_skills')
        min_ctc = request.form.get('min_ctc')
        max_ctc = request.form.get('max_ctc')
        location = request.form.get('location')
        deadline_str = request.form.get('deadline')
        status = request.form.get('status', 'pending')
        
        if not all([job_title, description, eligibility, required_skills, location, deadline_str]):
            flash('All required fields must be filled.', 'error')
            return redirect(url_for('company.create_drive'))
            
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        if deadline < datetime.now().date():
            flash('Deadline cannot be in the past.', 'error')
            return redirect(url_for('company.create_drive'))
            
        ctc_range = f"{min_ctc} - {max_ctc}" if min_ctc and max_ctc else (min_ctc or max_ctc)
        
        drive = PlacementDrive(
            company_id=company.id,
            job_title=job_title,
            description=description,
            eligibility=eligibility,
            required_skills=required_skills,
            ctc_range=ctc_range,
            location=location,
            deadline=deadline,
            status='pending' # Default to pending for new drives unless allowed direct active
        )
        db.session.add(drive)
        db.session.commit()
        
        flash('Placement drive submitted for Admin approval.', 'success')
        return redirect(url_for('company.dashboard'))
        
    return render_template('company_create_drive.html', company=company)

@company_bp.route('/drive/<int:id>/applicants')
def view_applicants(id):
    company = Company.query.filter_by(user_id=current_user.id).first()
    drive = PlacementDrive.query.get_or_404(id)
    
    if drive.company_id != company.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('company.dashboard'))
        
    status_filter = request.args.get('status', 'All')
    query = Application.query.filter_by(drive_id=id)
    
    if status_filter != 'All':
        query = query.filter_by(status=status_filter.lower())
        
    applications = query.all()
    return render_template('company_applicants.html', drive=drive, applications=applications, current_status=status_filter)

@company_bp.route('/applicant/<int:id>/profile')
def view_applicant_profile(id):
    application = Application.query.get_or_404(id)
    company = Company.query.filter_by(user_id=current_user.id).first()
    
    if application.drive_details.company_id != company.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('company.dashboard'))
        
    return render_template('company_student_detail.html', student=application.student_details, application=application)

@company_bp.route('/application/<int:id>/update_status', methods=['POST'])
def update_application_status(id):
    application = Application.query.get_or_404(id)
    company = Company.query.filter_by(user_id=current_user.id).first()
    
    # Security check
    if application.drive_details.company_id != company.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('company.dashboard'))
        
    new_status = request.form.get('status')
    if new_status in ['applied', 'shortlisted', 'selected', 'rejected']:
        application.status = new_status
        db.session.commit()
        flash(f'Application status updated to {new_status}.', 'success')
        
    return redirect(url_for('company.view_applicants', id=application.drive_id))

@company_bp.route('/application/<int:id>/update_status_ajax', methods=['POST'])
def update_application_status_ajax(id):
    application = Application.query.get_or_404(id)
    company = Company.query.filter_by(user_id=current_user.id).first()
    
    # Security check
    if application.drive_details.company_id != company.id:
        return {'success': False, 'message': 'Unauthorized'}, 403
        
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status in ['applied', 'shortlisted', 'selected', 'rejected']:
        application.status = new_status
        db.session.commit()
        return {'success': True, 'message': f'Status updated to {new_status}'}
    
    return {'success': False, 'message': 'Invalid status'}, 400

@company_bp.route('/drive/<int:id>/close', methods=['POST'])
def close_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    company = Company.query.filter_by(user_id=current_user.id).first()
    
    if drive.company_id == company.id:
        drive.status = 'closed'
        db.session.commit()
        flash('Drive closed successfully.', 'success')
    
    return redirect(url_for('company.dashboard'))

@company_bp.route('/drive/<int:id>/edit', methods=['GET', 'POST'])
def edit_drive(id):
    company = Company.query.filter_by(user_id=current_user.id).first()
    drive = PlacementDrive.query.get_or_404(id)
    
    if drive.company_id != company.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('company.dashboard'))
        
    if drive.status != 'pending':
        flash('You can only edit pending placement drives.', 'error')
        return redirect(url_for('company.dashboard'))
        
    if request.method == 'POST':
        drive.job_title = request.form.get('job_title')
        drive.description = request.form.get('description')
        drive.eligibility = request.form.get('eligibility')
        drive.required_skills = request.form.get('required_skills')
        drive.ctc_range = request.form.get('ctc_range')
        drive.location = request.form.get('location')
        deadline_str = request.form.get('deadline')
        
        if deadline_str:
            drive.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
            
        db.session.commit()
        flash('Drive updated successfully.', 'success')
        return redirect(url_for('company.dashboard'))
        
    return render_template('company_edit_drive.html', company=company, drive=drive)

@company_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    company = Company.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        company.company_name = request.form.get('company_name', company.company_name)
        company.hr_name = request.form.get('hr_name', company.hr_name)
        company.hr_phone = request.form.get('hr_phone', company.hr_phone)
        website = request.form.get('website', company.website)
        
        # URL validation
        import urllib.parse
        parsed = urllib.parse.urlparse(website)
        if website and not (parsed.scheme and parsed.netloc):
            flash('Invalid URL format for website.', 'error')
            return redirect(url_for('company.profile'))
            
        company.website = website
        company.description = request.form.get('description', company.description)
        
        # Upload logo logic mock
        from werkzeug.utils import secure_filename
        import os
        from flask import current_app
        logo = request.files.get('logo')
        if logo and logo.filename:
            filename = secure_filename(logo.filename)
            upload_dir = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            logo.save(os.path.join(upload_dir, filename))
            company.logo_path = 'uploads/' + filename
            
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('company.profile'))
        
    return render_template('company_profile.html', company=company)

@company_bp.route('/drive/<int:id>/delete', methods=['POST'])
def delete_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    company = Company.query.filter_by(user_id=current_user.id).first()
    
    if drive.company_id == company.id:
        db.session.delete(drive)
        db.session.commit()
        flash('Drive deleted successfully.', 'success')
    else:
        flash('Unauthorized access.', 'error')
        
    return redirect(url_for('company.dashboard'))

