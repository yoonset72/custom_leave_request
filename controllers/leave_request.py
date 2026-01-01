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

    @http.route('/api/leave-balance', type='json', auth='public', methods=['POST'], csrf=False)
    def get_leave_balance(self, **kwargs):
        try:
            _logger.debug("Called /api/leave-balance with kwargs: %s", kwargs)

            employee_number = request.session.get('employee_number')
            if not employee_number:
                _logger.debug("Missing employee_number in request")
                return {'success': False, 'error': 'Missing employee_number'}

            today = date.today()
            current_year = today.year
            _logger.debug("Today's date: %s, Current year: %s", today, current_year)

            

            # Casual leave logic
            # total_casual = today.month / 2
            start_of_year = date(current_year, 1, 1)
            end_of_year = date(current_year, 12, 31)

            employee = request.env['hr.employee'].sudo().search([
                ('id', '=', employee_number)
            ], limit=1)

            if employee.join_date:
                join_date = employee.join_date  # Already a datetime.date object
                today = datetime.today().date()  # Make sure both are date objects
                service_duration = relativedelta(today, join_date)

            if today.year == join_date.year:
                total_casual = (13 - join_date.month)/2
            else:
                total_casual = 6

            if not employee:
                _logger.debug("No employee found with employee_number: %s", employee_number)
                return {'success': False, 'error': 'Employee not found'}

            _logger.debug("Found employee: %s (ID: %s)", employee.name, employee.id)

            # Calculate approved casual leaves
            casual_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'casual'),
                ('request_date_from', '>=', start_of_year),
                ('request_date_to', '<=', end_of_year),
                ('state', '=', 'validate'),
            ])

            # Calculate pending casual leaves
            casual_pending_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'casual'),
                ('request_date_from', '>=', start_of_year),
                ('request_date_to', '<=', end_of_year),
                ('state', '=', 'confirm'),
            ])

            taken_casual = sum(casual_leaves.mapped('number_of_days'))
            available_casual = max(total_casual - taken_casual, 0)
            pending_casual = sum(casual_pending_leaves.mapped('number_of_days'))
          
            carried_forward_cutoff = date(current_year, 6, 30)
            start_of_year = date(current_year, 1, 1)

            # Determine new accrued leave
            if service_duration.years == 1:
                months_passed = today.month - join_date.month
            else:
                months_passed = today.month

            accrued_new = months_passed  # 1 day per month

            # Find last year carried forward balance (only until June)
            previous_year = current_year - 1
            prev_start = date(previous_year, 1, 1)
            prev_end = date(previous_year, 12, 31)

            prev_annual_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'annual'),
                ('request_date_from', '>=', prev_start),
                ('request_date_to', '<=', prev_end),
                ('state', '=', 'validate'),
            ])
            prev_taken = sum(prev_annual_leaves.mapped('number_of_days'))
            prev_total = 12  # Assuming max earned was 12
            carried_forward = max(prev_total - prev_taken, 0)

            # Carried forward only valid until June
            if today <= carried_forward_cutoff:
                effective_carried = carried_forward
            else:
                effective_carried = 0

            total_annual = accrued_new + effective_carried
            _logger.info("Accured new %d", accrued_new)
            _logger.info("Carry %d", effective_carried)
            _logger.info("current month %d", today.month)

            # Taken in this year
            current_annual_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'annual'),
                ('request_date_from', '>=', start_of_year),
                ('request_date_to', '<=', end_of_year),
                ('state', '=', 'validate'),
            ])

            annual_pending_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'annual'),
                ('request_date_from', '>=', start_of_year),
                ('request_date_to', '<=', end_of_year),
                ('state', '=', 'confirm'),
            ])
            taken_annual = sum(current_annual_leaves.mapped('number_of_days'))
            available_annual = max(total_annual - taken_annual, 0)
            pending_annual = sum(annual_pending_leaves.mapped('number_of_days'))

            total_medical = 30
            medical_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'medical'),
                ('request_date_from', '>=', start_of_year),
                ('request_date_to', '<=', end_of_year),
                ('state', '=', 'validate'),
            ])
            taken_medical = sum(medical_leaves.mapped('number_of_days'))
            available_medical = max(total_medical - taken_medical, 0)

            medical_pending_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'medical'),
                ('request_date_from', '>=', start_of_year),
                ('request_date_to', '<=', end_of_year),
                ('state', '=', 'confirm'),
            ])
            pending_medical = sum(medical_pending_leaves.mapped('number_of_days'))

            total_funeral = 7
            funeral_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'funeral'),
                ('state', '=', 'validate'),
            ])
            taken_funeral = sum(funeral_leaves.mapped('number_of_days'))
            available_funeral = max(total_funeral - taken_funeral, 0)

            funeral_pending_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'funeral'),
                ('state', '=', 'confirm'),
            ])
            pending_funeral = sum(funeral_pending_leaves.mapped('number_of_days'))

            total_marriage = 5
            marriage_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'marriage'),
                ('state', '=', 'validate'),
            ])
            
            taken_marriage = sum(marriage_leaves.mapped('number_of_days'))
            available_marriage = max(total_marriage - taken_marriage, 0)

            marriage_pending_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'marriage'),
                ('state', '=', 'confirm'),
            ]) 
            pending_marriage = sum(marriage_pending_leaves.mapped('number_of_days'))  

            total_unpaid = 30
            unpaid_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'unpaid'),
                ('request_date_from', '>=', start_of_year),
                ('request_date_to', '<=', end_of_year),
                ('state', '=', 'validate'),
            ])
            taken_unpaid = sum(unpaid_leaves.mapped('number_of_days'))
            available_unpaid = max(total_unpaid - taken_unpaid, 0)

            unpaid_pending_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'unpaid'),
                ('request_date_from', '>=', start_of_year),
                ('request_date_to', '<=', end_of_year),
                ('state', '=', 'confirm'),
            ])
            pending_unpaid = sum(unpaid_pending_leaves.mapped('number_of_days')) 

            total_maternity = 98
            maternity_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'maternity'),
                ('state', '=', 'validate'),
            ])
            taken_maternity = sum(maternity_leaves.mapped('number_of_days'))
            available_maternity = max(total_maternity - taken_maternity, 0)

            maternity_pending_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'maternity'),
                ('state', '=', 'confirm'),
            ])
            pending_maternity = sum(maternity_pending_leaves.mapped('number_of_days'))    
            
            total_paternity = 15
            paternity_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'paternity'),
                ('state', '=', 'validate'),
            ])
            taken_paternity = sum(paternity_leaves.mapped('number_of_days'))
            available_paternity = max(total_paternity - taken_paternity, 0)

            paternity_pending_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id.name', 'ilike', 'paternity'),
                ('state', '=', 'confirm'),
            ])
            pending_paternity = sum(paternity_pending_leaves.mapped('number_of_days'))        

            return {
                'success': True,
                'casual': {
                    'total': total_casual,
                    'taken': taken_casual,
                    'available': available_casual,
                    'pending': pending_casual
                },
                'annual': {
                    'total': total_annual,
                    'taken': taken_annual,
                    'available': available_annual,
                    'pending': pending_annual
                },
                'medical': {
                    'total': total_medical,
                    'taken': taken_medical,
                    'available': available_medical,
                    'pending': pending_medical
                },
                'funeral': {
                    'total': total_funeral,
                    'taken': taken_funeral,
                    'available': available_funeral,
                    'pending': pending_funeral
                },
                'marriage': {
                    'total': total_marriage,
                    'taken': taken_marriage,
                    'available': available_marriage,
                    'pending': pending_marriage
                },
                'unpaid': {
                    'total': total_unpaid,
                    'taken': taken_unpaid,
                    'available': available_unpaid,
                    'pending': pending_unpaid
                },
                'maternity': {
                    'total': total_maternity,
                    'taken': taken_maternity,
                    'available': available_maternity,
                    'pending': pending_maternity
                },
                'paternity': {
                    'total': total_paternity,
                    'taken': taken_paternity,
                    'available': available_paternity,
                    'pending': pending_paternity
                }
            }

        except Exception as e:
            _logger.exception("Error in leave balance API: %s", str(e))
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

