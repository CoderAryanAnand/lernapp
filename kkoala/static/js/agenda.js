document.addEventListener('DOMContentLoaded', function () {
    let calendar;
    const overlay = document.getElementById('overlay');
    const popups = {
        event: document.getElementById('event-popup'),
        create: document.getElementById('create-popup'),
        scheduler: document.getElementById('scheduler-popup')
    };

    // --- HELPER FUNCTIONS ---
    function openPopup(popupKey) {
        closeAllPopups();
        overlay.classList.remove('hidden');
        if (popups[popupKey]) {
            popups[popupKey].classList.remove('hidden');
        }
    }

    window.closeAllPopups = function() {
        overlay.classList.add('hidden');
        for (const key in popups) {
            if (popups[key]) popups[key].classList.add('hidden');
        }
    }

    function openEventPopup(event) {
        document.getElementById('event-id').value = event.id;
        document.getElementById('recurrence-id').value = event.extendedProps.recurrence_id;
        document.getElementById('edit-event-priority').value = event.extendedProps.priority;
        document.getElementById('event-title').value = event.title;
        document.getElementById('event-color').value = event.backgroundColor;
        function toLocalInputValue(date) {
            if (!date) return '';
            const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
            return local.toISOString().slice(0, 16);
        }
        document.getElementById('event-start').value = toLocalInputValue(event.start);
        document.getElementById('event-end').value = event.end ? toLocalInputValue(event.end) : '';
        document.getElementById('edit-all-day').checked = !!event.allDay;
        openPopup('event');
    }

    function openCreatePopup(dateStr, endTime) {
        document.getElementById('create-event-form').reset();
        document.getElementById('create-start').value = dateStr;
        document.getElementById('create-end').value = endTime;
        openPopup('create');
    }

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
    window.deleteEvent = async function() {
        if (!confirm("Sind Sie sicher, dass Sie diesen Termin löschen möchten?")) return;
        const eventId = document.getElementById('event-id').value;
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        await fetch(`/api/events/${eventId}`, { method: 'DELETE', headers: { 'X-CSRF-Token': csrfToken } });
        calendar.refetchEvents();
        closeAllPopups();
    }

    window.deleteRecurringEvents = async function() {
        if (!confirm("Sind Sie sicher, dass Sie diese gesamte Terminserie löschen möchten?")) return;
        const recurrenceId = document.getElementById('recurrence-id').value;
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        await fetch(`/api/events/recurring/${recurrenceId}`, { method: 'DELETE', headers: { 'X-CSRF-Token': csrfToken } });
        calendar.refetchEvents();
        closeAllPopups();
    }

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

    window.exportICS = function() { window.location.href = '/api/events/export-ics'; }

    // --- INITIALIZE THE CALENDAR ---
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
});