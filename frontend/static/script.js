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
            return response.blob();
        })
        .then(blob => {
            console.log("Attempting to render")
            const imageUrl = URL.createObjectURL(blob);
            outputImage.src = imageUrl;
            outputImage.onload = () => {
                URL.revokeObjectURL(imageUrl); // Clean up after loading
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
