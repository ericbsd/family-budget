"""Web blueprint for serving HTML templates."""
from flask import Blueprint, render_template

web_bp = Blueprint('web', __name__)


@web_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@web_bp.route('/transactions')
def transactions():
    return render_template('transactions.html')


@web_bp.route('/upload')
def upload():
    return render_template('upload.html')


@web_bp.route('/categories')
def categories():
    return render_template('categories.html')