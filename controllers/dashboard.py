from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class DashboardController(http.Controller):

    @http.route('/api/my-leave-requests', type='json', auth='user', methods=['GET'], csrf=False)
    def get_my_leave_requests(self):
        """Fetch leave requests for the currently logged-in user"""
        try:
            employee = request.env.user.employee_id
            if not employee:
                return {'success': False, 'error': 'Employee not linked to user'}

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
