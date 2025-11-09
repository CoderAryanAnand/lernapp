document.addEventListener('DOMContentLoaded', function() {
    const saturdayCheckbox = document.getElementById('saturday');
    const sundayCheckbox = document.getElementById('sunday');
    const warningDiv = document.getElementById('weekend-warning');

    function checkWeekendSelection() {
        if (saturdayCheckbox.checked && sundayCheckbox.checked) {
            warningDiv.classList.remove('hidden');
        } else {
            warningDiv.classList.add('hidden');
        }
    }

    // Add event listeners to both checkboxes
    saturdayCheckbox.addEventListener('change', checkWeekendSelection);
    sundayCheckbox.addEventListener('change', checkWeekendSelection);

    // Initial check when the page loads
    checkWeekendSelection();
});