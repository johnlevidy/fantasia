document.addEventListener('DOMContentLoaded', function() {
    class SVGViewer {
        constructor() {
            this.elements = {
                body: document.body,
                contentDiv: document.querySelector('.centered-content'),
                spinner: document.getElementById('spinner'),
                tableBody: document.getElementById('notificationsBody'),
                notificationsContainer: document.getElementById('notificationsContainer'),
                svgContainer: document.getElementById('svgContainer')
            };

            this.state = {
                panZoomInstance: null,
                isProcessing: false,
                hasPastedContent: false
            };

            this.init();
        }

        init() {
            this.setupLayout();
            this.setupEventListeners();
            this.resizeHandler();
        }

        setupLayout() {
            this.applyStyles();
            this.restructureDOM();
        }

        applyStyles() {
            const style = document.createElement('style');
            style.textContent = `
                :root {
                --primary-color: #1a73e8;
                --primary-dark: #0d66d0;
                --accent-color: #42854f4;
                --background-color: #f8f9fa;
                --surface-color: #ffffff;
                --error-color: #ea4335;
                    --warning-color: #fbbc04;
                    --info-color: #4285f4;
                    --success-color: #34a853;
                    --text-primary: #202124;
                    --text-secondary: #5f6368;
                    --border-radius: 8px;
                    --shadow-sm: 0 1px 2px rgba(60 ,64, 67, .3), 0 1px 3px 1px rgba(60, 64, 67, 0.15);
                    --shadow-md: 0 1px 6px rgba(60 ,64, 67, .3), 0 1px 8px 1px rgba(60, 64, 67, 0.15);
                    --transition: all 0.2s ease;
                }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            html, body {
                height: 100%;
                width: 100%;
                overflow: hidden;
            }

            body {
                font-family: 'Roboto', Arial, sans-serif;
                background-color: var(--background-color);
                color: var(--text-primary);
                display: flex;
                flex-direction: column;
            }

            .app-container {
                display: flex;
                flex-direction: column;
                height: 100vh;
                width: 100%;
                padding: 16px;
                overflow: hidden;
            }

            .app-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0 0 16px 0;
                flex-shrink: 0;
            }

            .app-header h1 {
                font-size: 22px;
                font-weight: 500;
                color: var(--text-primary);
            }

            .app-main {
                display: flex;
                flex-direction: column;
                flex: 1;
                min-height: 0;
                position: relative;
                align-items: center;
            }

            .paste-area {
                background-color: var(--surface-color);
                border-radius: var(--border-radius);
                border: 2px dashed #dadce0
                padding: 40px 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
                cursor: pointer;
                transition: var(--transition);
                box-shadow: var(--shadow-sm);
                margin-bottom: 16px;
                height: 180px;
                width: 90%;
            }

            .paste-area:hover {
                border-color: var(--primary-color);
            }

            .paste-area svg {
                margin-bottom: 16px;
                color: var(--text-secondary);
            }

            .paste-area p {
                color: var(--text-secondary);
                font-size: 16px;
            }

            .paste-area.hidden {
                display: none;
            }

            .svg-viewer {
                background-color: var(--surface-color);
                border-radius: var(--border-radius);
                box-shadow: var(--shadow-sm);
                flex: 1;
                min-height: 0;
                width: 90%;
                position: relative;
                display: none;
                overflow: hidden;
            }

            .spinner {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 40px;
                height: 40px;
                border: 4px solid rgba(0, 0, 0, 0.1);
                border-radius: 50%;
                border-top-color: var(--primary-color);
                animation: spin 1s linear infinite;
                z-index: 100;
                display: none;
            }

            @keyframes spin {
                to { transform: translate(-50%, -50%) rotate(360deg); }
            }

            .button {
                background-color: var(--primary-color);
                color: white;
                border: none;
                border-radius: 24px;
                padding: 8px 24px;
                font-family: inherit;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: var(--transition);
                box-shadow: var(--shadow-sm);
                display: none;
            }

            .button:hover {
                background-color: var(--primary-dark);
                box-shadow: var(--shadow-md);
            }

            .button:activate {
                transform: scale(0.98);
            }

            .notifications {
                background-color: var(--surface-color);
                border-radius: var(--border-radius);
                box-shadow: var(--shadow-sm);
                padding: 16px;
                margin-top: 16px;
                height: 300px;
                width: 90%;
                overflow-y: auto;
                display: none;
                flex-shrink: 0;
            }

            .notifications-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }

            .notifications-header h2 {
                font-size: 16px;
                font-weight: 500;
                color: var(--text-primary);
            }

            .notifications-table {
                width: 100%;
                border-collapse: collapse;
            }

            .notifications-table th {
                text-align: left;
                padding: 8px 16px;
                font-weight: 500;
                color: var(--text-secondary);
                border-bottom: 1px solid #e0e0e0;
            }

            .notifications-table td {
                padding: 8px 16px;
                border-bottom: 1px solid #e0e0e0;
            }

            .notifications-table tr:last-child td {
                border-bottom: none;
            }

            .severity-cell {
                width: 100px;
                font-weight: 500;
            }

            .severity-error {color: var(--error-color); }
            .severity-warning {color: var(--warning-color); }
            .severity-info {color: var(--info-color); }
            .severity-success {color: var(--success-color); }

            /* SVG Pan Zoom Controls */
            .svg-pan-zoom-control {
                background-color: var(--surface-color);
                border-radius: 50%;
                box-shadow: var(--shadow-sm);
                opacity: 0.8;
                transition: var(--transition);
            }

            .svg-pan-zoom-control:hover {
                opacity: 1;
                box-shadow: var(--shadow-md);
            }

            .error-message {
                color: var(--error-color);
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
                padding: 20px;
            }

            .error-message svg {
                margin-bottom: 12px;
            }
          `;
            document.head.appendChild(style);
        }

        restructureDOM() {
            const appContainer = document.createElement('div');
            appContainer.className = 'app-container';

            const header = document.createElement('header');
            header.className = 'app-header'

            const title = document.createElement('h1');
            title.textContent = 'Fantasia Project Scheduling';
            header.appendChild(title);

            this.copyButton = document.createElement('button');
            this.copyButton.textContent = 'Copy Plan';
            this.copyButton.className = 'button';
            this.copyButton.id = 'copyButton';
            header.appendChild(this.copyButton);

            const main = document.createElement('main');
            main.className = 'app-main';

            const existingElements = Array.from(document.body.children);

            document.body.innerHTML = '';
            document.body.appendChild(appContainer);
            appContainer.appendChild(header);
            appContainer.appendChild(main);

            existingElements.forEach(element => {
                if (element.classList && element.classList.contains('centered-content')) {
                    const pasteArea = this.createPasteArea();
                    main.appendChild(pasteArea);
                    this.elements.contentDiv = pasteArea;
                } else if (element.id === 'svgContainer') {
                    element.className = 'svg-viewer';
                    main.appendChild(element);
                    this.elements.svgContainer = element;
                }
            });

            // Create new spinner
            const spinner = document.createElement('div');
            spinner.className = 'spinner';
            spinner.id = 'spinner';
            main.appendChild(spinner);
            this.elements.spinner = spinner;

            const notifications = document.createElement('div');
            notifications.className = 'notifications';
            notifications.id = 'notificationsContainer';

            const notificationsHeader = document.createElement('div');
            notificationsHeader.className = 'notifications-header';

            const notificationsTitle = document.createElement('h2');
            notificationsTitle.textContent = 'Notifications';
            notificationsHeader.appendChild(notificationsTitle);

            notifications.appendChild(notificationsHeader);

            const table = document.createElement('table');
            table.className = 'notifications-table';

            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');

            const severityHeader = document.createElement('th');
            severityHeader.textContent = 'Severity';

            const messageHeader = document.createElement('th');
            messageHeader.textContent = 'Message';

            headerRow.appendChild(severityHeader);
            headerRow.appendChild(messageHeader);
            thead.appendChild(headerRow);

            const tbody = document.createElement('tbody');
            tbody.id = 'notificationsBody'

            table.appendChild(thead);
            table.appendChild(tbody);
            notifications.appendChild(table)

            main.appendChild(notifications);

            this.elements.tableBody = tbody;
            this.elements.notificationsContainer = notifications;
        }

        createPasteArea() {
            const pasteArea = document.createElement('div');
            pasteArea.className = 'paste-area';
            pasteArea.innerHTML = `<p>Paste your spreadsheet content here</p>`;
            return pasteArea;
        }

        setupEventListeners() {
            window.addEventListener('resize', this.resizeHandler.bind(this));
            this.elements.contentDiv.addEventListener('paste', this.handlePaste.bind(this));
            this.copyButton.addEventListener('click', this.handleCopyClick.bind(this));
        }

        resizeHandler() {
            const svgEl = this.elements.svgContainer.querySelector('svg');
            if (svgEl) {
                const containerWidth = this.elements.svgContainer.clientWidth;
                const containerHeight = this.elements.svgContainer.clientHeight;

                svgEl.setAttribute('width', `${containerWidth}px`);
                svgEl.setAttribute('height', `${containerHeight}px`);

                if (this.state.panZoomInstance) {
                    this.state.panZoomInstance.resize();
                    this.state.panZoomInstance.fit();
                    this.state.panZoomInstance.center();
                }
            }
        }

        handleCopyClick() {
            if (this.state.isProcessing) return;

            this.state.isProcessing = true;

            fetch('/get-copy-text')
            .then(response => response.json())
            .then(data => {
                if (navigator.clipbard && navigator.clipboard.writeText) {
                    return navigator.clipboard.writeText(data.texet);
                } else {
                    const textarea = document.createElement('textarea');
                    textarea.value = data.text;
                    textarea.style.position = 'absolute';
                    textarea.style.left = '-9999px';
                    document.body.appendChild(textarea);
                    textarea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textarea);
                    return Promise.resolve();
                }
            })
            .then(() => {
                this.showButtonFeedback('Copied!');
            })
            .catch(error => {
                console.error('Copy error:', error);
                this.showButtonFeedback('Error');
            })
            .finally(() => {
                this.state.isProcessing = false;
            });
        }


        showButtonFeedback(message) {
            const originalText = this.copyButton.textContent;
            this.copyButton.textContent = message;

            setTimeout(() => {
                this.copyButton.textContent = originalText;
            }, 2000);
        }

        handlePaste(event) {
            event.preventDefault();

            if (this.state.isProcessing) return;
            this.state.isProcessing = true;

            this.elements.spinner.style.display = 'block';
            this.clearNotifications();
            const text = (event.clipboardData || window.clipboardData).getData('text');
            this.elements.contentDiv.classList.add('hidden');

            fetch('/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({content: text })
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw data;
                    });
                }
                return response.json();
            })
            .then(data => {
                this.handleSuccessResponse(data);
            })
            .catch(error => {
                this.handleErrorResponse(error);
            })
            .finally(() => {
                this.elements.spinner.style.display = 'none';
                this.state.isProcessing = false;
            });
        }

        handleSuccessResponse(data) {
            if (data.notifications && Array.isArray(data.notifications)) {
                data.notifications.forEach(notification => {
                    this.addNotification(notification);
                });
            }

            this.elements.svgContainer.innerHTML = atob(data.image);
            this.elements.svgContainer.style.display = 'block';

            const svgEl = this.elements.svgContainer.querySelector('svg');

            if (svgEl) {
                this.state.panZoomInstance = svgPanZoom(svgEl, {
                    constrolIconsEnabled: false,
                    zoomEnabled: true,
                    fit: true,
                    center: true,
                    zoomScaleSensitivity: .5,
                    minZoom: .1,
                    maxZoom: 7,
                });

                this.resizeHandler();
            }
            this.elements.notificationsContainer.style.display = 'block';
            this.copyButton.style.display = 'block';
            this.state.hasPastedContent = true;
        }

        handleErrorResponse(error) {
            this.elements.contentDiv.classList.remove('hidden');
            this.elements.contentDiv.innerHTML = `<p>Failed to load the image: ${error.message || 'Unknown error'}</p>`;

            if (error.notifications && Array.isArray(error.notifications)) {
                error.notifications.forEach(notification => {
                    this.addNotification(notification);
                });
                this.elements.notificationsContainer.style.display = 'block';
            }
            this.copyButton.style.display = 'block';
        }

        clearNotifications() {
            while (this.elements.tableBody.firstChild) {
                this.elementss.tableBody.removeChild(this.elements.tableBody.firstChild);
            }
        }

        addNotification(notification) {
            const row = this.elements.tableBody.insertRow();

            const severityCell = row.insertCell(0);
            severityCell.textContent = notification.severity;
            severityCell.className = `severity-cell severity-${notification.severity.toLowerCase()}`;

            const messageCell = row.insertCell(1);
            messageCell.textContent = notification.message;
        }
    }
    const svgViewer = new SVGViewer();
});
        
