from flask import Flask, render_template, request, redirect, flash, send_file
from config import Config
from models import db, Student, Subject, Result
import pandas as pd

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()


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


# ---------------- ADD STUDENT ----------------
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        try:
            adm_no = request.form["adm_no"]
            first_name = request.form["first_name"]
            second_name = request.form["second_name"]
            student = Student(
                adm_no=adm_no,
                first_name=first_name,
                second_name=second_name
            )
            db.session.add(student)
            db.session.commit()
            flash("Student added successfully!")
            return redirect("/")
        except:
            db.session.rollback()
            flash("Error adding student, adm_no already exists!!")

    return render_template("add_student.html")


# ---------------- ADD SUBJECT ----------------
@app.route("/add_subject", methods=["GET", "POST"])
def add_subject():
    if request.method == "POST":
        try:
            subject_name = request.form["subject_name"]
            subject = Subject(subject_name=subject_name)
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
    subjects = Subject.query.all()

    if request.method == "POST":
        try:
            student_id = request.form["student"]
            subject_id = request.form["subject"]
            marks = request.form["marks"]

            result = Result(
                student_id=student_id,
                subject_id=subject_id,
                marks=marks
            )

            db.session.add(result)
            db.session.commit()
            flash("Marks added successfully!")
            return redirect("/results")

        except:
            db.session.rollback()
            flash("Error adding marks")

    return render_template(
        "add_marks.html",
        students=students,
        subjects=subjects
    )


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
            flash("Excel must contain a 'adm_no' column", "error")
            return redirect("/import_marks")

        subjects = Subject.query.all()
        subject_map = {s.subject_name: s.id for s in subjects}

        for _, row in df.iterrows():
            adm_no = str(row["adm_no"]).strip()

            student = Student.query.filter_by(adm_no=adm_no).first()

            

            if not student:
                flash("Student must be present")

            for subject_name, subject_id in subject_map.items():
                if subject_name not in df.columns:
                    flash("subject name must be in column")

                mark = row[subject_name]
                if pd.isna(mark):
                    flash("mark not available")

                try:
                    mark = float(mark)
                except ValueError:
                    continue

                grade, points = grade_and_points(mark)

                existing = Result.query.filter_by(
                    student_id=student.id,
                    subject_id=subject_id
                ).first()

                if existing:
                    existing.marks = mark
                    existing.grade = grade
                    existing.points = points
                else:
                    db.session.add(
                        Result(student_id=student.id, subject_id=subject_id, marks=mark, grade=grade, points=points)
                    )

        db.session.commit()
        flash("Marks uploaded successfully", "success")
        return redirect("/results")

    except Exception as e:
        db.session.rollback()
        flash("Something went wrong. Upload failed.", "error")
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



