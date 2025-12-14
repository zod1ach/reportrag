/**
 * Main Application Logic for Report RAG
 */

class App {
    constructor() {
        this.currentTab = 'documents';
        this.currentRunId = null;
        this.pollingInterval = null;
        this.selectedFile = null;
        this.init();
    }

    /**
     * Initialize application
     */
    init() {
        this.setupEventListeners();
        this.loadDocuments();
        this.loadRuns();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });

        // Document form
        const docForm = document.getElementById('document-form');
        docForm.addEventListener('submit', (e) => this.handleDocumentSubmit(e));

        // File input and drop zone
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');

        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            const file = e.dataTransfer.files[0];
            if (file) this.handleFileUpload(file);
        });

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) this.handleFileUpload(file);
        });

        // New run button
        document.getElementById('new-run-btn').addEventListener('click', () => {
            showNewRunModal();
        });

        // Back to list button
        document.getElementById('back-to-list-btn').addEventListener('click', () => {
            this.hideRunDetail();
        });

        // Download LaTeX button
        document.getElementById('download-latex-btn').addEventListener('click', () => {
            this.downloadLatex();
        });

        // Modal close
        document.querySelector('.modal-close').addEventListener('click', () => {
            hideModal();
        });

        // Close modal on outside click
        document.getElementById('modal').addEventListener('click', (e) => {
            if (e.target.id === 'modal') {
                hideModal();
            }
        });
    }

    /**
     * Switch tab
     */
    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}-tab`);
        });

        this.currentTab = tabName;

        // Load data if needed
        if (tabName === 'documents') {
            this.loadDocuments();
        } else if (tabName === 'runs') {
            this.loadRuns();
        }
    }

    /**
     * Handle file upload
     */
    async handleFileUpload(file) {
        try {
            // Store the file for later upload
            this.selectedFile = file;

            // Extract title from filename
            const filename = file.name.replace(/\.[^/.]+$/, '');
            if (!document.getElementById('title').value) {
                document.getElementById('title').value = filename;
            }

            // For text files, show preview in content area
            if (file.name.toLowerCase().endsWith('.txt') || file.name.toLowerCase().endsWith('.md')) {
                const content = await file.text();
                document.getElementById('content').value = content;
            } else if (file.name.toLowerCase().endsWith('.pdf')) {
                // For PDFs, just show a message
                document.getElementById('content').value = `[PDF file selected: ${file.name}]\n\nText will be extracted automatically during upload.`;
            }

            showToast(`File selected: ${file.name}`, 'success');
        } catch (error) {
            showToast(`Failed to read file: ${error.message}`, 'error');
        }
    }

    /**
     * Handle document form submission
     */
    async handleDocumentSubmit(e) {
        e.preventDefault();

        const title = document.getElementById('title').value.trim();
        const author = document.getElementById('author').value.trim();
        const year = document.getElementById('year').value;
        const content = document.getElementById('content').value.trim();

        if (!title) {
            showToast('Title is required', 'error');
            return;
        }

        try {
            let result;

            // If a file is selected, use file upload
            if (this.selectedFile) {
                result = await window.api.uploadDocumentFile(
                    this.selectedFile,
                    title,
                    author,
                    year
                );
                showToast(`Document uploaded successfully (${result.chunk_count} chunks)`, 'success');
            } else {
                // Otherwise, use text content upload
                if (!content) {
                    showToast('Content is required when not uploading a file', 'error');
                    return;
                }

                const data = {
                    title: title,
                    author: author,
                    year: year,
                    content: content,
                };

                result = await window.api.uploadDocument(data);
                showToast(`Document uploaded successfully (${result.chunk_count} chunks)`, 'success');
            }

            // Reset form and selected file
            document.getElementById('document-form').reset();
            this.selectedFile = null;

            // Reload documents list
            this.loadDocuments();
        } catch (error) {
            showToast(`Failed to upload document: ${error.message}`, 'error');
        }
    }

    /**
     * Load documents
     */
    async loadDocuments() {
        const container = document.getElementById('documents-list');

        try {
            const documents = await window.api.listDocuments();

            if (documents.length === 0) {
                container.innerHTML = '<p class="loading">No documents uploaded yet</p>';
                return;
            }

            container.innerHTML = '';
            documents.forEach(doc => {
                const card = createDocumentCard(doc);

                // Add delete handler
                card.querySelector('.btn-delete').addEventListener('click', async () => {
                    if (confirm(`Delete "${doc.title}"?`)) {
                        try {
                            await window.api.deleteDocument(doc.doc_id);
                            showToast('Document deleted', 'success');
                            this.loadDocuments();
                        } catch (error) {
                            showToast(`Failed to delete: ${error.message}`, 'error');
                        }
                    }
                });

                container.appendChild(card);
            });
        } catch (error) {
            container.innerHTML = `<p class="loading" style="color: var(--danger-color)">Failed to load documents: ${error.message}</p>`;
        }
    }

    /**
     * Load runs
     */
    async loadRuns() {
        const container = document.getElementById('runs-list');

        try {
            const runs = await window.api.listRuns();

            if (runs.length === 0) {
                container.innerHTML = '<p class="loading">No runs created yet</p>';
                return;
            }

            container.innerHTML = '';
            runs.forEach(run => {
                const card = createRunCard(run);

                // Add delete handler
                card.querySelector('.btn-delete-run').addEventListener('click', async () => {
                    if (confirm(`Delete run for "${run.topic}"?`)) {
                        try {
                            await window.api.deleteRun(run.run_id);
                            showToast('Run deleted', 'success');
                            this.loadRuns();
                        } catch (error) {
                            showToast(`Failed to delete: ${error.message}`, 'error');
                        }
                    }
                });

                // Add view handler
                card.querySelector('.btn-view').addEventListener('click', () => {
                    this.viewRunDetail(run.run_id);
                });

                container.appendChild(card);
            });
        } catch (error) {
            container.innerHTML = `<p class="loading" style="color: var(--danger-color)">Failed to load runs: ${error.message}</p>`;
        }
    }

    /**
     * View run detail
     */
    async viewRunDetail(runId) {
        this.currentRunId = runId;

        // Hide runs list, show run detail
        document.getElementById('runs-list').style.display = 'none';
        document.querySelector('#runs-tab .section-header').style.display = 'none';
        document.getElementById('run-detail').style.display = 'block';

        // Start polling
        this.startPolling();

        // Initial load
        await this.updateRunDetail();
    }

    /**
     * Hide run detail
     */
    hideRunDetail() {
        this.stopPolling();

        document.getElementById('runs-list').style.display = 'block';
        document.querySelector('#runs-tab .section-header').style.display = 'flex';
        document.getElementById('run-detail').style.display = 'none';

        this.currentRunId = null;
    }

    /**
     * Update run detail
     */
    async updateRunDetail() {
        if (!this.currentRunId) return;

        try {
            const status = await window.api.getRunStatus(this.currentRunId);

            // Update title
            document.getElementById('run-detail-title').textContent = status.topic;

            // Update progress stepper
            const stepper = createProgressStepper(status);
            document.getElementById('progress-stepper').innerHTML = '';
            document.getElementById('progress-stepper').appendChild(stepper);

            // Update progress bar
            const progressBar = document.getElementById('progress-bar');
            const progressText = document.getElementById('progress-text');
            progressBar.style.width = `${status.progress_percent}%`;
            progressText.textContent = `${Math.round(status.progress_percent)}%`;

            // Update job counts
            const jobCounts = createJobCounts(status.job_counts);
            document.getElementById('job-counts').innerHTML = '';
            document.getElementById('job-counts').appendChild(jobCounts);

            // If completed, load LaTeX
            if (status.status === 'completed') {
                this.stopPolling();
                await this.loadLatex();
            }

            // Load artifacts
            await this.loadArtifacts();

        } catch (error) {
            showToast(`Failed to load run status: ${error.message}`, 'error');
            this.stopPolling();
        }
    }

    /**
     * Load artifacts
     */
    async loadArtifacts() {
        if (!this.currentRunId) return;

        try {
            const artifacts = await window.api.getRunArtifacts(this.currentRunId);

            const section = document.getElementById('artifacts-section');
            const content = document.getElementById('artifacts-content');

            if (artifacts.outline_nodes && artifacts.outline_nodes.length > 0) {
                section.style.display = 'block';

                let html = '<div style="margin-bottom: 1rem;">';
                html += '<h4>Outline</h4><ul style="margin-left: 1.5rem;">';
                artifacts.outline_nodes.forEach(node => {
                    html += `<li>${escapeHtml(node.title)} <span class="status-badge status-${node.status}">${node.status}</span></li>`;
                });
                html += '</ul></div>';

                html += '<div style="margin-bottom: 1rem;">';
                html += '<h4>Evidence Summary</h4><ul style="margin-left: 1.5rem;">';
                for (const [nodeId, count] of Object.entries(artifacts.evidence_summary || {})) {
                    html += `<li>${nodeId}: ${count} items</li>`;
                }
                html += '</ul></div>';

                html += '<div>';
                html += '<h4>Claims Summary</h4><ul style="margin-left: 1.5rem;">';
                for (const [nodeId, count] of Object.entries(artifacts.claims_summary || {})) {
                    html += `<li>${nodeId}: ${count} claims</li>`;
                }
                html += '</ul></div>';

                content.innerHTML = html;
            }
        } catch (error) {
            console.error('Failed to load artifacts:', error);
        }
    }

    /**
     * Load LaTeX
     */
    async loadLatex() {
        if (!this.currentRunId) return;

        try {
            const result = await window.api.getRunLatex(this.currentRunId);

            const section = document.getElementById('latex-section');
            const preview = document.getElementById('latex-preview');

            section.style.display = 'block';
            preview.textContent = result.latex;

            this.latexContent = result.latex;
        } catch (error) {
            console.error('Failed to load LaTeX:', error);
        }
    }

    /**
     * Download LaTeX
     */
    downloadLatex() {
        if (!this.latexContent) {
            showToast('No LaTeX available', 'error');
            return;
        }

        const filename = `report_${this.currentRunId}.tex`;
        downloadTextFile(this.latexContent, filename);
        showToast('LaTeX downloaded', 'success');
    }

    /**
     * Start polling for run updates
     */
    startPolling() {
        this.stopPolling();
        this.pollingInterval = setInterval(() => {
            this.updateRunDetail();
        }, 3000);
    }

    /**
     * Stop polling
     */
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
