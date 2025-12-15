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
            const files = e.dataTransfer.files;
            if (files.length > 0) this.handleFileSelection(files);
        });

        fileInput.addEventListener('change', (e) => {
            const files = e.target.files;
            if (files.length > 0) this.handleFileSelection(files);
        });

        // Upload and clear buttons
        document.getElementById('upload-btn').addEventListener('click', () => {
            this.uploadSelectedFiles();
        });

        document.getElementById('clear-btn').addEventListener('click', () => {
            this.clearFileSelection();
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
     * Handle file selection
     */
    handleFileSelection(fileList) {
        const files = Array.from(fileList);
        this.selectedFiles = files;

        // Show preview
        const preview = document.getElementById('selected-files-preview');
        const filesList = document.getElementById('files-list');

        filesList.innerHTML = '';
        files.forEach((file, i) => {
            const fileItem = document.createElement('div');
            fileItem.style.cssText = 'padding: 8px; margin: 5px 0; background: rgba(255,255,255,0.03); border-radius: 4px; display: flex; justify-content: space-between; align-items: center;';

            const fileName = document.createElement('span');
            fileName.textContent = `${i + 1}. ${file.name}`;

            const fileSize = document.createElement('span');
            fileSize.style.opacity = '0.6';
            fileSize.style.fontSize = '0.9em';
            fileSize.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;

            fileItem.appendChild(fileName);
            fileItem.appendChild(fileSize);
            filesList.appendChild(fileItem);
        });

        preview.style.display = 'block';
        showToast(`${files.length} file(s) selected`, 'success');
    }

    /**
     * Clear file selection
     */
    clearFileSelection() {
        this.selectedFiles = null;
        document.getElementById('file-input').value = '';
        document.getElementById('selected-files-preview').style.display = 'none';
        showToast('Selection cleared', 'info');
    }

    /**
     * Upload selected files
     */
    async uploadSelectedFiles() {
        if (!this.selectedFiles || this.selectedFiles.length === 0) {
            showToast('No files selected', 'error');
            return;
        }

        try {
            const uploadBtn = document.getElementById('upload-btn');
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';

            if (this.selectedFiles.length === 1) {
                // Single file upload - metadata will be extracted automatically
                const file = this.selectedFiles[0];
                const filename = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
                const result = await window.api.uploadDocumentFile(
                    file,
                    filename,  // Use filename as placeholder, will be replaced by LLM extraction
                    '',
                    null
                );
                showToast(`Document uploaded successfully! (${result.chunk_count} chunks)`, 'success');
            } else {
                // Batch upload - metadata extracted for each file
                showToast(`Uploading ${this.selectedFiles.length} files. Extracting metadata with AI...`, 'info');
                const result = await window.api.uploadDocumentsBatch(this.selectedFiles);

                const successCount = result.successful;
                const failCount = result.failed;

                if (failCount === 0) {
                    showToast(`Success! All ${successCount} documents uploaded with metadata extracted.`, 'success');
                } else {
                    showToast(`${successCount} succeeded, ${failCount} failed. Check console for details.`, 'warning');
                    console.log('Batch upload results:', result.results);
                }
            }

            // Clear selection and reload
            this.clearFileSelection();
            this.loadDocuments();

        } catch (error) {
            showToast(`Upload failed: ${error.message}`, 'error');
        } finally {
            const uploadBtn = document.getElementById('upload-btn');
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload Documents';
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
            const detailedProgress = await window.api.getDetailedProgress(this.currentRunId);

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

            // Display detailed per-section progress
            this.displaySectionProgress(detailedProgress.nodes);

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
     * Display per-section progress
     */
    displaySectionProgress(nodes) {
        const container = document.getElementById('section-progress');
        if (!container) return;

        container.innerHTML = '<h3 style="margin-bottom: 1rem;">Section Progress</h3>';

        nodes.forEach(node => {
            const sectionDiv = document.createElement('div');
            sectionDiv.style.cssText = 'margin-bottom: 1rem; padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px; border-left: 3px solid var(--primary-color);';

            // Status badge
            const statusBadge = node.status === 'drafted' ? '✓' :
                               node.status === 'retrieved' ? '⟳' :
                               node.status === 'pending' ? '⏳' : '○';

            const statusColor = node.status === 'drafted' ? '#4ade80' :
                               node.status === 'retrieved' ? '#60a5fa' :
                               node.status === 'pending' ? '#fbbf24' : '#9ca3af';

            sectionDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 1.2em; color: ${statusColor};">${statusBadge}</span>
                        <strong>${escapeHtml(node.node_id)}: ${escapeHtml(node.title)}</strong>
                    </div>
                    <span class="status-badge status-${node.status}">${node.status}</span>
                </div>
                <div style="font-size: 0.9em; opacity: 0.8; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.5rem;">
                    <div>📄 Chunks: <strong>${node.chunks_retrieved}</strong></div>
                    <div>🔍 Evidence: <strong>${node.evidence_extracted}</strong></div>
                    <div>💡 Claims: <strong>${node.claims_generated}</strong></div>
                    <div>✍️ Draft: <strong>${node.draft_completed ? `${node.draft_length} chars` : 'Not yet'}</strong></div>
                </div>
            `;

            container.appendChild(sectionDiv);
        });
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
