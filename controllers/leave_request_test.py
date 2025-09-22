import logging
from odoo import http, fields
from odoo.http import request, Response
from datetime import datetime, timedelta
import json
import base64
from datetime import datetime
from datetime import date
from dateutil.relativedelta import relativedelta
from werkzeug.utils import secure_filename
from calendar import monthrange
import calendar

_logger = logging.getLogger(__name__)

class LeaveController(http.Controller):
    
    @http.route('/leave/request', type='http', auth='public', website=True, method=['GET','POST'])
    def leave_request_form(self, **kwargs):
        """Render the leave request form page"""
        try:
            # Get time off types for the form
            time_off_types = request.env['hr.leave.type'].sudo().search([
                ('active', '=', True)
            ])
            
            employee_number = request.session.get('employee_number')
            _logger.info("DEBUG: employee_number from session = %s", employee_number)
            
            employee = False
            if employee_number:
                employee = request.env['hr.employee'].sudo().search([('id', '=', employee_number)], limit=1)
                _logger.info("DEBUG: employee search result = %s", employee)
            if not employee or not employee.exists():
                # Pass an explicit None or False value for employee
                return request.redirect('/employee/register')
            return request.render('custom_leave_request.leave_request_form_template', {
                'time_off_types': time_off_types,
                'employee': employee,
                'page_title': 'Submit Leave Request'
            })
            
        except Exception as e:
            _logger.exception("Error loading leave request form: %s", str(e))
            return request.not_found()
    
    @http.route('/leave/success', type='http', auth='public', website=True)
    def leave_request_success(self, **kwargs):
        """Render success page after leave request submission"""

        employee_number = request.session.get('employee_number')

        if not employee_number:
            return request.redirect('/employee/register')

        return request.render('custom_leave_request.leave_request_success_template', {
            'employee_name': kwargs.get('employee_name', ''),
            'leave_type': kwargs.get('leave_type', ''),
            'date_from': kwargs.get('date_from', ''),
            'date_to': kwargs.get('date_to', ''),
            'number_of_days': kwargs.get('number_of_days', ''),
            'description': kwargs.get('description', ''),
            'page_title': 'Request Submitted Successfully'
        })
      
    @http.route('/leave/requests', type='http', auth='public', website=True)
    def my_leave_requests(self, **kwargs):
        """Show employee's leave requests"""
        try:
            employee_number = request.session.get('employee_number')
            if not employee_number:
                return request.redirect('/employee/register')
            
            employee = request.env['hr.employee'].sudo().browse(int(employee_number))
            if not employee.exists():
                return request.render('custom_leave_request.leave_requests_list_template', {
                    'error': 'Employee not found',
                    'leave_requests': [],
                    'page_title': 'My Leave Requests'
                })
            
            # Get employee's leave requests
            leave_requests = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id)
            ], order='create_date desc')

            
            
            return request.render('custom_leave_request.leave_requests_list_template', {
                'employee': employee,
                'leave_requests': leave_requests,
                'page_title': f'{employee.name} - Leave Requests'
            })
            
        except Exception as e:
            _logger.exception("Error loading leave requests: %s", str(e))
            return request.render('custom_leave_request.leave_requests_list_template', {
                'error': 'Error loading requests',
                'leave_requests': [],
                'page_title': 'My Leave Requests'
            })
    
    @http.route('/api/time-off-types', type='json', auth='public', methods=['POST'], csrf=False)
    def get_time_off_types(self):
        """Return eligible leave types for an employee (rules only, no balances)."""
        try:
            data = request.jsonrequest or {}
            employee_number = data.get('employee_number') or request.session.get('employee_number')

            employee = False
            if employee_number:
                employee = request.env['hr.employee'].sudo().search([
                    '|', ('id', '=', employee_number),
                    ('employee_number', '=', employee_number)
                ], limit=1)

            if not employee or not employee.exists():
                _logger.info("No employee found for employee_number: %s", employee_number)
                return {'success': True, 'result': []}

            gender = (employee.gender or '').lower()
            marital_status = (employee.marital or '').lower()
            join_date = employee.join_date
            lower_tags = [t.lower() for t in employee.category_ids.mapped('name')]
            today = datetime.today().date()

            # Calculate service duration in months
            service_months = 0
            if join_date:
                delta = relativedelta(today, join_date)
                service_months = delta.years * 12 + delta.months

            eligible_leaves = []

            # -------------------
            # Rule 1: Intern/Probation
            # -------------------
            if 'intern' in lower_tags or 'probation' in lower_tags:
                eligible_leaves = ['Unpaid Leave']

            # -------------------
            # Rule 2: Permanent
            # -------------------
            elif 'permanent' in lower_tags:
                # Always include casual, funeral, unpaid
                eligible_leaves = ['Casual Leave', 'Funeral Leave', 'Unpaid Leave']

                # Annual leave if service ≥ 12 months
                if service_months >= 12:
                    eligible_leaves.append('Annual Leave')

                # Medical leave if service ≥ 6 months
                if service_months >= 6:
                    eligible_leaves.append('Medical Leave')

                # Marriage leave if single and service ≥ 12 months
                if marital_status == 'single' and service_months >= 12:
                    eligible_leaves.append('Marriage Leave')

                # Maternity/Paternity leave if married
                if marital_status == 'married':
                    if gender == 'female':
                        eligible_leaves.append('Maternity Leave')
                    elif gender == 'male':
                        eligible_leaves.append('Paternity Leave')

            # -------------------
            # Fetch only rule-based leave type records
            # -------------------
            time_off_types = request.env['hr.leave.type'].sudo().search([
                ('name', 'in', eligible_leaves),
                ('active', '=', True)
            ])

            result = [{
                'id': lt.id,
                'name': lt.name,
                'color': lt.color or 1,
                'requires_allocation': lt.requires_allocation,
                'leave_validation_type': lt.leave_validation_type
            } for lt in time_off_types]

            _logger.info("[API] Returning rule-based time off types: %s", [t['name'] for t in result])
            return {'success': True, 'result': result}

        except Exception as e:
            _logger.exception("Error fetching time off types: %s", str(e))
            return {'success': False, 'error': str(e)}



    
    @http.route('/api/employees', type='json', auth='public', methods=['POST'], csrf=False)
    def get_employees(self):
        """Get all active employees"""
        try:
            employees = request.env['hr.employee'].sudo().search([
                ('active', '=', True)
            ])
            
            result = []
            for employee in employees:
                result.append({
                    'id': employee.id,
                    'name': employee.name,
                    'employee_number': employee.employee_number or f'EMP{employee.id:03d}',
                    'department': employee.department_id.name if employee.department_id else '',
                    'job_title': employee.job_title or ''
                })
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            _logger.exception("Error fetching employees: %s", str(e))
            return {'success': False, 'error': str(e)}
    
    
    @http.route('/api/leave-request', type='http', auth='public', methods=['POST'], csrf=False)
    def create_leave_request(self, **post):
        try:
            data = request.params
            files = request.httprequest.files

            required_fields = ['employee_number', 'holiday_status_id', 'request_date_from', 'request_date_to', 'name']
            for field in required_fields:
                if not data.get(field):
                    return request.make_response(json.dumps({'success': False, 'error': f'Missing required field: {field}'}), headers=[('Content-Type', 'application/json')])

            employee = request.env['hr.employee'].sudo().search([('employee_number', '=', data['employee_number'])], limit=1)
            if not employee:
                return request.make_response(json.dumps({'success': False, 'error': 'Employee not found'}), headers=[('Content-Type', 'application/json')])

            leave_type = request.env['hr.leave.type'].sudo().browse(int(data['holiday_status_id']))
            if not leave_type.exists():
                return request.make_response(json.dumps({'success': False, 'error': 'Leave type not found'}), headers=[('Content-Type', 'application/json')])

            date_from = datetime.strptime(data['request_date_from'], '%Y-%m-%d').date()
            date_to = datetime.strptime(data['request_date_to'], '%Y-%m-%d').date()
            if date_from > date_to:
                return request.make_response(json.dumps({'success': False, 'error': 'From date cannot be after to date'}), headers=[('Content-Type', 'application/json')])

            number_of_days = float(data.get('number_of_days') or 1)
            request_unit_half = data.get('half_day') == 'on'

            leave_values = {
                'name': data['name'],
                'employee_id': employee.id,
                'holiday_status_id': leave_type.id,
                'request_date_from': date_from,
                'request_date_to': date_to,
                'number_of_days': number_of_days,
                'state': 'confirm',
                'request_unit_half': request_unit_half,
                'request_unit_hours': False,
            }

            if request.env.user.id != request.env.ref('base.public_user').id:
                leave_values['user_id'] = request.env.user.id

            leave_request = request.env['hr.leave'].sudo().create(leave_values)

            # Attach file if provided
            if 'attachment' in files:
                uploaded_file = files['attachment']
                filename = secure_filename(uploaded_file.filename)
                file_content = uploaded_file.read()
                if filename and file_content:
                    request.env['ir.attachment'].sudo().create({
                        'name': filename,
                        'datas': base64.b64encode(file_content),
                        'res_model': 'hr.leave',
                        'res_id': leave_request.id,
                        'type': 'binary',
                        'mimetype': uploaded_file.mimetype,
                    })

            result_data = {
                'leave_id': leave_request.id,
                'employee_name': employee.name,
                'leave_type': leave_type.name,
                'date_from': date_from.strftime('%Y-%m-%d'),
                'date_to': date_to.strftime('%Y-%m-%d'),
                'number_of_days': number_of_days,
                'state': leave_request.state,
                'description': leave_request.name,
            }

            return request.make_response(json.dumps({
                'success': True,
                'message': 'Leave request submitted successfully',
                'data': result_data
            }), headers=[('Content-Type', 'application/json')])

        except Exception as e:
            _logger.exception("Leave submission error: %s", str(e))
            request.env.cr.rollback()
            return request.make_response(json.dumps({'success': False, 'error': str(e)}), headers=[('Content-Type', 'application/json')])

    
    def _calculate_leave_days(self, date_from, date_to, leave_type):
        """Calculate the number of leave days, excluding weekends if configured"""
        try:
            # Basic calculation - can be enhanced based on company calendar
            total_days = (date_to - date_from).days + 1
        
            return max(total_days, 0)
            
        except Exception as e:
            _logger.error("Error calculating leave days: %s", str(e))
            return (date_to - date_from).days + 1
    
    @http.route('/api/leave-requests', type='json', auth='user', methods=['GET'], csrf=False)
    def get_my_leave_requests(self):
        """Get leave requests for the logged-in employee"""
        try:
            # Find the employee linked to the logged-in user
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not employee:
                return {'success': False, 'error': 'Employee not linked to this user'}

            # Get leave requests
            leave_requests = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id)
            ], order='create_date desc')

            result = []
            for leave in leave_requests:
                result.append({
                    'id': leave.id,
                    'name': leave.name,
                    'leave_type': leave.holiday_status_id.name,
                    'date_from': leave.request_date_from.strftime('%Y-%m-%d') if leave.request_date_from else '',
                    'date_to': leave.request_date_to.strftime('%Y-%m-%d') if leave.request_date_to else '',
                    'number_of_days': leave.number_of_days,
                    'state': leave.state,
                    'create_date': leave.create_date.strftime('%Y-%m-%d %H:%M:%S') if leave.create_date else ''
                })

            return {'success': True, 'result': result}

        except Exception as e:
            _logger.exception("Error fetching leave requests: %s", str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/api/check/leave/valid', type='json', auth='user', methods=['POST'], csrf=False)
    def check_leave_valid(self, **kwargs):
        try:
            data = request.jsonrequest
            employee_number = data.get('employee_number')
            request_date_from = data.get('request_date_from')
            request_date_to = data.get('request_date_to')

            # Log incoming data for debugging
            print("DEBUG - Incoming data:")
            print(f"  employee_number: {employee_number}")
            print(f"  request_date_from: {request_date_from} ({type(request_date_from)})")
            print(f"  request_date_to: {request_date_to} ({type(request_date_to)})")

            # Validate input presence
            if not employee_number or not request_date_from or not request_date_to:
                return {
                    'success': False,
                    'error': 'Missing required parameters: employee_number, request_date_from, or request_date_to'
                }

            # Try to parse date strings
            try:
                date_from = datetime.strptime(request_date_from, '%Y-%m-%d').date()
                date_to = datetime.strptime(request_date_to, '%Y-%m-%d').date()
            except Exception as parse_err:
                print("ERROR parsing dates:", parse_err)
                return {
                    'success': False,
                    'error': 'Dates must be in string format: YYYY-MM-DD'
                }

            # Find employee
            employee = request.env['hr.employee'].sudo().search([('employee_number', '=', employee_number)], limit=1)
            if not employee:
                return {'success': False, 'error': 'Employee not found'}

            # Check leaves before the start date
            before_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('request_date_to', '=', date_from - timedelta(days=1))
            ])

            if before_leaves:
                return {
                    'success': False,
                    'error': 'Casual Leave cannot be combined with any other form of leave before the start date.'
                }

            # Check leaves after the end date
            after_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('request_date_from', '=', date_to + timedelta(days=1))
            ])

            if after_leaves:
                return {
                    'success': False,
                    'error': 'Casual Leave cannot be combined with any other form of leave after the end date.'
                }

            return {'success': True}

        except Exception as e:
            print("ERROR - Exception in check_leave_valid:", e)
            return {'success': False, 'error': str(e)}
    

    @http.route('/api/leave-balance', type='json', auth='public', methods=['POST'], csrf=False)
    def get_leave_balance_with_tracker(self, **kwargs):
        try:
            _logger.info("Called /api/leave-balance with kwargs: %s", kwargs)

            employee_number = kwargs.get('employee_number') or request.session.get('employee_number')
            if not employee_number:
                _logger.debug("Missing employee_number in request")
                return {'success': False, 'error': 'Missing employee_number'}

            today = date.today()
            current_year = today.year
            _logger.info("Today's date: %s, Current year: %s", today, current_year)

            # Match by ID or employee_number (string/number safe)
            employee = request.env['hr.employee'].sudo().search([
                '|', ('id', '=', employee_number),
                ('employee_number', '=', employee_number)
            ], limit=1)
            if not employee:
                _logger.debug("No employee found with employee_number: %s", employee_number)
                return {'success': False, 'error': 'Employee not found'}

            _logger.info("Found employee: %s (ID: %s)", employee.name, employee.id)

            leave_types = [
                {'name': 'casual', 'display_name': 'Casual Leave'},
                {'name': 'annual', 'display_name': 'Annual Leave'},
                {'name': 'medical', 'display_name': 'Medical Leave'},
                {'name': 'funeral', 'display_name': 'Funeral Leave'},
                {'name': 'marriage', 'display_name': 'Marriage Leave'},
                {'name': 'unpaid', 'display_name': 'Unpaid Leave'},
                {'name': 'maternity', 'display_name': 'Maternity Leave'},
                {'name': 'paternity', 'display_name': 'Paternity Leave'}
            ]

            result = {'success': True}

            for leave_type in leave_types:
                _logger.info("Processing leave type: %s (%s)", leave_type['name'], leave_type['display_name'])

                tracker_record = request.env['hr.leave.tracker'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('leave_type_name', '=', leave_type['display_name']),
                    ('year', '=', current_year)
                ], limit=1)

                if tracker_record:
                    # Use the dynamic calculation from tracker — do not overwrite with default
                    leave_balance = self._update_existing_record(tracker_record, employee, today)

                    # Update DB fields (optional)
                    tracker_record.sudo().write({
                        'total_allocation': leave_balance.get('total', 0),
                        'taken_leaves': leave_balance.get('taken', 0),
                        'pending_requests': leave_balance.get('pending', 0),
                        'current_balance': leave_balance.get('available', 0),
                        'annual_carry': leave_balance.get('carried_forward', 0),
                        'expired_carry': leave_balance.get('expired_carried', 0),
                        'write_date': fields.Datetime.now(),
                        'write_uid': request.env.user.id,
                    })

                else:
                    # Only calculate default if no tracker exists
                    balance_dict = self._calculate_default_leave_balance(
                        leave_type['display_name'], employee, today
                    )
                    leave_balance = self._create_tracker_record(
                        employee, leave_type, balance_dict, current_year
                    )

                if not leave_balance or not isinstance(leave_balance, dict):
                    _logger.warning("Leave balance came back empty for %s, forcing defaults", leave_type['display_name'])
                    leave_balance = {
                        'total': 0,
                        'taken': 0,
                        'available': 0,
                        'pending': 0,
                        'carried_forward': 0,
                        'expired_carried': 0,
                    }

                # Only add leave if eligible (total > 0) or has pending/taken
                if (
                    leave_balance.get('total', 0) > 0
                    or leave_balance.get('pending', 0) > 0
                    or leave_balance.get('taken', 0) > 0
                ):
                    _logger.info("✅ Final leave_balance for %s: %s", leave_type['display_name'], leave_balance)
                    result[leave_type['name']] = leave_balance
                else:
                    _logger.info("⏩ Skipping leave type %s because not eligible (total=0 and no pending/taken)", leave_type['display_name'])
            return result

        except Exception as e:
            _logger.error("Error in get_leave_balance_with_tracker: %s", str(e))
            return {'success': False, 'error': 'Internal server error'}
    
    def _get_system_start_date(self):
        """Define when your system started tracking leaves in hr_leave"""
        return date(2025, 9, 20)  # Updated to match requirements

    def _get_permanent_date(self, employee):
        """Get employee's permanent date"""
        # Check if permanent_date field exists, otherwise calculate from join_date
        if hasattr(employee, 'permanent_date') and employee.permanent_date:
            return employee.permanent_date
        elif employee.join_date:
            return employee.join_date + relativedelta(years=1)
        return None

    def _is_historical_data(self, year, record_create_date=None):
        """Enhanced method to properly detect historical data"""
        system_start_date = self._get_system_start_date()
        system_start_year = system_start_date.year
        year_start = date(year, 1, 1)
        
        _logger.info(f"Checking historical data for year {year}: system_start={system_start_date}, year_start={year_start}")
        
        # If year is before system start year → always historical
        if year < system_start_year:
            _logger.info(f"Year {year} < system start year {system_start_year} → HISTORICAL")
            return True
        
        # If same year as system start
        if year == system_start_year:
            if record_create_date:
                # Created before system start date → historical
                if record_create_date < system_start_date:
                    _logger.info(f"Record created {record_create_date} < system start {system_start_date} → HISTORICAL")
                    return True
            else:
                # No create_date? Check if year start is before system start
                if year_start < system_start_date:
                    _logger.info(f"Year start {year_start} < system start {system_start_date}, no create date → HISTORICAL")
                    return True
        
        _logger.info(f"Year {year} → REAL-TIME")
        return False

    def _get_carry_forward_from_previous_year(self, employee, current_year, leave_type_name='Annual Leave'):
        """Get carry forward, respecting imported/historical tracker snapshots."""
        previous_year = current_year - 1
        if leave_type_name != 'Annual Leave':
            return 0

        system_start = self._get_system_start_date()
        is_prev_year_historical = self._is_historical_data(previous_year)

        previous_tracker = request.env['hr.leave.tracker'].sudo().search([
            ('employee_id', '=', employee.id),
            ('leave_type_name', '=', leave_type_name),
            ('year', '=', previous_year)
        ], limit=1)

        if previous_tracker:
            try:
                created_before_start = previous_tracker.create_date and previous_tracker.create_date.date() <= system_start
            except Exception:
                created_before_start = False

            if created_before_start or is_prev_year_historical:
                # Always use imported_taken for historical carry-forward
                return max(previous_tracker.imported_taken if hasattr(previous_tracker, "imported_taken") and previous_tracker.imported_taken is not None else previous_tracker.current_balance or 0, 0)

            # Compute from tracker allocation minus actual leaves
            actual_taken = self._get_actual_taken_leaves(employee.id, leave_type_name, previous_year)
            prev_alloc = previous_tracker.total_allocation or 0
            return max(prev_alloc - actual_taken, 0)

        if not is_prev_year_historical:
            prev_alloc = self._calculate_previous_year_allocation(employee, previous_year)
            actual_taken = self._get_actual_taken_leaves(employee.id, leave_type_name, previous_year)
            return max(prev_alloc - actual_taken, 0)

        return 0

    
    def _months_accrued(self, start_date, as_of_date, accrue_on_month_start=True):
        if start_date > as_of_date:
            return 0

        if not accrue_on_month_start:
            y, m = start_date.year, start_date.month
            months = 0
            while (y, m) <= (as_of_date.year, as_of_date.month):
                last_day = date(y, m, monthrange(y, m)[1])
                if last_day <= as_of_date:
                    months += 1
                else:
                    break
                if m == 12:
                    y, m = y + 1, 1
                else:
                    m += 1
            return months

        # accrue_on_month_start == True:
        months = (as_of_date.year - start_date.year) * 12 + (as_of_date.month - start_date.month)
        if as_of_date.day > 1:
            months += 1
        return max(0, months)

    def _update_existing_record(self, record, employee, today):
        """
        Idempotent recalculation for trackers:
        - Always use the original imported_taken as base_taken for historical years.
        - Never use record.taken_leaves as input for recalculation after the first import.
        """
        current_year = today.year
        record_create_date = record.create_date.date() if record.create_date else None
        is_historical = self._is_historical_data(current_year, record_create_date)

        if record.leave_type_name in ['Annual Leave', 'Casual Leave']:
            accrual = (
                self._calculate_annual_leave_accrual(employee, today)
                if record.leave_type_name == 'Annual Leave'
                else self._calculate_casual_leave_accrual(employee, today)
            )

            if is_historical:
                system_start = self._get_system_start_date()
                # Always use imported_taken as base for historical data
                if hasattr(record, "imported_taken") and record.imported_taken is not None:
                    base_taken = record.imported_taken
                else:
                    # fallback logic
                    base_taken = 0.0

                # Fallback for legacy/empty imports
                if base_taken == 0.0:
                    imported_snapshot = False
                    if record.create_date:
                        try:
                            imported_snapshot = (record.create_date.date() < system_start)
                        except Exception:
                            imported_snapshot = False

                    if imported_snapshot:
                        base_taken = record.taken_leaves or 0.0
                        # Set imported_taken for one-time migration, if missing
                        try:
                            record.sudo().write({'imported_taken': base_taken})
                        except Exception:
                            pass
                    else:
                        # Not imported: sum validated before system start
                        base_domain = [
                            ('employee_id', '=', employee.id),
                            ('holiday_status_id.name', 'ilike', record.leave_type_name),
                            ('state', '=', 'validate'),
                            ('request_date_to', '<', system_start),
                        ]
                        base_leaves = request.env['hr.leave'].sudo().search(base_domain)
                        base_taken = sum(base_leaves.mapped('number_of_days')) or 0.0

                # Only add new leaves after system start
                new_taken = self._get_taken_leaves_after_date(
                    employee.id, record.leave_type_name, current_year, system_start
                ) or 0.0

                total_taken = base_taken + new_taken
                pending = self._get_actual_pending_leaves(employee.id, record.leave_type_name, current_year)

                total_allocation = record.total_allocation or 0.0 
                available = max(total_allocation - total_taken, 0.0)

                record_vals = {
                    'taken_leaves': total_taken,
                    'pending_requests': pending,
                    'current_balance': available,
                    'write_date': fields.Datetime.now(),
                    'write_uid': request.env.user.id,
                }
                record.sudo().write(record_vals)

                return {
                    'total': total_allocation,
                    'taken': total_taken,
                    'available': available,
                    'pending': pending,
                    'carried_forward': getattr(record, 'annual_carry', 0),
                    'expired_carried': getattr(record, 'expired_carry', 0),
                }
            else:
                # real-time: use live accrual + actuals
                total_taken = self._get_actual_taken_leaves(employee.id, record.leave_type_name, current_year)
                pending = self._get_actual_pending_leaves(employee.id, record.leave_type_name, current_year)
                total_allocation = accrual['total']
                available = max(total_allocation - total_taken, 0)
                record.sudo().write({
                    'total_allocation': total_allocation,
                    'taken_leaves': total_taken,
                    'pending_requests': pending,
                    'current_balance': available,
                    'annual_carry': accrual.get('carried_forward', 0),
                    'expired_carry': accrual.get('expired_carried', 0),
                    'write_date': fields.Datetime.now(),
                    'write_uid': request.env.user.id,
                })
                return {
                    'total': total_allocation,
                    'taken': total_taken,
                    'available': available,
                    'pending': pending,
                    'carried_forward': accrual.get('carried_forward', 0),
                    'expired_carried': accrual.get('expired_carried', 0),
                }
        else:
            # For all other leave types, return tracker values directly
            return {
                'total': record.total_allocation or 0,
                'taken': record.taken_leaves or 0,
                'available': record.current_balance or 0,
                'pending': record.pending_requests or 0,
                'carried_forward': getattr(record, 'annual_carry', 0),
                'expired_carried': getattr(record, 'expired_carry', 0),
            }
    
    def _get_taken_leaves_after_date(self, employee_id, leave_type, year, after_date):
        """Get taken leaves after a specific date in the year"""
        start_of_year = date(year, 1, 1)
        end_of_year = date(year, 12, 31)
        
        domain = [
            ('employee_id', '=', employee_id),
            ('holiday_status_id.name', 'ilike', leave_type),
            ('state', '=', 'validate'),
            ('request_date_from', '>=', max(start_of_year, after_date)),
            ('request_date_to', '<=', end_of_year)
        ]

        leaves = request.env['hr.leave'].sudo().search(domain)
        taken_after_date = sum(leaves.mapped('number_of_days'))
        
        _logger.info(f"Taken leaves after {after_date} for {leave_type}: {taken_after_date}")
        return taken_after_date

    def _create_tracker_record(self, employee, leave_type, balance, year):
        """Create tracker record with proper handling for historical vs current data"""

        # Check if this should be treated as historical data
        system_start_date = self._get_system_start_date()
        year_start = date(year, 1, 1)
        is_historical_year = year_start < system_start_date

        leave_type_obj = request.env['hr.leave.type'].sudo().search(
            [('name', '=', leave_type['display_name'])], limit=1
        )
        if not leave_type_obj:
            leave_type_obj = request.env['hr.leave.type'].sudo().create({
                'name': leave_type['display_name']
            })

        # Search again to avoid duplicates
        existing_tracker = request.env['hr.leave.tracker'].sudo().search([
            ('employee_id', '=', employee.id),
            ('leave_type_name', '=', leave_type['display_name']),
            ('year', '=', year)
        ], limit=1)

        if existing_tracker:
            return {
                'total': existing_tracker.total_allocation or 0,
                'taken': existing_tracker.taken_leaves or 0,
                'available': existing_tracker.current_balance or 0,
                'pending': existing_tracker.pending_requests or 0,
                'carried_forward': getattr(existing_tracker, 'annual_carry', 0),
                'expired_carried': getattr(existing_tracker, 'expired_carry', 0),
            }

        # Create the record
        tracker_data = {
            'employee_id': employee.id,
            'leave_type_id': leave_type_obj.id,
            'leave_type_name': leave_type['display_name'],
            'year': year,
            'total_allocation': balance['total'],
            'taken_leaves': balance['taken'],
            'pending_requests': balance['pending'],
            'current_balance': balance['available'],
            'employee_name': employee.name,
            'employee_number': employee.employee_number or '',
            'name': f"{leave_type['display_name']} {year}",
            'department_id': employee.department_id.id if employee.department_id else False,
            'annual_carry': balance.get('carried_forward', 0),
            'expired_carry': balance.get('expired_carried', 0),
            'create_uid': request.env.user.id,
            'write_uid': request.env.user.id
        }

        # Add historical flag if your model supports it
        if hasattr(request.env['hr.leave.tracker'], 'is_historical'):
            tracker_data['is_historical'] = is_historical_year

        _logger.info(
            f"Creating new tracker record for {employee.name} - {leave_type['display_name']} "
            f"- Year: {year} - Historical: {is_historical_year}"
        )

        request.env['hr.leave.tracker'].sudo().create(tracker_data)

        # ✅ IMPORTANT: return the original balance dict (with allocations),
        # not the just-created tracker fields which may still be defaulted
        return {
            'total': balance['total'],
            'taken': balance['taken'],
            'available': balance['available'],
            'pending': balance['pending'],
            'carried_forward': balance.get('carried_forward', 0),
            'expired_carried': balance.get('expired_carried', 0),
        }

    def _calculate_default_leave_balance(self, leave_type, employee, today):
        """Calculate leave balance using default logic when no tracker record exists"""
        current_year = today.year
        gender = (employee.gender or '').lower()
        marital_status = (employee.marital or '').lower()
        join_date = employee.join_date
        service_months = 0
        if join_date:
            delta = relativedelta(today, join_date)
            service_months = delta.years * 12 + delta.months

        if leave_type == 'Casual Leave':
            return self._calculate_casual_leave_accrual(employee, today)

        elif leave_type == 'Annual Leave' and service_months >= 12:
            return self._calculate_annual_leave_accrual(employee, today)

        elif leave_type == 'Medical Leave' and service_months >= 6:
            return self._calculate_fixed_leave(30, employee.id, leave_type, current_year)

        elif leave_type == 'Funeral Leave':
            return self._calculate_lifetime_leave(7, employee.id, leave_type)

        elif leave_type == 'Marriage Leave' and marital_status == 'single' and service_months >= 12:
            return self._calculate_lifetime_leave(5, employee.id, leave_type)

        elif leave_type == 'Unpaid Leave':
            return self._calculate_fixed_leave(30, employee.id, leave_type, current_year)

        elif leave_type == 'Maternity Leave' and marital_status == 'married' and gender == 'female':
            return self._calculate_lifetime_leave(98, employee.id, leave_type)

        elif leave_type == 'Paternity Leave' and marital_status == 'married' and gender == 'male':
            return self._calculate_lifetime_leave(15, employee.id, leave_type)

        else:
            # If not eligible, return empty balance
            return {'total': 0, 'taken': 0, 'available': 0, 'pending': 0,
                    'carried_forward': 0, 'expired_carried': 0}

    
    def _calculate_casual_leave_accrual(self, employee, today):
        current_year = today.year
        permanent_date = self._get_permanent_date(employee)
        _logger.info('Permanent date %s', permanent_date)

        if not permanent_date or today < permanent_date:
            return {'total': 0, 'taken': 0, 'available': 0, 'pending': 0, 'carried_forward': 0, 'expired_carried': 0}

        if permanent_date.year < current_year:
            total_casual = 12 * 0.5  # Full year allocation
        elif permanent_date.year == current_year:
            if today >= permanent_date:
                # Accrue from permanent month (inclusive) through December (inclusive)
                # Example: permanent_date = 2025-08-26 -> months = 5 (Aug, Sep, Oct, Nov, Dec)
                months = 12 - permanent_date.month + 1
                total_casual = months * 0.5
            else:
                total_casual = 0  # Not eligible until permanent date
        else:
            total_casual = 0

        taken = self._get_actual_taken_leaves(employee.id, 'Casual Leave', current_year)
        pending = self._get_actual_pending_leaves(employee.id, 'Casual Leave', current_year)
        available = max(total_casual - taken, 0)

        return {
            'total': total_casual,
            'taken': taken,
            'available': available,
            'pending': pending,
            'carried_forward': 0,
            'expired_carried': 0
        }
    
    def _count_accrued_months(start_date, today):
            months = (today.year - start_date.year) * 12 + (today.month - start_date.month)
            last_day_of_month = (date(today.year, today.month, 1) + relativedelta(months=1)) - timedelta(days=1)
            if today == last_day_of_month:
                months += 1
            return max(0, months)

    def _calculate_annual_leave_accrual(self, employee, today):
        current_year = today.year
        join_date = getattr(employee, 'join_date', None)

        if not join_date:
            return {'total': 0, 'taken': 0, 'available': 0, 'pending': 0,
                    'carried_forward': 0, 'expired_carried': 0}

        service_date = join_date + relativedelta(years=1)
        if today < service_date:
            return {'total': 0, 'taken': 0, 'available': 0, 'pending': 0,
                    'carried_forward': 0, 'expired_carried': 0}

        system_start_date = self._get_system_start_date()

        # ---------------- Tracker branch ----------------
        tracker = request.env['hr.leave.tracker'].sudo().search([
            ('employee_id', '=', employee.id),
            ('leave_type_name', '=', 'Annual Leave'),
            ('year', '=', current_year),
            ('create_date', '<=', datetime.combine(system_start_date, datetime.min.time()))
        ], limit=1)


        cutoff = date(current_year, 6, 30)

        if tracker:
            _logger.debug("Tracker exists for employee %s", employee.id)
            accrue_start = max(tracker.create_date.date(), service_date)
            accrued_new = self._count_accrued_months(accrue_start, today)
            _logger.debug("Accrue start: %s, Newly accrued months: %s", accrue_start, accrued_new)

            total_dynamic = (tracker.total_allocation or 0) + accrued_new
            _logger.debug("Tracker total_allocation: %s, total_dynamic: %s", tracker.total_allocation, total_dynamic)

            # Validated leaves from HR Leave table
            validated_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'Annual Leave'),
                ('state', '=', 'validate'),
                ('request_date_from', '>=', accrue_start),
                ('request_date_to', '<=', date(current_year, 12, 31)),
            ])
            validated_taken = sum(validated_leaves.mapped('number_of_days'))
            import_taken = getattr(tracker, 'imported_taken', 0)

            # ✅ Apply import_applied flag logic
            if not getattr(tracker, 'import_applied', False):
                total_taken = (tracker.taken_leaves or 0) + validated_taken + (import_taken or 0)
                tracker.sudo().write({'import_applied': True})
                _logger.debug("Applied import_taken=%s for employee %s", import_taken, employee.id)
            else:
                total_taken = (tracker.taken_leaves or 0) + validated_taken
                _logger.debug("Skipped import_taken (already applied) for employee %s", employee.id)

            pending = self._get_actual_pending_leaves(employee.id, 'Annual Leave', current_year)
            available = max(total_dynamic - total_taken, 0)
            _logger.debug("Available leave: %s", available)

            return {
                'total': total_dynamic,
                'taken': total_taken,
                'available': available,
                'pending': pending,
                'carried_forward': 0,
                'expired_carried': 0,
            }


        # ---------------- System calculation branch (only if no tracker) ----------------
        else:
            _logger.debug("No tracker found, running system calculation for employee %s", employee.id)

            carry_from_last_year = self._get_carry_forward_from_previous_year(employee, current_year, 'Annual Leave')
            accrual_start = service_date if today.year == service_date.year else date(today.year, 1, 1)
            accrued_new = self._count_accrued_months(accrual_start, today)

            validated_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'Annual Leave'),
                ('state', '=', 'validate'),
                ('request_date_from', '>=', accrual_start),
                ('request_date_to', '<=', date(current_year, 12, 31)),
            ])
            total_taken = sum(validated_leaves.mapped('number_of_days'))
            pending = self._get_actual_pending_leaves(employee.id, 'Annual Leave', current_year)

            if today <= cutoff:
                total = carry_from_last_year + accrued_new
                resp_carried = carry_from_last_year
                resp_expired = 0
                final_taken = total_taken
            else:
                new_taken = max(total_taken - carry_from_last_year, 0)
                remaining_carry = max(carry_from_last_year - total_taken, 0)
                if remaining_carry > 0:
                    resp_carried = 0
                    resp_expired = remaining_carry
                    final_taken = 0
                else:
                    resp_carried = 0
                    resp_expired = 0
                    final_taken = new_taken
                total = accrued_new

            available = max(total - final_taken, 0)

            _logger.debug(
                "System calculation: total=%s, accrued_new=%s, carry_from_last_year=%s, final_taken=%s, total_taken=%s, available=%s",
                total, accrued_new, carry_from_last_year, final_taken, total_taken, available
            )

            return {
                'total': total,
                'taken': final_taken,
                'available': available,
                'pending': pending,
                'carried_forward': resp_carried,
                'expired_carried': resp_expired,
            }


    def _calculate_monthly_accrual(self, start_date, end_date, accrual_per_month=1.0):
        """
        Count full months from start_date up to last completed month before end_date.
        Include the month of start_date if it is completed.
        """
        if start_date > end_date:
            return 0

        # Calculate months from start_date to end_date
        months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        
        # Add partial month accrual based on day completion
        if end_date.day >= start_date.day:
            months += 1
        
        return max(months * accrual_per_month, 0)



    def _calculate_previous_year_allocation(self, employee, year):
        """Calculate what the allocation should have been for a previous year"""
        permanent_date = self._get_permanent_date(employee)
        if not permanent_date:
            return 0
        
        if year < permanent_date.year:
            return 0
        elif year == permanent_date.year:
            # Pro-rated allocation based on permanent month
            return 12 - permanent_date.month + 1
        else:
            # Full year allocation (12 months)
            return 12

    def _calculate_fixed_leave(self, total_allocation, employee_id, leave_type, year):
        """Calculate fixed annual allocation leaves (medical, unpaid)"""
        start_of_year = date(year, 1, 1)
        end_of_year = date(year, 12, 31)
        
        leaves = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee_id),
            ('holiday_status_id.name', 'ilike', leave_type),
            ('request_date_from', '>=', start_of_year),
            ('request_date_to', '<=', end_of_year),
            ('state', '=', 'validate'),
        ])
        taken = sum(leaves.mapped('number_of_days'))

        pending_leaves = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee_id),
            ('holiday_status_id.name', 'ilike', leave_type),
            ('request_date_from', '>=', start_of_year),
            ('request_date_to', '<=', end_of_year),
            ('state', '=', 'confirm'),
        ])
        pending = sum(pending_leaves.mapped('number_of_days'))

        return {
            'total': total_allocation,
            'taken': taken,
            'available': max(total_allocation - taken, 0),
            'pending': pending,
            'carried_forward': 0,
            'expired_carried': 0
        }

    def _calculate_lifetime_leave(self, total_allocation, employee_id, leave_type):
        """Calculate lifetime allocation leaves (funeral, marriage, maternity, paternity)"""
        leaves = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee_id),
            ('holiday_status_id.name', 'ilike', leave_type),
            ('state', '=', 'validate'),
        ])
        taken = sum(leaves.mapped('number_of_days'))

        pending_leaves = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee_id),
            ('holiday_status_id.name', 'ilike', leave_type),
            ('state', '=', 'confirm'),
        ])
        pending = sum(pending_leaves.mapped('number_of_days'))

        return {
            'total': total_allocation,
            'taken': taken,
            'available': max(total_allocation - taken, 0),
            'pending': pending,
            'carried_forward': 0,
            'expired_carried': 0
        }

    def _get_actual_taken_leaves(self, employee_id, leave_type, year):
        """Get actual taken leaves from hr_leave table"""
        start_of_year = date(year, 1, 1)
        end_of_year = date(year, 12, 31)

        domain = [
            ('employee_id', '=', employee_id),
            ('holiday_status_id.name', 'ilike', leave_type),
            ('state', '=', 'validate')
        ]
        
        # For lifetime leaves, don't filter by year
        if leave_type not in ['Funeral Leave', 'Marriage Leave', 'Maternity Leave', 'Paternity Leave']:
            domain += [('request_date_from', '>=', start_of_year), ('request_date_to', '<=', end_of_year)]

        leaves = request.env['hr.leave'].sudo().search(domain)
        taken = sum(leaves.mapped('number_of_days'))
        
        _logger.info(f"Actual taken leaves for {leave_type} in {year}: {taken}")
        return taken

    def _get_actual_pending_leaves(self, employee_id, leave_type, year):
        """Get actual pending leaves from hr_leave table"""
        start_of_year = date(year, 1, 1)
        end_of_year = date(year, 12, 31)

        domain = [
            ('employee_id', '=', employee_id),
            ('holiday_status_id.name', 'ilike', leave_type),
            ('state', '=', 'confirm')
        ]
        
        # For lifetime leaves, don't filter by year
        if leave_type not in ['Funeral Leave', 'Marriage Leave', 'Maternity Leave', 'Paternity Leave']:
            domain += [('request_date_from', '>=', start_of_year), ('request_date_to', '<=', end_of_year)]

        leaves = request.env['hr.leave'].sudo().search(domain)
        pending = sum(leaves.mapped('number_of_days'))
        
        _logger.info(f"Actual pending leaves for {leave_type} in {year}: {pending}")
        return pending