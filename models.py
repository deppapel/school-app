
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Student(db.Model):
    __tablename__ = "student"


    id = db.Column(db.Integer, primary_key=True)
    adm_no = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    second_name = db.Column(db.String(50))

    results = db.relationship(
        "Result", backref="student", cascade="all, delete-orphan"
    )

    def __repr__(self):
         return f"<Student {self.adm_no} - {self.first_name}>"


class Subject(db.Model):
    __tablename__ = "subject"

    id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(100), unique=True, nullable=False)

    results=db.relationship(
        "Result", backref="subject", cascade="all, delete-orphan"
    )
    def __repr__(self):
        return f"<Subject {self.subject_name}>"    


class Result(db.Model):
    __tablename__="result"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(2))
    points = db.Column(db.Integer)

   # PREVENT DUPLICATE
    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", name="unique_student_subject"),
   )

    def __repr__(self):
        return f"<Result {self.student_id}-{self.subject_id}: {self.marks}>"

