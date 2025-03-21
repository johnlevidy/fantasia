document.addEventListener('DOMContentLoaded', function() {
    const contentDiv = document.querySelector('.centered-content');
    const outputSVG = document.getElementById('outputSVG');
    const spinner = document.getElementById('spinner');
    const tableBody = document.getElementById('notificationsBody');
    const notificationsContainer = document.getElementById('notificationsContainer');
    var panZoomInstance = svgPanZoom('#outputSVG', {
        controlIconsEnabled: false,
    });

    // I think this isn't exactly what I want, since I believe it's setting the height / width to the full container but it seems to render OK / the other styles are taking the proper priority. Maybe this can just take a delta or something.
    window.addEventListener('resize', () => {
      const containerWidth = document.getElementById('svgContainer').clientWidth;
      const containerHeight = document.getElementById('svgContainer').clientHeight;
      const svgEl = svgContainer.querySelector('svg');
      svgEl.setAttribute('width', `${containerWidth}px`);
      svgEl.setAttribute('height', `${containerHeight}px`);
    });

    contentDiv.addEventListener('paste', (event) => {
        // Prevent the default paste behavior
        event.preventDefault();
        // Show spinner
        spinner.style.display = 'block';

        // Get the text content from the clipboard
        const text = (event.clipboardData || window.clipboardData).getData('text');
        // Send the pasted content to the server via fetch API
        contentDiv.textContent = '';  // Clear the instructional text
        fetch('/process', {
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
            svgContainer.innerHTML = atob(data.image);
            svgContainer.style.display = 'block';
            svgContainer.style.border = '4px solid #000';
            const svgEl = svgContainer.querySelector('svg');
            if (svgEl) {
                const panZoomInstance = svgPanZoom(svgEl, {
                    controlIconsEnabled: false,
                    zoomEnabled: true,
                    fit: false,
                    center: true,
                    zoomScaleSensitivity: .45,
                    minZoom: .1,
                    maxZoom: 10,
                });
                const containerWidth = document.getElementById('svgContainer').clientWidth;
                const containerHeight = document.getElementById('svgContainer').clientHeight;
                svgEl.setAttribute('width', `${containerWidth}px`);
                svgEl.setAttribute('height', `${containerHeight}px`);
            }
            // svgContainer.classList.toggle('active');
            notificationsContainer.style.display = 'block';
            spinner.style.display = 'none'; // Hide spinner
        })
        .catch(errorPromise => {
            errorPromise.then(errorMessage => {
                contentDiv.textContent = 'Failed to load the image: [' + errorMessage.message + ']';
                spinner.style.display = 'none'; // Hide spinner
                errorMessage.notifications.forEach(notification => {
                    const row = tableBody.insertRow();
                    const severityCell = row.insertCell(0);
                    const messageCell = row.insertCell(1);
                    severityCell.textContent = notification.severity;
                    messageCell.textContent = notification.message;
                });
                notificationsContainer.style.display = 'block';
            });
        });
    });
});
