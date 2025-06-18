document.addEventListener('DOMContentLoaded', function() {
    const semesterSelect = document.getElementById('semester-input');

    if (semesterSelect) {
        semesterSelect.addEventListener('change', function() {
            const selectedSemesterId = this.value;
            
            // Get the current URL
            const currentUrl = new URL(window.location.href);

            // Set the 'semester' query parameter to the selected value
            if (selectedSemesterId) {
                currentUrl.searchParams.set('semester', selectedSemesterId);
            } else {
                // If the user selects an empty option, remove the parameter
                currentUrl.searchParams.delete('semester');
            }
            
            // Redirect the browser to the new URL
            window.location.href = currentUrl.toString();
        });
    }
});