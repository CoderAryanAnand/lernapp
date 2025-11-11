// Wait for the DOM to be fully loaded before running the script
document.addEventListener('DOMContentLoaded', function() {
    // Get references to the Saturday and Sunday checkboxes and the warning div
    const saturdayCheckbox = document.getElementById('saturday');
    const sundayCheckbox = document.getElementById('sunday');
    const warningDiv = document.getElementById('weekend-warning');

    // Checks if both weekend days are selected and shows/hides the warning accordingly
    function checkWeekendSelection() {
        if (saturdayCheckbox.checked && sundayCheckbox.checked) {
            warningDiv.classList.remove('hidden');
        } else {
            warningDiv.classList.add('hidden');
        }
    }

    // Add event listeners to both checkboxes to trigger the check on change
    saturdayCheckbox.addEventListener('change', checkWeekendSelection);
    sundayCheckbox.addEventListener('change', checkWeekendSelection);

    // Perform an initial check when the page loads
    checkWeekendSelection();
});