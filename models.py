
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Student(db.Model):
    __tablename__ = "student"


    id = db.Column(db.Integer, primary_key=True)
    adm_no = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    second_name = db.Column(db.String(50))

    #optional subjects
    arts_subject_id = db.Column(
        db.Integer, db.ForeignKey("subject.id"), nullable=False
    )

    applied_subject_id = db.Column(
        db.Integer, db.ForeignKey("subject.id"), nullable=False
    )
    arts_subject = db.relationship(
        "Subject", foreign_keys=[arts_subject_id]
    )
    applied_subject = db.relationship(
        "Subject", foreign_keys=[applied_subject_id]
    )
    results = db.relationship(
        "Result", backref="student", cascade="all, delete-orphan"
    )

    def __repr__(self):
         return f"<Student {self.adm_no} - {self.first_name}>"


class Subject(db.Model):
    __tablename__ = "subject"

    id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(100), unique=True, nullable=False)

    category = db.Column(db.Enum("COMPULSORY", "ARTS", "APPLIED", name="subject_category"), nullable=False)

    results=db.relationship(
        "Result", backref="subject", cascade="all, delete-orphan"
    )
    def __repr__(self):
        return f"<Subject {self.subject_name} ({self.category})>"    


class Result(db.Model):
    __tablename__="result"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(2), nullable=False)
    points = db.Column(db.Integer, nullable=False)

    
    
   # PREVENT DUPLICATE
    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", name="unique_student_subject"),
   )

    def __repr__(self):
        return f"<Result S{self.student_id}-Sub{self.subject_id}: {self.marks}>"

