// Global timer variables and default settings
let timer;
let isRunning = false;
let isWork = true;
let isLongBreak = false;
let workMinutes = 25;
let breakMinutes = 5;
let longBreakMinutes = 15;
let rounds = 4;
let currentRound = 1;
let secondsLeft = workMinutes * 60;

// DOM elements for timer display and status
const timerEl = document.getElementById('timer');
const statusEl = document.getElementById('status');
const roundInfoEl = document.getElementById('round-info');

// Updates timer settings from user input fields
function updateSettings() {
    workMinutes = parseInt(document.getElementById('work-minutes').value) || 25;
    breakMinutes = parseInt(document.getElementById('break-minutes').value) || 5;
    longBreakMinutes = parseInt(document.getElementById('longbreak-minutes').value) || 15;
    rounds = parseInt(document.getElementById('rounds').value) || 4;
}

// Updates the timer display, status, and round info in the UI
function updateDisplay() {
    const min = Math.floor(secondsLeft / 60).toString().padStart(2, '0');
    const sec = (secondsLeft % 60).toString().padStart(2, '0');
    timerEl.textContent = `${min}:${sec}`;
    
    if (isWork) {
        statusEl.textContent = "Fokus";
        timerEl.classList.remove('text-green-500');
        timerEl.classList.add('text-red-500');
        roundInfoEl.textContent = `Runde ${currentRound} von ${rounds}`;
    } else {
        statusEl.textContent = isLongBreak ? "Lange Pause" : "Pause";
        timerEl.classList.remove('text-red-500');
        timerEl.classList.add('text-green-500');
        roundInfoEl.textContent = 'Zeit für eine Pause!';
    }
}

// Starts the timer countdown and handles session transitions
function startTimer() {
    if (isRunning) return;
    updateSettings();
    
    if (!isRunning && secondsLeft === (isWork ? workMinutes : (isLongBreak ? longBreakMinutes : breakMinutes)) * 60) {
        secondsLeft = (isWork ? workMinutes : (isLongBreak ? longBreakMinutes : breakMinutes)) * 60;
    }

    isRunning = true;
    timer = setInterval(() => {
        if (secondsLeft > 0) {
            secondsLeft--;
            updateDisplay();
        } else {
            clearInterval(timer);
            isRunning = false;
            // Play a sound or notification here if you want
            
            if (isWork) {
                if (currentRound < rounds) {
                    isWork = false;
                    isLongBreak = false;
                    secondsLeft = breakMinutes * 60;
                } else {
                    isWork = false;
                    isLongBreak = true;
                    secondsLeft = longBreakMinutes * 60;
                }
            } else {
                if (isLongBreak) {
                    currentRound = 1;
                } else {
                    currentRound++;
                }
                isWork = true;
                isLongBreak = false;
                secondsLeft = workMinutes * 60;
            }
            updateDisplay();
            startTimer(); // Automatically start the next session
        }
    }, 1000);
}

// Pauses the timer countdown
function pauseTimer() {
    clearInterval(timer);
    isRunning = false;
}

// Resets the timer to initial state and updates the display
function resetTimer() {
    clearInterval(timer);
    isRunning = false;
    updateSettings();
    isWork = true;
    isLongBreak = false;
    currentRound = 1;
    secondsLeft = workMinutes * 60;
    updateDisplay();
}

// Resets timer when any settings input changes
document.querySelectorAll('.settings input').forEach(input => {
    input.addEventListener('change', resetTimer);
});

// Initialize timer display on page load
updateDisplay();