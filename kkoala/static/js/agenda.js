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

        // *** MODIFIED: Show/hide recurrence options based on event ***
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
        // *** END MODIFICATION ***

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

    // *** MODIFIED: Replaced deleteEvent and deleteRecurringEvents with a single handleDelete ***
    window.handleDelete = async function() {
        const recurrenceSelect = document.getElementById('edit-recurrence');
        const recurrenceId = document.getElementById('recurrence-id').value;
        const deleteType = recurrenceSelect.value;
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        
        // Check if the event is recurring AND the user selected 'all'
        if (recurrenceId !== '0' && recurrenceId != null && deleteType === 'all') {
            // Logic for deleting the entire series
            if (!confirm("Sind Sie sicher, dass Sie diese gesamte Terminserie löschen möchten?")) return;
            await fetch(`/api/events/recurring/${recurrenceId}`, { 
                method: 'DELETE', 
                headers: { 'X-CSRF-Token': csrfToken } 
            });
        } else {
            // Logic for deleting a single event (or single instance of a series)
            if (!confirm("Sind Sie sicher, dass Sie diesen Termin löschen möchten?")) return;
            const eventId = document.getElementById('event-id').value;
            await fetch(`/api/events/${eventId}`, { 
                method: 'DELETE', 
                headers: { 'X-CSRF-Token': csrfToken } 
            });
        }
        
        // After either delete action, refetch and close
        calendar.refetchEvents();
        closeAllPopups();
    }
    // *** END MODIFICATION ***

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

    // Holen Sie sich die Elemente des "Termin erstellen"-Popups
    const createPrioritySelect = document.getElementById('create-event-priority');
    const createColorInput = document.getElementById('create-color');

    // Prüfen, ob die Elemente und die eingebetteten Daten existieren
    if (createPrioritySelect && createColorInput && typeof priorityColors !== 'undefined') {
        
        // Funktion zur Aktualisierung der Farbe basierend auf der Priorität
        function updateCreateColorBasedOnPriority() {
            const selectedPriority = createPrioritySelect.value;
            let newColor = '#000000'; // Standardfarbe (z.B. blau-500)

            // Suchen Sie die Farbe im eingebetteten Objekt
            if (priorityColors[selectedPriority]) {
                newColor = priorityColors[selectedPriority];
            }
            
            // Aktualisieren Sie den Wert des Farbfeldes
            createColorInput.value = newColor;
        }

        // Fügen Sie den Event-Listener hinzu
        createPrioritySelect.addEventListener('change', updateCreateColorBasedOnPriority);
        
        // OPTIONAL: Beim Öffnen des Popups die Farbe initial setzen
        // Wenn Sie eine Funktion haben, die das 'create-popup' öffnet:
        // Fügen Sie 'updateCreateColorBasedOnPriority();' am Ende dieser Funktion hinzu.
        // Wenn nicht, wird die Farbe beim ersten Mal, wenn der Benutzer die Priorität ändert, gesetzt.
        
        // Führen Sie die Funktion einmal aus, um sicherzustellen, dass die Standardpriorität
        // beim Laden die richtige Farbe hat.
        updateCreateColorBasedOnPriority();
    }

    // --- LOGIK FÜR DAS "TERMIN BEARBEITEN"-POPUP ---
    
    // Holen Sie sich die Elemente des "Termin bearbeiten"-Popups
    const editPrioritySelect = document.getElementById('edit-event-priority');
    const editColorInput = document.getElementById('event-color'); // Das Farbfeld hat die ID 'event-color'

    // Prüfen, ob die Elemente und die eingebetteten Daten existieren
    if (editPrioritySelect && editColorInput && typeof priorityColors !== 'undefined') {
        
        // Funktion zur Aktualisierung der Farbe basierend auf der Priorität
        function updateEditColorBasedOnPriority() {
            const selectedPriority = editPrioritySelect.value;
            // Nutzen Sie die Farbe von Priorität 1 als Fallback, wenn nichts gefunden wird
            let newColor = priorityColors["1"] || '#000000'; 

            // Suchen Sie die Farbe im eingebetteten Objekt
            if (priorityColors[selectedPriority]) {
                newColor = priorityColors[selectedPriority];
            }
            
            // Aktualisieren Sie den Wert des Farbfeldes
            editColorInput.value = newColor;

        }

        // Fügen Sie den Event-Listener hinzu
        editPrioritySelect.addEventListener('change', updateEditColorBasedOnPriority);
        
        // HINWEIS: Hier ist keine sofortige Initialisierung beim Laden nötig, da das Bearbeiten-Popup
        // erst geöffnet wird, wenn ein Event angeklickt wird. 
        // 
        // WICHTIG: Sie MÜSSEN 'updateEditColorBasedOnPriority()' in Ihrer Funktion 
        // aufrufen, die das 'event-popup' öffnet, BEVOR Sie das Farbfeld mit den 
        // tatsächlichen Event-Daten überschreiben.
        //
        // Beispiel: In Ihrer Funktion 'openEditEventPopup(event)', nachdem das Dropdown
        // mit der Priorität des Events befüllt wurde, aber bevor die Farbe des Events
        // zugewiesen wird, sollten Sie dies aufrufen:
        //
        // updateEditColorBasedOnPriority(); 
        //
        // Der Grund dafür ist, dass die Farbe eines *existierenden* Events nicht der
        // Standardfarbe der Priorität entsprechen muss, wenn der Benutzer sie zuvor 
        // manuell geändert hat.
    }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' || e.key === 'Esc') {
            try {
                const anyVisible = Object.values(popups).some(p => p && !p.classList.contains('hidden'));
                if (anyVisible && typeof closeAllPopups === 'function') {
                    closeAllPopups();
                    e.preventDefault();
                }
            } catch (err) {
                // fail silently
                console.error('Escape handler error:', err);
            }
        }
    });
});