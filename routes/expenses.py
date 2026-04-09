import base64
import io
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from core import app, db
from models import Expense, Intervenant
from utils import (current_user, current_organization, login_required,
                   admin_required, subscription_required)
from datetime import datetime, date

MAX_FACTURE_BYTES = 5 * 1024 * 1024   # 5 Mo
ALLOWED_MIMES = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}


def _iv_label(iv):
    """Construit le libellé affiché pour un intervenant."""
    name = ''
    if iv.nom_societe:
        name = iv.nom_societe
    else:
        parts = [p for p in [iv.prenom, iv.nom] if p]
        name = ' '.join(parts)
    return f"{iv.categorie} - {name}" if name else iv.categorie


def _handle_facture(request_files, existing_data=None, existing_mime=None, existing_nom=None):
    """Lit le fichier facture du formulaire. Retourne (data_b64, mime, nom) ou None si aucun fichier."""
    f = request_files.get('facture')
    if not f or f.filename == '':
        # Pas de nouveau fichier — on garde l'existant
        return existing_data, existing_mime, existing_nom
    mime = f.mimetype
    if mime not in ALLOWED_MIMES:
        flash('Format non accepté. Utilisez une image (JPG, PNG) ou un PDF.', 'warning')
        return existing_data, existing_mime, existing_nom
    raw = f.read()
    if len(raw) > MAX_FACTURE_BYTES:
        flash('Fichier trop lourd (max 5 Mo).', 'warning')
        return existing_data, existing_mime, existing_nom
    return base64.b64encode(raw).decode('utf-8'), mime, f.filename


@app.route('/expenses', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def expenses():
    org = current_organization()
    intervenants = Intervenant.query.filter_by(organization_id=org.id)\
        .order_by(Intervenant.categorie, Intervenant.nom_societe, Intervenant.nom).all()

    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            if amount <= 0 or amount > 9_999_999:
                flash('Montant invalide (doit être > 0 et < 10 000 000 DT).', 'danger')
                return redirect(url_for('expenses'))
            expense_date = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
            description  = request.form.get('description', '')[:300]

            # Catégorie : soit un intervenant (iv:ID), soit une catégorie fixe
            raw_cat      = request.form.get('category', 'Autre')
            intervenant_id = None
            if raw_cat.startswith('iv:'):
                iv_id = int(raw_cat[3:])
                iv = Intervenant.query.filter_by(id=iv_id, organization_id=org.id).first()
                if iv:
                    intervenant_id = iv.id
                    category = _iv_label(iv)
                else:
                    category = 'Autre'
            else:
                category = raw_cat

            # Facture
            facture_data, facture_mime, facture_nom = _handle_facture(request.files)

            e = Expense(
                organization_id=org.id,
                amount=amount,
                expense_date=expense_date,
                category=category,
                description=description,
                intervenant_id=intervenant_id,
                facture_data=facture_data,
                facture_mime=facture_mime,
                facture_nom=facture_nom,
            )
            db.session.add(e)
            db.session.commit()
            flash('Dépense enregistrée', 'success')
        except Exception as ex:
            print(f"ERREUR dépense: {ex}")
            flash('Une erreur est survenue. Réessayez.', 'danger')
        return redirect(url_for('expenses'))

    expenses_list = Expense.query.filter_by(organization_id=org.id)\
        .order_by(Expense.expense_date.desc()).all()
    return render_template('expenses.html',
                           expenses=expenses_list,
                           intervenants=intervenants,
                           user=current_user())


@app.route('/expense/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def edit_expense(expense_id):
    org = current_organization()
    e = Expense.query.filter_by(id=expense_id, organization_id=org.id).first_or_404()
    intervenants = Intervenant.query.filter_by(organization_id=org.id)\
        .order_by(Intervenant.categorie, Intervenant.nom_societe, Intervenant.nom).all()

    if request.method == 'POST':
        e.amount       = float(request.form['amount'])
        e.expense_date = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
        e.description  = request.form.get('description', '')

        raw_cat = request.form.get('category', 'Autre')
        if raw_cat.startswith('iv:'):
            iv_id = int(raw_cat[3:])
            iv = Intervenant.query.filter_by(id=iv_id, organization_id=org.id).first()
            if iv:
                e.intervenant_id = iv.id
                e.category = _iv_label(iv)
            else:
                e.intervenant_id = None
                e.category = 'Autre'
        else:
            e.intervenant_id = None
            e.category = raw_cat

        # Facture : nouveau fichier ou suppression
        if request.form.get('supprimer_facture') == '1':
            e.facture_data = None
            e.facture_mime = None
            e.facture_nom  = None
        else:
            e.facture_data, e.facture_mime, e.facture_nom = _handle_facture(
                request.files, e.facture_data, e.facture_mime, e.facture_nom)

        db.session.commit()
        flash('Dépense modifiée', 'success')
        return redirect(url_for('expenses'))

    return render_template('edit_expense.html',
                           expense=e,
                           intervenants=intervenants,
                           user=current_user())


@app.route('/expense/<int:expense_id>/facture')
@login_required
@admin_required
@subscription_required
def expense_facture(expense_id):
    """Affiche ou télécharge la facture jointe à une dépense."""
    org = current_organization()
    e = Expense.query.filter_by(id=expense_id, organization_id=org.id).first_or_404()
    if not e.facture_data:
        abort(404)
    raw = base64.b64decode(e.facture_data)
    buf = io.BytesIO(raw)
    buf.seek(0)
    download = request.args.get('dl', '0') == '1'
    filename = e.facture_nom or f"facture_{expense_id}"
    return send_file(buf, mimetype=e.facture_mime,
                     as_attachment=download, download_name=filename)


@app.route('/expense/nouvelle-immobilisation', methods=['GET', 'POST'])
@login_required
@admin_required
@subscription_required
def nouvelle_immobilisation():
    org = current_organization()
    if request.method == 'POST':
        try:
            amount        = float(request.form['amount'])
            expense_date  = datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date()
            asset_name    = request.form.get('asset_name', '').strip()
            supplier      = request.form.get('supplier', '').strip()
            invoice_num   = request.form.get('invoice_number', '').strip()
            duration      = request.form.get('duration_years', '5')
            notes         = request.form.get('notes', '').strip()

            try:
                taux = round(1 / int(duration) * 100, 1)
                dotation = round(amount / int(duration), 3)
            except (ValueError, ZeroDivisionError):
                taux, dotation = 20.0, round(amount / 5, 3)

            parts = [f"Bien: {asset_name}"]
            if supplier:
                parts.append(f"Fourn.: {supplier}")
            if invoice_num:
                parts.append(f"Facture: {invoice_num}")
            parts.append(f"Amort.: {duration} ans ({taux}%) - Dot./an: {dotation:.3f} DT")
            if notes:
                parts.append(f"Note: {notes}")
            description = " | ".join(parts)

            facture_data, facture_mime, facture_nom = _handle_facture(request.files)

            e = Expense(
                organization_id=org.id,
                amount=amount,
                expense_date=expense_date,
                category='Immobilisation',
                description=description,
                facture_data=facture_data,
                facture_mime=facture_mime,
                facture_nom=facture_nom,
            )
            db.session.add(e)
            db.session.commit()
            flash(f'Immobilisation "{asset_name}" enregistrée ({amount:.3f} DT, amort. {duration} ans).', 'success')
        except Exception as ex:
            print(f"ERREUR immobilisation: {ex}")
            flash('Une erreur est survenue. Réessayez.', 'danger')
        return redirect(url_for('expenses'))

    prefill_amount = request.args.get('amount', '')
    prefill_date   = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    return render_template('new_asset.html',
                           user=current_user(),
                           prefill_amount=prefill_amount,
                           prefill_date=prefill_date)


@app.route('/expense/delete/<int:expense_id>', methods=['POST'])
@login_required
@admin_required
@subscription_required
def delete_expense(expense_id):
    org = current_organization()
    e = Expense.query.filter_by(id=expense_id, organization_id=org.id).first_or_404()
    db.session.delete(e)
    db.session.commit()
    flash('Dépense supprimée', 'success')
    return redirect(url_for('expenses'))
