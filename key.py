from app.pomodoro import PomodoroTimer
timer = PomodoroTimer(work_minutes=1, break_minutes=1, cycles=2)
timer.start()
print(timer.get_log())