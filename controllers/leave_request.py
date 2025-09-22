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
        """Get all available time off types for the employee (with debug)"""
        try:
            data = request.jsonrequest or {}
            employee_number = data.get('employee_number') or request.session.get('employee_number')
            employee = False
            if employee_number:
                employee = request.env['hr.employee'].sudo().search(['|', ('id', '=', employee_number), ('employee_number', '=', employee_number)], limit=1)
            if not employee or not employee.exists():
                _logger.info("No employee found for employee_number: %s", employee_number)
                return {'success': True, 'result': []}

            tag_names = employee.category_ids.mapped('name')
            gender = (employee.gender or '').lower()
            marital_status = (employee.marital or '').lower()
            join_date_str = (employee.join_date or '')

            _logger.info("[API] Employee %s - tags: %s, gender: %s - status: %s - Join Date: %s",
                        employee.name, tag_names, gender, marital_status, join_date_str)

            lower_tags = [t.lower() for t in tag_names]
            domain = [('active', '=', True)]

            # Basic tag-based conditions
            if 'intern' in lower_tags or 'probation' in lower_tags:
                domain += [('name', 'ilike', 'unpaid')]
            elif 'permanent' in lower_tags:
                if marital_status == 'married':
                    domain += [('name', 'not ilike', 'marriage')]
                if gender == 'male':
                    domain += [('name', 'not ilike', 'maternity')]
                    if marital_status != 'married':
                        domain += [('name', 'not ilike', 'paternity')]
                elif gender == 'female':
                    domain += [('name', 'not ilike', 'paternity')] 
                    if marital_status != 'married':
                        domain += [('name', 'not ilike', 'maternity')]
            
            if employee.join_date:
                try:
                    join_date = employee.join_date  # Already a datetime.date object
                    today = datetime.today().date()  # Make sure both are date objects
                    service_duration = relativedelta(today, join_date)

                    _logger.info("[DEBUG] Service Duration for %s: %s years, %s months, %s days",
                                employee.name, service_duration.years, service_duration.months, service_duration.days)

                    # Add medical leave after 6 months
                    if today <= join_date + relativedelta(years=1):
                        _logger.info("[DEBUG] %s eligible for Medical Leave (6+ months service)", employee.name)
                        domain += [('name', 'not ilike', 'annual')]
                        domain += [('name', 'not ilike', 'marriage')]
                        if today <= join_date + relativedelta(months=6):
                            domain += [('name', 'not ilike', 'medical')]

                except Exception as e:
                    _logger.warning("Unexpected error while calculating service duration for %s: %s", employee.name, e)

                                

            # Fetch eligible leave types
            time_off_types = request.env['hr.leave.type'].sudo().search(domain)
            result = []
            for leave_type in time_off_types:
                result.append({
                    'id': leave_type.id,
                    'name': leave_type.name,
                    'color': leave_type.color or 1,
                    'requires_allocation': leave_type.requires_allocation,
                    'leave_validation_type': leave_type.leave_validation_type
                })

            _logger.info("[API] Returning time off types: %s", [t['name'] for t in result])
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
                ('employee_number', '=', employee.id)
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

    # @http.route('/api/leave-balance', type='json', auth='public', methods=['POST'], csrf=False)
    # def get_leave_balance(self, **kwargs):
    #     try:
    #         _logger.debug("Called /api/leave-balance with kwargs: %s", kwargs)

    #         employee_number = request.session.get('employee_number')
    #         if not employee_number:
    #             _logger.debug("Missing employee_number in request")
    #             return {'success': False, 'error': 'Missing employee_number'}

    #         today = date.today()
    #         current_year = today.year
    #         _logger.debug("Today's date: %s, Current year: %s", today, current_year)

    #         start_of_year = date(current_year, 1, 1)
    #         end_of_year = date(current_year, 12, 31)

    #         employee = request.env['hr.employee'].sudo().search([
    #             ('id', '=', employee_number)
    #         ], limit=1)

    #         if not employee:
    #             _logger.debug("No employee found with employee_number: %s", employee_number)
    #             return {'success': False, 'error': 'Employee not found'}

    #         _logger.debug("Found employee: %s (ID: %s)", employee.name, employee.id)

    #         # Calculate service duration
    #         if employee.join_date:
    #             join_date = employee.join_date
    #             today_date = datetime.today().date()
    #             service_duration = relativedelta(today_date, join_date)

    #         # Casual leave logic with permanent_date
    #         if employee.permanent_date:
    #             permanent_date = employee.permanent_date
    #             _logger.debug("Using permanent_date: %s", permanent_date)
                
    #             if today.year == permanent_date.year:
    #                 months_from_permanent = 12 - permanent_date.month + 1
    #                 total_casual = months_from_permanent * 0.5
    #                 _logger.debug("Same year as permanent date. Months from permanent to end of year: %d, Total casual: %f", 
    #                             months_from_permanent, total_casual)
    #             else:
    #                 total_casual = 6.0
    #                 _logger.debug("Different year from permanent date. Total casual: %f", total_casual)
    #         else:
    #             _logger.debug("No permanent_date found, using join_date logic")
    #             if today.year == join_date.year:
    #                 total_casual = (13 - join_date.month)/2
    #             else:
    #                 total_casual = 6

    #         # Calculate approved casual leaves
    #         casual_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'casual'),
    #             ('request_date_from', '>=', start_of_year),
    #             ('request_date_to', '<=', end_of_year),
    #             ('state', '=', 'validate'),
    #         ])

    #         # Calculate pending casual leaves
    #         casual_pending_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'casual'),
    #             ('request_date_from', '>=', start_of_year),
    #             ('request_date_to', '<=', end_of_year),
    #             ('state', '=', 'confirm'),
    #         ])

    #         taken_casual = sum(casual_leaves.mapped('number_of_days'))
    #         available_casual = max(total_casual - taken_casual, 0)
    #         pending_casual = sum(casual_pending_leaves.mapped('number_of_days'))
        
    #         carried_forward_cutoff = date(current_year, 6, 30)

    #         one_year_service_date = join_date + relativedelta(years=1)
    #         _logger.debug("One year service date: %s", one_year_service_date)
            
    #         # Check if employee has completed 1 year of service
    #         if today < one_year_service_date:
    #             # Not eligible for annual leave yet
    #             total_annual = 0
    #             taken_annual = 0
    #             available_annual = 0
    #             pending_annual = 0
    #             _logger.debug("Employee not eligible for annual leave yet")
    #         else:
    #             # Calculate annual leave starting from the month of completing 1 year
    #             annual_start_month = one_year_service_date.month
    #             annual_start_year = one_year_service_date.year
                
    #             # Calculate carry forward from previous year
    #             previous_year = current_year - 1
    #             carried_forward = 0
                
    #             if annual_start_year < current_year:
    #                 # Calculate previous year's total annual leave
    #                 if annual_start_year == previous_year:
    #                     # Annual started in previous year - count from start month to December
    #                     prev_months = 12 - annual_start_month + 1
    #                     prev_total_annual = prev_months
    #                 else:
    #                     # Full previous year
    #                     prev_total_annual = 12
                    
    #                 # Get previous year's taken annual leave
    #                 prev_start = date(previous_year, 1, 1)
    #                 prev_end = date(previous_year, 12, 31)
                    
    #                 prev_annual_leaves = request.env['hr.leave'].sudo().search([
    #                     ('employee_id', '=', employee.id),
    #                     ('holiday_status_id.name', 'ilike', 'annual'),
    #                     ('request_date_from', '>=', prev_start),
    #                     ('request_date_to', '<=', prev_end),
    #                     ('state', '=', 'validate'),
    #                 ])
    #                 prev_taken = sum(prev_annual_leaves.mapped('number_of_days'))
    #                 carried_forward = max(prev_total_annual - prev_taken, 0)
    #                 _logger.debug("Previous year total: %d, taken: %d, carried forward: %d", 
    #                             prev_total_annual, prev_taken, carried_forward)
                
    #             # Calculate current year's new annual leave (1 day per completed month)
    #             if annual_start_year == current_year:
    #                 # Annual leave started this year - count from start month to current month
    #                 if today.month >= annual_start_month:
    #                     # Count completed months from annual start month
    #                     last_day_of_month = monthrange(today.year, today.month)[1]
    #                     if today.day == last_day_of_month:
    #                         # Current month is completed
    #                         accrued_new = today.month - annual_start_month + 1
    #                     else:
    #                         # Current month not completed yet
    #                         accrued_new = today.month - annual_start_month
    #                 else:
    #                     accrued_new = 0
    #                 _logger.debug("Annual started this year in month %d. Current month %d. Accrued: %d", 
    #                             annual_start_month, today.month, accrued_new)
    #             else:
    #                 # Full year of annual leave - count completed months only
    #                 last_day_of_month = monthrange(today.year, today.month)[1]
    #                 if today.day == last_day_of_month:
    #                     accrued_new = today.month
    #                 else:
    #                     accrued_new = today.month - 1
    #                 _logger.debug("Full year annual leave. Completed months: %d", accrued_new)
                
    #             # Handle carry forward expiry and leave deduction
    #             if today <= carried_forward_cutoff and carried_forward > 0:
    #                 # Before July - carry forward is still valid
    #                 total_annual = accrued_new + carried_forward
                    
    #                 # Get taken annual leave for current year
    #                 current_annual_leaves = request.env['hr.leave'].sudo().search([
    #                     ('employee_id', '=', employee.id),
    #                     ('holiday_status_id.name', 'ilike', 'annual'),
    #                     ('request_date_from', '>=', start_of_year),
    #                     ('request_date_to', '<=', end_of_year),
    #                     ('state', '=', 'validate'),
    #                 ])
    #                 taken_annual = sum(current_annual_leaves.mapped('number_of_days'))
                    
    #                 # Deduct from carry forward first, then from new accrued
    #                 remaining_carried = max(carried_forward - taken_annual, 0)
    #                 taken_from_new = max(taken_annual - carried_forward, 0)
    #                 remaining_new = max(accrued_new - taken_from_new, 0)
    #                 available_annual = remaining_carried + remaining_new
                    
    #                 _logger.debug("Before June cutoff - Total: %d (carry: %d + new: %d), Taken: %d, Available: %d", 
    #                             total_annual, carried_forward, accrued_new, taken_annual, available_annual)
                
    #             else:
    #                 # After June - carry forward expired, only new accrued leave
    #                 # Get all taken annual leave for current year
    #                 current_annual_leaves = request.env['hr.leave'].sudo().search([
    #                     ('employee_id', '=', employee.id),
    #                     ('holiday_status_id.name', 'ilike', 'annual'),
    #                     ('request_date_from', '>=', start_of_year),
    #                     ('request_date_to', '<=', end_of_year),
    #                     ('state', '=', 'validate'),
    #                 ])
    #                 total_taken_annual = sum(current_annual_leaves.mapped('number_of_days'))
                    
    #                 # Calculate deduction: first from carry forward, then from new accrued
    #                 taken_from_carry = min(total_taken_annual, carried_forward)
    #                 taken_from_new = max(total_taken_annual - carried_forward, 0)
                    
    #                 # After June cutoff: only show new accrued leave as total and available
    #                 total_annual = accrued_new
    #                 taken_annual = taken_from_new  # Only count what was taken from new accrued
    #                 available_annual = max(accrued_new - taken_from_new, 0)
                    
    #                 _logger.debug("After June cutoff - Carried forward: %d, New accrued: %d, Total taken this year: %d, Taken from carry: %d, Taken from new: %d", 
    #                             carried_forward, accrued_new, total_taken_annual, taken_from_carry, taken_from_new)
    #                 _logger.debug("After June cutoff - Showing Total: %d, Taken: %d, Available: %d", 
    #                             total_annual, taken_annual, available_annual)
                
    #             # Calculate pending annual leaves
    #             annual_pending_leaves = request.env['hr.leave'].sudo().search([
    #                 ('employee_id', '=', employee.id),
    #                 ('holiday_status_id.name', 'ilike', 'annual'),
    #                 ('request_date_from', '>=', start_of_year),
    #                 ('request_date_to', '<=', end_of_year),
    #                 ('state', '=', 'confirm'),
    #             ])
    #             pending_annual = sum(annual_pending_leaves.mapped('number_of_days'))

    #             if today <= carried_forward_cutoff:
        
    #                 resp_expired_carried = 0
    #                 resp_carried_forward = carried_forward

    #                 # last_day = calendar.monthrange(today.year, today.month)[1]  
    #                 # end_of_month = date(today.year, today.month, last_day)

    #                 # carry_count = request.env['hr.leave'].sudo().search([
    #                 #     ('employee_id', '=', employee.id),
    #                 #     ('holiday_status_id.name', 'ilike', 'annual'),
    #                 #     ('request_date_from', '>=', start_of_year),
    #                 #     ('request_date_to', '<=', end_of_month),
    #                 #     ('state', '=', 'validate'),
    #                 # ])
    #                 # taken = sum(carry_count.mapped('number_of_days'))
    #                 # resp_carried_forward = carried_forward - taken
    #             else:
    #                 resp_carried_forward = 0
    #                 resp_expired_carried = max(carried_forward - taken_from_carry, 0)


    #         # Medical leave calculation
    #         total_medical = 30
    #         medical_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'medical'),
    #             ('request_date_from', '>=', start_of_year),
    #             ('request_date_to', '<=', end_of_year),
    #             ('state', '=', 'validate'),
    #         ])
    #         taken_medical = sum(medical_leaves.mapped('number_of_days'))
    #         available_medical = max(total_medical - taken_medical, 0)

    #         medical_pending_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'medical'),
    #             ('request_date_from', '>=', start_of_year),
    #             ('request_date_to', '<=', end_of_year),
    #             ('state', '=', 'confirm'),
    #         ])
    #         pending_medical = sum(medical_pending_leaves.mapped('number_of_days'))

    #         # Funeral leave calculation
    #         total_funeral = 7
    #         funeral_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'funeral'),
    #             ('state', '=', 'validate'),
    #         ])
    #         taken_funeral = sum(funeral_leaves.mapped('number_of_days'))
    #         available_funeral = max(total_funeral - taken_funeral, 0)

    #         funeral_pending_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'funeral'),
    #             ('state', '=', 'confirm'),
    #         ])
    #         pending_funeral = sum(funeral_pending_leaves.mapped('number_of_days'))

    #         # Marriage leave calculation
    #         total_marriage = 5
    #         marriage_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'marriage'),
    #             ('state', '=', 'validate'),
    #         ])
            
    #         taken_marriage = sum(marriage_leaves.mapped('number_of_days'))
    #         available_marriage = max(total_marriage - taken_marriage, 0)

    #         marriage_pending_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'marriage'),
    #             ('state', '=', 'confirm'),
    #         ]) 
    #         pending_marriage = sum(marriage_pending_leaves.mapped('number_of_days'))  

    #         # Unpaid leave calculation
    #         total_unpaid = 30
    #         unpaid_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'unpaid'),
    #             ('request_date_from', '>=', start_of_year),
    #             ('request_date_to', '<=', end_of_year),
    #             ('state', '=', 'validate'),
    #         ])
    #         taken_unpaid = sum(unpaid_leaves.mapped('number_of_days'))
    #         available_unpaid = max(total_unpaid - taken_unpaid, 0)

    #         unpaid_pending_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'unpaid'),
    #             ('request_date_from', '>=', start_of_year),
    #             ('request_date_to', '<=', end_of_year),
    #             ('state', '=', 'confirm'),
    #         ])
    #         pending_unpaid = sum(unpaid_pending_leaves.mapped('number_of_days')) 

    #         # Maternity leave calculation
    #         total_maternity = 98
    #         maternity_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'maternity'),
    #             ('state', '=', 'validate'),
    #         ])
    #         taken_maternity = sum(maternity_leaves.mapped('number_of_days'))
    #         available_maternity = max(total_maternity - taken_maternity, 0)

    #         maternity_pending_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'maternity'),
    #             ('state', '=', 'confirm'),
    #         ])
    #         pending_maternity = sum(maternity_pending_leaves.mapped('number_of_days'))    
            
    #         # Paternity leave calculation
    #         total_paternity = 15
    #         paternity_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'paternity'),
    #             ('state', '=', 'validate'),
    #         ])
    #         taken_paternity = sum(paternity_leaves.mapped('number_of_days'))
    #         available_paternity = max(total_paternity - taken_paternity, 0)

    #         paternity_pending_leaves = request.env['hr.leave'].sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('holiday_status_id.name', 'ilike', 'paternity'),
    #             ('state', '=', 'confirm'),
    #         ])
    #         pending_paternity = sum(paternity_pending_leaves.mapped('number_of_days'))        

    #         return {
    #             'success': True,
    #             'casual': {
    #                 'total': total_casual,
    #                 'taken': taken_casual,
    #                 'available': available_casual,
    #                 'pending': pending_casual
    #             },
    #             'annual': {
    #                 'total': total_annual,
    #                 'taken': taken_annual,
    #                 'available': available_annual,
    #                 'pending': pending_annual,
    #                 'carried_forward': resp_carried_forward,
    #                 'expired_carried': resp_expired_carried
                    
    #             },
    #             'medical': {
    #                 'total': total_medical,
    #                 'taken': taken_medical,
    #                 'available': available_medical,
    #                 'pending': pending_medical
    #             },
    #             'funeral': {
    #                 'total': total_funeral,
    #                 'taken': taken_funeral,
    #                 'available': available_funeral,
    #                 'pending': pending_funeral
    #             },
    #             'marriage': {
    #                 'total': total_marriage,
    #                 'taken': taken_marriage,
    #                 'available': available_marriage,
    #                 'pending': pending_marriage
    #             },
    #             'unpaid': {
    #                 'total': total_unpaid,
    #                 'taken': taken_unpaid,
    #                 'available': available_unpaid,
    #                 'pending': pending_unpaid
    #             },
    #             'maternity': {
    #                 'total': total_maternity,
    #                 'taken': taken_maternity,
    #                 'available': available_maternity,
    #                 'pending': pending_maternity
    #             },
    #             'paternity': {
    #                 'total': total_paternity,
    #                 'taken': taken_paternity,
    #                 'available': available_paternity,
    #                 'pending': pending_paternity
    #             }
    #         }

    #     except Exception as e:
    #         _logger.error("Error in get_leave_balance: %s", str(e))
    #         return {'success': False, 'error': 'Internal server error'}

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
            if (not employee_number and not request_date_from) or (not employee_number and not request_date_to):
                return {
                    'success': False,
                    'error': 'Missing required parameters: employee_number, request_date_from, or request_date_to'
                }

            # Ensure dates are strings
            if (not employee_number and not request_date_from) or (not employee_number and not request_date_to):
                return {
                    'success': False,
                    'error': 'Dates must be in string format: YYYY-MM-DD'
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
            _logger.debug("Called /api/leave-balance-with-tracker with kwargs: %s", kwargs)

            employee_number = request.session.get('employee_number')
            if not employee_number:
                _logger.debug("Missing employee_number in request")
                return {'success': False, 'error': 'Missing employee_number'}

            today = date.today()
            current_year = today.year
            _logger.debug("Today's date: %s, Current year: %s", today, current_year)

            employee = request.env['hr.employee'].sudo().search([('id', '=', employee_number)], limit=1)
            if not employee:
                _logger.debug("No employee found with employee_number: %s", employee_number)
                return {'success': False, 'error': 'Employee not found'}

            _logger.debug("Found employee: %s (ID: %s)", employee.name, employee.id)

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
                # Search existing tracker record by employee_id, leave_type_name, and year
                _logger.debug("Processing leave type: %s (%s)", leave_type['name'], leave_type['display_name'])

                tracker_record = request.env['hr.leave.tracker'].sudo().search([
                    ('employee_number', '=', employee.employee_number),
                    ('leave_type_name', '=', leave_type['display_name']),
                    ('year', '=', current_year)
                ], limit=1)

                if tracker_record:
                    # Update existing tracker
                    leave_balance = self._update_existing_record(tracker_record, employee, today)
                else:
                    # Calculate leave balance and create tracker record
                    leave_balance = self._calculate_default_leave_balance(leave_type['display_name'], employee, today)
                    tracker_record = self._create_tracker_record(employee, leave_type, leave_balance, current_year)

                result[leave_type['name']] = leave_balance

            return result

        except Exception as e:
            _logger.error("Error in get_leave_balance_with_tracker: %s", str(e))
            return {'success': False, 'error': 'Internal server error'}
    
    def _get_carry_forward_from_previous_year(self, employee, current_year):
        """Get carry forward with proper historical data handling"""
        previous_year = current_year - 1
        _logger.info(f"Getting carry forward for {employee.name} from {previous_year} to {current_year}")
        
        # Check if previous year is historical
        is_previous_year_historical = self._is_historical_data(previous_year)
        
        # Find previous year's tracker record
        previous_tracker = request.env['hr.leave.tracker'].sudo().search([
            ('employee_id', '=', employee.id),
            ('leave_type_name', '=', 'Annual Leave'),
            ('year', '=', previous_year)
        ], limit=1)
        
        if previous_tracker:
            _logger.info(f"Found previous year tracker: total={previous_tracker.total_allocation}, taken={previous_tracker.taken_leaves}")
            _logger.info(f"Previous year is historical: {is_previous_year_historical}")
            
            if is_previous_year_historical:
                # Use current_balance directly for historical years (this is the actual available balance)
                carry_forward = max(previous_tracker.current_balance, 0)
                _logger.info(f"Using historical tracker data → carry forward: {carry_forward}")
                return carry_forward
            else:
                # For real-time years, verify with hr.leave records
                actual_taken = self._get_actual_taken_leaves(employee.id, 'Annual Leave', previous_year)
                carry_forward = max(previous_tracker.total_allocation - actual_taken, 0)
                _logger.info(f"Using real-time calculation → actual taken: {actual_taken}, carry forward: {carry_forward}")
                return carry_forward
        
        # If no tracker record found and not historical, try to calculate from hr.leave
        if not is_previous_year_historical:
            _logger.info(f"No tracker found for {previous_year}, calculating from hr.leave records")
            previous_allocation = self._calculate_previous_year_allocation(employee, previous_year)
            actual_taken = self._get_actual_taken_leaves(employee.id, 'Annual Leave', previous_year)
            carry_forward = max(previous_allocation - actual_taken, 0)
            _logger.info(f"Calculated from hr.leave → allocation: {previous_allocation}, taken: {actual_taken}, carry forward: {carry_forward}")
            return carry_forward
        
        _logger.info(f"No previous year data found → carry forward: 0")
        return 0

    def _get_system_start_date(self):
        """Define when your system started tracking leaves in hr_leave"""
        return date(2025, 10, 5)

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


    

    def _update_existing_record(self, record, employee, today):
        """Update tracker with proper distinction between historical and real-time data"""
        current_year = today.year
        record_create_date = record.create_date.date() if record.create_date else None
        is_historical = self._is_historical_data(current_year, record_create_date)

        _logger.info(f"Updating tracker for {employee.name} - {record.leave_type_name} - Year: {current_year}")
        _logger.info(f"Record created: {record_create_date}, Is historical: {is_historical}")

        if record.leave_type_name in ['Annual Leave', 'Casual Leave']:
            # Calculate accrual (always dynamic)
            if record.leave_type_name == 'Annual Leave':
                accrual = self._calculate_annual_leave(employee, today)
            else:
                accrual = self._calculate_casual_leave(employee, today)

            if is_historical:
                # Preserve manual taken + add new leaves from hr_leave
                new_taken = self._get_actual_taken_leaves(employee.id, record.leave_type_name, current_year)
                total_taken = record.taken_leaves + new_taken

                # Pending from hr_leave (not frozen)
                actual_pending = self._get_actual_pending_leaves(employee.id, record.leave_type_name, current_year)

                total_allocation = accrual['total']
                available = max(total_allocation - total_taken, 0)

                record.sudo().write({
                    'total_allocation': total_allocation,
                    'taken_leaves': total_taken,
                    'pending_requests': actual_pending,
                    'current_balance': available,
                    'annual_carry': record.annual_carry,
                    'expired_carry': record.expired_carry,
                    'write_date': fields.Datetime.now(),
                    'write_uid': request.env.user.id,
                })

                balance = {
                    'total': total_allocation,
                    'taken': total_taken,
                    'available': available,
                    'pending': actual_pending,
                    'carried_forward': record.annual_carry,
                    'expired_carried': record.expired_carry,
                }
                _logger.info(f"Historical accrual applied (manual + new taken): {balance}")

            else:
                # Real-time → full recalculation
                record.sudo().write({
                    'total_allocation': accrual['total'],
                    'taken_leaves': accrual['taken'],
                    'pending_requests': accrual['pending'],
                    'current_balance': accrual['available'],
                    'annual_carry': accrual.get('carried_forward', 0),
                    'expired_carry': accrual.get('expired_carried', 0),
                    'write_date': fields.Datetime.now(),
                    'write_uid': request.env.user.id,
                })
                balance = accrual
                _logger.info(f"Real-time accrual applied: {balance}")

        else:
            # Fixed/lifetime leave types
            actual_taken = self._get_actual_taken_leaves(employee.id, record.leave_type_name, current_year)
            actual_pending = self._get_actual_pending_leaves(employee.id, record.leave_type_name, current_year)

            record.sudo().write({
                'taken_leaves': actual_taken,
                'pending_requests': actual_pending,
                'current_balance': max(record.total_allocation - actual_taken, 0),
                'write_date': fields.Datetime.now(),
                'write_uid': request.env.user.id,
            })

            balance = {
                'total': record.total_allocation,
                'taken': actual_taken,
                'available': record.current_balance,
                'pending': actual_pending,
                'carried_forward': record.annual_carry,
                'expired_carried': record.expired_carry,
            }

        return balance

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
            return existing_tracker

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
            
        _logger.info(f"Creating new tracker record for {employee.name} - {leave_type['display_name']} - Year: {year} - Historical: {is_historical_year}")
        
        return request.env['hr.leave.tracker'].sudo().create(tracker_data)

    def _handle_manual_tracker_creation(self, tracker_record):
        """Handle when a tracker record is manually created (e.g., for historical data)"""
        
        # If this is a manually created record with historical data
        if tracker_record.taken_leaves > 0:
            current_year = tracker_record.year
            system_start_date = self._get_system_start_date()
            year_start = date(current_year, 1, 1)
            
            # Check if there are corresponding hr_leave records
            actual_taken = self._get_actual_taken_leaves(
                tracker_record.employee_id.id, 
                tracker_record.leave_type_name, 
                current_year
            )
            
            if actual_taken == 0 and tracker_record.taken_leaves > 0 and year_start < system_start_date:
                # This is likely historical data - preserve it
                _logger.info(f"Detected historical data in tracker: {tracker_record.name} - Preserving taken_leaves: {tracker_record.taken_leaves}")
                
                # Mark as historical if field exists
                if hasattr(tracker_record, 'is_historical'):
                    tracker_record.sudo().write({'is_historical': True})
                    
                return True  # Indicates this is historical data
                
        return False  # Indicates this should use system calculations

    def _calculate_default_leave_balance(self, leave_type, employee, today):
        """Calculate leave balance using default logic when no tracker record exists"""
        current_year = today.year

        if leave_type == 'Casual Leave':
            return self._calculate_casual_leave(employee, today)
        elif leave_type == 'Annual Leave':
            return self._calculate_annual_leave(employee, today)
        elif leave_type == 'Medical Leave':
            return self._calculate_fixed_leave(30, employee.id, leave_type, current_year)
        elif leave_type == 'Funeral Leave':
            return self._calculate_lifetime_leave(7, employee.id, leave_type)
        elif leave_type == 'Marriage Leave':
            return self._calculate_lifetime_leave(5, employee.id, leave_type)
        elif leave_type == 'Unpaid Leave':
            return self._calculate_fixed_leave(30, employee.id, leave_type, current_year)
        elif leave_type == 'Maternity Leave':
            return self._calculate_lifetime_leave(98, employee.id, leave_type)
        elif leave_type == 'Paternity Leave':
            return self._calculate_lifetime_leave(15, employee.id, leave_type)
        else:
            return {'total': 0, 'taken': 0, 'available': 0, 'pending': 0}

    def _calculate_casual_leave(self, employee, today):
        """Casual leave accrues monthly with carry forward into next year."""
        current_year = today.year
        start_of_year = date(current_year, 1, 1)
        end_of_year = date(current_year, 12, 31)
        join_date = employee.join_date

        # One-year service milestone (if probation rules apply)
        one_year_service_date = join_date + relativedelta(years=1)
        carried_forward_cutoff = date(current_year, 6, 30)

        _logger.info(f"Calculating casual leave for {employee.name} on {today}")

        # Not eligible until after 1 year service (if rule applies)
        if today < one_year_service_date:
            return {'total': 0, 'taken': 0, 'available': 0, 'pending': 0,
                    'carried_forward': 0, 'expired_carried': 0}

        # Carry forward from previous year
        carried_forward = self._get_carry_forward_from_previous_year(employee, current_year)

        # Accrued casual leave (0.5 per month)
        last_day_of_month = monthrange(today.year, today.month)[1]
        is_end_of_month = today.day == last_day_of_month
        months_completed = today.month if is_end_of_month else today.month - 1
        accrued_new = months_completed * 0.5
        _logger.info(f"Accrued new casual leave: {accrued_new}, Carried forward: {carried_forward}")

        # Total leaves taken
        total_taken = self._get_actual_taken_leaves(employee.id, 'Casual Leave', current_year)
        taken_from_carry = min(total_taken, carried_forward)
        taken_from_new = max(total_taken - carried_forward, 0)

        # Apply carry forward cutoff
        if today <= carried_forward_cutoff and carried_forward > 0:
            total_casual = accrued_new + carried_forward
            taken_casual = total_taken
            available_casual = max(total_casual - taken_casual, 0)
            resp_carried_forward = carried_forward
            resp_expired_carried = 0
        else:
            total_casual = accrued_new
            taken_casual = taken_from_new
            available_casual = max(accrued_new - taken_from_new, 0)
            resp_carried_forward = 0
            resp_expired_carried = max(carried_forward - taken_from_carry, 0)

        # Pending casual leaves
        casual_pending = self._get_actual_pending_leaves(employee.id, 'Casual Leave', current_year)

        # --- Special handling for Jan 1 rollover ---
        if today.month == 1 and today.day == 1:
            total_casual = carried_forward
            taken_casual = 0
            available_casual = carried_forward
            resp_carried_forward = carried_forward
            resp_expired_carried = 0

        result = {
            'total': total_casual,
            'taken': taken_casual,
            'available': available_casual,
            'pending': casual_pending,
            'carried_forward': resp_carried_forward,
            'expired_carried': resp_expired_carried
        }

        _logger.info(f"Final casual leave calculation: {result}")
        return result


    def _calculate_annual_leave(self, employee, today, is_historical=False):
        """Annual leave accrues monthly with carry forward into next year.
        Historical mode preserves taken (no reset on Jan 1).
        """
        current_year = today.year
        start_of_year = date(current_year, 1, 1)
        end_of_year = date(current_year, 12, 31)
        join_date = employee.join_date

        one_year_service_date = join_date + relativedelta(years=1)
        carried_forward_cutoff = date(current_year, 6, 30)

        _logger.info(f"Calculating annual leave for {employee.name} on {today} (historical={is_historical})")

        # Not eligible until 1 year of service
        if today < one_year_service_date:
            return self._empty_annual_leave_result()

        # Carried forward from previous year
        carried_forward = self._get_carry_forward_from_previous_year(employee, current_year)

        # How many months accrued in the current year
        accrued_new = self._calculate_current_year_allocation(employee, today)

        # Total taken leaves this year (from hr_leave)
        total_taken = self._get_actual_taken_leaves(employee.id, 'Annual Leave', current_year)

        # Allocation & availability rules
        if today <= carried_forward_cutoff and carried_forward > 0:
            total_annual = accrued_new + carried_forward
            taken_annual = total_taken
            available_annual = max(total_annual - taken_annual, 0)
            resp_carried_forward = carried_forward
            resp_expired_carried = 0
        else:
            total_annual = accrued_new
            taken_from_new = max(total_taken - carried_forward, 0)
            taken_annual = taken_from_new
            available_annual = max(accrued_new - taken_from_new, 0)
            resp_carried_forward = 0
            resp_expired_carried = max(carried_forward - total_taken, 0)

        # Pending (still in confirm state)
        pending_annual = self._get_pending_annual_leaves(employee, start_of_year, end_of_year)

        # --- Special handling for year rollover ---
        if today.month == 1 and today.day == 1 and not is_historical:
            # Jan 1 reset only for real-time (not historical)
            total_annual = carried_forward
            taken_annual = 0
            available_annual = carried_forward
            resp_carried_forward = carried_forward
            resp_expired_carried = 0

        result = {
            'total': total_annual,
            'taken': taken_annual,
            'available': available_annual,
            'pending': pending_annual,
            'carried_forward': resp_carried_forward,
            'expired_carried': resp_expired_carried
        }

        _logger.info(f"Final annual leave calculation: {result}")
        return result
    
    def _get_pending_annual_leaves(self, employee, start_of_year, end_of_year):
        """Calculate pending annual leaves for an employee in the current year."""
        leaves = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id.name', 'ilike', 'annual'),
            ('request_date_from', '>=', start_of_year),
            ('request_date_to', '<=', end_of_year),
            ('state', '=', 'confirm')
        ])
        return sum(leaves.mapped('number_of_days'))





    def _calculate_current_year_allocation(self, employee, today):
        """Accrues 1 per month, but only after the month is fully completed."""
        join_date = employee.join_date
        one_year_service_date = join_date + relativedelta(years=1)

        if today < one_year_service_date:
            return 0

        if today.year == one_year_service_date.year:
            start_month = one_year_service_date.month
        else:
            start_month = 1

        # Check if today is the last day of the month
        last_day_of_month = monthrange(today.year, today.month)[1]
        is_end_of_month = today.day == last_day_of_month

        # Count only fully completed months
        months_completed = today.month - start_month
        if is_end_of_month:
            months_completed += 1

        return max(months_completed, 0)


    
    def _calculate_previous_year_allocation(self, employee, year):
        """Calculate what the allocation should have been for a previous year"""
        # This is a simplified version - you should implement your actual allocation logic
        join_date = employee.join_date
        one_year_service_date = join_date + relativedelta(years=1)
        
        if year < one_year_service_date.year:
            return 0
        elif year == one_year_service_date.year:
            # Pro-rated allocation based on service start month
            return 12 - one_year_service_date.month + 1
        else:
            # Full year allocation
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
            'pending': pending
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
            'pending': pending
        }

    def _get_actual_taken_leaves(self, employee_id, leave_type, year):
        start_of_year = date(year, 1, 1)
        end_of_year = date(year, 12, 31)

        domain = [
            ('employee_id', '=', employee_id),
            ('holiday_status_id.name', 'ilike', leave_type),
            ('state', '=', 'validate')
        ]
        if leave_type not in ['Funeral Leave', 'Marriage Leave', 'Maternity Leave', 'Paternity Leave']:
            domain += [('request_date_from', '>=', start_of_year), ('request_date_to', '<=', end_of_year)]

        leaves = request.env['hr.leave'].sudo().search(domain)
        return sum(leaves.mapped('number_of_days'))

    def _get_actual_pending_leaves(self, employee_id, leave_type, year):
        start_of_year = date(year, 1, 1)
        end_of_year = date(year, 12, 31)

        domain = [
            ('employee_id', '=', employee_id),
            ('holiday_status_id.name', 'ilike', leave_type),
            ('state', '=', 'confirm')
        ]
        if leave_type not in ['Funeral Leave', 'Marriage Leave', 'Maternity Leave', 'Paternity Leave']:
            domain += [('request_date_from', '>=', start_of_year), ('request_date_to', '<=', end_of_year)]

        leaves = request.env['hr.leave'].sudo().search(domain)
        return sum(leaves.mapped('number_of_days'))