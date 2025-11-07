document.addEventListener('DOMContentLoaded', () => {
    // Add event listeners to all accordion toggle buttons
    document.querySelectorAll('.accordion-toggle').forEach(button => {
        button.addEventListener('click', () => {
            // Find the content panel and the icon
            const content = button.nextElementSibling;
            const icon = button.querySelector('svg');

            // Toggle the 'hidden' class on the content
            content.classList.toggle('hidden');

            // Rotate the icon
            if (content.classList.contains('hidden')) {
                icon.classList.remove('rotate-180');
            } else {
                icon.classList.add('rotate-180');
            }
        });
    });
});