/**
 * AGB Communication Myanmar Employee Profile JavaScript
 * Handles all interactive functionality for the employee profile page
 */
// Global variables
let currentEditSection = null;
let originalFormData = {};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeProfile();
    setupEventListeners();
    loadRecentActivity();
});

/**
 * Initialize profile page functionality
 */
function initializeProfile() {
    console.log('AGB Employee Profile initialized');
    
    // Add loading states
    addLoadingStates();
    
    // Initialize tooltips if needed
    initializeTooltips();
    
    // Check for unsaved changes
    window.addEventListener('beforeunload', handleBeforeUnload);
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Edit button listeners
    const editButtons = document.querySelectorAll('.agb-btn-edit');
    editButtons.forEach(button => {
        button.addEventListener('click', function() {
            const section = this.getAttribute('data-section') || 
                           this.getAttribute('onclick')?.match(/editSection\('(.+?)'\)/)?.[1];
            if (section) {
                editSection(section);
            }
        });
    });
    
    // Modal close listeners
    const closeButtons = document.querySelectorAll('.agb-modal-close');
    closeButtons.forEach(button => {
        button.addEventListener('click', closeModal);
    });
    
    // Form submission listeners
    const editForm = document.getElementById('editForm');
    if (editForm) {
        editForm.addEventListener('submit', handleFormSubmit);
    }
    
    // Settings button listeners
    setupSettingsListeners();
    
    // Navigation listeners
    setupNavigationListeners();
}

/**
 * Edit a specific section of the profile
 * @param {string} section - The section to edit (personal, contact, education, etc.)
 */
function editSection(section) {
    const modal = document.getElementById('editModal');
    const modalTitle = document.getElementById('modalTitle');
    const editFields = document.getElementById('editFields');
    
    if (!modal || !modalTitle || !editFields) {
        console.error('Modal elements not found');
        return;
    }
    
    currentEditSection = section;
    
    // Clear previous fields
    editFields.innerHTML = '';
    
    // Store original form data
    storeOriginalFormData(section);
    
    // Set title and fields based on section
    switch(section) {
        case 'personal':
            setupPersonalEditForm(modalTitle, editFields);
            break;
        case 'contact':
            setupContactEditForm(modalTitle, editFields);
            break;
        case 'education':
            setupEducationEditForm(modalTitle, editFields);
            break;
        case 'work':
            setupWorkEditForm(modalTitle, editFields);
            break;
        default:
            console.error('Unknown section:', section);
            return;
    }
    
    // Show modal with animation
    showModal(modal);
}

/**
 * Setup personal information edit form
 */
function setupPersonalEditForm(modalTitle, editFields) {
    modalTitle.textContent = 'Edit Personal Information';
    editFields.innerHTML = `
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-user"></i>
                Full Name
            </label>
            <input type="text" name="name" class="agb-input" 
                   value="${getEmployeeData('name')}" required/>
        </div>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-venus-mars"></i>
                Gender
            </label>
            <select name="gender" class="agb-input">
                <option value="">Select Gender</option>
                <option value="male" ${getEmployeeData('gender') === 'male' ? 'selected' : ''}>Male</option>
                <option value="female" ${getEmployeeData('gender') === 'female' ? 'selected' : ''}>Female</option>
                <option value="other" ${getEmployeeData('gender') === 'other' ? 'selected' : ''}>Other</option>
            </select>
        </div>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-calendar"></i>
                Date of Birth
            </label>
            <input type="date" name="birthday" class="agb-input" 
                   value="${getEmployeeData('birthday')}"/>
        </div>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-id-card"></i>
                NRC Number
            </label>
            <input type="text" name="nrc_full" class="agb-input" 
                   value="${getEmployeeData('nrc_full')}" 
                   placeholder="e.g., 12/KAMANA(N)123456" disabled/>
        </div>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-flag"></i>
                Nationality
            </label>
            <input type="text" name="country_id" class="agb-input" 
                value="${getEmployeeData('country_id.name')}" placeholder="e.g., Myanmar"/>
        </div>

        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-heart"></i>
                Marital Status
            </label>
            <select name="marital" class="agb-input">
                <option value="">Select Status</option>
                <option value="single" ${getEmployeeData('marital') === 'single' ? 'selected' : ''}>Single</option>
                <option value="married" ${getEmployeeData('marital') === 'married' ? 'selected' : ''}>Married</option>
                <option value="divorced" ${getEmployeeData('marital') === 'divorced' ? 'selected' : ''}>Divorced</option>
                <option value="widowed" ${getEmployeeData('marital') === 'widowed' ? 'selected' : ''}>Widowed</option>
            </select>
        </div>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-id-badge"></i>
                SSB Registration No
            </label>
            <input type="text" name="permit_no" class="agb-input"
                value="${getEmployeeData('permit_no')}" placeholder="e.g., 123456789"/>
        </div>
    `;
}

/**
 * Setup education information edit form
 */
function setupEducationEditForm(modalTitle, editFields) {
    modalTitle.textContent = 'Edit Education & Contact Information';
    editFields.innerHTML = `
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-graduation-cap"></i>
                Highest Level of Education
            </label>
            <select name="certificate" class="agb-input">
                <option value="">Select Education Level</option>
                <option value="high_school" ${getEmployeeData('certificate') === 'high_school' ? 'selected' : ''}>High School</option>
                <option value="diploma" ${getEmployeeData('certificate') === 'diploma' ? 'selected' : ''}>Diploma</option>
                <option value="bachelor" ${getEmployeeData('certificate') === 'bachelor' ? 'selected' : ''}>Bachelor's Degree</option>
                <option value="master" ${getEmployeeData('certificate') === 'master' ? 'selected' : ''}>Master's Degree</option>
                <option value="phd" ${getEmployeeData('certificate') === 'phd' ? 'selected' : ''}>PhD</option>
            </select>
        </div>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-book"></i>
                Specialization/Field of Study
            </label>
            <input type="text" name="study_field" class="agb-input" 
                   value="${getEmployeeData('study_field')}" 
                   placeholder="e.g., Computer Science, Business Administration"/>
        </div>
        <br/>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-phone"></i>
                Personal Phone
            </label>
            <input type="tel" name="personal_phone" class="agb-input" 
                   value="${getEmployeeData('personal_phone')}" 
                   placeholder="+95-9-xxx-xxx-xxx"/>
        </div>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-envelope"></i>
                Personal Email
            </label>
            <input type="email" name="personal_email" class="agb-input" 
                   value="${getEmployeeData('personal_email')}" 
                   placeholder="your.email@gmail.com"/>
        </div>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-home"></i>
                Home Address
            </label>
            <textarea name="home_address" class="agb-input" rows="3" 
                      placeholder="Enter your complete home address">${getEmployeeData('home_address')}</textarea>
        </div>
    `;
}

/**
 * Setup work information edit form
 */
function setupWorkEditForm(modalTitle, editFields) {
    modalTitle.textContent = 'Edit Work Information';
    editFields.innerHTML = `
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-briefcase"></i>
                Job Title
            </label>
            <input type="text" name="job_title" class="agb-input" 
                   value="${getEmployeeData('job_title')}" 
                   placeholder="e.g., Senior Software Developer"/>
        </div>
        <div class="agb-form-group">
            <label class="agb-label">
                <i class="fa fa-envelope"></i>
                Work Email
            </label>
            <input type="email" name="work_email" class="agb-input" 
                   value="${getEmployeeData('work_email')}" 
                   placeholder="your.name@agb.com.mm"/>
        </div>
    `;
}

/**
 * Get employee data from the page
 */
function getEmployeeData(field) {
    const element = document.querySelector(`[data-field="${field}"]`);
    if (element) {
        const value = element.textContent.trim() || element.value || '';
        console.log(`getEmployeeData("${field}") =>`, value);
        
        // Handle "Not Set" values
        if (value === 'Not Set' || value === 'false') {
            return '';
        }
        // Handle Odoo object representations like "res.partner(41,)"
        if (value.includes('res.partner(') || value.includes('res.')) {
            return '';
        }
        return value;
    }
    console.log(`getEmployeeData("${field}") => no element found`);
    return '';
}



/**
 * Store original form data for comparison
 */
function storeOriginalFormData(section) {
    originalFormData[section] = {};
    // Store current values for comparison later
}

/**
 * Show modal with animation
 */
function showModal(modal) {
    modal.style.display = 'flex';
    modal.style.opacity = '0';
    
    // Trigger animation
    requestAnimationFrame(() => {
        modal.style.opacity = '1';
        const modalContent = modal.querySelector('.agb-modal-content');
        if (modalContent) {
            modalContent.style.transform = 'translateY(0)';
        }
    });
    
    // Focus first input
    const firstInput = modal.querySelector('input, select, textarea');
    if (firstInput) {
        setTimeout(() => firstInput.focus(), 100);
    }
    
    // Add escape key listener
    document.addEventListener('keydown', handleEscapeKey);
}

/**
 * Close modal
 */
function closeModal() {
    const modal = document.getElementById('editModal');
    if (!modal) return;
    
    // Check for unsaved changes
    if (hasUnsavedChanges()) {
        if (!confirm('You have unsaved changes. Are you sure you want to close?')) {
            return;
        }
    }
    
    // Animate out
    modal.style.opacity = '0';
    const modalContent = modal.querySelector('.agb-modal-content');
    if (modalContent) {
        modalContent.style.transform = 'translateY(-20px)';
    }
    
    setTimeout(() => {
        modal.style.display = 'none';
        currentEditSection = null;
        originalFormData = {};
    }, 300);
    
    // Remove escape key listener
    document.removeEventListener('keydown', handleEscapeKey);
}

/**
 * Handle escape key press
 */
function handleEscapeKey(event) {
    if (event.key === 'Escape') {
        closeModal();
    }
}

/**
 * Handle form submission
 */
function handleFormSubmit(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    // Convert FormData to plain object
    const data = {};
    formData.forEach((value, key) => {
        data[key] = value;
    });
    
    // Add section and employee_number
    data['section'] = currentEditSection;
    
    console.log('Sending data:', data); // Debug log
    
    showLoadingState(form);
    
    fetch('/employee/profile/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(data)
    })
    .then(response => {
        console.log('Response status:', response.status);
        return response.json();
    })
    .then(responseData => {
        hideLoadingState(form);
        console.log('Server response:', responseData);
        
        const data = responseData.result || responseData;
        
        if (data.success) {
            showNotification('Profile updated successfully!', 'success');
            if (data.updated_data) {
                updatePageData(data.updated_data);
            }
            closeModal();
        } else {
            showNotification(data.error || 'Failed to update profile', 'error');
        }
    })
    .catch(error => {
        hideLoadingState(form);
        console.error('Error updating profile:', error);
        showNotification('Network error. Please try again.', 'error');
    });
}



/**
 * Get CSRF token for secure requests
 */
function getCsrfToken() {
    const token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.getAttribute('content') : '';
}


/**
 * Check for unsaved changes
 */
function hasUnsavedChanges() {
    const form = document.getElementById('editForm');
    if (!form) return false;
    
    const formData = new FormData(form);
    // Compare with original data
    // Implementation depends on your specific needs
    return false;
}

/**
 * Show loading state on form
 */
function showLoadingState(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Saving...';
    }
}

/**
 * Hide loading state on form
 */
function hideLoadingState(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="fa fa-save"></i> Save Changes';
    }
}

/**
 * Update page data after successful save
 */
function updatePageData(updatedData) {
    console.log('Updating page data:', updatedData);
    for (const [field, value] of Object.entries(updatedData)) {
        const elements = document.querySelectorAll(`[data-field="${field}"]`);
        elements.forEach(element => {
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                element.value = value;
            } else {
                // Handle false values and object representations
                let displayValue = value;
                if (value === false || value === null || value === undefined) {
                    displayValue = 'Not Set';
                } else if (typeof value === 'string' && value.includes('res.partner(')) {
                    displayValue = 'Not Set';
                }
                element.textContent = displayValue;
            }
        });
    }
}


/**
 * Show notification message
 */
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `agb-notification agb-notification-${type}`;
    notification.innerHTML = `
        <i class="fa fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
        <button class="agb-notification-close" onclick="this.parentElement.remove()">
            <i class="fa fa-times"></i>
        </button>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
    
    // Animate in
    requestAnimationFrame(() => {
        notification.style.transform = 'translateX(0)';
        notification.style.opacity = '1';
    });
}

/**
 * Setup settings button listeners
 */
function setupSettingsListeners() {
    // Change password
    const changePasswordBtn = document.querySelector('[onclick="changePassword()"]');
    if (changePasswordBtn) {
        changePasswordBtn.addEventListener('click', function(e) {
            e.preventDefault();
            changePassword();
        });
    }
    
    // Update notifications
    const notificationsBtn = document.querySelector('[onclick="updateNotifications()"]');
    if (notificationsBtn) {
        notificationsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            updateNotifications();
        });
    }
    
    // Download profile
    const downloadBtn = document.querySelector('[onclick="downloadProfile()"]');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function(e) {
            e.preventDefault();
            downloadProfile();
        });
    }
}

/**
 * Setup navigation listeners
 */
function setupNavigationListeners() {
    const navLinks = document.querySelectorAll('.agb-nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Add loading state for navigation
            if (!this.classList.contains('active')) {
                this.innerHTML += ' <i class="fa fa-spinner fa-spin"></i>';
            }
        });
    });
}


/**
 * Change password functionality
 */
function changePassword() {
  const employeeNumberElement = document.querySelector('[data-field="employee_number"]');
  const employeeNumber = employeeNumberElement ? employeeNumberElement.textContent.trim() : null;

  if (employeeNumber) {
    window.location.href = `/employee/register?forgot=1`;
  } else {
    alert("Employee ID not found.");
  }
}






/**
 * Add loading states to elements
 */
function addLoadingStates() {
    // Add loading states to buttons and forms as needed
    console.log('Loading states initialized');
}

/**
 * Initialize tooltips
 */
function initializeTooltips() {
    // Initialize any tooltips if using a tooltip library
    console.log('Tooltips initialized');
}

/**
 * Handle before unload
 */
function handleBeforeUnload(event) {
    if (hasUnsavedChanges()) {
        event.preventDefault();
        event.returnValue = '';
        return '';
    }
}

/**
 * Close modal when clicking outside
 */
window.addEventListener('click', function(event) {
    const modal = document.getElementById('editModal');
    if (event.target === modal) {
        closeModal();
    }
});

// Export functions for global access (if needed)
window.editSection = editSection;
window.closeModal = closeModal;
window.changePassword = changePassword;
window.updateNotifications = updateNotifications;
window.downloadProfile = downloadProfile;