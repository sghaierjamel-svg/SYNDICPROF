from core import app, db
import models
import utils
import routes.auth
import routes.dashboard
import routes.apartments
import routes.payments
import routes.expenses
import routes.reports
import routes.tickets
import routes.users
import routes.superadmin
import routes.subscription
import routes.profile
import routes.settings
import routes.konnect
import routes.ai
import routes.automation
import routes.access
import routes.financial_statements


@app.errorhandler(404)
def not_found_error(error):
    from flask import render_template
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    from flask import render_template
    db.session.rollback()
    return render_template('500.html'), 500


with app.app_context():
    models.init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
