from odoo import http
from odoo.http import request
import logging
from datetime import datetime 
_logger = logging.getLogger(__name__)

class EmployeePortal(http.Controller):

    @http.route('/employee/register', type='http', auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def employee_register(self, **kwargs):
        _logger.info("Rendering employee register template with context: %s", kwargs)

        if http.request.httprequest.method == 'POST':
            input_emp_id = kwargs.get('employee_number')
            password = kwargs.get('password')
            new_password = kwargs.get('new_password')
            forgot = kwargs.get('forgot')

            employee = request.env['hr.employee'].sudo().search([('employee_number', '=', input_emp_id)], limit=1)

            _logger.info("Incoming employee data: %s", employee)
            if not employee:
                # Wrong Employee ID
                return request.render('custom_leave_request.register_template', {
                    'error': 'Employee ID not found.',
                    'employee_number': input_emp_id,
                    'forgot': False,
                })

            login_record = request.env['employee.login'].sudo().search([('employee_number', '=', employee.id)], limit=1)

            if not login_record:
                # Register new employee login
                request.env['employee.login'].sudo().create({
                    'employee_number': employee.id,
                    'password': password
                })
                request.session['employee_number'] = employee.id
                return request.redirect('/employee/profile')

            if forgot:
                # Only show reset template if user explicitly clicked "Forgot Password"
                if not new_password:
                    return request.render('custom_leave_request.register_template', {
                        'error': 'Please enter a new password.',
                        'employee_number': input_emp_id,
                        'forgot': True
                    })
                login_record.sudo().write({'password': new_password})
                return request.render('custom_leave_request.register_template', {
                    'success': 'Password updated successfully. Please log in again.',
                    'employee_number': input_emp_id,
                    'forgot': False
                })
            else:
                # User is trying to login
                if login_record.password == password:
                    request.session['employee_number'] = employee.id
                    return request.redirect('/employee/profile')
                else:
                    # Correct ID but wrong password, show noti, do NOT show reset template
                    return request.render('custom_leave_request.register_template', {
                        'error': 'Wrong password.',
                        'employee_number': input_emp_id,
                        'forgot': False
                    })
        else:
            # GET method - show form
            employee_number = kwargs.get('employee_number', '')
            forgot = kwargs.get('forgot', '')
            return request.render('custom_leave_request.register_template', {
                'employee_number': employee_number,
                'forgot': forgot.lower() in ['1', 'true', 'yes'],
            })


    @http.route('/employee/profile', type='http', auth='public', website=True)
    def employee_profile(self, **kwargs):
        employee_number = request.session.get('employee_number')

        if not employee_number:
            return request.redirect('/employee/register')

        employee = request.env['hr.employee'].sudo().browse(employee_number)
        if not employee.exists():
            return request.not_found()

        return request.render('custom_leave_request.employee_profile_template', {
            'employee': employee,
        })


    @http.route('/employee/profile/update', type='json', auth='public', methods=['POST'], csrf=False)
    def update_employee_profile(self):
        post = request.jsonrequest
        try:
            employee_number = request.session.get('employee_number')
            if not employee_number:
                return {'success': False, 'error': 'Not logged in or session expired.'}

            employee = request.env['hr.employee'].sudo().browse(employee_number)
            if not employee.exists():
                return {'success': False, 'error': 'Employee record not found.'}


            section = post.get('section', '')
            _logger.info("Updating section: %s for employee: %s", section, employee.name)
            _logger.info("Incoming POST data: %s", post)

            values = {}

            if section == 'personal':
                # Basic fields
                if post.get('name'):
                    values['name'] = post.get('name')
                if post.get('gender'):
                    values['gender'] = post.get('gender')
                if post.get('nrc_full'):
                    values['nrc_full'] = post.get('nrc_full')
                if post.get('marital'):
                    values['marital'] = post.get('marital')
                if post.get('permit_no'):
                    values['permit_no'] = post.get('permit_no')

                # Nationality (country_id) - resolve by name
                if post.get('country_id'):
                    country = request.env['res.country'].sudo().search([('name', '=', post.get('country_id'))], limit=1)
                    if country:
                        values['country_id'] = country.id

                # Birthday (date)
                if post.get('birthday'):
                    try:
                        values['birthday'] = datetime.strptime(post.get('birthday'), '%Y-%m-%d').date()
                    except ValueError as e:
                        _logger.warning("Invalid birthday format: %s", e)

            elif section == 'education':
                if post.get('certificate'):
                    values['certificate'] = post.get('certificate')
                if post.get('study_field'):
                    values['study_field'] = post.get('study_field')
                if post.get('personal_phone'):
                    values['personal_phone'] = post.get('personal_phone')
                if post.get('personal_email'):
                    values['personal_email'] = post.get('personal_email')
                if post.get('home_address'):
                    values['home_address'] = post.get('home_address')

            elif section == 'work':
                if post.get('job_title'):
                    values['job_title'] = post.get('job_title')
                if post.get('work_email'):
                    values['work_email'] = post.get('work_email')

            if values:
                employee.sudo().write(values)
                request.env.cr.commit()
                _logger.info("Profile updated for employee: %s", employee.name)
            else:
                _logger.info("No fields to update for employee: %s", employee.name)

            # Prepare updated data for frontend refresh
            updated_data = {
                'name': employee.name or '',
                'gender': employee.gender or '',
                'birthday': employee.birthday.strftime('%Y-%m-%d') if employee.birthday else '',
                'nrc_full': employee.nrc_full or '',
                'marital': employee.marital or '',
                'permit_no': employee.permit_no or '',
                'country_id': employee.country_id.name if employee.country_id else '',
                'certificate': employee.certificate or '',
                'study_field': employee.study_field or '',
                'personal_phone': employee.personal_phone or '',
                'personal_email': employee.personal_email or '',
                'home_address': employee.home_address or '',
                'job_title': employee.job_title or '',
                'work_email': employee.work_email or '',
            }

            return {
                'success': True,
                'message': 'Profile updated successfully',
                'updated_data': updated_data
            }

        except Exception as e:
            _logger.exception("Error updating employee profile: %s", str(e))
            request.env.cr.rollback()
            return {
                'success': False,
                'error': f'Failed to update profile: {str(e)}'
            }

    # @http.route('/employee/congrats', type='http', auth='public', website=True)
    # def employee_congrats(self, **kwargs):
    #     return request.render('custom_leave_request.congrats_template')

    @http.route('/custom__leave__request/custom__leave__request', auth='public', website=True)
    def index(self, **kw):
        return "Hello, world"
