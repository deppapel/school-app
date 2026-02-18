from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default="GUEST")

    def __repr__(self):
        return f"<User {self.username} - {self.role}>"

class SystemSettings(db.Model):
    __tablename__ = "system_settings"
    id = db.Column(db.Integer, primary_key=True)
    current_academic_year = db.Column(db.Integer, default=2025)
    current_term = db.Column(db.Integer, default=1)

class Student(db.Model):
    __tablename__ = "student"

    id = db.Column(db.Integer, primary_key=True)
    adm_no = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    second_name = db.Column(db.String(50))

    entry_form = db.Column(db.Integer, default=1) # Form they joined in
    admission_year = db.Column(db.Integer, default=2025) # Year they joined
    date_of_admission = db.Column(db.Date, default=datetime.utcnow)
    
    # --- THE BRAINS: Calculated Property ---
    @property
    def calculated_current_form(self):
        # Fetches the master year from settings and does the math
        settings = SystemSettings.query.first()
        if not settings:
            return self.entry_form
        years_passed = settings.current_academic_year - self.admission_year
        current_form = self.entry_form + years_passed
        return current_form

    # Optional subjects
    arts_subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    applied_subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)

    arts_subject = db.relationship("Subject", foreign_keys=[arts_subject_id])
    applied_subject = db.relationship("Subject", foreign_keys=[applied_subject_id])

    results = db.relationship("Result", backref="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student {self.adm_no} - {self.first_name}>"


class Subject(db.Model):
    __tablename__ = "subject"

    id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(100), unique=True, nullable=False)

    category = db.Column(
        db.Enum("COMPULSORY", "ARTS", "APPLIED", name="subject_category"), nullable=False
    )

    results = db.relationship("Result", backref="subject", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Subject {self.subject_name} ({self.category})>"


class Result(db.Model):
    __tablename__ = "result"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(2), nullable=False)
    points = db.Column(db.Integer, nullable=False)

    form = db.Column(db.Integer, nullable=False)
    term = db.Column(db.Integer, nullable=False)

    academic_year = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", "form", "term", "academic_year",  name="unique_student_exam_record"),
    )

    def __repr__(self):
        return f"<Result S{self.student_id}-Sub{self.subject_id} F{self.form}T{self.term}: {self.marks}>"


