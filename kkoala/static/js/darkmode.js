    (function() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        
        function applyTheme(isDark) {
            if (isDark) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        }

        // Apply theme on initial load
        applyTheme(mediaQuery.matches);

        // Listen for changes in system preference
        mediaQuery.addEventListener('change', (e) => {
            applyTheme(e.matches);
        });
    })();