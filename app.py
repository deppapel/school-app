
from flask import Flask, render_template, request, redirect, flash
from config import Config
from models import db, Student, Subject, Result

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":

        try:    
            name = request.form["name"]
            student = Student(name=name)
            db.session.add(student)
            db.session.commit()
            flash('Student added succesfully!')
            return redirect("/")
        except Exception as e:
            db.session.rollback()
            flash('Error adding student')

    return render_template("add_student.html")

@app.route("/add_subject", methods=["GET", "POST"])
def add_subject():
    if request.method == "POST":
        try:    
            subject_name = request.form["subject_name"]
            subject = Subject(subject_name=subject_name)
    
            db.session.add(subject)
            db.session.commit()
            flash('Subject added succesfully!')
            return redirect("/")
        except Exception as e:
            db.session.rollback()
            flash('Error adding subject!')
    return render_template("add_subject.html")

@app.route("/add_marks", methods=["GET", "POST"])
def add_marks():
    students = Student.query.all()
    subjects = Subject.query.all()

    if request.method == "POST":
        try:    
            student_id = request.form["student"]
            subject_id = request.form["subject"]
            marks = request.form["marks"]

            result = Result(student_id=student_id, subject_id=subject_id, marks=marks)
        
            db.session.add(result)
            db.session.commit()
            flash('Marks added succesfully!')
            return redirect("/results")
        except Exception as e:
            db.sessionrollback()
            flash('Error adding student marks')

    return render_template("add_marks.html", students=students, subjects=subjects)

@app.route("/results")
def results():
    students = Student.query.all()
    subjects = Subject.query.all()
    results = Result.query.all()
    return render_template("view_results.html", students=students, subjects=subjects, results=results)

if __name__ == "__main__":
    app.run(debug=True)


