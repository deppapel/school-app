from flask import Flask, render_template, request, redirect, flash, send_file
from config import Config
from models import db, Student, Subject, Result
import pandas as pd
import tempfile

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

app.secret_key = "super-secret-key"  # Required for flash messages

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


with app.app_context():
    db.create_all()
    seed_subjects()


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
    


def save_or_update_result(student, subject, mark):
    grade, points = grade_and_points(mark)
    existing = Result.query.filter_by(student_id=student.id, subject_id=subject.id).first()
    if existing:
        existing.marks = mark
        existing.grade = grade
        existing.points = points
    else:
        db.session.add(
            Result(student_id=student.id, subject_id=subject.id, marks=mark, grade=grade, points=points)
        )


# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------- ADD STUDENT ----------------
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    arts_subjects = Subject.query.filter_by(category="ARTS").all()
    applied_subjects = Subject.query.filter_by(category="APPLIED").all()

    if request.method == "POST":
        try:
            adm_no = request.form["adm_no"]
            first_name = request.form["first_name"]
            second_name = request.form["second_name"]
            arts_id = request.form["arts_subject"]
            applied_id = request.form["applied_subject"]

            if arts_id == applied_id:
                flash("Arts and Applied subjects must be different", "error")
                return redirect("/add_student")

            student = Student(
                adm_no=adm_no,
                first_name=first_name,
                second_name=second_name,
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
def add_subject():
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


# ---------------- ADD MARKS (MANUAL) ----------------
@app.route("/add_marks", methods=["GET", "POST"])
def add_marks():
    students = Student.query.all()
    if request.method == "POST":
        try:
            student_id = request.form["student"]
            subject_id = request.form["subject"]
            mark = float(request.form["marks"])
            existing = Result.query.filter_by(student_id=student_id, subject_id=subject_id).first()
            if existing:
                flash("Marks already entered for this subject", "error")
                return redirect("/add_marks")
            save_or_update_result(Student.query.get(student_id), Subject.query.get(subject_id), mark)
            db.session.commit()
            flash("Marks added successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding marks: {str(e)}", "error")

    return render_template("add_marks.html", students=students)


# ---------------- DOWNLOAD EXCEL TEMPLATE ----------------
@app.route("/download_marks_template")
def download_marks_template():
    students = Student.query.all()
    
    COMPULSORY_SUBJECTS = [
        "English",
        "Mathematics",
        "Biology",
        "Chemistry",
        "Physics",
        "Kiswahili"
    ]
    
    columns = ["adm_no", "student_name"] + COMPULSORY_SUBJECTS + ["ARTS", "APPLIED"]

    data = []

    for student in students:
        row = {"adm_no": student.adm_no, "student_name": student.first_name}

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
def import_marks():
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
                save_or_update_result(student, subject, mark)
                subject_count += 1
                total_points += grade_and_points(mark)[1]

            # ARTS
            if "ARTS" in df.columns and student.arts_subject_id:
                arts_mark = row["ARTS"]
                if not pd.isna(arts_mark):
                    try:
                        arts_mark = float(arts_mark)
                        save_or_update_result(student, student.arts_subject, arts_mark)
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
                        save_or_update_result(student, student.applied_subject, applied_mark)
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
def results():

    students = Student.query.all()

    student_data = []

    for student in students:
        compulsory_subjects = Subject.query.filter_by(category="COMPULSORY").all()

        results = Result.query.filter_by(student_id=student.id).all()

        total_points = sum(r.points for r in results)
        total_subjects = len(results)

        final_grade = student_final_grade(total_points)

        student_data.append({
            "student": student,
            "results": results,
            "total_points": total_points,
            "total_subjects": total_subjects,
            "final_grade": final_grade 
        })

    return render_template(
        "view_results.html",
        student_data=student_data,
        compulsory_subjects=compulsory_subjects
    )



if __name__ == "__main__":
    app.run(debug=True)




