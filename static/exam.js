document.addEventListener('DOMContentLoaded', function () {
    let remaining = REMAINING;
    const timerEl = document.getElementById('timer');
    const answeredEl = document.getElementById('answered-count');
    const form = document.getElementById('exam-form');
    const submitBtn = document.getElementById('submit-btn');
    let submitted = false;

    // --- Timer ---
    function updateTimer() {
        if (remaining <= 0) {
            timerEl.textContent = '00:00';
            autoSubmit();
            return;
        }
        const min = Math.floor(remaining / 60);
        const sec = remaining % 60;
        timerEl.textContent =
            String(min).padStart(2, '0') + ':' + String(sec).padStart(2, '0');

        if (remaining <= 60) {
            timerEl.classList.add('warning');
        }
        remaining--;
    }

    updateTimer();
    setInterval(updateTimer, 1000);

    // --- Answer count ---
    function updateAnsweredCount() {
        const radios = document.querySelectorAll('.answer-radio:checked');
        answeredEl.textContent = radios.length;
    }

    document.querySelectorAll('.answer-radio').forEach(function (radio) {
        radio.addEventListener('change', updateAnsweredCount);
    });
    updateAnsweredCount();

    // --- Auto-save every 30s ---
    setInterval(function () {
        if (submitted) return;
        const formData = new FormData(form);
        fetch(SAVE_URL, { method: 'POST', body: formData });
    }, 30000);

    // --- Auto-submit on time expiry ---
    function autoSubmit() {
        if (submitted) return;
        submitted = true;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Time is up! Submitting...';
        form.submit();
    }

    // --- Confirm before leaving ---
    window.addEventListener('beforeunload', function (e) {
        if (!submitted) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    // --- Mark as submitted on form submit ---
    form.addEventListener('submit', function (e) {
        if (submitted && e.submitter === submitBtn) {
            // Already auto-submitting, let it through
            return;
        }
        if (!submitted && !confirm('Are you sure you want to submit the exam?')) {
            e.preventDefault();
            return;
        }
        submitted = true;
    });
});
