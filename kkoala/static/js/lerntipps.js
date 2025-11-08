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

    // --- Scroll to Top Button Logic ---
    const scrollTopBtn = document.getElementById('scrollTopBtn');

    if (scrollTopBtn) {
        // Show or hide the button based on scroll position
        window.onscroll = function() {
            if (document.body.scrollTop > 100 || document.documentElement.scrollTop > 100) {
                scrollTopBtn.classList.remove('hidden');
            } else {
                scrollTopBtn.classList.add('hidden');
            }
        };

        // Scroll to the top when the button is clicked
        scrollTopBtn.addEventListener('click', function() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
});