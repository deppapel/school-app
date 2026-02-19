from flask import Flask, render_template, request, redirect, flash, send_file
from config import Config
from models import db, Student, Subject, Result, User, SystemSettings
import pandas as pd
import tempfile
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
import os


def get_settings():
    settings = SystemSettings.query.first()
    if not settings:
        # Initial default if table is empty
        settings = SystemSettings(current_academic_year=2026, current_term=1)
        db.session.add(settings)
        db.session.commit()
    return settings

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def manage_settings():
    if current_user.role != "ADMIN":
        flash("Unauthorized access!")
        return redirect("/")
    
    settings = get_settings()
    if request.method == "POST":
        settings.current_academic_year = int(request.form["year"])
        settings.current_term = int(request.form["term"])
        db.session.commit()
        flash(f"System updated: {settings.current_academic_year} Term {settings.current_term}")
        return redirect("/admin/settings")
        
    return render_template("manage_settings.html", settings=settings)

app.secret_key = "super-secret-key"  # Required for flash messages

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- SYSTEM SUBJECTS ----------------
SYSTEM_SUBJECTS = [
    # Compulsory
    ("English", "COMPULSORY"),
    ("Mathematics", "COMPULSORY"),
    ("Kiswahili", "COMPULSORY"),
    ("Biology", "COMPULSORY"),
    ("Chemistry", "COMPULSORY"),
    ("Physics", "COMPULSORY"),

    # Arts
    ("History", "ARTS"),
    ("Geography", "ARTS"),
    ("CRE", "ARTS"),

    # Applied
    ("Computer Studies", "APPLIED"),
    ("Agriculture", "APPLIED"),
    ("Business Studies", "APPLIED"),
]


def seed_subjects():
    for name, category in SYSTEM_SUBJECTS:
        exists = Subject.query.filter_by(subject_name=name).first()
        if not exists:
            db.session.add(Subject(subject_name=name, category=category))
    db.session.commit()


# ---------------- HELPER FUNCTIONS ----------------
def grade_and_points(mark):
    if mark >= 80:
        return "A", 12
    elif mark >= 70:
        return "B", 10
    elif mark >= 60:
        return "C", 8
    elif mark >= 50:
        return "D", 6
    else:
        return "E", 2
    
def student_final_grade(total_points):
    if total_points >= 86:
        return "A"
    elif total_points >= 82:
        return "A-"
    elif total_points >= 78:
        return "B+"
    elif total_points >= 74:
        return "B"
    elif total_points >= 70:
        return "B-"
    elif total_points >= 66:
        return "C+"
    elif total_points >= 62:
        return "C"
    elif total_points >= 58:
        return "C-"
    elif total_points >= 48:
        return "D"
    else:
        return "E"
    


def save_or_update_result(student, subject, mark, form_lvl, term_lvl, year_lvl):
    grade, points = grade_and_points(mark)
    existing = Result.query.filter_by(student_id=student.id, subject_id=subject.id, form=form_lvl, term=term_lvl, academic_year=year_lvl).first()
    if existing:
        existing.marks = mark
        existing.grade = grade
        existing.points = points
    else:
        db.session.add(
            Result(student_id=student.id, subject_id=subject.id, marks=mark, grade=grade, points=points, form=form_lvl, term=term_lvl, academic_year=year_lvl)
        )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # 1. Admin Login
        if username == "admin" and password == "school123":
            user = User.query.filter_by(username="admin").first()
            if not user:
                # Seed admin user if not exists
                user = User(username="admin", password="school123", role="ADMIN")
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect("/")

        # 2. Guest Login (Student)
        student = Student.query.filter_by(adm_no=username).first()
        if student and password == "student":
            user = User.query.filter_by(username=username).first()
            if not user:
                # Create a user record if it doesn't exist yet
                user = User(username=username, password="student", role="GUEST")
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect("/dashboard") # Send guests straight to the matrix
            
    return render_template("login.html")

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/dashboard")
@login_required
def student_dashboard():
    # Find the student record linked to the logged-in user
    student = Student.query.filter_by(adm_no=current_user.username).first()
    if not student:
        flash("Student profile not found.")
        return redirect("/login")
        
    return render_template("student_dashboard.html", student=student)

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    # If the user is NOT logged in, send them straight to the login page
    if not current_user.is_authenticated:
        return redirect("/login")
    
    # If they ARE logged in, check their role to see where they go
    if current_user.role == 'ADMIN':
        settings = get_settings()
        return render_template("index.html", settings=settings)
    
    # If they are a student, send them to their results or portal
    return redirect("/dashboard")


# ---------------- ADD STUDENT ----------------
@app.route("/add_student", methods=["GET", "POST"])
@login_required
def add_student():
    if current_user.role != 'ADMIN':
        flash("Unauthorized acces! please login as admin")
        return redirect("/login")
    
    arts_subjects = Subject.query.filter_by(category="ARTS").all()
    applied_subjects = Subject.query.filter_by(category="APPLIED").all()

    if request.method == "POST":
        try:
            adm_no = request.form["adm_no"]
            first_name = request.form["first_name"]
            second_name = request.form["second_name"]
            e_form = int(request.form["entry_form"])
            adm_year = int(request.form["admission_year"])
            arts_id = request.form["arts_subject"]
            applied_id = request.form["applied_subject"]

            if arts_id == applied_id:
                flash("Arts and Applied subjects must be different", "error")
                return redirect("/add_student")

            student = Student(
                adm_no=adm_no,
                first_name=first_name,
                second_name=second_name,
                entry_form=e_form,
                admission_year=adm_year,
                arts_subject_id=arts_id,
                applied_subject_id=applied_id
            )
            db.session.add(student)
            db.session.commit()
            flash("Student added successfully!", "success")
            return redirect("/")
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding student: {str(e)}", "error")

    return render_template("add_student.html", arts_subjects=arts_subjects, applied_subjects=applied_subjects)


# ---------------- ADD SUBJECT ----------------
@app.route("/add_subject", methods=["GET", "POST"])
@login_required
def add_subject():
    if current_user.role != 'ADMIN':
        flash("Unauthorized acces! please login as admin")
        return redirect("/login")
    
    if request.method == "POST":
        try:
            subject_name = request.form["subject_name"]
            category = request.form["category"]
            subject = Subject(subject_name=subject_name, category=category)
            db.session.add(subject)
            db.session.commit()
            flash("Subject added successfully!", "success")
            return redirect("/")
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding subject: {str(e)}", "error")

    return render_template("add_subject.html")


# ---------------- UPDATE MARKS (MANUAL) ----------------
@app.route("/update_marks", methods=["GET", "POST"])
@login_required
def update_marks():
    if current_user.role != "ADMIN":
        flash("Unauthorised! Only school admin can modify marks")
        return redirect("/login")
    student = Student.query.all()
    subject = Subject.query.all()
    settings = get_settings()
    if request.method == "POST":
        try:
            student_id = request.form["student"]
            subject_id = request.form["subject"]
            mark = float(request.form["marks"])

            student = Student.query.get(student_id)
            subject = Subject.query.get(subject_id)

            existing = Result.query.filter_by(student_id=student_id, subject_id=subject_id).first()

            save_or_update_result(student, subject, mark, student.calculated_current_form, settings.current_term, settings.current_academic_year)
            db.session.commit()

            if existing:
                flash(f"Marks updated for {student.first_name} in {subject.subject_name}")   
            else:
                flash(f"marks added for {student.first_name} in {subject.subject_name}")             
            return redirect("/update_marks")

        except Exception as e:
            db.session.rollback()
            flash(f"Error adding marks: {str(e)}", "error")

    return render_template("update_marks.html", students=student, subjects=subject)


# ---------------- DOWNLOAD EXCEL TEMPLATE ----------------
@app.route("/download_marks_template/<int:form>/<int:year>/<int:term>")
def download_marks_template(form, year, term):
    # Filter students by the calculated form requested
    all_students = Student.query.all()
    students = [s for s in all_students if s.calculated_current_form == form]
    
    COMPULSORY_SUBJECTS = ["English", "Mathematics", "Biology", "Chemistry", "Physics", "Kiswahili"]
    
    # Added form, year, term to columns so the upload can read them
    columns = ["adm_no", "student_name", "form", "year", "term"] + COMPULSORY_SUBJECTS + ["ARTS", "APPLIED"]
    data = []

    for student in students:
        # Reverted to your exact naming: student.first_name
        row = {"adm_no": student.adm_no, "student_name": student.first_name, "form": form, "year": year, "term": term}

        for subject in COMPULSORY_SUBJECTS:
            row[subject] = ""

        row["ARTS"] = "" 
        row["APPLIED"] = "" 
        data.append(row)

    if not data:
        data.append({col: "" for col in columns})    

    df = pd.DataFrame(data, columns=columns)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(tmp.name, index=False)
    tmp.close()
    return send_file(tmp.name, as_attachment=True)


# ---------------- UPLOAD EXCEL MARKS ----------------
@app.route("/import_marks", methods=["GET", "POST"])
@login_required
def import_marks():
    if current_user.role != "ADMIN":
        flash("Unauthorized access!")
        return redirect("/login")

    if request.method == "GET":
        return render_template("import_marks.html")

    try:
        if "file" not in request.files:
            flash("No file uploaded", "error")
            return redirect("/import_marks")
        file = request.files["file"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect("/import_marks")

        try:
            df = pd.read_excel(file)
        except Exception:
            flash("Invalid Excel file", "error")
            return redirect("/import_marks")

        if "adm_no" not in df.columns:
            flash("Excel must contain an 'adm_no' column", "error")
            return redirect("/import_marks")
        
        compulsory_subjects = Subject.query.filter_by(category="COMPULSORY").all()

        for _, row in df.iterrows():
            adm_no = str(row["adm_no"]).strip()
            if pd.isna(adm_no):
                continue
            student = Student.query.filter_by(adm_no=adm_no).first()
            if not student:
                flash(f"Student {adm_no} not found. Skipping.", "warning")
                continue

            # CRITICAL UPDATE: Read these from the Excel row instead of global settings
            # This ensures the upload matches the template's designated period
            student_form = int(row["form"])
            curr_year = int(row["year"])
            curr_term = int(row["term"])

            subject_count = 0
            total_points = 0

            # Compulsory
            for subject in compulsory_subjects:
                if subject.subject_name not in df.columns:
                    flash(f"Compulsory subject {subject.subject_name} missing in Excel", "warning")
                    continue
                mark = row[subject.subject_name]
                if pd.isna(mark):
                    flash(f"Mark missing for {subject.subject_name} for {adm_no}", "warning")
                    continue
                try:
                    mark = float(mark)
                except (ValueError, TypeError):
                    flash(f"Invalid mark {mark} for {subject.subject_name} for {adm_no}", "warning")
                    continue
                
                # Using your exact function signature
                save_or_update_result(student, subject, mark, student_form, curr_term, curr_year)
                subject_count += 1
                total_points += grade_and_points(mark)[1]

            # ARTS (Keeping your exact logic and naming)
            if "ARTS" in df.columns and student.arts_subject_id:
                arts_mark = row["ARTS"]
                if not pd.isna(arts_mark):
                    try:
                        arts_mark = float(arts_mark)
                        save_or_update_result(student, student.arts_subject, arts_mark, student_form, curr_term, curr_year)
                        subject_count += 1
                        total_points += grade_and_points(arts_mark)[1]
                    except (ValueError, TypeError):
                        flash(f"Invalid Arts mark for {adm_no}", "warning")

            # APPLIED (Keeping your exact logic and naming)
            if "APPLIED" in df.columns and student.applied_subject_id:
                applied_mark = row["APPLIED"]
                if not pd.isna(applied_mark):
                    try:
                        applied_mark = float(applied_mark)
                        save_or_update_result(student, student.applied_subject, applied_mark, student_form, curr_term, curr_year)
                        subject_count += 1
                        total_points += grade_and_points(applied_mark)[1]
                    except (ValueError, TypeError):
                        flash(f"Invalid Applied mark for {adm_no}", "warning")

            # Validation
            if subject_count > 8:
                flash(f"Student {adm_no} has more than 8 subjects. Skipping extra.", "warning")
            if total_points > 96:
                flash(f"Total points for student {adm_no} exceeds 96.", "warning")

        try:
            db.session.commit()
            flash("Marks uploaded successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Database commit failed: {str(e)}", "error")
            return redirect("/import_marks")

        return redirect("/results")

    except Exception as e:
        db.session.rollback()
        flash(f"Upload failed: {str(e)}", "error")
        return redirect("/import_marks")


# ---------------- VIEW RESULTS ----------------
@app.route("/results")
@login_required
def results():
    settings = get_settings()
    
    # 1. GET SEARCH PARAMETERS
    sel_year = request.args.get('year', settings.current_academic_year, type=int)
    sel_term = request.args.get('term', settings.current_term, type=int)
    sel_form = request.args.get('form', type=int)

    # --- HISTORICAL FORM CALCULATION ---
    if current_user.role == 'GUEST' or current_user.role == 'STUDENT':
        student_rec = Student.query.filter_by(adm_no=current_user.username).first()
        if student_rec:
            # If the student is searching for a past year, 
            # calculate what form they were in back then.
            # Example: Current Year (2026) Form 4 - (2026 - 2023) = Form 1.
            year_diff = settings.current_academic_year - sel_year
            calculated_historic_form = student_rec.calculated_current_form - year_diff
            
            # Lock the search to that historic form
            sel_form = calculated_historic_form
            
            # Safety check: If the calculation goes below 1 (before they started school)
            # or they search for the future, we cap it or handle it.
            if sel_form < 1:
                sel_form = 1 
        else:
            flash("Student profile not found.")
            return redirect("/login")
    # --- END HISTORICAL LOCK ---

    # 2. FILTER STUDENTS
    all_students = Student.query.all()
    filtered_students = []
    
    for student in all_students:
        # We filter based on the student's calculated form FOR THE SEARCHED YEAR
        # We need to calculate each student's form relative to the selected year
        year_diff = settings.current_academic_year - sel_year
        student_form_at_that_time = student.calculated_current_form - year_diff
        
        if sel_form:
            if student_form_at_that_time == sel_form:
                filtered_students.append(student)
        else:
            # If no form is selected (Admin view 'All'), show everyone
            filtered_students.append(student)

    # 3. BUILD THE DATA MATRIX (Keep your existing code)
    compulsory_subjects = Subject.query.filter_by(category="COMPULSORY").all()
    arts_subjects = Subject.query.filter_by(category="ARTS").all()
    applied_subjects = Subject.query.filter_by(category="APPLIED").all()
    
    student_data = []

    for student in filtered_students:
        # Find results matching the student, the selected year/term, 
        # and the form they were in at that specific time.
        year_diff = settings.current_academic_year - sel_year
        form_at_time = student.calculated_current_form - year_diff

        results = Result.query.filter_by(
            student_id=student.id,
            academic_year=sel_year,
            term=sel_term,
            form=form_at_time
        ).all()

        results_dict = {result.subject_id: result for result in results}
        total_points = sum(r.points for r in results)
        total_marks = sum(r.marks for r in results)
        final_grade = student_final_grade(total_points)

        if results:
            student_data.append({
                "student": student,
                "results_dict": results_dict,
                "total_points": total_points,
                "total_marks": total_marks,
                "final_grade": final_grade 
            })

    # 4. RANKING (Keep your existing code)
    student_data.sort(key=lambda x: (x['total_points'], x['total_marks']), reverse=True)
    for index, data in enumerate(student_data):
        data['rank'] = index + 1

    return render_template(
        "view_results.html",
        student_data=student_data,
        compulsory_subjects=compulsory_subjects,
        arts_subjects=arts_subjects,
        applied_subjects=applied_subjects,
        sel_year=sel_year,
        sel_term=sel_term,
        sel_form=sel_form
    )

@app.route("/my_report_card")
@login_required
def my_report_card():

    student = Student.query.filter_by(adm_no=current_user.username).first()
    if not student:
        return "Student record not found", 404
    
    settings = get_settings()
    
    # Get search params, defaulting to current system settings
    sel_year = request.args.get('year', settings.current_academic_year, type=int)
    sel_term = request.args.get('term', settings.current_term, type=int)

    results = Result.query.filter_by(student_id=student.id, academic_year=sel_year, term=sel_term).all()

    total_points = sum(r.points for r in results)
    final_grade = student_final_grade(total_points)

    return render_template("personal_report.html", student=student, results=results, final_grade=final_grade, sel_year=sel_year, sel_term=sel_term)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not Subject.query.first():
            seed_subjects()

        if not SystemSettings.query.first():
            default_settings = SystemSettings(current_academic_year=2026, current_term=1)
            db.session.add(default_settings)
            
        # 3. Seed Admin User
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", password="school123", role="ADMIN")
            db.session.add(admin)
            
        db.session.commit()



