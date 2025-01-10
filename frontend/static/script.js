document.addEventListener('DOMContentLoaded', function() {
    const contentDiv = document.querySelector('.centered-content');
    const outputImage = document.getElementById('outputImage');
    const spinner = document.getElementById('spinner');
    const tableBody = document.getElementById('notificationsBody');
    const notificationsContainer = document.getElementById('notificationsContainer');

    contentDiv.addEventListener('paste', (event) => {
        // Prevent the default paste behavior
        event.preventDefault();
        // Show spinner
        spinner.style.display = 'block';

        // Get the text content from the clipboard
        const text = (event.clipboardData || window.clipboardData).getData('text');
        // Send the pasted content to the server via fetch API
        contentDiv.textContent = '';  // Clear the instructional text
        fetch('/validate_json', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content: text })
        })
        .then(response => {
            if (!response.ok) {
                throw response.json();
            }
            return response.json();
        })
        .then(data => {
            console.log(data.notifications);
            // Add new notifications to the table
            data.notifications.forEach(notification => {
                const row = tableBody.insertRow();
                const severityCell = row.insertCell(0);
                const messageCell = row.insertCell(1);
                severityCell.textContent = notification.severity;
                messageCell.textContent = notification.message;
            });
            outputImage.src = 'data:image/png;base64,' + data.image;
            outputImage.onload = () => {
                notificationsContainer.style.display = 'block';
                spinner.style.display = 'none'; // Hide spinner
            };
        })
        .catch(errorPromise => {
            errorPromise.then(errorMessage => {
                contentDiv.textContent = 'Failed to load the image ' + errorMessage.message;
                spinner.style.display = 'none'; // Hide spinner
            });
        });
    });
});
