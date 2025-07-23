// Custom JavaScript for the Cupertino Meeting Scraper

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const alertInstance = new bootstrap.Alert(alert);
            alertInstance.close();
        }, 5000);
    });

    // Form validation enhancement
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                
                // Focus on first invalid field
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                }
            }
            form.classList.add('was-validated');
        });
    });

    // File size formatter utility
    window.formatFileSize = function(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    // Copy to clipboard utility
    window.copyToClipboard = function(text) {
        navigator.clipboard.writeText(text).then(function() {
            // Show success feedback
            const toast = document.createElement('div');
            toast.className = 'toast align-items-center text-white bg-success border-0 position-fixed top-0 end-0 m-3';
            toast.setAttribute('role', 'alert');
            toast.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body">
                        <i data-feather="check" class="me-2"></i>
                        Copied to clipboard!
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            `;
            document.body.appendChild(toast);
            
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
            
            // Re-initialize feather icons
            feather.replace();
            
            // Remove toast after it's hidden
            toast.addEventListener('hidden.bs.toast', function() {
                document.body.removeChild(toast);
            });
        });
    };

    // Dark theme toggle (if needed in future)
    window.toggleTheme = function() {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-bs-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-bs-theme', newTheme);
        localStorage.setItem('preferred-theme', newTheme);
    };

    // Load preferred theme
    const preferredTheme = localStorage.getItem('preferred-theme');
    if (preferredTheme) {
        document.documentElement.setAttribute('data-bs-theme', preferredTheme);
    }

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Loading state management
    window.showLoading = function(element, text = 'Loading...') {
        if (element) {
            element.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                ${text}
            `;
            element.disabled = true;
        }
    };

    window.hideLoading = function(element, originalText) {
        if (element) {
            element.innerHTML = originalText;
            element.disabled = false;
        }
    };

    // Progress bar utilities
    window.updateProgressBar = function(element, percentage, text) {
        if (element) {
            element.style.width = percentage + '%';
            element.setAttribute('aria-valuenow', percentage);
            if (text) {
                element.textContent = text;
            }
        }
    };

    // Error handling utilities
    window.showError = function(message, container) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger alert-dismissible fade show';
        errorDiv.innerHTML = `
            <i data-feather="alert-circle" class="me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        if (container) {
            container.insertBefore(errorDiv, container.firstChild);
        } else {
            document.querySelector('.container').insertBefore(errorDiv, document.querySelector('.container').firstChild);
        }
        
        // Re-initialize feather icons
        feather.replace();
        
        // Scroll to error
        errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };

    window.showSuccess = function(message, container) {
        const successDiv = document.createElement('div');
        successDiv.className = 'alert alert-success alert-dismissible fade show';
        successDiv.innerHTML = `
            <i data-feather="check-circle" class="me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        if (container) {
            container.insertBefore(successDiv, container.firstChild);
        } else {
            document.querySelector('.container').insertBefore(successDiv, document.querySelector('.container').firstChild);
        }
        
        // Re-initialize feather icons
        feather.replace();
        
        // Auto-dismiss after 3 seconds
        setTimeout(function() {
            const alertInstance = new bootstrap.Alert(successDiv);
            alertInstance.close();
        }, 3000);
    };
});

// Utility functions for API calls
window.apiCall = async function(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
};

// Date formatting utilities
window.formatDateTime = function(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
};

window.formatDate = function(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString();
};

// File extension utilities
window.getFileIcon = function(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'pdf': 'file-text',
        'doc': 'file-text',
        'docx': 'file-text',
        'txt': 'file-text',
        'md': 'file-text',
        'jpg': 'image',
        'jpeg': 'image',
        'png': 'image',
        'gif': 'image',
        'zip': 'archive',
        'rar': 'archive',
        '7z': 'archive',
        'mp4': 'video',
        'avi': 'video',
        'mov': 'video',
        'mp3': 'music',
        'wav': 'music',
        'ogg': 'music'
    };
    
    return iconMap[ext] || 'file';
};

// URL validation
window.isValidUrl = function(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
};

// Date validation for MM/DD/YYYY format
window.isValidDate = function(dateString) {
    const regex = /^\d{1,2}\/\d{1,2}\/\d{4}$/;
    if (!regex.test(dateString)) {
        return false;
    }
    
    const parts = dateString.split('/');
    const month = parseInt(parts[0], 10);
    const day = parseInt(parts[1], 10);
    const year = parseInt(parts[2], 10);
    
    const date = new Date(year, month - 1, day);
    return date.getFullYear() === year && 
           date.getMonth() === month - 1 && 
           date.getDate() === day;
};
