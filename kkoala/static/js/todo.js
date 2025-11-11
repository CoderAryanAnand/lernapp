// Retrieves the CSRF token from the meta tag for secure requests
function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

// Opens the popup for creating a new category and focuses the input
function openCreateCategoryPopup() {
    document.getElementById('overlay').classList.remove('hidden');
    document.getElementById('create-category-popup').classList.remove('hidden');
    document.getElementById('category-name').focus();
}

// Closes all popups and clears the category name input
function closeAllPopups() {
    document.getElementById('overlay').classList.add('hidden');
    document.getElementById('create-category-popup').classList.add('hidden');
    document.getElementById('category-name').value = '';
}

// Expands or collapses a category and rotates the chevron icon
function toggleCategory(categoryId) {
    const content = document.getElementById(`category-${categoryId}`);
    const icon = document.getElementById(`icon-${categoryId}`);
    content.classList.toggle('expanded');
    icon.classList.toggle('rotated');
}

// Handles the creation of a new category via form submission
document.getElementById('create-category-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('category-name').value.trim();
    if (!name) {
        alert('Bitte geben Sie einen Kategorienamen ein.');
        return;
    }
    try {
        const response = await fetch('/api/todo/categories', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken()
            },
            body: JSON.stringify({ name })
        });
        if (response.ok) {
            const data = await response.json();
            location.reload(); // Reload to show new category
        } else {
            const error = await response.json();
            alert(error.message || 'Fehler beim Erstellen der Kategorie');
        }
    } catch (error) {
        console.error('Error creating category:', error);
        alert('Fehler beim Erstellen der Kategorie');
    }
});

// Deletes a category after user confirmation and animates its removal
async function deleteCategory(categoryId) {
    if (!confirm('Möchten Sie diese Kategorie wirklich löschen? Alle Aufgaben werden ebenfalls gelöscht.')) {
        return;
    }
    try {
        const response = await fetch(`/api/todo/categories/${categoryId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRF-Token': getCsrfToken()
            }
        });
        if (response.ok) {
            // Animate and remove the category from the DOM
            const categoryEl = document.querySelector(`[data-category-id="${categoryId}"]`);
            categoryEl.style.transition = 'opacity 0.3s ease-out';
            categoryEl.style.opacity = '0';
            setTimeout(() => {
                categoryEl.remove();
                // If no categories left, reload the page
                const container = document.getElementById('categories-container');
                if (container.children.length === 0) {
                    location.reload();
                }
            }, 300);
        } else {
            const error = await response.json();
            alert(error.message || 'Fehler beim Löschen der Kategorie');
        }
    } catch (error) {
        console.error('Error deleting category:', error);
        alert('Fehler beim Löschen der Kategorie');
    }
}

// Adds a new todo item to a category and updates the DOM
async function addTodoItem(categoryId) {
    const input = document.getElementById(`new-item-${categoryId}`);
    const description = input.value.trim();
    if (!description) {
        alert('Bitte geben Sie eine Aufgabe ein.');
        return;
    }
    try {
        const response = await fetch(`/api/todo/categories/${categoryId}/items`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken()
            },
            body: JSON.stringify({ description })
        });
        if (response.ok) {
            const data = await response.json();
            // Create and append the new item element to the DOM
            const itemsContainer = document.getElementById(`items-${categoryId}`);
            const itemEl = document.createElement('div');
            itemEl.className = 'flex items-start space-x-3 p-3 bg-zinc-50 dark:bg-zinc-700/50 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors group cursor-pointer';
            itemEl.onclick = function(event) {
                if (event.target.tagName !== 'INPUT') {
                    this.querySelector('input[type=checkbox]').checked = true;
                    completeAndDeleteTodoItem(data.item.id, this.querySelector('input[type=checkbox]'));
                }
            };
            itemEl.setAttribute('data-item-id', data.item.id);
            itemEl.innerHTML = `
                <input type="checkbox" 
                       onchange="completeAndDeleteTodoItem(${data.item.id}, this)"
                       class="h-5 w-5 mt-0.5 flex-shrink-0 rounded border-zinc-300 dark:border-zinc-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer">
                <span class="flex-1 text-zinc-800 dark:text-zinc-200 break-words min-w-0">
                    ${escapeHtml(data.item.description)}
                </span>
            `;
            itemsContainer.appendChild(itemEl);
            updateItemCount(categoryId);
            input.value = '';
            input.focus();
        } else {
            const error = await response.json();
            alert(error.message || 'Fehler beim Hinzufügen der Aufgabe');
        }
    } catch (error) {
        console.error('Error adding item:', error);
        alert('Fehler beim Hinzufügen der Aufgabe');
    }
}

// Marks a todo item as completed, animates, and deletes it from backend and DOM
async function completeAndDeleteTodoItem(itemId, checkbox) {
    if (!checkbox.checked) {
        // Only allow checking, not unchecking
        checkbox.checked = false;
        return;
    }
    try {
        // Delete the item in backend and animate removal in DOM
        const delResponse = await fetch(`/api/todo/items/${itemId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRF-Token': getCsrfToken()
            }
        });
        if (delResponse.ok) {
            const itemEl = document.querySelector(`[data-item-id="${itemId}"]`);
            const categoryId = itemEl.closest('[data-category-id]').getAttribute('data-category-id');
            const textSpan = itemEl.querySelector('span');
            // Add strikethrough animation
            textSpan.classList.add('line-through', 'text-zinc-500', 'dark:text-zinc-500', 'strikethrough-animation');
            itemEl.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
            setTimeout(() => {
                itemEl.style.opacity = '0';
                itemEl.style.transform = 'translateX(20px)';
                setTimeout(() => {
                    itemEl.remove();
                    updateItemCount(categoryId);
                }, 300);
            }, 300);
        } else {
            checkbox.checked = false;
            const error = await delResponse.json();
            alert(error.message || 'Fehler beim Löschen der Aufgabe');
        }
    } catch (error) {
        console.error('Error deleting item:', error);
        checkbox.checked = false;
        alert('Fehler beim Löschen der Aufgabe');
    }
}

// Updates the item count in the category header after changes
function updateItemCount(categoryId) {
    const categoryEl = document.querySelector(`[data-category-id="${categoryId}"]`);
    const itemsContainer = document.getElementById(`items-${categoryId}`);
    const itemCount = itemsContainer.querySelectorAll('[data-item-id]').length;
    const countSpan = categoryEl.querySelector('.text-sm.text-zinc-500');
    if (countSpan) {
        countSpan.textContent = `(${itemCount})`;
    }
}

// Escapes HTML to prevent XSS when rendering user input
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// On page load, collapse all categories and reset icons
document.addEventListener('DOMContentLoaded', () => {
    const categories = document.querySelectorAll('[data-category-id]');
    categories.forEach(cat => {
        const categoryId = cat.getAttribute('data-category-id');
        const content = document.getElementById(`category-${categoryId}`);
        const icon = document.getElementById(`icon-${categoryId}`);
        if (content && icon) {
            content.classList.remove('expanded');
            icon.classList.remove('rotated');
        }
    });
});

// Closes all popups when the Escape key is pressed
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAllPopups();
    }
});