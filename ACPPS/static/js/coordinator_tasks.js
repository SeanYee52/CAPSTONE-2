document.addEventListener('DOMContentLoaded', function() {
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

    /**
    * Polls the task status and manages the UI during the polling process.
    * @param {string} taskId - The ID of the task to poll.
    * @param {HTMLElement} statusElement - The element to update with status messages.
    * @param {HTMLButtonElement} button - The button that triggered the task.
    * @param {string} originalButtonText - The original text of the button to restore on failure.
    */
    function pollTaskStatus(taskId, statusElement, button, originalButtonText) {
        statusElement.className = 'mt-3 alert alert-info';
        statusElement.innerHTML = `Task initiated (ID: ${taskId}).<br>Polling for result... <span class="spinner-border spinner-border-sm"></span>`;

        const pollingInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/coordinator/task-status/${taskId}/`);
                const data = await response.json();

                if (data.status === 'SUCCESS' || data.status === 'FAILURE') {
                    clearInterval(pollingInterval); 

                    if (data.status === 'SUCCESS') {
                        statusElement.className = 'mt-3 alert alert-success';
                        let successMessage = `Success: ${data.result?.result || 'Task completed.'}`;
                        statusElement.textContent = `${successMessage} The page will now reload.`;
                        setTimeout(() => window.location.reload(), 2000);
                        
                    } else { // Handle FAILURE
                        statusElement.className = 'mt-3 alert alert-danger';
                        statusElement.textContent = `Task Failed: ${data.result}`;
                        // ** FIX: Re-enable the button ONLY on failure **
                        button.disabled = false;
                        button.innerHTML = originalButtonText;
                    }
                }
            } catch (error) {
                console.error("Polling failed:", error);
                clearInterval(pollingInterval);
                statusElement.className = 'mt-3 alert alert-danger';
                statusElement.textContent = 'Error: Could not retrieve task status.';
                // ** FIX: Re-enable the button on polling error **
                button.disabled = false;
                button.innerHTML = originalButtonText;
            }
        }, 3000);
    }

    /**
    * Starts a task by calling its API endpoint.
    * It disables the button and only re-enables it if the INITIAL call fails.
    * If the call succeeds, it hands off UI management to pollTaskStatus.
    */
    async function startTask(button, statusElement, url, body = null) {
        const originalButtonText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Starting...`;
        
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                body: body ? JSON.stringify(body) : null,
            });

            const data = await response.json();
            
            if (response.ok) {
                // On success, hand off to the poller. DO NOT re-enable the button here.
                pollTaskStatus(data.task_id, statusElement, button, originalButtonText);
            } else {
                // Handle API errors (e.g., 400 Bad Request)
                statusElement.className = 'mt-3 alert alert-danger';
                statusElement.textContent = `Error: ${data.detail || data.error}`;
                // ** FIX: Re-enable the button because the task never started **
                button.disabled = false;
                button.innerHTML = originalButtonText;
            }
        // NOTE: The `finally` block has been REMOVED.
        } catch (error) {
            // Handle network errors
            console.error("Task start failed:", error);
            statusElement.className = 'mt-3 alert alert-danger';
            statusElement.textContent = 'A network error occurred while starting the task.';
            // ** FIX: Re-enable the button because the task never started **
            button.disabled = false;
            button.innerHTML = originalButtonText;
        }
    }

    // --- Attach Event Listeners based on elements present on the page ---
    const standardizeBtn = document.getElementById('standardize-btn');
    if (standardizeBtn) {
        const standardizeStatus = document.getElementById('standardize-status-message');
        standardizeBtn.addEventListener('click', function() {
            // Get the API url from the button's data attribute
            const url = standardizeBtn.dataset.url;
            startTask(standardizeBtn, standardizeStatus, url);
        });
    }

    const labelBtn = document.getElementById('label-btn');
    if (labelBtn) {
        const labelStatus = document.getElementById('label-status-message');
        const semesterInput = document.getElementById('semester-input');
        labelBtn.addEventListener('click', function() {
            const semester = semesterInput.value;
            if (!semester) { alert('Please select a semester.'); return; }
            const body = { semester: semester };
            // Get the API url from the button's data attribute
            const url = labelBtn.dataset.url;
            startTask(labelBtn, labelStatus, url, body);
        });
    }
    
    const matchBtn = document.getElementById('match-btn');
    if (matchBtn) {
        const status = document.getElementById('status-message');
        const semesterInput = document.getElementById('semester-input');
        const weightageInput = document.getElementById('weightage-input')
        matchBtn.addEventListener('click', function(){
            const semester = semesterInput.value;
            const weightage = weightageInput.value;
            if (!semester) { alert('Please select a semester.'); return;}
            const body = { 
                semester: semester,
                weightage: weightage,
             };
            // Get the API url from the button's data attribute
            const url = matchBtn.dataset.url;
            startTask(matchBtn, status, url, body);
        })
    }

    const resetBtn = document.getElementById('reset-btn');
    if (resetBtn) {
        const status = document.getElementById('status-message');
        const semesterInput = document.getElementById('semester-input');
        resetBtn.addEventListener('click', function(){
            const semester = semesterInput.value;
            if (!semester) { alert('Please select a semester.'); return;}
            const body = { semester: semester };
            // Get the API url from the button's data attribute
            const url = resetBtn.dataset.url;
            startTask(resetBtn, status, url, body);
        })
    }
});
