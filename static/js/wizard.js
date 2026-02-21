/**
 * XPACK Wizard System
 * One-field-at-a-time wizard for intuitive data entry
 */

class XpackWizard {
    constructor(wizardId, options = {}) {
        this.container = document.getElementById(wizardId);
        if (!this.container) return;
        
        this.overlay = this.container.closest('.wizard-overlay');
        this.steps = Array.from(this.container.querySelectorAll('.wizard-step'));
        this.progressSteps = Array.from(this.container.querySelectorAll('.wizard-progress-step'));
        this.counterEl = this.container.querySelector('.wizard-step-counter');
        this.btnBack = this.container.querySelector('.wizard-btn-back');
        this.btnNext = this.container.querySelector('.wizard-btn-next');
        this.btnSubmit = this.container.querySelector('.wizard-btn-submit');
        this.form = this.container.querySelector('form') || this.container.closest('form');
        
        this.currentStep = 0;
        this.totalSteps = this.steps.length;
        this.onStepChange = options.onStepChange || null;
        this.onBeforeNext = options.onBeforeNext || null;
        this.onSubmit = options.onSubmit || null;
        this.data = {};
        
        this._bindEvents();
        this._updateView();
    }
    
    _bindEvents() {
        if (this.btnBack) {
            this.btnBack.addEventListener('click', () => this.prev());
        }
        if (this.btnNext) {
            this.btnNext.addEventListener('click', () => this.next());
        }
        if (this.btnSubmit) {
            this.btnSubmit.addEventListener('click', (e) => {
                if (this.onSubmit) {
                    this.onSubmit(e, this.data);
                } else if (this.form) {
                    this.form.submit();
                }
            });
        }
        
        // Close button
        const closeBtn = this.container.querySelector('.wizard-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }
        
        // Close on overlay click
        if (this.overlay) {
            this.overlay.addEventListener('click', (e) => {
                if (e.target === this.overlay) this.close();
            });
        }
        
        // ESC to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay && this.overlay.classList.contains('active')) {
                this.close();
            }
        });
        
        // Enter to go next
        this.container.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                if (this.currentStep < this.totalSteps - 1) {
                    this.next();
                }
            }
        });
        
        // Auto-validate inputs
        this.container.addEventListener('input', () => {
            this._updateNextButton();
        });
        this.container.addEventListener('change', () => {
            this._updateNextButton();
        });
    }
    
    next() {
        if (this.currentStep >= this.totalSteps - 1) return;
        
        // Validate current step
        if (!this._validateStep(this.currentStep)) return;
        
        // Callback before next
        if (this.onBeforeNext) {
            const result = this.onBeforeNext(this.currentStep, this.data);
            if (result === false) return;
        }
        
        // Collect data from current step
        this._collectStepData(this.currentStep);
        
        this.currentStep++;
        this._updateView();
        
        if (this.onStepChange) {
            this.onStepChange(this.currentStep, this.data);
        }
    }
    
    prev() {
        if (this.currentStep <= 0) return;
        this.currentStep--;
        this._updateView();
        
        if (this.onStepChange) {
            this.onStepChange(this.currentStep, this.data);
        }
    }
    
    goTo(step) {
        if (step < 0 || step >= this.totalSteps) return;
        this.currentStep = step;
        this._updateView();
    }
    
    open() {
        if (this.overlay) {
            this.overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
        this.reset();
        
        // Focus first input
        setTimeout(() => {
            const firstInput = this.steps[0]?.querySelector('input, select, textarea');
            if (firstInput) firstInput.focus();
        }, 300);
    }
    
    close() {
        if (this.overlay) {
            this.overlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    }
    
    reset() {
        this.currentStep = 0;
        this.data = {};
        this._updateView();
    }
    
    setData(key, value) {
        this.data[key] = value;
    }
    
    getData(key) {
        return this.data[key];
    }
    
    _validateStep(stepIndex) {
        const step = this.steps[stepIndex];
        if (!step) return true;
        
        const inputs = step.querySelectorAll('[required]');
        let valid = true;
        
        inputs.forEach(input => {
            if (!input.value || input.value.trim() === '') {
                input.classList.add('is-invalid');
                valid = false;
                
                // Shake animation
                input.style.animation = 'none';
                setTimeout(() => input.style.animation = 'shake 0.4s ease', 10);
            } else {
                input.classList.remove('is-invalid');
            }
        });
        
        // Check wizard-options (if any option needs selection)
        const optionsContainer = step.querySelector('.wizard-options[data-required]');
        if (optionsContainer) {
            const selected = optionsContainer.querySelector('.wizard-option.selected');
            if (!selected) {
                valid = false;
                optionsContainer.style.animation = 'none';
                setTimeout(() => optionsContainer.style.animation = 'shake 0.4s ease', 10);
            }
        }
        
        return valid;
    }
    
    _collectStepData(stepIndex) {
        const step = this.steps[stepIndex];
        if (!step) return;
        
        // Collect from inputs
        const inputs = step.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            if (input.name) {
                if (input.type === 'checkbox') {
                    this.data[input.name] = input.checked;
                } else {
                    this.data[input.name] = input.value;
                }
            }
        });
        
        // Collect from selected options
        const selectedOption = step.querySelector('.wizard-option.selected');
        if (selectedOption) {
            const key = selectedOption.closest('.wizard-options')?.dataset.name;
            if (key) {
                this.data[key] = selectedOption.dataset.value;
                this.data[key + '_label'] = selectedOption.querySelector('.wizard-option-title')?.textContent;
            }
        }
    }
    
    _updateView() {
        // Show/hide steps
        this.steps.forEach((step, i) => {
            step.classList.toggle('active', i === this.currentStep);
        });
        
        // Update progress
        this.progressSteps.forEach((dot, i) => {
            dot.classList.remove('completed', 'active');
            if (i < this.currentStep) dot.classList.add('completed');
            else if (i === this.currentStep) dot.classList.add('active');
        });
        
        // Update counter
        if (this.counterEl) {
            this.counterEl.textContent = `Paso ${this.currentStep + 1} de ${this.totalSteps}`;
        }
        
        // Show/hide buttons
        const isFirst = this.currentStep === 0;
        const isLast = this.currentStep === this.totalSteps - 1;
        
        if (this.btnBack) {
            this.btnBack.style.display = isFirst ? 'none' : 'flex';
        }
        if (this.btnNext) {
            this.btnNext.style.display = isLast ? 'none' : 'flex';
        }
        if (this.btnSubmit) {
            this.btnSubmit.style.display = isLast ? 'flex' : 'none';
        }
        
        // Update next button state
        this._updateNextButton();
        
        // Focus first input of current step
        setTimeout(() => {
            const input = this.steps[this.currentStep]?.querySelector('input:not([type=hidden]), select, textarea');
            if (input) input.focus();
        }, 300);
    }
    
    _updateNextButton() {
        if (!this.btnNext) return;
        
        const step = this.steps[this.currentStep];
        if (!step) return;
        
        const inputs = step.querySelectorAll('[required]');
        let allFilled = true;
        
        inputs.forEach(input => {
            if (!input.value || input.value.trim() === '') {
                allFilled = false;
            }
        });
        
        // Check wizard-options
        const optionsContainer = step.querySelector('.wizard-options[data-required]');
        if (optionsContainer) {
            const selected = optionsContainer.querySelector('.wizard-option.selected');
            if (!selected) allFilled = false;
        }
        
        this.btnNext.disabled = !allFilled;
    }
}

/* Shake animation for validation */
const shakeStyle = document.createElement('style');
shakeStyle.textContent = `
@keyframes shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-8px); }
    75% { transform: translateX(8px); }
}
.is-invalid {
    border-color: var(--danger) !important;
    box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1) !important;
}
`;
document.head.appendChild(shakeStyle);


/**
 * Helper: Setup wizard option selection
 */
function setupWizardOptions(containerSelector) {
    document.querySelectorAll(containerSelector + ' .wizard-option').forEach(option => {
        option.addEventListener('click', function() {
            // Single select: deselect all others
            const container = this.closest('.wizard-options');
            container.querySelectorAll('.wizard-option').forEach(o => o.classList.remove('selected'));
            this.classList.add('selected');
            
            // Update hidden input if present
            const name = container.dataset.name;
            if (name) {
                let hiddenInput = container.querySelector(`input[name="${name}"]`);
                if (!hiddenInput) {
                    hiddenInput = document.createElement('input');
                    hiddenInput.type = 'hidden';
                    hiddenInput.name = name;
                    container.appendChild(hiddenInput);
                }
                hiddenInput.value = this.dataset.value;
            }
            
            // Trigger change event for wizard validation
            container.dispatchEvent(new Event('change', { bubbles: true }));
        });
    });
}

/**
 * Helper: Search/filter wizard options
 */
function setupWizardSearch(searchInputSelector, optionsSelector) {
    const searchInput = document.querySelector(searchInputSelector);
    if (!searchInput) return;
    
    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase();
        document.querySelectorAll(optionsSelector + ' .wizard-option').forEach(option => {
            const text = option.textContent.toLowerCase();
            option.style.display = text.includes(query) ? 'flex' : 'none';
        });
    });
}

/**
 * Sidebar functionality
 */
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const backdrop = document.querySelector('.sidebar-backdrop');
    
    sidebar.classList.toggle('open');
    backdrop.classList.toggle('active');

    // Prevent body scroll when sidebar is open
    if (sidebar.classList.contains('open')) {
        document.body.style.overflow = 'hidden';
    } else {
        document.body.style.overflow = '';
    }
}

function closeSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const backdrop = document.querySelector('.sidebar-backdrop');
    
    sidebar.classList.remove('open');
    backdrop.classList.remove('active');
    document.body.style.overflow = '';
}

function toggleSubmenu(element) {
    const submenu = element.nextElementSibling;
    const isExpanded = element.classList.contains('expanded');
    
    if (isExpanded) {
        element.classList.remove('expanded');
        submenu.classList.remove('show');
    } else {
        element.classList.add('expanded');
        submenu.classList.add('show');
    }
}

/**
 * Format currency
 */
function formatCurrency(amount) {
    return 'RD$ ' + parseFloat(amount).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

/**
 * Quick toast notification
 */
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed`;
    toast.style.cssText = 'top: 1rem; right: 1rem; z-index: 9999; min-width: 280px; animation: slideUp 0.3s ease;';
    toast.innerHTML = `${message} <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

/**
 * Confirm dialog
 */
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

/**
 * Initialize on DOM ready
 */
document.addEventListener('DOMContentLoaded', function() {
    // Keep active submenus open
    document.querySelectorAll('.submenu-item.active').forEach(item => {
        const submenu = item.closest('.submenu');
        if (submenu) {
            submenu.classList.add('show');
            const parent = submenu.previousElementSibling;
            if (parent?.classList.contains('has-submenu')) {
                parent.classList.add('expanded');
            }
        }
    });
    
    // Init flatpickr on date inputs
    if (typeof flatpickr !== 'undefined') {
        document.querySelectorAll('input[type="date"]').forEach(input => {
            flatpickr(input, {
                locale: 'es',
                dateFormat: 'Y-m-d',
                altInput: true,
                altFormat: 'd/m/Y',
                allowInput: true
            });
        });
    }
    
    // Mobile sidebar toggle
    const backdrop = document.querySelector('.sidebar-backdrop');
    if (backdrop) {
        backdrop.addEventListener('click', closeSidebar);
    }

    // Close sidebar when a nav link is clicked (mobile)
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebar.querySelectorAll('.nav-link:not(.has-submenu)').forEach(link => {
            link.addEventListener('click', function() {
                if (window.innerWidth <= 992) {
                    closeSidebar();
                }
            });
        });

        // Swipe-to-close sidebar
        let touchStartX = 0;
        let touchCurrentX = 0;
        let isSwiping = false;

        sidebar.addEventListener('touchstart', function(e) {
            touchStartX = e.touches[0].clientX;
            isSwiping = true;
        }, { passive: true });

        sidebar.addEventListener('touchmove', function(e) {
            if (!isSwiping) return;
            touchCurrentX = e.touches[0].clientX;
            const diff = touchStartX - touchCurrentX;
            // Only track leftward swipes
            if (diff > 0) {
                const translate = Math.min(diff, 260);
                sidebar.style.transition = 'none';
                sidebar.style.transform = `translateX(-${translate}px)`;
            }
        }, { passive: true });

        sidebar.addEventListener('touchend', function() {
            if (!isSwiping) return;
            isSwiping = false;
            sidebar.style.transition = '';
            const diff = touchStartX - touchCurrentX;
            if (diff > 80) {
                closeSidebar();
            } else {
                sidebar.style.transform = '';
                if (sidebar.classList.contains('open')) {
                    sidebar.style.transform = 'translateX(0)';
                }
            }
        }, { passive: true });
    }
});
