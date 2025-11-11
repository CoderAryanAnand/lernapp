document.addEventListener('DOMContentLoaded', () => {
    // Add click event listeners to all accordion toggle buttons
    document.querySelectorAll('.accordion-toggle').forEach(button => {
        button.addEventListener('click', () => {
            // Get the content panel and the chevron icon inside the button
            const content = button.nextElementSibling;
            const icon = button.querySelector('svg');

            // Toggle visibility of the accordion content
            content.classList.toggle('hidden');

            // Rotate the chevron icon based on the content's visibility
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
        // Show or hide the scroll-to-top button based on scroll position
        window.onscroll = function() {
            if (document.body.scrollTop > 100 || document.documentElement.scrollTop > 100) {
                scrollTopBtn.classList.remove('hidden');
            } else {
                scrollTopBtn.classList.add('hidden');
            }
        };

        // Smoothly scroll to the top when the button is clicked
        scrollTopBtn.addEventListener('click', function() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
});