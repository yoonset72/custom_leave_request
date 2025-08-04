{
    "name": "Employee Portal Registration",
    "summary": "Allows employees to self-register using Employee ID and set password for portal use",
    "version": "15.0.1.0.0",
    "category": "Human Resources",
    "author": "AGB Communication",
    "depends": ["base", "hr", "website", "hr_holidays" ],
    "data": [
        "security/ir.model.access.csv",
        "views/register_template.xml",
        "views/employee_profile_template.xml",
        "views/leave_request_form_template.xml",
        "views/hr_leave_tree.xml"
    ],
    'assets': {
        'web.assets_frontend': [
            'custom_leave_request/static/src/js/register.js',
            'custom_leave_request/static/src/css/register.css',
            'custom_leave_request/static/src/js/profile.js',
            'custom_leave_request/static/src/css/leave_request.css',
            'custom_leave_request/static/src/js/leave_request.js',
        ],
    },
    "application": True,
    "installable": True,
    "license": "LGPL-3",
    "description": """
        This module adds a portal registration system for employees using their Employee ID and a custom password.
        After successful registration, employees can log in and, in the future, request leave and manage attendance.
    """,
}