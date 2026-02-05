# Quiz Machine

Web-based exam application for IT students. Teachers manage a question bank and review results; students log in, take a timed quiz with shuffled questions and options, and get instant scores.

## Features

- **Question bank** — import from CSV or manage via teacher panel (add / edit / delete)
- **Randomized exams** — questions and answer options are shuffled per student
- **Single-attempt enforcement** — each student (email + index number) can take the exam only once
- **Server-side timer** — exam duration enforced on the backend; JS countdown is cosmetic
- **Auto-save** — answers are periodically saved so nothing is lost on disconnect
- **Teacher dashboard** — view all results, drill into individual exams, see per-question breakdown
- **Configurable** — exam length, question count, and pass threshold set via environment variables

## Tech Stack

- **Backend:** Python 3 / Flask / Flask-SQLAlchemy / SQLite
- **Frontend:** Jinja2 templates / Bootstrap 5 (CDN) / vanilla JS
- **Deployment:** Gunicorn + Nginx

## Quick Start

```bash
# Clone the repo
git clone https://github.com/pbrudny/quiz-machine.git
cd quiz-machine

# Create virtualenv and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# (Optional) copy and edit environment config
cp .env.example .env

# Run the dev server
flask run
```

The app will be available at `http://localhost:5000`.

## Configuration

Create a `.env` file (or export environment variables):

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret | `change-me-in-production` |
| `DATABASE_URL` | SQLAlchemy database URI | `sqlite:///quiz.db` |
| `TEACHER_PASSWORD` | Password for the teacher panel | `teacher123` |
| `EXAM_DURATION_MINUTES` | Time limit per exam | `20` |
| `EXAM_QUESTION_COUNT` | Number of questions per exam | `20` |
| `PASS_THRESHOLD` | Fraction required to pass (0.0 – 1.0) | `0.5` |

## Importing Questions

A sample question bank is included in `sample_questions.csv`. Log in to the teacher panel at `/teacher/login` and use the CSV import feature, or add questions manually.

CSV format:

```
question,option_a,option_b,option_c,option_d,correct
"What does CPU stand for?","Central Processing Unit","Central Program Utility","Computer Personal Unit","Central Processor Unifier",a
```

## Project Structure

```
app.py                - Flask application (all routes)
models.py             - SQLAlchemy models (Question, Exam)
config.py             - Configuration from environment variables
wsgi.py               - Gunicorn entry point
templates/            - Jinja2 templates
static/               - CSS and JS
sample_questions.csv  - 25 sample IT questions
deploy.sh             - Deployment script for VPS
```

## Deployment

A deployment script for a Linux VPS (tested on mikr.us) is included:

```bash
SSH_HOST=user@your-server SSH_PORT=22 ./deploy.sh
```

This sets up a virtualenv, configures systemd and Nginx, and starts the app behind a reverse proxy.

## License

MIT
