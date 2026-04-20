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
import routes.appel_fonds
import routes.onboarding
import routes.push
import routes.lifts
import routes.payment_requests
import routes.messaging
import routes.badges
import routes.analytics


@app.after_request
def _track_page_view(response):
    from utils_analytics import track_visit
    return track_visit(response)


@app.before_request
def _daily_subscription_reminders():
    """Envoie les rappels d'expiration d'abonnement une fois par jour."""
    from datetime import date
    from models import SuperAdminSettings, Organization, Subscription
    from utils_email import send_subscription_reminder
    try:
        settings = SuperAdminSettings.get()
        today = date.today()
        if settings.last_reminder_check == today:
            return  # déjà traité aujourd'hui
        settings.last_reminder_check = today
        db.session.commit()
        # Chercher les orgs dont l'abonnement expire dans 7 ou 1 jour
        for sub in Subscription.query.filter(Subscription.end_date.isnot(None)).all():
            days = sub.days_remaining()
            if days in (7, 1):
                org = sub.organization
                if org and org.email:
                    try:
                        send_subscription_reminder(org.name, org.email, days)
                    except Exception:
                        pass
    except Exception:
        pass


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
