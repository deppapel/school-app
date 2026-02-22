from flask import Flask, render_template, request, redirect, flash, send_file
from config import Config
from models import db, Student, Subject, Result, User, SystemSettings
import pandas as pd
import tempfile
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask import jsonify
from sqlalchemy import func
from datetime import datetime

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
        return redirect("/login")
    
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


@app.route("/search_students")
@login_required
def search_students():
    # Only admins can search (same as the main update_marks page)
    if current_user.role != "ADMIN":
        return jsonify([]), 403

    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify([])

    # Search by adm_no (case-insensitive partial match)
    students = Student.query.filter(Student.adm_no.ilike(f'%{query}%')).limit(10).all()

    results = []
    for s in students:
        results.append({
            'id': s.id,
            'adm_no': s.adm_no,
            'first_name': s.first_name,
            'second_name': s.second_name or '',
            'current_form': s.calculated_current_form
        })

    return jsonify(results)

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
    
    subject = Subject.query.all()
    settings = get_settings()
    if request.method == "POST":
        try:
            student_id = request.form["student"]
            subject_id = request.form["subject"]
            mark = float(request.form["marks"])

            student = Student.query.get(student_id)
            subject = Subject.query.get(subject_id)

            if not student or not subject:
                flash("Invalid student or subject selected", "error")
                return redirect("/update_marks")

            existing = Result.query.filter_by(student_id=student.id, subject_id=subject_id, form=student.calculated_current_form, term=settings.current_term, academic_year=settings.current_academic_year).first()

            save_or_update_result(student, subject, mark, student.calculated_current_form, settings.current_term, settings.current_academic_year)
            db.session.commit()

            if existing:
                flash(f"Marks updated for {student.first_name} in {subject.subject_name}", "success")   
            else:
                flash(f"marks added for {student.first_name} in {subject.subject_name}", "success")             
            return redirect("/update_marks")

        except Exception as e:
            db.session.rollback()
            flash(f"Error adding marks: {str(e)}", "error")

    return render_template("update_marks.html",  subjects=subject)


# ---------------- DOWNLOAD EXCEL TEMPLATE ----------------
@app.route("/download_marks_template/<int:form>/<int:year>/<int:term>")
@login_required
def download_marks_template(form, year, term):

    if current_user.role != 'ADMIN':
        flash("Unauthorized access!", "error")
        return redirect("/login")
    
    settings = get_settings()
    current_year = settings.current_academic_year

    students = Student.query.filter(
        Student.entry_form + current_year - Student.admission_year == form
    ).all()

    compulsory_subjects = Subject.query.filter_by(category="COMPULSORY").all()
    compulsory_subject_names = [s.subject_name for s in compulsory_subjects]

    columns = ["adm_no", "student_name", "form", "year", "term"] + compulsory_subject_names + ["ARTS", "APPLIED"]
    data = []

    for student in students:
        row = {
            "adm_no": student.adm_no,
            "student_name": f"{student.first_name} {student.second_name or ''}".strip(),
            "form": form,
            "year": year,
            "term": term
        }
        for subj in compulsory_subject_names:
            row[subj] = ""

        row["ARTS"] = ""
        row["APPLIED"] = ""
        data.append(row)

    if not data:
        data.append({col: "" for col in columns})

    df = pd.DataFrame(data, columns=columns)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(tmp.name, index=False)
    tmp.close()

    return send_file(
        tmp.name,
        as_attachment=True,
        download_name=f"marks_template_form{form}_term{term}_{year}.xlsx"
    )


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

            # ARTS 
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

            # APPLIED 
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
    
    # --- Get search parameters ---
    sel_year = request.args.get('year', settings.current_academic_year, type=int)
    sel_term = request.args.get('term', settings.current_term, type=int)
    
    # Admin default: if no form specified, use 1
    form_param = request.args.get('form')
    if form_param is None:
        sel_form = 1 if current_user.role == 'ADMIN' else None
    else:
        try:
            sel_form = int(form_param)
            # Ensure it's 1-4 for admin; for students it may be calculated later
        except (ValueError, TypeError):
            sel_form = 1 if current_user.role == 'ADMIN' else None

    # --- Student historic form calculation ---
    if current_user.role in ['GUEST', 'STUDENT']:
        student_rec = Student.query.filter_by(adm_no=current_user.username).first()
        if not student_rec:
            flash("Student profile not found.")
            return redirect("/login")
        year_diff = settings.current_academic_year - sel_year
        calculated_historic_form = student_rec.calculated_current_form - year_diff
        sel_form = max(calculated_historic_form, 1)   # cap at 1
        # For students, we will still query all students with that historic form,
        # but we need to know their ID to possibly restrict? No, they see whole class.
        # So we'll continue as before.

    # --- Fetch students efficiently using SQL (no more all_students list) ---
    # Build base query: we want all students
    query = Student.query

    # If a specific form is selected (and we are not student with sel_form set),
    # filter using SQL expression for historic form.
    if sel_form is not None:
        # Historic form formula: entry_form + (current_year - admission_year) - (current_year - sel_year)
        # Simplify: entry_form + (sel_year - admission_year)
        # But careful: the original formula used calculated_current_form = entry_form + (current_year - admission_year)
        # Then historic = calculated_current_form - (current_year - sel_year) = entry_form + (sel_year - admission_year)
        # So we can directly use entry_form + (sel_year - admission_year) == sel_form
        from sqlalchemy import func
        query = query.filter(
            Student.entry_form + (sel_year - Student.admission_year) == sel_form
        )
    
    filtered_students = query.all()   # Only loads needed students

    # --- Subject lists (unchanged) ---
    compulsory_subjects = Subject.query.filter_by(category="COMPULSORY").all()
    arts_subjects = Subject.query.filter_by(category="ARTS").all()
    applied_subjects = Subject.query.filter_by(category="APPLIED").all()

    # --- Build result matrix (similar, but we already have filtered_students) ---
    student_data = []
    for student in filtered_students:
        # For the result query, we need the form the student was in during the selected year.
        # Use the same formula: entry_form + (sel_year - admission_year)
        form_at_time = student.entry_form + (sel_year - student.admission_year)
        # But ensure it's at least 1 (for safety)
        if form_at_time < 1:
            form_at_time = 1

        results = Result.query.filter_by(
            student_id=student.id,
            academic_year=sel_year,
            term=sel_term,
            form=form_at_time
        ).all()

        if results:   # Only include students with at least one result
            results_dict = {r.subject_id: r for r in results}
            total_points = sum(r.points for r in results)
            total_marks = sum(r.marks for r in results)
            final_grade = student_final_grade(total_points)
            student_data.append({
                "student": student,
                "results_dict": results_dict,
                "total_points": total_points,
                "total_marks": total_marks,
                "final_grade": final_grade
            })

    # --- Ranking ---
    student_data.sort(key=lambda x: (x['total_points'], x['total_marks']), reverse=True)
    for idx, data in enumerate(student_data):
        data['rank'] = idx + 1

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
    sel_year = request.args.get('year', settings.current_academic_year, type=int)
    sel_term = request.args.get('term', settings.current_term, type=int)

    # --- Validate selected year is within reasonable range ---
    if sel_year < student.admission_year:
        flash("You were not enrolled in that year.", "warning")
        sel_year = student.admission_year

    # --- Calculate student's form at selected time ---
    form_at_time = student.entry_form + (sel_year - student.admission_year)
    if form_at_time < 1:
        form_at_time = 1
    if form_at_time > 4:   # assuming max form 4
        form_at_time = 4

    # --- Fetch student's results for selected term (with subject joined) ---
    results = Result.query.options(db.joinedload(Result.subject)).filter_by(
        student_id=student.id,
        academic_year=sel_year,
        term=sel_term
    ).all()

    if not results:
        flash("No results found for this term.", "info")

    # --- Build subject details in consistent order using subject lists ---
    compulsory_subjects = Subject.query.filter_by(category="COMPULSORY").all()
    arts_subjects = Subject.query.filter_by(category="ARTS").all()
    applied_subjects = Subject.query.filter_by(category="APPLIED").all()
    all_subjects = compulsory_subjects + arts_subjects + applied_subjects

    result_by_subject_id = {r.subject_id: r for r in results}

    subject_details = []
    for subj in all_subjects:
        r = result_by_subject_id.get(subj.id)
        if r:
            remark = "Excellent" if r.marks >= 80 else "Good" if r.marks >= 70 else "Fair" if r.marks >= 60 else "Needs Improvement"
            subject_details.append({
                'id': subj.id,
                'name': subj.subject_name,
                'category': subj.category,
                'score': r.marks,
                'grade': r.grade,
                'points': r.points,
                'remark': remark
            })
        # else: subject not taken – skip

    # --- Compute totals ---
    total_points = sum(r.points for r in results)
    final_grade = student_final_grade(total_points)

    # --- Find classmates in the same form, term, year ---
    classmates = Student.query.filter(
        Student.entry_form + (sel_year - Student.admission_year) == form_at_time
    ).all()
    classmate_ids = [c.id for c in classmates]

    # Get total points for each classmate via a GROUP BY query
    if classmate_ids:
        rank_data = db.session.query(
            Result.student_id,
            func.sum(Result.points).label('total_points')
        ).filter(
            Result.student_id.in_(classmate_ids),
            Result.academic_year == sel_year,
            Result.term == sel_term
        ).group_by(Result.student_id).all()
    else:
        rank_data = []

    points_dict = {r.student_id: r.total_points for r in rank_data}
    # Ensure current student is in dict (even if no results, points = 0)
    if student.id not in points_dict:
        points_dict[student.id] = 0

    sorted_students = sorted(points_dict.items(), key=lambda x: x[1], reverse=True)
    rank = 1
    for i, (sid, pts) in enumerate(sorted_students):
        if sid == student.id:
            rank = i + 1
            break
    total_students = len(sorted_students)

    # --- Compute class average per subject ---
    subject_averages = {}
    if classmate_ids:
        avg_data = db.session.query(
            Result.subject_id,
            func.avg(Result.marks).label('avg_mark')
        ).filter(
            Result.student_id.in_(classmate_ids),
            Result.academic_year == sel_year,
            Result.term == sel_term
        ).group_by(Result.subject_id).all()
        subject_averages = {a.subject_id: round(a.avg_mark, 1) for a in avg_data}

    average_scores = [subject_averages.get(subj['id'], 0) for subj in subject_details]

    # --- Trend data: fetch previous terms in same academic year ---
    trend_data = []
    for term in range(1, sel_term + 1):
        term_results = Result.query.filter_by(
            student_id=student.id,
            academic_year=sel_year,
            term=term
        ).all()
        term_points = sum(r.points for r in term_results)
        trend_data.append({'term': term, 'points': term_points})

    # --- Find weakest subject for class teacher comment ---
    if subject_details:
        weakest = min(subject_details, key=lambda x: x['score'])
        weakest_name = weakest['name']
        weakest_score = weakest['score']
    else:
        weakest_name = "N/A"
        weakest_score = 0

    # --- Head teacher remark based on total points ---
    if total_points >= 86:
        head_teacher_remark = "Perfect! Maintain this excellence and aim for consistency."
    elif total_points >= 82:
        head_teacher_remark = "Outstanding! You are very close to an A. Keep the momentum."
    elif total_points >= 78:
        head_teacher_remark = "Excellent. Strive for an A- by refining your understanding."
    elif total_points >= 74:
        head_teacher_remark = "Very good. You are capable of an even higher grade."
    elif total_points >= 70:
        head_teacher_remark = "Great work! With a little more effort, you can attain a B."
    elif total_points >= 66:
        head_teacher_remark = "Commendable. Keep pushing – the next grade is within reach."
    elif total_points >= 62:
        head_teacher_remark = "Satisfactory performance. Aim higher by strengthening weak areas."
    elif total_points >= 58:
        head_teacher_remark = "Good effort. With consistent revision, you can achieve a higher grade."
    elif total_points >= 48:
        head_teacher_remark = "You are on the right track, but need to work harder to reach the next level."
    else:
        head_teacher_remark = "Needs significant improvement. Focus on core subjects and seek extra help."

    # --- Class teacher remark based on rank and weakest subject ---
    if total_students == 0:
        overall_teacher_comment = "No data available for class comparison."
    else:
        if rank == 1:
            overall_teacher_comment = f"Excellent performance! You are at the top of your class. Keep up the great work."
        elif rank <= total_students * 0.1:  # top 10%
            overall_teacher_comment = f"Very good! You are among the top performers. To reach the top, focus on {weakest_name} where you scored {weakest_score}."
        elif rank <= total_students * 0.25:  # top 25%
            overall_teacher_comment = f"Good job! You are in the top quarter. Work a bit more on {weakest_name} ({weakest_score}) to climb higher."
        elif rank <= total_students * 0.5:  # top half
            overall_teacher_comment = f"Satisfactory. You are in the top half. Putting extra effort into {weakest_name} ({weakest_score}) will boost your rank."
        else:
            overall_teacher_comment = f"You are in the lower half. Don't be discouraged. With consistent effort, especially in {weakest_name} ({weakest_score}), you can improve significantly."

    # --- Prepare data for charts ---
    chart_subjects = [s['name'] for s in subject_details]
    chart_scores = [s['score'] for s in subject_details]

    return render_template(
        "personal_report.html",
        student=student,
        subject_details=subject_details,
        total_points=total_points,
        final_grade=final_grade,
        rank=rank,
        total_students=total_students,
        sel_year=sel_year,
        sel_term=sel_term,
        form_at_time=form_at_time,
        trend_data=trend_data,
        subject_averages=subject_averages,
        average_scores=average_scores,
        chart_subjects=chart_subjects,
        chart_scores=chart_scores,
        overall_teacher_comment=overall_teacher_comment,
        head_teacher_remark=head_teacher_remark,
        date_of_issue=datetime.now().strftime("%d %B %Y")
    )

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



