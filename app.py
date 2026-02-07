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


# ---------------- ADD STUDENT ----------------
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        try:
            name = request.form["name"]
            student = Student(name=name)
            db.session.add(student)
            db.session.commit()
            flash("Student added successfully!")
            return redirect("/")
        except:
            db.session.rollback()
            flash("Error adding student")

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
            "student_name": student.name
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

        if "student_name" not in df.columns:
            flash("Excel must contain a 'student_name' column", "error")
            return redirect("/import_marks")

        subjects = Subject.query.all()
        subject_map = {s.subject_name: s.id for s in subjects}

        for _, row in df.iterrows():
            student_name = row["student_name"]

            if pd.isna(student_name):
                continue

            student = Student.query.filter_by(name=str(student_name).strip()).first()
            if not student:
                continue

            for subject_name, subject_id in subject_map.items():
                if subject_name not in df.columns:
                    continue

                mark = row[subject_name]
                if pd.isna(mark):
                    continue

                try:
                    mark = float(mark)
                except ValueError:
                    continue

                existing = Result.query.filter_by(
                    student_id=student.id,
                    subject_id=subject_id
                ).first()

                if existing:
                    existing.marks = mark
                else:
                    db.session.add(
                        Result(student_id=student.id, subject_id=subject_id, marks=mark)
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
    results = Result.query.all()
    return render_template(
        "view_results.html",
        students=students,
        subjects=subjects,
        results=results
    )


if __name__ == "__main__":
    app.run(debug=True)



