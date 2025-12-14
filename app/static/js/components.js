/**
 * UI Components for Report RAG
 */

/**
 * Create a document card
 */
function createDocumentCard(doc) {
    const card = document.createElement('div');
    card.className = 'item-card';
    card.innerHTML = `
        <div class="item-header">
            <div>
                <div class="item-title">${escapeHtml(doc.title)}</div>
                <div class="item-meta">
                    ${doc.author ? `By ${escapeHtml(doc.author)}` : 'Unknown Author'}
                    ${doc.year ? ` • ${doc.year}` : ''}
                    ${doc.created_at ? ` • Added ${formatDate(doc.created_at)}` : ''}
                </div>
            </div>
            <div class="item-actions">
                <button class="btn btn-danger btn-delete" data-doc-id="${doc.doc_id}">Delete</button>
            </div>
        </div>
    `;
    return card;
}

/**
 * Create a run card
 */
function createRunCard(run) {
    const card = document.createElement('div');
    card.className = 'item-card';
    card.style.cursor = 'pointer';
    card.innerHTML = `
        <div class="item-header">
            <div>
                <div class="item-title">${escapeHtml(run.topic)}</div>
                <div class="item-meta">
                    <span class="status-badge status-${run.status}">${run.status}</span>
                    ${run.created_at ? ` • Created ${formatDate(run.created_at)}` : ''}
                </div>
            </div>
            <div class="item-actions">
                <button class="btn btn-primary btn-view" data-run-id="${run.run_id}" onclick="event.stopPropagation()">View</button>
                <button class="btn btn-danger btn-delete-run" data-run-id="${run.run_id}" onclick="event.stopPropagation()">Delete</button>
            </div>
        </div>
    `;

    // Make entire card clickable
    card.addEventListener('click', () => {
        window.app.viewRunDetail(run.run_id);
    });

    return card;
}

/**
 * Create progress stepper for agent workflow
 */
function createProgressStepper(status) {
    const steps = [
        { name: 'Outline', icon: '📝' },
        { name: 'Retrieval', icon: '🔍' },
        { name: 'Evidence', icon: '📋' },
        { name: 'Claims', icon: '✓' },
        { name: 'Draft', icon: '📄' },
        { name: 'Assembly', icon: '🔧' },
    ];

    const stepper = document.createElement('div');
    stepper.className = 'progress-stepper';

    // Determine step states based on job counts
    const jobCounts = status.job_counts || {};
    const totalDone = jobCounts.done || 0;

    steps.forEach((step, index) => {
        const stepDiv = document.createElement('div');
        stepDiv.className = 'step';

        // Simple heuristic: each agent roughly corresponds to a step
        // This is a simplification - real implementation would track specific jobs
        const stepProgress = totalDone > index * 2 ? 'done' : totalDone === index * 2 ? 'running' : 'pending';

        stepDiv.classList.add(stepProgress);
        stepDiv.innerHTML = `
            <div class="step-icon">${step.icon}</div>
            <div class="step-label">${step.name}</div>
        `;

        stepper.appendChild(stepDiv);
    });

    return stepper;
}

/**
 * Create job counts display
 */
function createJobCounts(jobCounts) {
    const container = document.createElement('div');
    container.className = 'job-counts';

    const counts = [
        { label: 'Queued', value: jobCounts.queued || 0, color: 'var(--secondary-color)' },
        { label: 'Running', value: jobCounts.running || 0, color: 'var(--warning-color)' },
        { label: 'Completed', value: jobCounts.done || 0, color: 'var(--success-color)' },
        { label: 'Failed', value: jobCounts.failed || 0, color: 'var(--danger-color)' },
    ];

    counts.forEach(item => {
        const div = document.createElement('div');
        div.className = 'job-count-item';
        div.innerHTML = `
            <div class="job-count-number" style="color: ${item.color}">${item.value}</div>
            <div class="job-count-label">${item.label}</div>
        `;
        container.appendChild(div);
    });

    return container;
}

/**
 * Show a toast notification
 */
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            container.removeChild(toast);
        }, 300);
    }, duration);
}

/**
 * Show a modal
 */
function showModal(title, content) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');

    modalTitle.textContent = title;

    if (typeof content === 'string') {
        modalBody.innerHTML = content;
    } else {
        modalBody.innerHTML = '';
        modalBody.appendChild(content);
    }

    modal.classList.add('active');
}

/**
 * Hide modal
 */
function hideModal() {
    const modal = document.getElementById('modal');
    modal.classList.remove('active');
}

/**
 * Show new run modal
 */
function showNewRunModal() {
    const form = document.createElement('form');
    form.innerHTML = `
        <div class="form-group">
            <label for="run-topic">Report Topic *</label>
            <input type="text" id="run-topic" required placeholder="e.g., Survey of Deep Learning Techniques">
        </div>
        <div class="form-group">
            <button type="submit" class="btn btn-primary">Create Run</button>
        </div>
    `;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const topic = document.getElementById('run-topic').value.trim();

        if (!topic) {
            showToast('Please enter a topic', 'error');
            return;
        }

        try {
            const result = await window.api.createRun(topic);
            showToast('Run created successfully', 'success');
            hideModal();

            // Start the run immediately
            await window.api.startRun(result.run_id);
            showToast('Run started', 'success');

            // Refresh runs list
            if (window.app && window.app.loadRuns) {
                window.app.loadRuns();
            }
        } catch (error) {
            showToast(`Failed to create run: ${error.message}`, 'error');
        }
    });

    showModal('Create New Run', form);
}

/**
 * Utility: Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Utility: Format date
 */
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

/**
 * Utility: Download text as file
 */
function downloadTextFile(content, filename) {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Add CSS for slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
