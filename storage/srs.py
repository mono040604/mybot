import math

INITIAL_STRENGTH = 50.0
DUE_THRESHOLD    = 30.0   # FIX: DUE_THRESHOULD → DUE_THRESHOLD（Threshold 拼成了 Threshould）
DECAY_RATE       = 0.9
STEP_PER_STREAK  = 10.0
MAX_STRENGTH     = 100.0
WRONG_FACTOR     = 0.5    # FIX: WORNG_FACTOR → WRONG_FACTOR（Wrong 拼成了 Worng）
ARCHIVE_LINE     = 90.0

def current_strength(strength, last_review_at, now):
    days = (now - last_review_at).total_seconds() / 86400  # FIX: `.` 和 total_seconds 之间多了个空格
    return strength * (DECAY_RATE ** days)

def is_due(strength, last_review_at, now):
    return current_strength(strength, last_review_at, now) < DUE_THRESHOLD  # FIX: 常量已改名

def next_streak(streak, is_correct):
    return streak + 1 if is_correct else 0

def strength_after_correct(streak):
    return min(INITIAL_STRENGTH + STEP_PER_STREAK * streak, MAX_STRENGTH)

def strength_after_wrong(current):
    return current * WRONG_FACTOR  # FIX: 这个函数之前整个漏了，record_answer 调用它时会 AttributeError

def should_archive(strength):
    return strength >= ARCHIVE_LINE

def days_until_due(strength):
    if strength <= DUE_THRESHOLD:
        return 0.0
    return math.log(DUE_THRESHOLD / strength) / math.log(DECAY_RATE)