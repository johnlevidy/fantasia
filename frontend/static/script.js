document.addEventListener('DOMContentLoaded', function() {
    const contentDiv = document.querySelector('.centered-content');
    const outputImage = document.getElementById('outputImage');
    const spinner = document.getElementById('spinner');

    contentDiv.addEventListener('paste', (event) => {
        // Prevent the default paste behavior
        event.preventDefault();
        // Show spinner
        spinner.style.display = 'block';

        // Get the text content from the clipboard
        const text = (event.clipboardData || window.clipboardData).getData('text');
        // Send the pasted content to the server via fetch API
        fetch('/validate_json', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content: text })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.blob();
        })
        .then(blob => {
            const imageUrl = URL.createObjectURL(blob);
            outputImage.src = imageUrl;
            outputImage.onload = () => {
                URL.revokeObjectURL(imageUrl); // Clean up after loading
                spinner.style.display = 'none'; // Hide spinner
                contentDiv.textContent = '';  // Clear the instructional text
            };
        })
        .catch(error => {
            console.error('Error:', error);
            contentDiv.textContent = 'Failed to load the image';
            spinner.style.display = 'none'; // Hide spinner
        });
    });
});
