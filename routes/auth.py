import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models import User, Company, Student

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role') # admin, company, or student
        
        # Admin logs in with username typically, but here we requested email in mockup. 
        # Check if email is 'admin' (username) or the actual email
        user = User.query.filter((User.email == email) | (User.username == email)).first()
        
        if user and user.check_password(password):
            if role and user.role != role.lower():
                flash('Incorrect role selected.', 'error')
                return redirect(url_for('auth.login'))
            
            if not user.is_active:
                flash('Account is inactive or blacklisted.', 'error')
                return redirect(url_for('auth.login'))

            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'company':
                if user.company_profile and user.company_profile.approval_status != 'approved':
                    logout_user()
                    flash('Your company account is pending admin approval or blacklisted.', 'error')
                    return redirect(url_for('auth.login'))
                return redirect(url_for('company.dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student.dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@auth_bp.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        hr_name = request.form.get('hr_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        website = request.form.get('website')
        description = request.form.get('description')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email address already registered.', 'error')
            return redirect(url_for('auth.register_company'))
            
        user = User(username=email, email=email, role='company')
        user.set_password(password)
        db.session.add(user)
        db.session.flush() # get user.id
        
        # Logo handling (optional for now, can be updated later)
        logo_file = request.files.get('logo')
        logo_path = None
        if logo_file and logo_file.filename:
            from flask import current_app
            import os
            from werkzeug.utils import secure_filename
            filename = secure_filename(logo_file.filename)
            upload_dir = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            logo_file.save(os.path.join(upload_dir, filename))
            logo_path = 'uploads/' + filename


        company = Company(
            user_id=user.id,
            company_name=company_name,
            hr_name=hr_name,
            hr_email=email,
            hr_phone=phone,
            website=website,
            description=description,
            logo_path=logo_path
        )
        db.session.add(company)
        db.session.commit()
        
        flash('Registration successful! Please wait for admin approval before logging in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('register_company.html')

@auth_bp.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        roll_no = request.form.get('roll_no')
        branch = request.form.get('branch')
        year = request.form.get('year')
        cgpa = request.form.get('cgpa')
        skills = request.form.get('skills')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first() or Student.query.filter_by(roll_no=roll_no).first():
            flash('Email or Roll Number already registered.', 'error')
            return redirect(url_for('auth.register_student'))
            
        user = User(username=roll_no, email=email, role='student') # roll_no as username
        user.set_password(password)
        db.session.add(user)
        db.session.flush() # get user.id
        
        # Resume handling (optional for now, can be updated later)
        resume_file = request.files.get('resume')
        resume_path = None
        if resume_file and resume_file.filename:
            from flask import current_app
            import os
            from werkzeug.utils import secure_filename
            filename = secure_filename(resume_file.filename)
            upload_dir = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            resume_file.save(os.path.join(upload_dir, filename))
            resume_path = 'uploads/' + filename


        student = Student(
            user_id=user.id,
            full_name=full_name,
            roll_no=roll_no,
            branch=branch,
            year=year,
            cgpa=float(cgpa) if cgpa else None,
            phone=phone,
            skills=skills,
            resume_path=resume_path
        )
        db.session.add(student)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('register_student.html')
