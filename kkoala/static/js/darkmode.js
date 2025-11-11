document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.getElementById('theme-toggle');
    const userThemeSetting = document.documentElement.getAttribute('data-theme-setting');

    // Applies the given theme by toggling the 'dark' class on the root element.
    function applyTheme(theme) {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }

    // Handles system theme changes if user setting is 'system'.
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    function handleSystemThemeChange(e) {
        if (document.documentElement.getAttribute('data-theme-setting') === 'system') {
            applyTheme(e.matches ? 'dark' : 'light');
        }
    }

    // Sets the initial theme based on user setting or system preference.
    if (userThemeSetting === 'dark') {
        applyTheme('dark');
    } else if (userThemeSetting === 'light') {
        applyTheme('light');
    } else {
        // In 'system' mode, use localStorage if set, otherwise use OS preference.
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            applyTheme(savedTheme);
        } else {
            applyTheme(mediaQuery.matches ? 'dark' : 'light');
        }
        // Listen for OS theme changes only in system mode.
        mediaQuery.addEventListener('change', handleSystemThemeChange);
    }

    // Handles the theme toggle button (only in 'system' mode).
    if (themeToggle) {
        if (userThemeSetting !== 'system') {
            // Hide the toggle if a theme is forced.
            themeToggle.style.display = 'none';
        } else {
            themeToggle.addEventListener('click', () => {
                const isDark = document.documentElement.classList.toggle('dark');
                localStorage.setItem('theme', isDark ? 'dark' : 'light');
            });
        }
    }
});