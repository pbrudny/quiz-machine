import csv
import io
import json
import random
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response, abort,
)
from config import Config
from models import db, QuestionSet, Question, Exam

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_teacher'):
            return redirect(url_for('teacher_login'))
        return f(*args, **kwargs)
    return decorated


def _shuffle_options(q_dict):
    """Shuffle options for a question and update the correct answer key."""
    options = [
        ('a', q_dict['option_a']),
        ('b', q_dict['option_b']),
        ('c', q_dict['option_c']),
        ('d', q_dict['option_d']),
    ]
    correct_text = q_dict[f'option_{q_dict["correct"]}']
    random.shuffle(options)
    keys = ['a', 'b', 'c', 'd']
    new_correct = 'a'
    result = {'id': q_dict['id'], 'text': q_dict['text']}
    for i, (_, text) in enumerate(options):
        result[f'option_{keys[i]}'] = text
        if text == correct_text:
            new_correct = keys[i]
    result['correct'] = new_correct
    return result


def _grade_exam(exam):
    """Grade an exam and persist the results."""
    questions = json.loads(exam.questions_data)
    answers = json.loads(exam.answers_data) if exam.answers_data else {}
    score = 0
    for q in questions:
        qid = str(q['id'])
        if answers.get(qid) == q['correct']:
            score += 1
    total = len(questions)
    exam.score = score
    exam.total = total
    exam.passed = (score / total) >= app.config['PASS_THRESHOLD'] if total > 0 else False
    exam.finished_at = datetime.utcnow()
    db.session.commit()


def _get_active_exam(email, index, set_id):
    """Find an active (unfinished, not expired) exam for this student in a given set."""
    exam = Exam.query.filter_by(
        student_email=email,
        student_index=index,
        question_set_id=set_id,
        finished_at=None,
    ).first()
    if exam is None:
        return None
    deadline = exam.started_at + timedelta(minutes=app.config['EXAM_DURATION_MINUTES'])
    if datetime.utcnow() > deadline:
        _grade_exam(exam)
        return None
    return exam


# ---------------------------------------------------------------------------
# Student Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('landing.html')


@app.route('/q/<set_uuid>')
def set_login(set_uuid):
    qs = QuestionSet.query.filter_by(uuid=set_uuid).first_or_404()
    return render_template('login.html', question_set=qs)


@app.route('/q/<set_uuid>/login', methods=['POST'])
def set_login_post(set_uuid):
    qs = QuestionSet.query.filter_by(uuid=set_uuid).first_or_404()
    email = request.form.get('email', '').strip().lower()
    index = request.form.get('index', '').strip()
    if not email or not index:
        flash('Please enter your email and student ID.', 'danger')
        return redirect(url_for('set_login', set_uuid=set_uuid))

    # Check if student already finished an exam for this set
    finished = Exam.query.filter(
        Exam.student_email == email,
        Exam.student_index == index,
        Exam.question_set_id == qs.id,
        Exam.finished_at.isnot(None),
    ).first()
    if finished:
        flash('You have already taken this exam.', 'warning')
        return redirect(url_for('result', exam_id=finished.id))

    # Resume or create
    exam = _get_active_exam(email, index, qs.id)
    if exam is None:
        all_questions = Question.query.filter_by(question_set_id=qs.id).all()
        count = min(app.config['EXAM_QUESTION_COUNT'], len(all_questions))
        if count == 0:
            flash('No questions in this exam set. Please contact your instructor.', 'danger')
            return redirect(url_for('set_login', set_uuid=set_uuid))
        selected = random.sample(all_questions, count)
        shuffled = [_shuffle_options(q.to_dict()) for q in selected]
        exam = Exam(
            question_set_id=qs.id,
            student_email=email,
            student_index=index,
            questions_data=json.dumps(shuffled, ensure_ascii=False),
            answers_data=json.dumps({}),
        )
        db.session.add(exam)
        db.session.commit()

    session['exam_id'] = exam.id
    session['student_email'] = email
    return redirect(url_for('exam_page'))


@app.route('/exam')
def exam_page():
    exam_id = session.get('exam_id')
    if not exam_id:
        return redirect(url_for('index'))
    exam = db.session.get(Exam, exam_id)
    if not exam or exam.finished_at:
        session.pop('exam_id', None)
        if exam and exam.finished_at:
            return redirect(url_for('result', exam_id=exam.id))
        return redirect(url_for('index'))

    deadline = exam.started_at + timedelta(minutes=app.config['EXAM_DURATION_MINUTES'])
    now = datetime.utcnow()
    if now > deadline:
        _grade_exam(exam)
        session.pop('exam_id', None)
        return redirect(url_for('result', exam_id=exam.id))

    remaining_seconds = int((deadline - now).total_seconds())
    questions = json.loads(exam.questions_data)
    answers = json.loads(exam.answers_data) if exam.answers_data else {}
    qs = db.session.get(QuestionSet, exam.question_set_id)
    return render_template(
        'exam.html',
        questions=questions,
        answers=answers,
        remaining=remaining_seconds,
        exam_id=exam.id,
        question_set=qs,
    )


@app.route('/exam/save', methods=['POST'])
def exam_save():
    """Save answers without submitting (called periodically by JS)."""
    exam_id = session.get('exam_id')
    if not exam_id:
        return {'ok': False}, 401
    exam = db.session.get(Exam, exam_id)
    if not exam or exam.finished_at:
        return {'ok': False}, 400

    answers = {}
    questions = json.loads(exam.questions_data)
    for q in questions:
        val = request.form.get(f'q_{q["id"]}')
        if val:
            answers[str(q['id'])] = val
    exam.answers_data = json.dumps(answers, ensure_ascii=False)
    db.session.commit()
    return {'ok': True}


@app.route('/exam/submit', methods=['POST'])
def exam_submit():
    exam_id = session.get('exam_id')
    if not exam_id:
        return redirect(url_for('index'))
    exam = db.session.get(Exam, exam_id)
    if not exam or exam.finished_at:
        session.pop('exam_id', None)
        if exam and exam.finished_at:
            return redirect(url_for('result', exam_id=exam.id))
        return redirect(url_for('index'))

    answers = {}
    questions = json.loads(exam.questions_data)
    for q in questions:
        val = request.form.get(f'q_{q["id"]}')
        if val:
            answers[str(q['id'])] = val
    exam.answers_data = json.dumps(answers, ensure_ascii=False)
    _grade_exam(exam)
    session.pop('exam_id', None)
    return redirect(url_for('result', exam_id=exam.id))


@app.route('/result/<int:exam_id>')
def result(exam_id):
    exam = db.session.get(Exam, exam_id)
    if not exam or not exam.finished_at:
        abort(404)
    questions = json.loads(exam.questions_data)
    answers = json.loads(exam.answers_data) if exam.answers_data else {}
    qs = db.session.get(QuestionSet, exam.question_set_id)
    return render_template(
        'result.html',
        exam=exam,
        questions=questions,
        answers=answers,
        question_set=qs,
    )


# ---------------------------------------------------------------------------
# Teacher Routes
# ---------------------------------------------------------------------------

@app.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == app.config['TEACHER_PASSWORD']:
            session['is_teacher'] = True
            return redirect(url_for('teacher_dashboard'))
        flash('Incorrect password.', 'danger')
    return render_template('teacher/login.html')


@app.route('/teacher/logout')
def teacher_logout():
    session.pop('is_teacher', None)
    return redirect(url_for('index'))


@app.route('/teacher/dashboard')
@teacher_required
def teacher_dashboard():
    total_questions = Question.query.count()
    total_exams = Exam.query.filter(Exam.finished_at.isnot(None)).count()
    passed = Exam.query.filter_by(passed=True).count()
    failed = Exam.query.filter_by(passed=False).filter(Exam.finished_at.isnot(None)).count()
    total_sets = QuestionSet.query.count()
    avg_score = None
    if total_exams > 0:
        exams = Exam.query.filter(Exam.finished_at.isnot(None)).all()
        avg_score = sum(e.score for e in exams) / total_exams
    return render_template(
        'teacher/dashboard.html',
        total_questions=total_questions,
        total_exams=total_exams,
        passed=passed,
        failed=failed,
        avg_score=avg_score,
        total_sets=total_sets,
    )


# --- Question Sets ---

@app.route('/teacher/sets', methods=['GET', 'POST'])
@teacher_required
def teacher_sets():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Please enter a set name.', 'danger')
        else:
            qs = QuestionSet(name=name)
            db.session.add(qs)
            db.session.commit()
            flash(f'Question set "{name}" created.', 'success')
        return redirect(url_for('teacher_sets'))
    sets = QuestionSet.query.order_by(QuestionSet.created_at.desc()).all()
    return render_template('teacher/sets.html', sets=sets)


@app.route('/teacher/sets/<int:set_id>/delete', methods=['POST'])
@teacher_required
def teacher_delete_set(set_id):
    qs = db.session.get(QuestionSet, set_id)
    if qs:
        db.session.delete(qs)
        db.session.commit()
        flash(f'Question set "{qs.name}" deleted.', 'success')
    return redirect(url_for('teacher_sets'))


# --- Questions (scoped by set) ---

@app.route('/teacher/questions', methods=['GET', 'POST'])
@teacher_required
def teacher_questions():
    sets = QuestionSet.query.order_by(QuestionSet.name).all()
    set_id = request.args.get('set', type=int)

    if not sets:
        flash('Create a question set first.', 'warning')
        return redirect(url_for('teacher_sets'))

    # Default to first set if none selected
    current_set = None
    if set_id:
        current_set = db.session.get(QuestionSet, set_id)
    if not current_set:
        current_set = sets[0]

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            text = request.form.get('text', '').strip()
            option_a = request.form.get('option_a', '').strip()
            option_b = request.form.get('option_b', '').strip()
            option_c = request.form.get('option_c', '').strip()
            option_d = request.form.get('option_d', '').strip()
            correct = request.form.get('correct', '').strip().lower()
            if not all([text, option_a, option_b, option_c, option_d, correct]):
                flash('Please fill in all fields.', 'danger')
            elif correct not in ('a', 'b', 'c', 'd'):
                flash('Correct answer must be a, b, c, or d.', 'danger')
            else:
                q = Question(
                    question_set_id=current_set.id,
                    text=text, option_a=option_a, option_b=option_b,
                    option_c=option_c, option_d=option_d, correct=correct,
                )
                db.session.add(q)
                db.session.commit()
                flash('Question added.', 'success')

        elif action == 'csv_upload':
            file = request.files.get('csv_file')
            if not file or not file.filename.endswith('.csv'):
                flash('Please upload a CSV file.', 'danger')
            else:
                try:
                    stream = io.TextIOWrapper(file.stream, encoding='utf-8')
                    reader = csv.DictReader(stream)
                    count = 0
                    for row in reader:
                        if not all(k in row for k in ('text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct')):
                            continue
                        if row['correct'].strip().lower() not in ('a', 'b', 'c', 'd'):
                            continue
                        q = Question(
                            question_set_id=current_set.id,
                            text=row['text'].strip(),
                            option_a=row['option_a'].strip(),
                            option_b=row['option_b'].strip(),
                            option_c=row['option_c'].strip(),
                            option_d=row['option_d'].strip(),
                            correct=row['correct'].strip().lower(),
                        )
                        db.session.add(q)
                        count += 1
                    db.session.commit()
                    flash(f'Imported {count} questions.', 'success')
                except Exception as e:
                    flash(f'Import error: {e}', 'danger')

        return redirect(url_for('teacher_questions', set=current_set.id))

    questions = Question.query.filter_by(question_set_id=current_set.id).order_by(Question.id).all()
    return render_template(
        'teacher/questions.html',
        questions=questions,
        sets=sets,
        current_set=current_set,
    )


@app.route('/teacher/questions/csv')
@teacher_required
def teacher_questions_csv():
    set_id = request.args.get('set', type=int)
    query = Question.query
    if set_id:
        query = query.filter_by(question_set_id=set_id)
    questions = query.order_by(Question.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct'])
    for q in questions:
        writer.writerow([q.text, q.option_a, q.option_b, q.option_c, q.option_d, q.correct])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=questions.csv'},
    )


@app.route('/teacher/questions/<int:qid>/edit', methods=['GET', 'POST'])
@teacher_required
def teacher_edit_question(qid):
    q = db.session.get(Question, qid)
    if not q:
        abort(404)
    if request.method == 'POST':
        q.text = request.form.get('text', '').strip()
        q.option_a = request.form.get('option_a', '').strip()
        q.option_b = request.form.get('option_b', '').strip()
        q.option_c = request.form.get('option_c', '').strip()
        q.option_d = request.form.get('option_d', '').strip()
        correct = request.form.get('correct', '').strip().lower()
        if correct in ('a', 'b', 'c', 'd'):
            q.correct = correct
        db.session.commit()
        flash('Question updated.', 'success')
        return redirect(url_for('teacher_questions', set=q.question_set_id))
    return render_template('teacher/edit_question.html', question=q)


@app.route('/teacher/questions/<int:qid>/delete', methods=['POST'])
@teacher_required
def teacher_delete_question(qid):
    q = db.session.get(Question, qid)
    set_id = q.question_set_id if q else None
    if q:
        db.session.delete(q)
        db.session.commit()
        flash('Question deleted.', 'success')
    return redirect(url_for('teacher_questions', set=set_id))


# --- Results ---

@app.route('/teacher/results')
@teacher_required
def teacher_results():
    set_id = request.args.get('set', type=int)
    sets = QuestionSet.query.order_by(QuestionSet.name).all()
    query = Exam.query.filter(Exam.finished_at.isnot(None))
    if set_id:
        query = query.filter_by(question_set_id=set_id)
    exams = query.order_by(Exam.finished_at.desc()).all()
    return render_template('teacher/results.html', exams=exams, sets=sets, current_set_id=set_id)


@app.route('/teacher/results/<int:exam_id>')
@teacher_required
def teacher_result_detail(exam_id):
    exam = db.session.get(Exam, exam_id)
    if not exam or not exam.finished_at:
        abort(404)
    questions = json.loads(exam.questions_data)
    answers = json.loads(exam.answers_data) if exam.answers_data else {}
    qs = db.session.get(QuestionSet, exam.question_set_id)
    return render_template(
        'teacher/result_detail.html',
        exam=exam,
        questions=questions,
        answers=answers,
        question_set=qs,
    )


@app.route('/teacher/results/csv')
@teacher_required
def teacher_results_csv():
    set_id = request.args.get('set', type=int)
    query = Exam.query.filter(Exam.finished_at.isnot(None))
    if set_id:
        query = query.filter_by(question_set_id=set_id)
    exams = query.order_by(Exam.finished_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['set', 'email', 'index', 'score', 'total', 'percentage', 'passed', 'started_at', 'finished_at'])
    for e in exams:
        pct = round(e.score / e.total * 100, 1) if e.total else 0
        set_name = e.question_set.name if e.question_set else ''
        writer.writerow([
            set_name, e.student_email, e.student_index, e.score, e.total,
            f'{pct}%', 'YES' if e.passed else 'NO',
            e.started_at.strftime('%Y-%m-%d %H:%M'), e.finished_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=results.csv'},
    )


if __name__ == '__main__':
    app.run(debug=True)
