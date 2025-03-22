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
            this.restructureDOM();
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
