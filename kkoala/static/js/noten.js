// --- Hardcoded Data ---
// Semester names and default subjects for each semester
const SEMESTER_NAMES = ["1. Semester", "2. Semester", "3. Semester", "4. Semester", "5. Semester", "6. Semester", "7. Semester", "8. Semester"];
const subjectsBySemesterName = {
    "1. Semester": ["Deutsch", "Mathematik", "Biologie", "Chemie", "Geografie", "Sport", "Englisch", "Französisch", "Informatik", "Wirtschaft und Recht", "Geschichte"],
    "2. Semester": ["Deutsch", "Mathematik", "Biologie", "Chemie", "Geografie", "Sport", "Englisch", "Französisch", "Informatik", "Wirtschaft und Recht", "Geschichte"],
    "3. Semester": ["Deutsch", "Mathematik", "Biologie", "Chemie", "Geografie", "Sport", "Englisch", "Französisch", "Informatik", "Wirtschaft und Recht", "Geschichte"],
    "4. Semester": ["Deutsch", "Mathematik", "Biologie", "Chemie", "Geografie", "Sport", "Englisch", "Französisch", "Informatik", "Wirtschaft und Recht", "Geschichte"],
    "5. Semester": ["Deutsch", "Mathematik", "Biologie", "Chemie", "Sport", "Englisch", "Französisch", "Geschichte"],
    "6. Semester": ["Deutsch", "Mathematik", "Biologie", "Chemie", "Sport", "Englisch", "Französisch", "Geschichte"],
    "7. Semester": ["Deutsch", "Mathematik", "Sport", "Physik", "Englisch", "Französisch", "Geschichte"],
    "8. Semester": ["Deutsch", "Mathematik", "Sport", "Physik", "Englisch", "Französisch", "Geschichte"]
};

// --- Global State Variables ---
// Track counters and currently edited elements
let semesterCounter = 0; 
let currentSubjectForGrade = null;
let editingGradeRow = null;
let editingSubjectHeader = null;
let editingSubjectContainer = null; 
let semesterToDelete = null; 
let currentSubjectForDreamCalc = null;

// --- Helper Functions ---
// Overlay element for modals
const overlay = document.getElementById("overlay");

// Rounds a grade to the nearest 0.5
function roundToHalf(grade) { return Math.round(grade * 2) / 2; }

// Calculates plus points based on rounded grade
function calculatePlusPoints(roundedGrade) {
    return roundedGrade >= 4.0 ? roundedGrade - 4.0 : 2 * (roundedGrade - 4.0);
}

// --- Modal/Popup Functions ---

// Opens the semester delete confirmation popup
function openDeleteConfirm(semesterDiv) {
    semesterToDelete = semesterDiv; 
    const semesterName = semesterDiv.querySelector('.semester-name').textContent.trim();
    document.getElementById('confirm-semester-name').textContent = `${semesterName} löschen?`;
    overlay.classList.remove("hidden");
    document.getElementById("delete-confirm-popup").classList.remove("hidden");
}

// Closes the semester delete confirmation popup
function closeDeleteConfirm() {
    overlay.classList.add("hidden");
    document.getElementById("delete-confirm-popup").classList.add("hidden");
    semesterToDelete = null; 
}

// Confirms and deletes the selected semester
function confirmDeleteSemester() {
    if (semesterToDelete) {
        semesterToDelete.remove(); 
        saveAllSemestersToBackend();
    }
    closeDeleteConfirm();
}

// Opens the dream grade calculator popup for a subject
function openDreamCalcPopup(subjectDiv) {
    currentSubjectForDreamCalc = subjectDiv;
    const subjectName = subjectDiv.querySelector('.subject-title').textContent;
    document.getElementById('dream-calc-subject-name').textContent = `Berechnen für ${subjectName}`;
    document.getElementById('wishedAvgInput').value = '';
    document.getElementById('nextWeightInput').value = '';
    document.getElementById('neededGradeOutput').textContent = 'Benötigte Note: -';
    overlay.classList.remove("hidden");
    document.getElementById("dream-calc-popup").classList.remove("hidden");
}

// Closes the dream grade calculator popup
function closeDreamCalcPopup() {
    overlay.classList.add("hidden");
    document.getElementById("dream-calc-popup").classList.add("hidden");
    currentSubjectForDreamCalc = null;
}

// Opens the grade add/edit popup, optionally pre-filling for edit
function openGradePopup(editRow = null) {
    overlay.classList.remove("hidden");
    document.getElementById("grade-popup").classList.remove("hidden");
    editingGradeRow = editRow;
    if (editRow) {
        document.getElementById("grade-popup-title").textContent = "Note bearbeiten";
        document.getElementById("gradeName").value = editRow.dataset.name;
        document.getElementById("gradeValue").value = editRow.dataset.value;
        document.getElementById("gradeWeight").value = editRow.dataset.weight;
        document.getElementById("gradeCounts").checked = (editRow.dataset.counts === "true");
        document.getElementById("grade-popup-save-btn").textContent = "Speichern";
    } else {
        document.getElementById("grade-popup-title").textContent = "Note hinzufügen";
        document.getElementById("gradeName").value = "";
        document.getElementById("gradeValue").value = "";
        document.getElementById("gradeWeight").value = "1";
        document.getElementById("gradeCounts").checked = true;
        document.getElementById("grade-popup-save-btn").textContent = "Hinzufügen";
    }
}

// Closes the grade popup
function closeGradePopup() {
    overlay.classList.add("hidden");
    document.getElementById("grade-popup").classList.add("hidden");
}

// Opens the subject edit popup
function openSubjectPopup(subjectDiv) {
    editingSubjectHeader = subjectDiv.querySelector('.subject-title');
    editingSubjectContainer = subjectDiv; 
    document.getElementById("subjectNameEdit").value = editingSubjectHeader.textContent;
    document.getElementById("subjectCountsAverage").checked = subjectDiv.dataset.countsAverage === "true";
    overlay.classList.remove("hidden");
    document.getElementById("subject-popup").classList.remove("hidden");
}

// Closes the subject edit popup
function closeSubjectPopup() {
    overlay.classList.add("hidden");
    document.getElementById("subject-popup").classList.add("hidden");
}

// Opens the semester rename popup
function openSemesterRenamePopup(semesterDiv) {
    window._semesterDivToRename = semesterDiv;
    const headerSpan = semesterDiv.querySelector('.semester-name');
    document.getElementById('semesterNameEdit').value = headerSpan ? headerSpan.textContent.trim() : '';
    overlay.classList.remove("hidden");
    document.getElementById("semester-rename-popup").classList.remove("hidden");
}

// Closes the semester rename popup
function closeSemesterRenamePopup() {
    overlay.classList.add("hidden");
    document.getElementById("semester-rename-popup").classList.add("hidden");
    window._semesterDivToRename = null;
}

// Saves the new semester name after renaming
function saveSemesterRename() {
    const newName = document.getElementById("semesterNameEdit").value.trim();
    if (window._semesterDivToRename && newName) {
        const headerSpan = window._semesterDivToRename.querySelector('.semester-name');
        if (headerSpan) headerSpan.textContent = newName;
        saveAllSemestersToBackend();
    }
    closeSemesterRenamePopup();
}

// --- Calculation and Core Logic ---

// Calculates the required grade for a desired average and displays it
function calculateDreamGradeFromPopup() {
    const wishedAvg = parseFloat(document.getElementById('wishedAvgInput').value);
    const nextWeight = parseFloat(document.getElementById('nextWeightInput').value);
    const outputP = document.getElementById('neededGradeOutput');
    if (!currentSubjectForDreamCalc || isNaN(wishedAvg) || wishedAvg < 1 || wishedAvg > 6 || isNaN(nextWeight) || nextWeight <= 0) {
        outputP.textContent = "Fehler: Gültigen Schnitt (1-6) und Gewichtung (>0) eingeben.";
        return;
    }
    let currentTotalScore = 0, currentWeightSum = 0;
    currentSubjectForDreamCalc.querySelector('.grades-list').querySelectorAll(".grade-row").forEach(row => {
        if (row.dataset.counts === "true") {
            currentTotalScore += parseFloat(row.dataset.value) * parseFloat(row.dataset.weight);
            currentWeightSum += parseFloat(row.dataset.weight);
        }
    });
    const neededGrade = ((wishedAvg * (currentWeightSum + nextWeight)) - currentTotalScore) / nextWeight;
    outputP.textContent = `Benötigte Note: ${neededGrade.toFixed(2)}` + (neededGrade > 6 ? ' (Unmöglich)' : (neededGrade < 1 ? ' (Jede Note)' : ''));
}

// Opens the semester rename popup for a given semester
function renameSemester(semesterDiv) {
    openSemesterRenamePopup(semesterDiv);
}

// Saves subject edits and updates averages
async function saveSubjectEdit() {
    if (editingSubjectHeader && editingSubjectContainer) {
        const newName = document.getElementById("subjectNameEdit").value.trim();
        const newCountsAverage = document.getElementById("subjectCountsAverage").checked;
        if (newName) {
            editingSubjectHeader.textContent = newName;
            editingSubjectContainer.dataset.countsAverage = newCountsAverage;
            const gradesList = editingSubjectContainer.querySelector(".grades-list");
            const avgSpan = editingSubjectContainer.querySelector(".subject-average");
            updateSubjectAverage(gradesList, avgSpan, editingSubjectContainer.closest('.semester'));
        }
    }
    closeSubjectPopup();
    await saveAllSemestersToBackend();
}

// Adds or edits a grade for a subject and updates averages
async function addOrEditGradeToSubject() {
    const name = document.getElementById("gradeName").value.trim();
    const value = parseFloat(document.getElementById("gradeValue").value);
    const weight = parseFloat(document.getElementById("gradeWeight").value);
    const counts = document.getElementById("gradeCounts").checked;
    if (value < 1.0 || value > 6.0) { alert("Die Note muss zwischen 1.0 und 6.0 liegen."); return; }
    if (!name || isNaN(value) || isNaN(weight) || weight <= 0) { alert("Bitte geben Sie gültige Notendetails ein."); return; }
    renderGradeRow(currentSubjectForGrade.gradesList, name, value, weight, counts, editingGradeRow);
    updateSubjectAverage(currentSubjectForGrade.gradesList, currentSubjectForGrade.avgSpan, currentSubjectForGrade.semesterDiv);
    closeGradePopup();
    await saveAllSemestersToBackend();
}

// Updates the subject average and semester average
function updateSubjectAverage(gradesList, avgSpan, semesterDiv) {
    const subjectDiv = gradesList.closest('.subject');
    if (!subjectDiv || !avgSpan) return;
    const countsAverage = subjectDiv.dataset.countsAverage === "true";
    let total = 0, weightSum = 0, hasGrade = false;
    gradesList.querySelectorAll(".grade-row").forEach(row => {
        if (row.dataset.counts === "true") {
            total += parseFloat(row.dataset.value) * parseFloat(row.dataset.weight);
            weightSum += parseFloat(row.dataset.weight);
            hasGrade = true;
        }
    });
    const avg = (weightSum && hasGrade) ? (total / weightSum).toFixed(2) : 0;
    avgSpan.textContent = `Schnitt: ${hasGrade ? avg : 0}${countsAverage ? '' : ' (zählt nicht)'}`;
    updateSemesterAverage(semesterDiv);
}

// Updates the semester average and plus points
function updateSemesterAverage(semesterDiv) {
    if (!semesterDiv) return;
    const semesterAvgSpan = semesterDiv.querySelector(".semester-average");
    let totalAvg = 0, count = 0, totalPlusPoints = 0; 
    semesterDiv.querySelectorAll(".subject").forEach(subjectDiv => {
        if (subjectDiv.dataset.countsAverage === "true") {
            const match = subjectDiv.querySelector(".subject-average").textContent.match(/Schnitt: ([\d.]+)/);
            if (match && parseFloat(match[1]) > 0) {
                const avgValue = parseFloat(match[1]);
                totalAvg += avgValue;
                count++;
                totalPlusPoints += calculatePlusPoints(roundToHalf(avgValue));
            }
        }
    });
    const avg = count ? (totalAvg / count).toFixed(2) : 0;
    if (semesterAvgSpan) semesterAvgSpan.textContent = `Schnitt: ${avg} | Pluspunkte: ${totalPlusPoints.toFixed(1)}`;
}

// --- HTML Rendering Functions ---

// Creates a new semester and renders it
function createSemester() {
    if (semesterCounter >= SEMESTER_NAMES.length) { alert("Maximale Anzahl an Semestern erreicht."); return; }
    const semesterName = SEMESTER_NAMES[semesterCounter];
    const semesterData = { name: semesterName, subjects: [] };
    (subjectsBySemesterName[semesterName] || []).forEach(subjectName => {
        semesterData.subjects.push({ name: subjectName, grades: [], counts_average: subjectName.toLowerCase() !== 'sport' });
    });
    renderSemester(semesterData, true);
    semesterCounter++;
    saveAllSemestersToBackend();
}

// Prompts for a new subject name and adds it to the container
function addSubjectPrompt(container) {
    const subjectName = prompt("Fachname eingeben:");
    if (subjectName) {
        addSubject(container, subjectName, [], subjectName.toLowerCase() !== 'sport');
        saveAllSemestersToBackend();
    }
}

// Adds a subject to the container and sets up its UI and event handlers
function addSubject(container, subjectName, grades = [], countsAverage = true) {
    const subjectDiv = document.createElement("div");
    subjectDiv.className = "subject bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg";
    subjectDiv.dataset.countsAverage = countsAverage;
    const header = document.createElement("div");
    header.className = "dropdown-header flex items-center justify-between p-4 cursor-pointer";
    header.innerHTML = `
        <div class="flex items-center space-x-3">
            <span class="subject-title font-semibold text-lg text-zinc-800 dark:text-white">${subjectName}</span>
            <span class="subject-average text-sm text-zinc-500 dark:text-zinc-400">${`Schnitt: 0${countsAverage ? '' : ' (zählt nicht)'}`}</span>
        </div>
        <div class="flex items-center space-x-2">
            <button class="edit-subject-btn p-1.5 text-zinc-500 hover:text-blue-600 dark:hover:text-blue-400 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-700">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L16.732 3.732z"></path>
                </svg>
            </button>
            <svg class="chevron w-5 h-5 text-zinc-500 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
            <span class="drag-handle cursor-grab active:cursor-grabbing ml-2 p-1 rounded text-zinc-500 hover:text-blue-600 dark:text-zinc-400 dark:hover:text-blue-400 hover:bg-zinc-100 dark:hover:bg-zinc-700 focus:outline-none" tabindex="0" title="Fach verschieben" aria-label="Fach verschieben">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 10h16M4 14h16"></path>
                </svg>
            </span>
        </div>
    `;
    
    const content = document.createElement("div");
    content.className = "dropdown-content hidden p-4 border-t border-zinc-200 dark:border-zinc-700";
    const gradesList = document.createElement("div");
    gradesList.className = "grades-list space-y-2";
    content.appendChild(gradesList);
    
    // Append to DOM before rendering grades
    subjectDiv.append(header, content);
    container.appendChild(subjectDiv);
    
    // Render grades for the subject
    grades.forEach(grade => renderGradeRow(gradesList, grade.name, grade.value, grade.weight, grade.counts));
    
    const actionsDiv = document.createElement("div");
    actionsDiv.className = "flex flex-wrap gap-2 mt-4";
    actionsDiv.innerHTML = `
        <button class="add-grade-btn text-sm px-3 py-2 font-semibold text-white bg-blue-600 rounded-md hover:bg-blue-700">Note hinzufügen</button>
        <button class="dream-calc-btn text-sm px-3 py-2 font-semibold text-white bg-green-600 rounded-md hover:bg-green-700">Wunschnote</button>
        <button class="delete-subject-btn text-sm px-3 py-2 font-semibold text-white bg-red-600 rounded-md hover:bg-red-700">Fach löschen</button>
    `;
    content.appendChild(actionsDiv);
    
    // Toggle dropdown and set up event handlers
    header.onclick = (e) => {
        if (!e.target.closest('button') && !e.target.classList.contains('drag-handle')) {
            content.classList.toggle("hidden");
            header.querySelector('.chevron').classList.toggle("rotate-180");
        }
    };
    header.querySelector('.edit-subject-btn').onclick = (e) => { e.stopPropagation(); openSubjectPopup(subjectDiv); };
    actionsDiv.querySelector('.add-grade-btn').onclick = () => {
        currentSubjectForGrade = { gradesList, avgSpan: header.querySelector(".subject-average"), semesterDiv: subjectDiv };
        openGradePopup();
    };
    actionsDiv.querySelector('.dream-calc-btn').onclick = () => openDreamCalcPopup(subjectDiv);
    actionsDiv.querySelector('.delete-subject-btn').onclick = () => { 
        openDeleteSubjectConfirm(subjectDiv);
    };
    updateSubjectAverage(gradesList, header.querySelector(".subject-average"), subjectDiv.closest('.semester'));
}

// Renders a grade row in the grades list, or updates an existing row
function renderGradeRow(gradesList, name, value, weight, counts, gradeRow = null) {
    const isNew = !gradeRow;
    if (isNew) {
        gradeRow = document.createElement("div");
        gradeRow.className = "grade-row";
        gradesList.appendChild(gradeRow);
    }
    
    const countsText = counts ? "" : " (Zählt nicht)";
    gradeRow.className = "grade-row grid grid-cols-[1fr_auto_auto_auto] items-center gap-x-4 p-2 rounded-md bg-zinc-50 dark:bg-zinc-700/50";
    gradeRow.innerHTML = `
        <div class="truncate">
            <strong class="text-zinc-800 dark:text-white">${name}</strong>
        </div>
        <div class="text-sm text-zinc-700 dark:text-zinc-300">Note: ${value}</div>
        <div class="text-sm text-zinc-700 dark:text-zinc-300">Gewichtung: ${weight}${countsText}</div>
        <div class="flex space-x-1 justify-end">
            <button class="edit-grade-btn p-1.5 text-zinc-500 hover:text-blue-600 dark:hover:text-blue-400 rounded-md hover:bg-zinc-200 dark:hover:bg-zinc-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L16.732 3.732z"></path></svg></button>
            <button class="delete-grade-btn p-1.5 text-zinc-500 hover:text-red-600 dark:hover:text-red-400 rounded-md hover:bg-zinc-200 dark:hover:bg-zinc-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg></button>
        </div>
    `;
    gradeRow.dataset.name = name; gradeRow.dataset.value = value; gradeRow.dataset.weight = weight; gradeRow.dataset.counts = counts;
    const subjectContext = { gradesList, avgSpan: gradesList.closest('.subject').querySelector('.subject-average'), semesterDiv: gradesList.closest('.semester') };
    gradeRow.querySelector('.edit-grade-btn').onclick = () => { currentSubjectForGrade = subjectContext; openGradePopup(gradeRow); };
    gradeRow.querySelector('.delete-grade-btn').onclick = () => {
        openDeleteGradeConfirm(gradeRow, subjectContext);
    };
}

// Renders a semester and its subjects, and sets up drag-and-drop
function renderSemester(sem, isNew = false) {
    const container = document.getElementById("semesters");
    const semesterDiv = document.createElement("div");
    semesterDiv.className = "semester bg-white dark:bg-zinc-800 rounded-xl shadow-md border border-zinc-200 dark:border-zinc-700";
    semesterDiv.dataset.id = sem.id || Date.now();
    const header = document.createElement("div");
    header.className = "dropdown-header flex items-center justify-between p-4 cursor-pointer";
    header.innerHTML = `
        <div class="flex items-center space-x-4">
            <span class="semester-name font-bold text-xl text-zinc-900 dark:text-white">${sem.name}</span>
            <span class="semester-average text-sm font-medium text-green-600 dark:text-zinc-300">Schnitt: 0 | Pluspunkte: 0.0</span>
        </div>
        <div class="flex items-center space-x-2">
            <button class="rename-semester-btn p-2 text-zinc-500 hover:text-blue-600 dark:hover:text-blue-400 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-700"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L16.732 3.732z"></path></svg></button>
            <svg class="chevron w-6 h-6 text-zinc-500 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
        </div>
    `;
    const content = document.createElement("div");
    content.className = "dropdown-content hidden p-4 border-t border-zinc-200 dark:border-zinc-700";
    const subjectsContainer = document.createElement("div");
    subjectsContainer.className = "subjects-container space-y-4";
    content.appendChild(subjectsContainer);
    sem.subjects.forEach(subject => addSubject(subjectsContainer, subject.name, subject.grades, subject.counts_average));
    const actionsDiv = document.createElement("div");
    actionsDiv.className = "flex gap-2 mt-4";
    actionsDiv.innerHTML = `
        <button class="add-subject-btn px-3 py-2 text-sm font-semibold text-white bg-blue-600 rounded-md hover:bg-blue-700">Fach hinzufügen</button>
        <button class="delete-semester-btn px-3 py-2 text-sm font-semibold text-white bg-red-600 rounded-md hover:bg-red-700">Semester löschen</button>
    `;
    content.appendChild(actionsDiv);
    semesterDiv.append(header, content);
    if (isNew) { container.prepend(semesterDiv); } else { container.appendChild(semesterDiv); }
    header.onclick = (e) => {
        if (!e.target.closest('button')) {
            content.classList.toggle("hidden");
            header.querySelector('.chevron').classList.toggle("rotate-180");
        }
    };
    header.querySelector('.rename-semester-btn').onclick = (e) => { e.stopPropagation(); renameSemester(semesterDiv); };
    actionsDiv.querySelector('.add-subject-btn').onclick = () => addSubjectPrompt(subjectsContainer);
    actionsDiv.querySelector('.delete-semester-btn').onclick = () => openDeleteConfirm(semesterDiv);
    updateSemesterAverage(semesterDiv);

    // Make subjects reorderable with SortableJS
    if (typeof Sortable !== "undefined") {
        new Sortable(subjectsContainer, {
            animation: 150,
            handle: '.drag-handle',
            onStart: function (evt) {
                evt.item.classList.add('ring-2', 'ring-blue-400', 'bg-blue-50', 'dark:bg-blue-900/30');
            },
            onEnd: function (evt) {
                evt.item.classList.remove('ring-2', 'ring-blue-400', 'bg-blue-50', 'dark:bg-blue-900/30');
                saveAllSemestersToBackend();
            },
            onMove: function (evt) {
                // Optionally, you can add more feedback here
            }
        });
    }
}

// --- Backend and Initialization ---

// Loads all semesters from the backend and renders them
async function loadSemestersFromBackend() {
    try {
        const response = await fetch("/api/noten");
        if (!response.ok) { console.error("Noten konnten nicht geladen werden."); return; }
        const semesters = await response.json();
        document.getElementById("semesters").innerHTML = "";
        semesterCounter = semesters.length;
        semesters.forEach(sem => renderSemester(sem));
    } catch (error) {
        console.error("Fehler beim Abrufen der Semester:", error);
    }
}

// Saves all semesters to the backend
async function saveAllSemestersToBackend() {
    const semesters = [];
    document.querySelectorAll('.semester').forEach(semesterDiv => {
        const subjects = [];
        semesterDiv.querySelectorAll('.subject').forEach(subjectDiv => {
            const grades = [];
            subjectDiv.querySelectorAll('.grade-row').forEach(gradeRow => {
                grades.push({ name: gradeRow.dataset.name, value: parseFloat(gradeRow.dataset.value), weight: parseFloat(gradeRow.dataset.weight), counts: gradeRow.dataset.counts === "true" });
            });
            subjects.push({ name: subjectDiv.querySelector('.subject-title').textContent.trim(), grades: grades, counts_average: subjectDiv.dataset.countsAverage === "true" });
        });
        semesters.push({ name: semesterDiv.querySelector('.semester-name').textContent.trim(), subjects });
    });
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content') || '';
    await fetch("/api/noten", {
        method: "POST",
        credentials: 'same-origin',
        headers: { "Content-Type": "application/json", ...(csrfToken ? {"X-CSRF-Token": csrfToken} : {}) },
        body: JSON.stringify(semesters)
    });
}

// --- Grade input: enforce 1-6 range in real time ---
document.addEventListener("DOMContentLoaded", function() {
    loadSemestersFromBackend();

    // Enforce 1-6 for gradeValue input
    const gradeValueInput = document.getElementById("gradeValue");
    if (gradeValueInput) {
        gradeValueInput.addEventListener("input", function() {
            let val = parseFloat(this.value);
            if (isNaN(val)) return;
            if (val < 1) this.value = 1;
            if (val > 6) this.value = 6;
        });
    }
});

// --- Keyboard Shortcuts for Popups ---
document.addEventListener('keydown', function (e) {
    // ESC: Close any open popup
    if (e.key === 'Escape' || e.key === 'Esc') {
        try {
            // List all popup IDs you use
            const popups = {
                grade: document.getElementById("grade-popup"),
                subject: document.getElementById("subject-popup"),
                semesterRename: document.getElementById("semester-rename-popup"),
                dreamCalc: document.getElementById("dream-calc-popup"),
                deleteConfirm: document.getElementById("delete-confirm-popup")
            };
            const anyVisible = Object.values(popups).some(p => p && !p.classList.contains('hidden'));
            if (anyVisible) {
                // Close all popups
                if (typeof closeGradePopup === 'function') closeGradePopup();
                if (typeof closeSubjectPopup === 'function') closeSubjectPopup();
                if (typeof closeSemesterRenamePopup === 'function') closeSemesterRenamePopup();
                if (typeof closeDreamCalcPopup === 'function') closeDreamCalcPopup();
                if (typeof closeDeleteConfirm === 'function') closeDeleteConfirm();
                e.preventDefault();
            }
        } catch (err) {
            // fail silently
            console.error('Escape handler error:', err);
        }
    }
    // ENTER: Confirm/save if a popup is open and focused
    if (e.key === 'Enter') {
        // Grade popup
        if (document.getElementById("grade-popup") && !document.getElementById("grade-popup").classList.contains('hidden')) {
            if (document.activeElement.tagName !== "TEXTAREA") {
                addOrEditGradeToSubject();
                e.preventDefault();
            }
        }
        // Subject popup
        if (document.getElementById("subject-popup") && !document.getElementById("subject-popup").classList.contains('hidden')) {
            saveSubjectEdit();
            e.preventDefault();
        }
        // Semester rename popup
        if (document.getElementById("semester-rename-popup") && !document.getElementById("semester-rename-popup").classList.contains('hidden')) {
            saveSemesterRename();
            e.preventDefault();
        }
        // Dream calc popup
        if (document.getElementById("dream-calc-popup") && !document.getElementById("dream-calc-popup").classList.contains('hidden')) {
            calculateDreamGradeFromPopup();
            e.preventDefault();
        }
        // Delete confirm popup
        if (document.getElementById("delete-confirm-popup") && !document.getElementById("delete-confirm-popup").classList.contains('hidden')) {
            confirmDeleteSemester();
            e.preventDefault();
        }
    }
});

// --- Subject Delete Confirm ---
let subjectToDelete = null;

// Opens the subject delete confirmation popup
function openDeleteSubjectConfirm(subjectDiv) {
    subjectToDelete = subjectDiv;
    const subjectName = subjectDiv.querySelector('.subject-title').textContent.trim();
    document.getElementById('confirm-subject-name').textContent = `${subjectName} löschen?`;
    overlay.classList.remove("hidden");
    document.getElementById("delete-subject-confirm-popup").classList.remove("hidden");
}

// Closes the subject delete confirmation popup
function closeDeleteSubjectConfirm() {
    overlay.classList.add("hidden");
    document.getElementById("delete-subject-confirm-popup").classList.add("hidden");
    subjectToDelete = null;
}

// Confirms and deletes the selected subject
function confirmDeleteSubject() {
    if (subjectToDelete) {
        subjectToDelete.remove();
        saveAllSemestersToBackend();
    }
    closeDeleteSubjectConfirm();
}

// --- Grade Delete Confirm ---
let gradeToDelete = null;

// Opens the grade delete confirmation popup
function openDeleteGradeConfirm(gradeRow, subjectContext) {
    gradeToDelete = { gradeRow, subjectContext };
    const gradeName = gradeRow.dataset.name;
    document.getElementById('confirm-grade-name').textContent = `${gradeName} löschen?`;
    overlay.classList.remove("hidden");
    document.getElementById("delete-grade-confirm-popup").classList.remove("hidden");
}

// Closes the grade delete confirmation popup
function closeDeleteGradeConfirm() {
    overlay.classList.add("hidden");
    document.getElementById("delete-grade-confirm-popup").classList.add("hidden");
    gradeToDelete = null;
}

// Confirms and deletes the selected grade, then updates averages
function confirmDeleteGrade() {
    if (gradeToDelete) {
        gradeToDelete.gradeRow.remove();
        updateSubjectAverage(
            gradeToDelete.subjectContext.gradesList,
            gradeToDelete.subjectContext.avgSpan,
            gradeToDelete.subjectContext.semesterDiv
        );
        saveAllSemestersToBackend();
    }
    closeDeleteGradeConfirm();
}