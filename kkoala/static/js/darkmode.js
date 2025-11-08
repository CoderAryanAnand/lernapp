document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.getElementById('theme-toggle');
    const userThemeSetting = document.documentElement.getAttribute('data-theme-setting');

    // Function to apply the theme
    function applyTheme(theme) {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }

    // Function to handle system theme changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    function handleSystemThemeChange(e) {
        // Only apply if the user setting is 'system'
        if (document.documentElement.getAttribute('data-theme-setting') === 'system') {
            applyTheme(e.matches ? 'dark' : 'light');
        }
    }

    // Initial theme application based on user setting
    if (userThemeSetting === 'dark') {
        applyTheme('dark');
    } else if (userThemeSetting === 'light') {
        applyTheme('light');
    } else { // 'system' or not set
        // Use localStorage for toggle state within 'system' mode
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            applyTheme(savedTheme);
        } else {
            applyTheme(mediaQuery.matches ? 'dark' : 'light');
        }
        // Listen for OS theme changes only in system mode
        mediaQuery.addEventListener('change', handleSystemThemeChange);
    }

    // The theme toggle button now only works if the mode is 'system'
    if (themeToggle) {
        if (userThemeSetting !== 'system') {
            // Optional: hide or disable the toggle if a theme is forced
            themeToggle.style.display = 'none'; 
        } else {
            themeToggle.addEventListener('click', () => {
                const isDark = document.documentElement.classList.toggle('dark');
                localStorage.setItem('theme', isDark ? 'dark' : 'light');
            });
        }
    }
});