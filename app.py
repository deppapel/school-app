from flask import Flask, render_template, request, redirect, flash, send_file
from config import Config
from models import db, Student, Subject, Result
import pandas as pd


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

#subject categories
SYSTEM_SUBJECTS = [
    #Compulsory
    ("English", "COMPULSORY"),
    ("Mathematics", "COMPULSORY"),
    ("Kiswahili", "COMPULSORY"),
    ("Biology", "COMPULSORY"),
    ("Chemistry", "COMPULSORY"),
    ("Physics", "COMPULSORY"),

    #Arts
    ("History", "ARTS"),
    ("Geography", "ARTS"),
    ("CRE", "ARTS"),

    #APPLIED
    ("Computer Studies", "APPLIED"),
    ("Agriculture", "APPLIED"),
    ("Business Studies", "APPLIED"),
]

def seed_subjects():
    for name, category in SYSTEM_SUBJECTS:
        exists = Subject.query.filter_by(subject_name=name).first()
        if not exists:
            db.session.add(
                Subject(subject_name=name, category=category)
            )
    db.session.commit()

with app.app_context():
    db.create_all()
    seed_subjects()


@app.route("/")
def index():
    return render_template("index.html")

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

def save_or_update_result(student, subject, mark):
    grade, points = grade_and_points(mark)
    existing = Result.query.filter_by(
        student_id=student.id,
        subject_id=subject.id
    ).first()

    if existing:
        existing.marks = mark
        existing.grade = grade
        existing.points = points
    else:
        db.session.add(
            Result(
                student_id=student.id,
                subject_id=subject.id,
                marks=mark,
                grade=grade,
                points=points
            )
        )


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
                flash("Arts and Applied subjects must be different")
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
            flash("Student added successfully!")
            return redirect("/")
        except:
            db.session.rollback()
            flash("Error adding student, adm_no already exists!!")

    return render_template("add_student.html",
                           arts_subjects=arts_subjects,
                           applied_subjects=applied_subjects
                           )


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
            flash("Subject added successfully!")
            return redirect("/")
        except:
            db.session.rollback()
            flash("Error adding subject")

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

            grade, points = grade_and_points(mark)

            existing = Result.query.filter_by(
                student_id=student_id,
                subject_id=subject_id
            ).first()

            if existing:
                flash("Marks already entered for this subject")
                return redirect("/add_marks")

            db.session.add(
                Result(
                    student_id=student_id,
                    subject_id=subject_id,
                    marks=mark,
                    grade=grade,
                    points=points
                )
            )
            db.session.commit()
            flash("Marks added successfully")

        except:
            db.session.rollback()
            flash("Error adding marks")

    return render_template("add_marks.html", students=students)



# ---------------- DOWNLOAD EXCEL TEMPLATE ----------------
@app.route("/download_marks_template")
def download_marks_template():
    students = Student.query.all()
    subjects = Subject.query.all()

    data = []

    for student in students:
        row = {
            "adm_no": student.adm_no, 
            "student_name":student.first_name
        }
        for subject in subjects:
            row[subject.subject_name] = ""
            
        data.append(row)
        
    df = pd.DataFrame(data)
    file_name = "marks_template.xlsx"
    df.to_excel(file_name, index=False)

    return send_file(file_name, as_attachment=True)


# ---------------- UPLOAD EXCEL MARKS ----------------
@app.route("/import_marks", methods=["GET", "POST"])
def import_marks():
    if request.method == "GET":
        return render_template("import_marks.html")

    try:
        # 1️⃣ Check if file is uploaded
        if "file" not in request.files:
            flash("No file uploaded", "error")
            return redirect("/import_marks")

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect("/import_marks")

        # 2️⃣ Read Excel
        try:
            df = pd.read_excel(file)
        except Exception:
            flash("Invalid Excel file", "error")
            return redirect("/import_marks")

        # 3️⃣ Validate mandatory column
        if "adm_no" not in df.columns:
            flash("Excel must contain an 'adm_no' column", "error")
            return redirect("/import_marks")

        # 4️⃣ Fetch subjects from DB
        compulsory_subjects = Subject.query.filter_by(category="COMPULSORY").all()
        arts_subjects = Subject.query.filter_by(category="ARTS").all()
        applied_subjects = Subject.query.filter_by(category="APPLIED").all()

        for _, row in df.iterrows():
            adm_no = str(row["adm_no"]).strip()
            if pd.isna(adm_no):
                continue  # skip blank rows

            student = Student.query.filter_by(adm_no=adm_no).first()
            if not student:
                flash(f"Student with adm_no {adm_no} not found. Skipping row.", "warning")
                continue

            subject_count = 0
            total_points = 0

            # 5️⃣ Handle compulsory subjects
            for subject in compulsory_subjects:
                if subject.subject_name not in df.columns:
                    flash(f"Compulsory subject '{subject.subject_name}' missing in Excel.", "warning")
                    continue

                mark = row[subject.subject_name]
                if pd.isna(mark):
                    flash(f"Mark for {subject.subject_name} is missing for student {adm_no}.", "warning")
                    continue

                try:
                    mark = float(mark)
                except ValueError:
                    flash(f"Invalid mark for {subject.subject_name} for student {adm_no}.", "warning")
                    continue

                save_or_update_result(student, subject, mark)
                subject_count += 1
                total_points += grade_and_points(mark)[1]

            # 6️⃣ Handle ARTS
            if "ARTS" in df.columns and student.arts_subject_id:
                arts_mark = row["ARTS"]
                if not pd.isna(arts_mark):
                    try:
                        arts_mark = float(arts_mark)
                        save_or_update_result(student, student.arts_subject, arts_mark)
                        subject_count += 1
                        total_points += grade_and_points(arts_mark)[1]
                    except ValueError:
                        flash(f"Invalid Arts mark for student {adm_no}.", "warning")

            # 7️⃣ Handle APPLIED
            if "APPLIED" in df.columns and student.applied_subject_id:
                applied_mark = row["APPLIED"]
                if not pd.isna(applied_mark):
                    try:
                        applied_mark = float(applied_mark)
                        save_or_update_result(student, student.applied_subject, applied_mark)
                        subject_count += 1
                        total_points += grade_and_points(applied_mark)[1]
                    except ValueError:
                        flash(f"Invalid Applied mark for student {adm_no}.", "warning")

            # 8️⃣ Validation: max subjects
            if subject_count > 8:
                flash(f"Student {adm_no} has more than 8 subjects. Skipping extra subjects.", "warning")

            # 9️⃣ Validation: max points
            if total_points > 96:
                flash(f"Total points for student {adm_no} exceeds 96.", "warning")

        # 10️⃣ Commit everything once per file
        db.session.commit()
        flash("Marks uploaded successfully!", "success")
        return redirect("/results")

    except Exception as e:
        db.session.rollback()
        flash(f"Upload failed: {str(e)}", "error")
        return redirect("/import_marks")


# ---------------- VIEW RESULTS ----------------
@app.route("/results")
def results():
    students = Student.query.all()
    subjects = Subject.query.all()
    return render_template(
        "view_results.html",
        students=students,
        subjects=subjects,
    )


if __name__ == "__main__":
    app.run(debug=True)



