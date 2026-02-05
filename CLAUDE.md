# Quiz Machine

Web-based exam application for IT students.

## Tech Stack
- **Backend**: Python 3 / Flask / Flask-SQLAlchemy / SQLite
- **Frontend**: Jinja2 templates / Bootstrap 5 (CDN) / vanilla JS
- **Deployment**: Gunicorn + Nginx

## Project Structure
```
app.py              - Main Flask application (all routes)
models.py           - SQLAlchemy models (Question, Exam)
config.py           - Configuration from environment variables
wsgi.py             - Gunicorn entry point
templates/          - Jinja2 templates (base, login, exam, result, teacher/*)
static/             - CSS and JS (style.css, exam.js)
sample_questions.csv - 25 IT questions for import
deploy.sh           - Deployment script for mikr.us VPS
```

## Running Locally
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
flask run
```

## Key Design Decisions
- **SQLite** - no separate DB server needed, perfect for small-scale exam tool
- **JSON in Exam model** - `questions_data` and `answers_data` store the shuffled questions/answers per student for audit trail
- **Single-attempt enforcement** - student identified by email+index, can only take exam once
- **Server-side timer** - exam duration enforced on backend, JS countdown is cosmetic
- **Option shuffling** - each student sees options in random order

## Routes
- Student: `/`, `/login`, `/exam`, `/exam/submit`, `/exam/save`, `/result/<id>`
- Teacher: `/teacher/login`, `/teacher/dashboard`, `/teacher/questions`, `/teacher/results`

## Configuration (.env)
- `SECRET_KEY` - Flask session secret
- `TEACHER_PASSWORD` - password for teacher panel
- `EXAM_DURATION_MINUTES` - exam time limit (default: 20)
- `EXAM_QUESTION_COUNT` - questions per exam (default: 20)
- `PASS_THRESHOLD` - fraction to pass (default: 0.5)

## Language
UI is in English.
