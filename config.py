import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///quiz.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEACHER_PASSWORD = os.environ.get('TEACHER_PASSWORD', 'teacher123')
    EXAM_DURATION_MINUTES = int(os.environ.get('EXAM_DURATION_MINUTES', '20'))
    EXAM_QUESTION_COUNT = int(os.environ.get('EXAM_QUESTION_COUNT', '20'))
    PASS_THRESHOLD = float(os.environ.get('PASS_THRESHOLD', '0.5'))
