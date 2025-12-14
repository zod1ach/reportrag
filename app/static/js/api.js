/**
 * API Client for Report RAG
 */
class APIClient {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
    }

    /**
     * Generic request handler
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;

        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Request failed' }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            // Handle different content types
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            return await response.text();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // ==================== Document Endpoints ====================

    /**
     * Upload a document (text content)
     */
    async uploadDocument(data) {
        return this.request('/documents/upsert', {
            method: 'POST',
            body: JSON.stringify({
                title: data.title,
                author: data.author || '',
                year: data.year ? parseInt(data.year) : null,
                content: data.content,
                embeddings: data.embeddings || null,
            }),
        });
    }

    /**
     * Upload a document file (PDF or text file)
     */
    async uploadDocumentFile(file, title, author, year) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        if (author) formData.append('author', author);
        if (year) formData.append('year', year);

        const url = `${this.baseURL}/documents/upload`;

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                // Don't set Content-Type header - let browser set it with boundary
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('File upload error:', error);
            throw error;
        }
    }

    /**
     * Upload multiple document files at once
     */
    async uploadDocumentsBatch(files) {
        const formData = new FormData();

        // Append all files with the same field name 'files'
        for (const file of files) {
            formData.append('files', file);
        }

        const url = `${this.baseURL}/documents/upload-batch`;

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                // Don't set Content-Type header - let browser set it with boundary
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Batch upload failed' }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Batch upload error:', error);
            throw error;
        }
    }

    /**
     * List all documents
     */
    async listDocuments() {
        return this.request('/documents/list');
    }

    /**
     * Delete a document
     */
    async deleteDocument(docId) {
        return this.request(`/documents/${docId}`, {
            method: 'DELETE',
        });
    }

    // ==================== Run Endpoints ====================

    /**
     * Create a new run
     */
    async createRun(topic, modelConfig = null) {
        return this.request('/runs', {
            method: 'POST',
            body: JSON.stringify({
                topic,
                model_config: modelConfig,
            }),
        });
    }

    /**
     * List all runs
     */
    async listRuns() {
        return this.request('/runs/list');
    }

    /**
     * Start a run
     */
    async startRun(runId) {
        return this.request(`/runs/${runId}/start`, {
            method: 'POST',
        });
    }

    /**
     * Get run status
     */
    async getRunStatus(runId) {
        return this.request(`/runs/${runId}`);
    }

    /**
     * Get run artifacts
     */
    async getRunArtifacts(runId) {
        return this.request(`/runs/${runId}/artifacts`);
    }

    /**
     * Get final LaTeX
     */
    async getRunLatex(runId) {
        return this.request(`/runs/${runId}/latex`);
    }

    /**
     * Delete a run
     */
    async deleteRun(runId) {
        return this.request(`/runs/${runId}`, {
            method: 'DELETE',
        });
    }

    // ==================== Health Check ====================

    /**
     * Health check
     */
    async healthCheck() {
        return this.request('/health');
    }
}

// Export as global
window.api = new APIClient();
