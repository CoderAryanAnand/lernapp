/**
 * agenda.js
 * Handles all logic for the Agenda (calendar) page.
 * - Initializes FullCalendar and manages events (CRUD).
 * - Handles popups for event creation, editing, and scheduling results.
 * - Supports .ics import/export and learning algorithm execution.
 * - Manages color selection based on priority.
 * - Uses CSRF tokens for secure API requests.
 */

document.addEventListener('DOMContentLoaded', function () {
    // --- GLOBAL VARIABLES ---
    let calendar;
    const overlay = document.getElementById('overlay');
    const popups = {
        event: document.getElementById('event-popup'),
        create: document.getElementById('create-popup'),
        scheduler: document.getElementById('scheduler-popup')
    };

    // --- HELPER FUNCTIONS ---

    // Opens a popup by key and shows the overlay. Closes all other popups first.
    function openPopup(popupKey) {
        closeAllPopups();
        overlay.classList.remove('hidden');
        if (popups[popupKey]) {
            popups[popupKey].classList.remove('hidden');
        }
    }

    // Closes all popups and hides the overlay.
    window.closeAllPopups = function() {
        overlay.classList.add('hidden');
        for (const key in popups) {
            if (popups[key]) popups[key].classList.add('hidden');
        }
    }

    // Opens the event edit popup and fills it with event data.
    function openEventPopup(event) {
        document.getElementById('event-id').value = event.id;
        document.getElementById('recurrence-id').value = event.extendedProps.recurrence_id;
        document.getElementById('edit-event-priority').value = event.extendedProps.priority;
        document.getElementById('event-title').value = event.title;
        document.getElementById('event-color').value = event.backgroundColor;
        // Helper to format date for input fields
        function toLocalInputValue(date) {
            if (!date) return '';
            const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
            return local.toISOString().slice(0, 16);
        }
        document.getElementById('event-start').value = toLocalInputValue(event.start);
        document.getElementById('event-end').value = event.end ? toLocalInputValue(event.end) : '';
        document.getElementById('edit-all-day').checked = !!event.allDay;

        // Show/hide recurrence options based on event
        const isRecurring = event.extendedProps.recurrence_id !== '0' && event.extendedProps.recurrence_id != null;
        const recurrenceContainer = document.getElementById('edit-recurrence-container');
        const recurrenceSelect = document.getElementById('edit-recurrence');
        if (isRecurring) {
            recurrenceContainer.classList.remove('hidden');
            recurrenceSelect.value = 'this'; // Default to 'this'
        } else {
            recurrenceContainer.classList.add('hidden');
            recurrenceSelect.value = 'this'; // Reset to 'this' for safety
        }

        openPopup('event');
    }

    // Opens the event creation popup and sets start/end time.
    function openCreatePopup(dateStr, endTime) {
        document.getElementById('create-event-form').reset();
        document.getElementById('create-start').value = dateStr;
        document.getElementById('create-end').value = endTime;
        openPopup('create');
    }

    // Displays the scheduling algorithm results in a popup.
    function displaySchedulingPopup(summary, results) {
        const messageContainer = document.getElementById('scheduler-message');
        let messageHTML = `<h3>Globale Zusammenfassung:</h3>`;
        messageHTML += `<p>Verarbeitete Prüfungen: <strong>${summary.exams_processed}</strong></p>`;
        messageHTML += `<p>Insgesamt hinzugefügte Blöcke: <strong>${summary.blocks_added}</strong></p>`;
        messageHTML += `<p>Insgesamt geplante Stunden: <strong>${summary.hours_added.toFixed(2)} Stunden</strong></p>`;
        messageHTML += `<hr class="my-2 border-zinc-300 dark:border-zinc-600"><h3>Prüfungsstatus:</h3>`;
        for (const examTitle in results) {
            const [success, details] = results[examTitle];
            const colorClass = success ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
            const icon = success ? '✅' : '❌';
            messageHTML += `<p class="${colorClass} my-1">${icon} <strong>${examTitle}:</strong> ${details}</p>`;
        }
        messageContainer.innerHTML = messageHTML;
        openPopup('scheduler');
    }

    // --- GLOBAL FUNCTIONS (ATTACHED TO WINDOW) ---

    // Handles delete button click in event edit popup.
    window.handleDelete = function() {
        const recurrenceId = document.getElementById('recurrence-id').value;
        const isRecurring = recurrenceId !== '0' && recurrenceId != null;
        const eventId = document.getElementById('event-id').value;
        const recurrenceSelect = document.getElementById('edit-recurrence');
        const deleteType_ = recurrenceSelect.value;
        openDeleteEventConfirm(isRecurring, eventId, recurrenceId, deleteType_);
    }

    // Handles .ics file import and sends it to the backend.
    window.importICSFile = async function(event) {
        const file = event.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async function (e) {
            const icsContent = e.target.result;
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            const response = await fetch('/api/events/import-ics', {
                method: 'POST', body: JSON.stringify({ ics: icsContent }),
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }
            });
            if (response.ok) { alert('Termine erfolgreich importiert!'); calendar.refetchEvents(); } 
            else { alert('Import der Termine fehlgeschlagen.'); }
        };
        reader.readAsText(file);
    }

    // Triggers .ics export by redirecting to the export endpoint.
    window.exportICS = function() { window.location.href = '/api/events/export-ics'; }

    // --- INITIALIZE THE CALENDAR ---

    // Initializes FullCalendar with configuration and event handlers.
    const calendarEl = document.getElementById('calendar');
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'timeGridWeek',
        headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek,timeGridDay' },
        locale: 'de',
        height: 'auto',
        slotLabelFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
        eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
        events: '/api/events',
        eventClick: function (info) { openEventPopup(info.event); },
        dateClick: function (info) {
            const endTime = new Date(info.date);
            endTime.setHours(endTime.getHours() + 1);
            const timezoneOffset = endTime.getTimezoneOffset() * 60000;
            const localEndTime = new Date(endTime - timezoneOffset);
            openCreatePopup(info.dateStr.slice(0, 16), localEndTime.toISOString().slice(0, 16));
        }
    });
    calendar.render();

    // --- EVENT LISTENERS ---

    // Handles event edit form submission (PUT)
    document.getElementById('edit-event-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        formData.set('all_day', document.getElementById('edit-all-day').checked);
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        await fetch('/api/events', {
            method: 'PUT', body: JSON.stringify(Object.fromEntries(formData)),
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }
        });
        calendar.refetchEvents();
        closeAllPopups();
    });

    // Handles event creation form submission (POST)
    document.getElementById('create-event-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        formData.set('all_day', document.getElementById('all-day').checked);
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        await fetch('/api/events', {
            method: 'POST', body: JSON.stringify(Object.fromEntries(formData)),
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }
        });
        calendar.refetchEvents();
        closeAllPopups();
    });

    // Handles learning algorithm execution
    document.getElementById('run-scheduler-btn').addEventListener('click', function() {
        this.disabled = true;
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        fetch('/api/events/run-learning-algorithm', {
            method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                displaySchedulingPopup(data.summary, data.results);
                calendar.refetchEvents();
            } else { alert('Fehler bei der Planung: ' + (data.error || 'Unbekannter Fehler')); }
        })
        .catch(error => { console.error('Fetch-Fehler:', error); alert('Ein Netzwerkfehler ist aufgetreten.'); })
        .finally(() => { this.disabled = false; });
    });

    // --- COLOR PICKER LOGIC FOR CREATE POPUP ---

    // Syncs color input with selected priority for create event popup.
    const createPrioritySelect = document.getElementById('create-event-priority');
    const createColorInput = document.getElementById('create-color');
    if (createPrioritySelect && createColorInput && typeof priorityColors !== 'undefined') {
        function updateCreateColorBasedOnPriority() {
            const selectedPriority = createPrioritySelect.value;
            let newColor = '#000000'; // Default color
            if (priorityColors[selectedPriority]) {
                newColor = priorityColors[selectedPriority];
            }
            createColorInput.value = newColor;
        }
        createPrioritySelect.addEventListener('change', updateCreateColorBasedOnPriority);
        updateCreateColorBasedOnPriority();
    }

    // --- COLOR PICKER LOGIC FOR EDIT POPUP ---

    // Syncs color input with selected priority for edit event popup.
    const editPrioritySelect = document.getElementById('edit-event-priority');
    const editColorInput = document.getElementById('event-color');
    if (editPrioritySelect && editColorInput && typeof priorityColors !== 'undefined') {
        function updateEditColorBasedOnPriority() {
            const selectedPriority = editPrioritySelect.value;
            let newColor = priorityColors["1"] || '#000000';
            if (priorityColors[selectedPriority]) {
                newColor = priorityColors[selectedPriority];
            }
            editColorInput.value = newColor;
        }
        editPrioritySelect.addEventListener('change', updateEditColorBasedOnPriority);
    }

    // --- ESCAPE KEY HANDLER FOR POPUPS ---

    // Closes popups when Escape key is pressed.
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' || e.key === 'Esc') {
            try {
                const anyVisible = Object.values(popups).some(p => p && !p.classList.contains('hidden'));
                if (anyVisible && typeof closeAllPopups === 'function') {
                    closeAllPopups();
                    e.preventDefault();
                }
            } catch (err) {
                // Fail silently
                console.error('Escape handler error:', err);
            }
        }
    });

    // --- DELETE EVENT LOGIC ---

    let eventToDelete = null;
    let deleteType = "single"; // "single" or "all"

    // Opens the delete confirmation popup for single or recurring events.
    window.openDeleteEventConfirm = function(isRecurring, eventId, recurrenceId, deleteAllorSingle) {
        eventToDelete = eventId;
        document.getElementById('overlay').classList.remove('hidden');
        document.getElementById('delete-event-confirm-popup').classList.remove('hidden');
        const msgDiv = document.getElementById('delete-event-confirm-message');
        if (isRecurring && deleteAllorSingle == 'all') {
            eventToDelete = recurrenceId; // Use recurrence ID to delete whole series
            msgDiv.textContent = `Möchtest du die gesamte Serie wirklich löschen?`;
            deleteType = "all";
        } else {
            eventToDelete = eventId;
            msgDiv.textContent = `Möchtest du diesen Termin wirklich löschen?`;
            deleteType = "single";
        }
    };

    // Closes the delete confirmation popup.
    window.closeDeleteEventConfirm = function() {
        document.getElementById('overlay').classList.add('hidden');
        document.getElementById('delete-event-confirm-popup').classList.add('hidden');
        eventToDelete = null;
    };

    // Confirms deletion of an event or recurring series. Sends DELETE request to backend and refreshes calendar.
    window.confirmDeleteEvent = async function() {
        if (!eventToDelete) return;
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        if (deleteType === "all") {
            // Delete recurring series
            await fetch(`/api/events/recurring/${eventToDelete}`, { 
                method: 'DELETE', 
                headers: { 'X-CSRF-Token': csrfToken } 
            });
        } else {
            // Delete single event
            await fetch(`/api/events/${eventToDelete}`, { 
                method: 'DELETE', 
                headers: { 'X-CSRF-Token': csrfToken } 
            });
        }
        // Refresh calendar and close popups
        if (typeof calendar !== "undefined") calendar.refetchEvents();
        closeDeleteEventConfirm();
        closeAllPopups();
    };
});