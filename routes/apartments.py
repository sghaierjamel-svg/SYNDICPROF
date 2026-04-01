from flask import render_template, request, redirect, url_for, flash
from core import app, db
from models import Block, Apartment
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required,
                   get_unpaid_months_count, get_next_unpaid_month)


@app.route('/apartments', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def apartments():
    org = current_organization()
    blocks = Block.query.filter_by(organization_id=org.id).all()
    if request.method == 'POST':
        if request.form.get('action') == 'add_block':
            name = request.form['block_name'].strip()
            if name and not Block.query.filter_by(organization_id=org.id, name=name).first():
                b = Block(name=name, organization_id=org.id)
                db.session.add(b)
                db.session.commit()
                flash(f'Bloc {name} ajouté', 'success')
        elif request.form.get('action') == 'add_apartment':
            current_count = Apartment.query.filter_by(organization_id=org.id).count()
            if org.subscription and current_count >= org.subscription.max_apartments:
                flash(f'Limite atteinte: {org.subscription.max_apartments} appartements max pour votre plan', 'warning')
                return redirect(url_for('apartments'))
            number = request.form['apt_number'].strip()
            block_id = request.form.get('block_id')
            monthly_fee = request.form.get('monthly_fee', 100.0)
            if number and block_id:
                try:
                    a = Apartment(
                        organization_id=org.id,
                        number=number,
                        block_id=int(block_id),
                        monthly_fee=float(monthly_fee),
                        credit_balance=0.0
                    )
                    db.session.add(a)
                    db.session.commit()
                    flash(f'Appartement {number} ajouté', 'success')
                except ValueError:
                    flash('Erreur de saisie', 'danger')
        return redirect(url_for('apartments'))
    for block in blocks:
        for apt in block.apartments:
            apt.unpaid_count = get_unpaid_months_count(apt.id)
            apt.next_unpaid = get_next_unpaid_month(apt.id)
    return render_template('apartments.html', blocks=blocks, user=current_user(), org=org)


@app.route('/apartment/edit/<int:apartment_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def edit_apartment(apartment_id):
    org = current_organization()
    apt = Apartment.query.filter_by(id=apartment_id, organization_id=org.id).first_or_404()
    blocks = Block.query.filter_by(organization_id=org.id).all()
    if request.method == 'POST':
        apt.number = request.form['apt_number']
        apt.block_id = int(request.form['block_id'])
        apt.monthly_fee = float(request.form.get('monthly_fee', 100.0))
        db.session.commit()
        flash('Appartement modifié', 'success')
        return redirect(url_for('apartments'))
    return render_template('edit_apartment.html', apartment=apt, blocks=blocks, user=current_user())


@app.route('/apartment/delete/<int:apartment_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def delete_apartment(apartment_id):
    org = current_organization()
    apt = Apartment.query.filter_by(id=apartment_id, organization_id=org.id).first_or_404()
    db.session.delete(apt)
    db.session.commit()
    flash('Appartement supprimé', 'success')
    return redirect(url_for('apartments'))
