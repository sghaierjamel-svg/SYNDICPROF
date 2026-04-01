from flask import render_template, redirect, url_for
from core import app
from models import Apartment
from utils import current_user, current_organization, login_required


@app.route('/subscription')
@login_required
def subscription_status():
    user = current_user()
    org = current_organization()
    if not org:
        return redirect(url_for('dashboard'))
    subscription = org.subscription
    apartments_count = Apartment.query.filter_by(organization_id=org.id).count()
    recommended_price = subscription.calculate_price(apartments_count) if subscription else 0
    return render_template('subscription_status.html', user=user, org=org, subscription=subscription, apartments_count=apartments_count, recommended_price=recommended_price)
