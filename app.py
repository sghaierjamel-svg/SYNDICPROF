from core import app, db
import os
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
import routes.flouci
import routes.ai
import routes.automation
import routes.access
import routes.financial_statements
import routes.announcements
import routes.assembly
import routes.intervenants
import routes.litiges


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
    # CRIT-002 : debug=False en production
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))
