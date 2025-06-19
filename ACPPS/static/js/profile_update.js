document.addEventListener('DOMContentLoaded', function() {

    const updateBtn = document.getElementById('update-btn');
    if (updateBtn) {
        updateBtn.addEventListener('click', function() {
            // Get the API url from the button's data attribute
            const url = updateBtn.dataset.url;
            window.location.href=url;
        });
    }

});