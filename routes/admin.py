from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from utils.decorators import admin_required
from models import User, Company, Student, PlacementDrive, Application
from extensions import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
@admin_required
def require_admin():
    pass # This will apply to all routes in this blueprint

@admin_bp.route('/dashboard')
def dashboard():
    total_students = Student.query.count()
    total_companies = Company.query.count()
    total_drives = PlacementDrive.query.count()
    total_applications = Application.query.count()
    
    recent_applications = db.session.query(
        Application, Student, PlacementDrive, Company
    ).join(Student).join(PlacementDrive).join(Company).order_by(Application.application_date.desc()).limit(5).all()

    # Pass logic for Chart.js counts
    # applications_per_drive = db.session.query(PlacementDrive.job_title, db.func.count(Application.id)).join(Application).group_by(PlacementDrive.id).all()
    # status_dist = db.session.query(Application.status, db.func.count(Application.id)).group_by(Application.status).all()

    return render_template('admin_dashboard.html', 
                           students=total_students, 
                           companies=total_companies, 
                           drives=total_drives, 
                           applications=total_applications,
                           recent_applications=recent_applications)

@admin_bp.route('/companies')
def manage_companies():
    status = request.args.get('status', 'All')
    search = request.args.get('search', '')
    
    query = Company.query
    if status != 'All':
        query = query.filter_by(approval_status=status.lower())
    if search:
        query = query.filter(Company.company_name.ilike(f'%{search}%'))
        
    page = request.args.get('page', 1, type=int)
    companies_paginated = query.paginate(page=page, per_page=10, error_out=False)
    return render_template('admin_companies.html', companies=companies_paginated, current_status=status)

@admin_bp.route('/company/<int:id>/<action>', methods=['POST'])
def update_company(id, action):
    company = Company.query.get_or_404(id)
    if action == 'approve':
        company.approval_status = 'approved'
        flash(f'Company {company.company_name} approved.', 'success')
    elif action == 'reject':
        company.approval_status = 'rejected'
        flash(f'Company {company.company_name} rejected.', 'success')
    elif action == 'blacklist':
        company.approval_status = 'blacklisted'
        company.user.is_active = False # Deactivate their login
        flash(f'Company {company.company_name} blacklisted.', 'success')
    
    db.session.commit()
    return redirect(url_for('admin.manage_companies'))

@admin_bp.route('/students')
def manage_students():
    status = request.args.get('status', 'All')
    search = request.args.get('search', '')
    
    query = Student.query
    if status == 'Blacklisted':
        query = query.filter_by(is_blacklisted=True)
    elif status == 'Active':
        query = query.filter_by(is_blacklisted=False)
        
    if search:
        query = query.join(User).filter(Student.full_name.ilike(f'%{search}%') | Student.roll_no.ilike(f'%{search}%') | User.email.ilike(f'%{search}%'))
        
    page = request.args.get('page', 1, type=int)
    students_paginated = query.paginate(page=page, per_page=10, error_out=False)
    return render_template('admin_students.html', students=students_paginated, current_status=status)

@admin_bp.route('/student/<int:id>/<action>', methods=['POST'])
def update_student(id, action):
    student = Student.query.get_or_404(id)
    if action == 'blacklist':
        student.is_blacklisted = True
        student.user.is_active = False
        flash(f'Student {student.full_name} blacklisted.', 'success')
    elif action == 'delete':
        db.session.delete(student.user) # Cascade deletes student if set properly, or delete explicit
        db.session.delete(student)
        flash(f'Student {student.full_name} deleted.', 'success')
        
    db.session.commit()
    return redirect(url_for('admin.manage_students'))

@admin_bp.route('/drives')
def manage_drives():
    status = request.args.get('status', 'All')
    
    query = PlacementDrive.query
    if status != 'All':
        query = query.filter_by(status=status.lower())
        
    drives = query.all()
    return render_template('admin_drives.html', drives=drives, current_status=status)

@admin_bp.route('/drive/<int:id>/<action>', methods=['POST'])
def update_drive(id, action):
    drive = PlacementDrive.query.get_or_404(id)
    if action == 'approve':
        drive.status = 'approved'
        flash(f'Drive {drive.job_title} approved.', 'success')
    elif action == 'reject':
        drive.status = 'rejected'
        flash(f'Drive {drive.job_title} rejected.', 'success')
        
    db.session.commit()
    return redirect(url_for('admin.manage_drives'))

@admin_bp.route('/applications')
def all_applications():
    drive_id = request.args.get('drive')
    status = request.args.get('status')
    
    query = db.session.query(
        Application, Student, PlacementDrive, Company
    ).join(Student).join(PlacementDrive).join(Company)
    
    if drive_id and drive_id != 'None':
        query = query.filter(PlacementDrive.id == drive_id)
    if status and status != 'All' and status != 'None':
        query = query.filter(Application.status == status.lower())
        
    applications = query.all()
    
    if request.args.get('export') == 'csv':
        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student Name', 'Roll No', 'Drive Title', 'Company', 'Status', 'Date Applied'])
        for app, student, drive, company in applications:
            writer.writerow([student.full_name, student.roll_no, drive.job_title, company.company_name, app.status, app.application_date.strftime('%Y-%m-%d')])
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=applications.csv"}
        )

    all_drives = PlacementDrive.query.all()
    return render_template('admin_applications.html', applications=applications, drives=all_drives, current_drive=drive_id, current_status=status)

@admin_bp.route('/company/<int:id>')
def view_company(id):
    company = Company.query.get_or_404(id)
    return render_template('admin_company_detail.html', company=company)

@admin_bp.route('/company/<int:id>/edit', methods=['GET', 'POST'])
def edit_company(id):
    company = Company.query.get_or_404(id)
    if request.method == 'POST':
        company.company_name = request.form.get('company_name', company.company_name)
        company.hr_name = request.form.get('hr_name', company.hr_name)
        company.hr_email = request.form.get('hr_email', company.hr_email)
        company.hr_phone = request.form.get('hr_phone', company.hr_phone)
        company.website = request.form.get('website', company.website)
        company.description = request.form.get('description', company.description)
        db.session.commit()
        flash(f'Company {company.company_name} updated successfully.', 'success')
        return redirect(url_for('admin.view_company', id=company.id))
        
    return render_template('admin_company_edit.html', company=company)

@admin_bp.route('/student/<int:id>')
def view_student(id):
    student = Student.query.get_or_404(id)
    return render_template('admin_student_detail.html', student=student)

@admin_bp.route('/student/<int:id>/edit', methods=['GET', 'POST'])
def edit_student(id):
    student = Student.query.get_or_404(id)
    if request.method == 'POST':
        student.full_name = request.form.get('full_name', student.full_name)
        student.roll_no = request.form.get('roll_no', student.roll_no)
        student.branch = request.form.get('branch', student.branch)
        student.year = request.form.get('year', student.year)
        student.skills = request.form.get('skills', student.skills)
        student.phone = request.form.get('phone', student.phone)
        cgpa_str = request.form.get('cgpa')
        if cgpa_str:
            try:
                student.cgpa = float(cgpa_str)
            except ValueError:
                pass
        db.session.commit()
        flash(f'Student {student.full_name} updated successfully.', 'success')
        return redirect(url_for('admin.view_student', id=student.id))
        
    return render_template('admin_student_edit.html', student=student)

@admin_bp.route('/drive/<int:id>')
def view_drive(id):
    from datetime import datetime
    drive = PlacementDrive.query.get_or_404(id)
    return render_template('admin_drive_detail.html', drive=drive, current_date=datetime.now().date())

@admin_bp.route('/application/<int:id>')
def view_application(id):
    application = Application.query.get_or_404(id)
    return render_template('admin_application_detail.html', application=application)

@admin_bp.route('/application/<int:id>/edit', methods=['GET', 'POST'])
def edit_application(id):
    application = Application.query.get_or_404(id)
    if request.method == 'POST':
        application.status = request.form.get('status', application.status)
        db.session.commit()
        flash(f'Application #{application.id} updated successfully.', 'success')
        return redirect(url_for('admin.view_application', id=application.id))
        
    return render_template('admin_application_edit.html', application=application)

