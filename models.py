import uuid as _uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class QuestionSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(_uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    questions = db.relationship('Question', backref='question_set', lazy=True, cascade='all, delete-orphan')
    exams = db.relationship('Exam', backref='question_set', lazy=True, cascade='all, delete-orphan')


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_set_id = db.Column(db.Integer, db.ForeignKey('question_set.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct = db.Column(db.String(1), nullable=False)  # 'a', 'b', 'c', or 'd'
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'option_a': self.option_a,
            'option_b': self.option_b,
            'option_c': self.option_c,
            'option_d': self.option_d,
            'correct': self.correct,
        }


class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_set_id = db.Column(db.Integer, db.ForeignKey('question_set.id'), nullable=False)
    student_email = db.Column(db.String(200), nullable=False)
    student_index = db.Column(db.String(50), nullable=False)
    started_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())
    finished_at = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Integer, nullable=True)
    total = db.Column(db.Integer, nullable=True)
    passed = db.Column(db.Boolean, nullable=True)
    questions_data = db.Column(db.Text, nullable=False)  # JSON
    answers_data = db.Column(db.Text, nullable=True)  # JSON
