/**
 * Leave Request Form - Standalone JavaScript for Odoo Integration
 * Modified to use only session employee (no employee dropdown)
 */

class LeaveRequestForm {
    constructor() {
        const container = document.getElementById('leave-request-app');
        this.employeeNumber = container.getAttribute('data-employee-number');
        this.employeeName = container.getAttribute('data-employee-name');
        this.timeOffTypes = [];
        this.formData = {
            employee_number: this.employeeNumber,
            holiday_status_id: 0,
            request_date_from: '',
            request_date_to: '',
            name: '',
            number_of_days: 0
        };
        console.log('DEBUG: employee_number from data attribute:', this.employeeNumber);
        console.log('DEBUG: employee_name from data attribute:', this.employeeName);
        this.init();
    }

    async init() {
        if (!this.employeeNumber) {
            console.error("Missing employee number.");
            return;
        }
        await this.loadTimeOffTypes();
        await this.loadLeaveBalance();
        this.renderForm();
        this.setupEventListeners();
    }

   async loadTimeOffTypes() {
    try {
        const typesResponse = await fetch('/api/time-off-types', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const typesData = await typesResponse.json();
        // Only show leave types as returned by the backend (according to rules)
        this.timeOffTypes = typesData.result.result || [];
    } catch (error) {
        this.showNotification('Error loading leave types', 'error');
    }
}
    async loadLeaveBalance() {
        const res = await fetch('/api/leave-balance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ employee_number: this.employeeNumber })
        });

        const response = await res.json();
        const data = response.result;

        if (data && data.success) {
            const today = new Date();
            const cutoff = new Date(today.getFullYear(), 5, 30); // June 30
            const annualData = data.annual || { total_dynamic: 0, taken: 0, available: 0, pending: 0 };

            // Apply cutoff rule: after June 30, use system_taken
            const annualTaken = (today > cutoff)
                ? (annualData.system_taken ?? annualData.taken ?? 0)
                : (annualData.taken ?? 0);

            this.leaveBalance = {
                casual: data.casual || { total: 0, taken: 0, available: 0, pending: 0 },
                annual: { ...annualData, taken: annualTaken },  // <-- replaced taken with cutoff-aware value
                medical: data.medical || { total: 30, taken: 0, available: 0, pending: 0 },
                funeral: data.funeral || { total: 7, taken: 0, available: 0, pending: 0 },
                marriage: data.marriage || { total: 5, taken: 0, available: 0, pending: 0 },
                unpaid: data.unpaid || { total: 30, taken: 0, available: 0, pending: 0 },
                maternity: data.maternity || { total: 98, taken: 0, available: 0, pending: 0 },
                paternity: data.paternity || { total: 15, taken: 0, available: 0, pending: 0 }
            };

            console.log("✅ Leave balance loaded:", this.leaveBalance);
        } else {
            console.warn("⚠️ Failed to load leave balance or success=false");
        }
    }

    isCasualLeaveSelected() {
        const casualLeaveType = this.timeOffTypes.find(type => type.id === this.formData.holiday_status_id);
        if (!casualLeaveType) return false;
        return casualLeaveType.name.toLowerCase().includes('casual');
    }

   async maybeCheckOverlap() {
    this.hasBlockingError = false;  // reset on every check

    // --- Get dates early ---
    const fromDateInput = document.querySelector('[name="request_date_from"]');
    const toDateInput = document.querySelector('[name="request_date_to"]');
    const fromDate = fromDateInput?.value;
    const toDate = toDateInput?.value;

    if (!fromDate || !toDate) return;

    // --- Balance check (non-casual leave) ---
    if (this.formData.leaveTypeName !== 'casual') {
        const leaveName = this.formData.leaveTypeName;
        const balance = this.leaveBalance?.[leaveName];

        if (balance && this.formData.number_of_days > balance.available) {
            this.showNotification(
                `You cannot request more than your available ${leaveName} leave balance.`,
                'error'
            );
            this.hasBlockingError = true;
            return;
        }
    }

    // --- Duration check ---
    const start = new Date(fromDate);
    const end = new Date(toDate);
    const durationInDays = (end - start) / (1000 * 60 * 60 * 24) + 1;

    if (this.formData.leaveTypeName === 'casual' && this.formData.number_of_days > 2) {
        this.showNotification("Casual Leave cannot exceed 2 days.", 'error');
        this.hasBlockingError = true;
        console.log(`DEBUG: Casual Leave cannot exceed 2 days.`);
        return;
    }

    // --- Overlap check (only once) ---
    try {
        const response = await this.checkCasualLeaveOverlap(fromDate, toDate);
        if (!response.success) {
            this.showNotification(response.error || "Overlap check failed", 'error');
            this.hasBlockingError = true;
        } else {
            this.hasBlockingError = false; // ✅ clear only if valid
            console.log("✅ No overlapping leave found.");
        }
    } catch (err) {
        this.showNotification("Network or parsing error: " + err.message, 'error');
        this.hasBlockingError = true;
    }

}


    async checkCasualLeaveOverlap(fromDate, toDate) {
    const payload = {
        employee_number: this.employeeNumber,
        request_date_from: fromDate,
        request_date_to: toDate
    };

    const res = await fetch('/api/check/leave/valid', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    const json = await res.json();
    return json.result || { success: false, error: 'Unexpected server response' };
}

    renderForm() {
        const container = document.getElementById('leave-request-app');
        if (!container) return;
        container.innerHTML = `
            <div class="leave-request-container">
                <div class="leave-form-card">
                    <form id="leaveRequestForm" class="leave-request-form" enctype="multipart/form-data">
                        <div class="form-section">
                            <h3><i class="fa fa-user"></i> Employee Information</h3>
                                <div class="form-row">
                                    <!-- Employee Name -->
                                    <div class="form-item">
                                        <label class="form-label">
                                        <i class="fa fa-user"></i> Employee
                                        </label>
                                        <input type="hidden" name="employee_number" value="${this.employeeNumber}" />
                                        <input type="text" class="form-control" value="${this.employeeName}" readonly />
                                    </div>

                                    <!-- Employee Number -->
                                    <div class="form-item">
                                        <label class="form-label">Employee Number</label>
                                        <input type="text" class="form-control" value="${this.employeeNumber}" readonly />
                                    </div>
                                    </div>
                                </div>

                         <!-- Time Off Type Selection -->
                        <div class="form-section">
                            <h3><i class="fa fa-calendar"></i> Leave Type 
                                (All the leave types cannot be requested for past date!)
                            </h3>
                            <div class="time-off-types">
                                ${this.timeOffTypes.map(type => {
                                    const lowerName = type.name.toLowerCase();

                                    // Leave balances from API
                                    const casual = this.leaveBalance?.casual || {};
                                    const annual = this.leaveBalance?.annual || {};
                                    const medical = this.leaveBalance?.medical || {};
                                    const funeral = this.leaveBalance?.funeral || {};
                                    const marriage = this.leaveBalance?.marriage || {};
                                    const unpaid = this.leaveBalance?.unpaid || {};
                                    const maternity = this.leaveBalance?.maternity || {};
                                    const paternity = this.leaveBalance?.paternity || {};

                                    // Generate leave balance HTML if type matches
                                    let extraInfo = '';

                                    if (lowerName.includes('casual')) {
                                        extraInfo = `
                                            <div class="leave-balance-info">
                                                <div style="display: grid; grid-template-columns: repeat(4, 1fr);  gap: 12px; text-align: center; color:#D32F2F">
                                                    <div>Total</div>
                                                    <div>Taken</div>
                                                    <div>Balance</div>
                                                    <div>Pending</div>
                                                    <div><strong>${casual.total ?? 0}</strong></div>
                                                    <div><strong>${casual.taken ?? 0}</strong></div>
                                                    <div><strong>${casual.available ?? 0}</strong></div>
                                                    <div><strong>${casual.pending ?? 0}</strong></div>
                                                </div>
                                            </div>
                                        `;
                                    } else if (lowerName.includes('annual')) {
                                        extraInfo = `
                                            <div class="leave-balance-info">
                                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; text-align: center; color:#D32F2F">
                                                    <div>Total</div>
                                                    <div>Taken</div>
                                                    <div>Balance</div>
                                                    <div>Pending</div>
                                                    <div><strong>${annual.total_dynamic ?? 0}</strong></div>
                                                    <div><strong>${annual.taken ?? 0}</strong></div>
                                                    <div><strong>${annual.available ?? 0}</strong></div>
                                                    <div><strong>${annual.pending ?? 0}</strong></div>
                                                </div>
                                            </div>
                                        `;
                                    } else if (lowerName.includes('medical')) {
                                        extraInfo = `
                                            <div class="leave-balance-info">
                                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; text-align: center; color:#D32F2F">
                                                    <div>Total</div>
                                                    <div>Taken</div>
                                                    <div>Balance</div>
                                                    <div>Pending</div>
                                                    <div><strong>${medical.total ?? 0}</strong></div>
                                                    <div><strong>${medical.taken ?? 0}</strong></div>
                                                    <div><strong>${medical.available ?? 0}</strong></div>
                                                    <div><strong>${medical.pending ?? 0}</strong></div>
                                                </div>
                                            </div>
                                        `;
                                    } else if (lowerName.includes('funeral')) {
                                        extraInfo = `
                                            <div class="leave-balance-info">
                                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; text-align: center; color:#D32F2F">
                                                    <div>Total</div>
                                                    <div>Taken</div>
                                                    <div>Balance</div>
                                                    <div>Pending</div>
                                                    <div><strong>${funeral.total ?? 0}</strong></div>
                                                    <div><strong>${funeral.taken ?? 0}</strong></div>
                                                    <div><strong>${funeral.available ?? 0}</strong></div>
                                                    <div><strong>${funeral.pending ?? 0}</strong></div>
                                                </div>
                                            </div>
                                        `;
                                    } else if (lowerName.includes('marriage')) {
                                        extraInfo = `
                                            <div class="leave-balance-info">
                                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; text-align: center; color:#D32F2F">
                                                    <div>Total</div>
                                                    <div>Taken</div>
                                                    <div>Balance</div>
                                                    <div>Pending</div>
                                                    <div><strong>${marriage.total ?? 0}</strong></div>
                                                    <div><strong>${marriage.taken ?? 0}</strong></div>
                                                    <div><strong>${marriage.available ?? 0}</strong></div>
                                                    <div><strong>${marriage.pending ?? 0}</strong></div>
                                                </div>
                                            </div>
                                        `;
                                    } else if (lowerName.includes('unpaid')) {
                                        extraInfo = `
                                            <div class="leave-balance-info">
                                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; text-align: center; color:#D32F2F">
                                                    <div>Total</div>
                                                    <div>Taken</div>
                                                    <div>Balance</div>
                                                    <div>Pending</div>
                                                    <div><strong>${unpaid.total ?? 0}</strong></div>
                                                    <div><strong>${unpaid.taken ?? 0}</strong></div>
                                                    <div><strong>${unpaid.available ?? 0}</strong></div>
                                                    <div><strong>${unpaid.pending ?? 0}</strong></div>
                                                </div>
                                            </div>
                                        `;
                                    } else if (lowerName.includes('maternity')) {
                                        extraInfo = `
                                            <div class="leave-balance-info">
                                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; text-align: center; color:#D32F2F">
                                                    <div>Total</div>
                                                    <div>Taken</div>
                                                    <div>Balance</div>
                                                    <div>Pending</div>
                                                    <div><strong>${maternity.total ?? 0}</strong></div>
                                                    <div><strong>${maternity.taken ?? 0}</strong></div>
                                                    <div><strong>${maternity.available ?? 0}</strong></div>
                                                    <div><strong>${maternity.pending ?? 0}</strong></div>
                                                </div>
                                            </div>
                                        `;
                                    } else if (lowerName.includes('paternity')) {
                                        extraInfo = `
                                            <div class="leave-balance-info">
                                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; text-align: center; color:#D32F2F">
                                                    <div>Total</div>
                                                    <div>Taken</div>
                                                    <div>Balance</div>
                                                    <div>Pending</div>
                                                    <div><strong>${paternity.total ?? 0}</strong></div>
                                                    <div><strong>${paternity.taken ?? 0}</strong></div>
                                                    <div><strong>${paternity.available ?? 0}</strong></div>
                                                    <div><strong>${paternity.pending ?? 0}</strong></div>
                                                </div>
                                            </div>
                                        `;
                                    }

                                    return `
                                        <div class="time-off-type" data-type-id="${type.id}" data-leave-name="${lowerName}">
                                            <input type="radio" name="holiday_status_id" value="${type.id}" id="type_${type.id}">
                                            <div class="time-off-type-name">${type.name}</div>
                                            ${extraInfo}
                                            <span class="time-off-type-badge">${type.requires_allocation ? 'Allocated' : 'Unlimited'}</span>
                                        </div>
                                    `;
                                }).join('')}
                            </div>

                        </div>

                        
                        <!-- Date Range -->
                        <div class="form-section">
                            <h3><i class="fa fa-calendar-alt"></i> Duration</h3>
                            <div class="date-range">
                                <div>
                                    <label class="form-label">
                                        <i class="fa fa-calendar"></i>
                                        From Date <span id="annualNote" style="color: #D32F2F; font-weight: 500; font-size: 13px; display: none;">
                                            (Annual leave must be requested at least 3 working days in advance)
                                        </span> *
                                    </label>
                                    <input type="date" name="request_date_from" class="form-control" required>
                                </div>
                                <div>
                                    <label class="form-label">
                                        <i class="fa fa-calendar"></i>
                                        To Date *
                                    </label>
                                    <input type="date" name="request_date_to" class="form-control" required>
                                </div>
                                <div style="font-weight: 600; color: #D32F2F; font-size: 14px;">
                                    <input type="checkbox" name="half_day" id="half_day">
                                    <label for="half_day_to">Half Day</label>
                                </div>
                            </div>
                            
                            <!-- Duration Display -->
                            <div id="durationDisplay" class="duration-display" style="display: none;">
                                <h4>Duration: <span id="durationDays">0</span> day(s)</h4>
                            </div>
                        </div>

                        <div id="attachmentContainer" style="display: none;"></div>
                      
                        <!-- Description -->
                        <div class="form-section">
                            <h3><i class="fa fa-file-text"></i> Description</h3>
                            <div class="form-group">
                                <label class="form-label">
                                    <i class="fa fa-comment"></i>
                                    Reason for Leave *
                                </label>
                                <textarea name="name" class="form-control" rows="4" 
                                         placeholder="Please provide a reason for your time off request..." required></textarea>
                            </div>
                        </div>
                        
                        <!-- Submit Button -->
                        <div class="submit-section">
                            <button type="submit" class="btn-submit" id="submitBtn">
                                <i class="fa fa-paper-plane"></i>
                                Submit Request
                            </button>
                        </div>
                    </form>
                </div>
                
                <!-- Info Card -->
                <div class="info-card">
                    <h4><i class="fa fa-info-circle"></i> Important Information</h4>
                    <ul>
                        <li>Submit your request at least 2 weeks in advance for planned leave</li>
                        <li>Emergency leave requests will be reviewed on a case-by-case basis</li>
                        <li>You will receive an email notification once your request is processed</li>
                        <li>Check your remaining leave balance before submitting</li>
                    </ul>
                </div>
            </div>
        `;
    }
    
    setupEventListeners() {
    const form = document.getElementById('leaveRequestForm');
    if (!form) return;

    form.addEventListener('submit', this.handleSubmit.bind(this));

    const fromDateInput = form.querySelector('[name="request_date_from"]');
    const toDateInput = form.querySelector('[name="request_date_to"]');
    const halfDay = form.querySelector('[name="half_day"]');

    // --- Helper: Add working days excluding weekends ---
    const addWorkingDays = (startDate, days) => {
        let remaining = days;
        let date = new Date(startDate);
        while (remaining > 0) {
            date.setDate(date.getDate() + 1);
            const day = date.getDay();
            if (day !== 0 && day !== 6) remaining--; // skip Sat/Sun
        }
        return date;
    };

    // --- Helper: Apply annual leave restriction ---
    const applyAnnualLeaveRestriction = () => {
        if (!fromDateInput || !toDateInput) return;
        const minDateObj = addWorkingDays(new Date(), 3);
        const minDate = minDateObj.toISOString().split('T')[0];

        fromDateInput.setAttribute('min', minDate);
        toDateInput.setAttribute('min', minDate);

        // 🚫 reset if old dates are invalid
        if ((fromDateInput.value && fromDateInput.value < minDate) || 
            (toDateInput.value && toDateInput.value < minDate)) {
            fromDateInput.value = '';
            toDateInput.value = '';
            this.showNotification(
                "Annual leave must be requested at least 3 working days in advance. Dates have been cleared.",
                'error'
            );
            this.hasBlockingError = true;
        }
    };


    // --- Helper: Apply default restriction (today) ---
    const applyDefaultRestriction = () => {
        if (!fromDateInput || !toDateInput) return;
        const todayStr = new Date().toISOString().split('T')[0];
        fromDateInput.setAttribute('min', todayStr);
        toDateInput.setAttribute('min', todayStr);
    };

    // Handle leave type selection
    document.querySelectorAll('.time-off-type').forEach(typeDiv => {
        typeDiv.addEventListener('click', () => {
            const radio = typeDiv.querySelector('input[type="radio"]');
            radio.checked = true;
            this.updateTypeSelection();
            this.formData.holiday_status_id = parseInt(radio.value);

            const leaveNameRaw = typeDiv.getAttribute('data-leave-name').toLowerCase();
            const leaveName = leaveNameRaw.replace('leave', '').trim();
            this.formData.leaveTypeName = leaveName;

            // Handle attachment requirement
            const attachmentContainer = document.getElementById('attachmentContainer');
            attachmentContainer.innerHTML = '';
            if (!['casual', 'annual', 'unpaid'].includes(leaveName)) {
                console.log(`Attachment required for leave type: ${leaveNameRaw}`);
                attachmentContainer.style.display = 'block';
                attachmentContainer.innerHTML = `
                    <div class="form-section">
                        <h3><i class="fa fa-paperclip"></i>Attachment</h3>
                        <div class="form-group">
                            <label class="form-label">
                                <i class="fa fa-paperclip"></i> Attachment for Evidence of Leave Request
                            </label>
                            <input type="file" name="attachment" class="form-control" 
                                   accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" required>
                        </div>
                    </div>
                `;
            } else {
                console.log(`No attachment required for leave type: ${leaveNameRaw}`);
                attachmentContainer.style.display = 'none';
            }

            // Toggle annual note
            const annualNote = document.getElementById('annualNote');
            if (annualNote) {
                annualNote.style.display = (leaveName === 'annual') ? 'inline' : 'none';
            }

            // Apply restrictions
            if (leaveName === 'annual') {
                applyAnnualLeaveRestriction();
            } else {
                applyDefaultRestriction();
            }
        });
    });

    // --- Date restrictions ---
    applyDefaultRestriction();

    if (fromDateInput && toDateInput) {
        fromDateInput.addEventListener('change', async () => {
            await this.calculateDuration();
            await this.maybeCheckOverlap();

            // Casual leave extra check
            if (this.formData.leaveTypeName === 'casual' && this.formData.number_of_days > 2) {
                this.showNotification("Casual leave cannot exceed 2 days.", 'error');
                fromDateInput.value = '';
            }

            // Annual leave check
            if (this.formData.leaveTypeName === 'annual') {
                applyAnnualLeaveRestriction();
            }
        });

        toDateInput.addEventListener('change', async () => {
            await this.calculateDuration();
            await this.maybeCheckOverlap();

            if (this.formData.leaveTypeName === 'casual' && this.formData.number_of_days > 2) {
                this.showNotification("Casual leave cannot exceed 2 days.", 'error');
                toDateInput.value = '';
            }
        });
    }

    // Half-day toggle
    if (halfDay) {
        halfDay.addEventListener('change', () => this.calculateDuration());
    }
}


    updateTypeSelection() {
        document.querySelectorAll('.time-off-type').forEach(div => {
            div.classList.remove('selected');
        });
        
        const selectedRadio = document.querySelector('[name="holiday_status_id"]:checked');
        if (selectedRadio) {
            selectedRadio.closest('.time-off-type').classList.add('selected');
        }
    }
   
    calculateDuration() {
        const form = document.getElementById('leaveRequestForm');
        const fromDateVal = form.querySelector('[name="request_date_from"]').value;
        const toDateVal = form.querySelector('[name="request_date_to"]').value;
        const isHalfDay = form.querySelector('[name="half_day"]').checked;

        if (fromDateVal && toDateVal) {
            const from = new Date(fromDateVal);
            const to = new Date(toDateVal);

            if (to < from) {
                this.formData.number_of_days = 0;
                document.getElementById('durationDisplay').style.display = 'none';
                this.showNotification("End date cannot be earlier than start date.", "error");
                this.hasBlockingError = true;   // 🚫 mark blocking
                return;
            }


            let totalDays = Math.floor((to - from) / (1000 * 60 * 60 * 24)) + 1;

            if (isHalfDay) {
                totalDays = totalDays / 2;
            }

            this.formData.number_of_days = totalDays;
            document.getElementById('durationDays').textContent = totalDays;
            document.getElementById('durationDisplay').style.display = 'block';
        }
    }

    async handleSubmit(e) {
        e.preventDefault();

        // 🚫 Block if error already active
        if (this.hasBlockingError) {
            this.showNotification("Please fix the highlighted errors before submitting.", "error");
            return;
        }

        const form = e.target;
        const formData = new FormData(form);
        formData.append('employee_number', this.employeeNumber);
        formData.append('number_of_days', this.formData.number_of_days);

        // --- Required fields validation ---
        const requiredFields = ['holiday_status_id', 'request_date_from', 'request_date_to', 'name'];
        for (let field of requiredFields) {
            const value = formData.get(field);
            if (!value || (field === 'name' && value.trim() === '')) {
                this.showNotification('Please fill in all required fields', 'error');
                return;
            }
        }

        // --- Date consistency check ---
        const fromDate = new Date(formData.get('request_date_from'));
        const toDate = new Date(formData.get('request_date_to'));

        if (toDate < fromDate) {
            this.showNotification("End date cannot be earlier than start date.", "error");
            this.hasBlockingError = true;
            return;
        }

        // --- Date duration check ---
        if (this.formData.number_of_days <= 0) {
            this.showNotification('Invalid date range selected', 'error');
            this.hasBlockingError = true;
            return;
        }

        // --- Casual leave rule check ---
        if (this.formData.leaveTypeName === 'casual' && this.formData.number_of_days > 2) {
            this.showNotification("Casual Leave cannot exceed 2 days.", 'error');
            this.hasBlockingError = true;

            // Reset from & to date so user must pick again
            const fromDateInput = document.querySelector('[name="request_date_from"]');
            const toDateInput = document.querySelector('[name="request_date_to"]');
            if (fromDateInput) fromDateInput.value = '';
            if (toDateInput) toDateInput.value = '';

            return;
        }

        // --- Annual leave rule check ---
        const today = new Date();
        const minAnnualStart = new Date();
        minAnnualStart.setDate(today.getDate() + 3);

        if (this.formData.leaveTypeName === 'annual' && fromDate < minAnnualStart) {
            this.showNotification("Annual leave must be requested at least 3 days in advance.", 'error');
            this.hasBlockingError = true;
            return;
        }

        this.setLoading(true);

        try {
            const response = await fetch('/api/leave-request', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const rpcResponse = await response.json();
            const result = rpcResponse?.result || rpcResponse; // support both shapes

            if (result?.success) {
                this.showNotification(result.message || 'Leave request submitted successfully!', 'success');

                setTimeout(() => {
                    const leaveData = result.data || {};
                    const params = new URLSearchParams({
                        employee_name: leaveData.employee_name || this.employeeName,
                        leave_type: leaveData.leave_type || this.formData.leaveTypeName,
                        date_from: leaveData.date_from || this.formData.request_date_from,
                        date_to: leaveData.date_to || this.formData.request_date_to,
                        number_of_days: leaveData.number_of_days || this.formData.number_of_days,
                        description: leaveData.description || ''
                    });
                    window.location.href = `/leave/success?${params.toString()}`;
                }, 1500);
            } else {
                const errorMessage = result?.error || 'Failed to submit leave request';
                this.showNotification(errorMessage, 'error');
                this.hasBlockingError = true;
            }
        } catch (error) {
            console.error('Error submitting request:', error);
            this.showNotification(error.message || 'Network error. Please try again.', 'error');
            this.hasBlockingError = true;
        } finally {
            this.setLoading(false);
        }
    }

   
    setLoading(loading) {
        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn) {
            submitBtn.disabled = loading;
            submitBtn.innerHTML = loading ? 
                '<div class="spinner"></div> Submitting...' : 
                '<i class="fa fa-paper-plane"></i> Submit Request';
        }
    }
    
    showNotification(message, type = 'info') {
        // Remove existing notifications
        document.querySelectorAll('.notification').forEach(n => n.remove());
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <i class="fa fa-${type === 'success' ? 'check-circle' : 
                              type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            ${message}
        `;
        
        document.body.appendChild(notification);
        
        // Show notification
        setTimeout(() => notification.classList.add('show'), 100);
        
        // Auto remove
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    new LeaveRequestForm();
});

