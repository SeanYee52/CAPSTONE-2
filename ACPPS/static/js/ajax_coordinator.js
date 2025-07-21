document.addEventListener('DOMContentLoaded', () => {
    // --- CSRF Token Helper ---
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    // --- Get URL templates from the DOM ---
    const supervisorTableBody = document.getElementById('supervisor-table-body');
    // Early exit if the table isn't on the page
    if (!supervisorTableBody) {
        return;
    }

    const toggleUrlTemplate = supervisorTableBody.dataset.toggleUrl;
    const capacityUrlTemplate = supervisorTableBody.dataset.capacityUrl;

    // --- Logic for Toggling 'Accepting Students' ---
    document.querySelectorAll('.toggle-acceptance').forEach(button => {
        button.addEventListener('click', (event) => {
            event.preventDefault();
            const supervisorId = button.dataset.supervisorId;
            const url = toggleUrlTemplate.replace('0', supervisorId); // Use the template from data-*

            fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                credentials: 'same-origin' // <-- IMPORTANT for authentication
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    const iconContainer = button.querySelector('span');
                    if (data.new_state) {
                        iconContainer.className = 'text-success';
                        iconContainer.innerHTML = '<i class="bi bi-check-circle-fill"></i>';
                    } else {
                        iconContainer.className = 'text-danger';
                        iconContainer.innerHTML = '<i class="bi bi-x-circle-fill"></i>';
                    }
                } else {
                    alert(`Error: ${data.message}`);
                }
            })
            .catch(error => console.error('Error toggling acceptance:', error));
        });
    });

    // --- Logic for Editing 'Supervision Capacity' ---
    document.querySelectorAll('.capacity-cell').forEach(cell => {
        const displaySpan = cell.querySelector('.capacity-display');
        const inputField = cell.querySelector('.capacity-input');

        displaySpan.addEventListener('click', () => {
            displaySpan.style.display = 'none';
            inputField.style.display = 'inline-block';
            inputField.focus();
            inputField.select();
        });

        const updateCapacity = () => {
            const supervisorId = cell.dataset.supervisorId;
            const newCapacity = inputField.value;

            if (newCapacity === displaySpan.textContent) {
                inputField.style.display = 'none';
                displaySpan.style.display = 'inline-block';
                return;
            }

            const url = capacityUrlTemplate.replace('0', supervisorId); // Use the template from data-*

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ capacity: newCapacity }),
                credentials: 'same-origin' // <-- IMPORTANT for authentication
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.message) });
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    displaySpan.textContent = data.new_capacity;
                }
                inputField.style.display = 'none';
                displaySpan.style.display = 'inline-block';
            })
            .catch(error => {
                alert(`Update Failed: ${error.message}`);
                inputField.value = displaySpan.textContent; 
                inputField.style.display = 'none';
                displaySpan.style.display = 'inline-block';
            });
        };

        inputField.addEventListener('blur', updateCapacity);
        inputField.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                inputField.blur();
            } else if (event.key === 'Escape') {
                inputField.value = displaySpan.textContent;
                inputField.style.display = 'none';
                displaySpan.style.display = 'inline-block';
            }
        });
    });
});