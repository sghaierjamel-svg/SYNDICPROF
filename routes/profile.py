from flask import render_template, request, redirect, url_for, flash
from core import app, db
from utils import current_user, login_required


@app.route('/profile/complete', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """Demande le nom + WhatsApp au résident à sa première connexion."""
    user = current_user()
    if user.role != 'resident':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name  = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()

        if not name:
            flash('Votre nom est obligatoire.', 'danger')
            return redirect(url_for('complete_profile'))

        user.name  = name
        user.phone = phone or user.phone
        db.session.commit()
        flash(f'Bienvenue {name} ! Votre profil est complet.', 'success')
        return redirect(url_for('residents_menu'))

    return render_template('complete_profile.html', user=user)


@app.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    user = current_user()
    if request.method == 'POST':
        current_pwd = request.form.get('current_password', '')
        new_pwd = request.form.get('new_password', '')
        confirm_pwd = request.form.get('confirm_password', '')
        if not user.check_password(current_pwd):
            flash('Mot de passe actuel incorrect.', 'danger')
            return redirect(url_for('change_password'))
        if len(new_pwd) < 6:
            flash('Le nouveau mot de passe doit contenir au moins 6 caractères.', 'danger')
            return redirect(url_for('change_password'))
        if new_pwd != confirm_pwd:
            flash('Les deux nouveaux mots de passe ne correspondent pas.', 'danger')
            return redirect(url_for('change_password'))
        user.set_password(new_pwd)
        db.session.commit()
        flash('Mot de passe changé avec succès !', 'success')
        return redirect(url_for('dashboard'))
    return render_template('profile_change_password.html', user=user)
