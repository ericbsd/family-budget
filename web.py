"""Web blueprint - server-side rendered pages with Jinja2."""
import json
from datetime import datetime, UTC
from bson import ObjectId
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    g,
)
from pymongo.errors import DuplicateKeyError
from werkzeug.utils import secure_filename

from models.transaction import Transaction
from models.category import Category
from models.account import Account, VALID_TYPES as ACCOUNT_TYPES, TYPE_LABELS as ACCOUNT_TYPE_LABELS
from utils.db import mongo
from utils.csv_parser import CSVParser, allowed_file
from utils.categorization import AutoCategorizer
from utils.aggregations import Aggregations
from utils.transaction_importer import process_transactions

web_bp = Blueprint('web', __name__)

PAGE_SIZE = 50
MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']


def _parse_date(s: str) -> datetime | None:
    """
    Parse a YYYY-MM-DD string to datetime, or return None.

    Args:
        s: Date string in YYYY-MM-DD format

    Returns:
        Parsed datetime, or None if the string is empty or invalid
    """
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        return None


def _resolve_period(periods: list, year: int, now: datetime) -> tuple:
    """
    Return (year, month) to display on the dashboard.

    Picks the most recent month with data for the given year, falling back
    to the most recent period overall, then to the current month.

    Args:
        periods: List of period dicts with 'year' and 'month' keys
        year: The selected year from the query string
        now: Current datetime used as fallback

    Returns:
        tuple: (year, month) integers
    """
    if request.args.get('month'):
        return year, int(request.args.get('month'))
    ym = [p['month'] for p in periods if p['year'] == year]
    if ym:
        return year, max(ym)
    if periods:
        return periods[0]['year'], periods[0]['month']
    return year, now.month


def _build_transaction_query(
    start_date: str,
    end_date: str,
    category_id: str,
    account_id: str,
) -> dict:
    """
    Build a MongoDB filter dict from transaction filter parameters.

    Args:
        start_date: Start date (YYYY-MM-DD) or empty string
        end_date: End date (YYYY-MM-DD) or empty string
        category_id: Category ID or empty string
        account_id: Account ID or empty string

    Returns:
        MongoDB query dict
    """
    query = {}
    date_query = {}
    date = _parse_date(start_date)
    if date:
        date_query['$gte'] = date
    date = _parse_date(end_date)
    if date:
        date_query['$lte'] = date.replace(hour=23, minute=59, second=59)
    if date_query:
        query['date'] = date_query
    if category_id:
        try:
            query['category_id'] = int(category_id)
        except ValueError:
            pass
    if account_id:
        try:
            query['account_id'] = int(account_id)
        except ValueError:
            pass
    return query


# ── Dashboard ─────────────────────────────────────────────────────
@web_bp.route('/dashboard')
def dashboard():
    """Render the main dashboard for a selected month/year."""
    now = datetime.now()
    pipeline = [
        {'$group': {'_id': {'year': {'$year': '$date'}, 'month': {'$month': '$date'}}}},
        {'$sort': {'_id.year': -1, '_id.month': -1}},
    ]
    periods = [{'year': p['_id']['year'], 'month': p['_id']['month']}
               for p in mongo.db.transactions.aggregate(pipeline)]

    year = int(request.args.get('year', now.year))
    year, month = _resolve_period(periods, year, now)

    start_date, end_date = Aggregations.get_date_range(year, month=month)
    stats = Aggregations.get_summary_stats(mongo, start_date, end_date)
    uncat_count = mongo.db.transactions.count_documents({'category_id': 0})
    category_data = Aggregations.aggregate_by_category(mongo, start_date, end_date)
    budget_status = Aggregations.calculate_budget_status(mongo, year, month)
    trend_data = Aggregations.get_spending_trend(mongo, year, months=6)
    top_merchants = Aggregations.get_top_merchants(mongo, start_date, end_date, limit=10)
    years = sorted({p['year'] for p in periods}, reverse=True) or [now.year]
    months = sorted({p['month'] for p in periods if p['year'] == year}, reverse=True) or [month]

    return render_template(
        'dashboard.html',
        year=year,
        month=month,
        month_name=MONTH_NAMES[month - 1],
        stats=stats,
        uncat_count=uncat_count,
        category_data=category_data,
        budget_status=budget_status,
        trend_data=trend_data,
        top_merchants=top_merchants,
        years=years,
        months=months,
        month_names=MONTH_NAMES,
        category_json=json.dumps(category_data),
        trend_json=json.dumps(trend_data),
    )


def _enrich_transactions(transaction_list: list) -> tuple:
    """
    Enrich each transaction dict with category, account, and formatted date fields.

    Fetches categories and accounts from the database using field projections,
    caches the results on the Flask request context via ``g`` to avoid redundant
    queries within the same request, and adds 'category', 'account', '_id_str',
    'date_str', and 'date_fmt' to each transaction in place.

    Args:
        transaction_list: List of transaction documents from MongoDB.

    Returns:
        tuple: (all_categories, all_accounts) lists for use in templates.
    """
    projection = {'_id': 0, 'id': 1, 'name': 1, 'color': 1}

    if not hasattr(g, 'category_map'):
        g.category_map = {
            category['id']: category
            for category in mongo.db.categories.find({}, projection).sort('id', 1)
        }
    if not hasattr(g, 'account_map'):
        g.account_map = {
            account['id']: account
            for account in mongo.db.accounts.find({}, projection).sort('id', 1)
        }

    for transaction in transaction_list:
        transaction['_id_str'] = str(transaction['_id'])
        transaction['date_str'] = (
            transaction['date'].strftime('%Y-%m-%d')
            if isinstance(transaction['date'], datetime) else ''
        )
        transaction['date_fmt'] = (
            transaction['date'].strftime('%b %d, %Y')
            if isinstance(transaction['date'], datetime) else ''
        )
        transaction['category'] = g.category_map.get(
            transaction.get('category_id', 0),
            {'name': 'Uncategorized', 'color': '#9E9E9E'},
        )
        transaction['account'] = g.account_map.get(transaction.get('account_id'))

    return list(g.category_map.values()), list(g.account_map.values())


# ── Transactions ──────────────────────────────────────────────────
@web_bp.route('/transactions')
def transactions():
    """Render the transactions list with filtering and pagination."""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    category_id = request.args.get('category_id', '')
    account_id = request.args.get('account_id', '')
    sort = request.args.get('sort', 'date')
    order = request.args.get('order', 'desc')
    page = max(1, int(request.args.get('page', 1) or 1))

    query = _build_transaction_query(start_date, end_date, category_id, account_id)
    if sort not in ('date', 'amount', 'description'):
        sort = 'date'
    transaction_list = list(mongo.db.transactions.find(query)
                            .sort(sort, -1 if order == 'desc' else 1)
                            .skip((page - 1) * PAGE_SIZE)
                            .limit(PAGE_SIZE))
    total = mongo.db.transactions.count_documents(query)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    all_categories, all_accounts = _enrich_transactions(transaction_list)
    page_range = list(range(max(1, page - 2), min(total_pages + 1, page + 3)))

    return render_template(
        'transactions.html',
        transactions=transaction_list,
        categories=all_categories,
        accounts=all_accounts,
        total=total,
        page=page,
        total_pages=total_pages,
        page_range=page_range,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
        account_id=account_id,
        sort=sort,
        order=order,
        today=datetime.now().strftime('%Y-%m-%d'),
    )


@web_bp.route('/transactions/add', methods=['POST'])
def add_transaction():
    """Add a new transaction from the modal form."""
    try:
        transaction = Transaction.create(
            date=request.form['date'],
            description=request.form['description'],
            amount=float(request.form['amount']),
            category_id=int(request.form.get('category_id', 0)),
            notes=request.form.get('notes', ''),
        )
        mongo.db.transactions.insert_one(transaction)
        flash('Transaction added.', 'success')
    except (ValueError, KeyError) as e:  # pylint: disable=broad-exception-caught
        flash(f'Error: {e}', 'danger')
    return redirect(request.referrer or url_for('web.transactions'))


@web_bp.route('/transactions/<transaction_id>/edit', methods=['POST'])
def edit_transaction(transaction_id):
    """Edit an existing transaction and trigger auto-categorization learning."""
    try:
        object_id = ObjectId(transaction_id)
        transaction = mongo.db.transactions.find_one({'_id': object_id})
        if not transaction:
            flash('Transaction not found.', 'danger')
        else:
            description = request.form['description'].strip()
            new_category_id = int(request.form.get('category_id', 0))
            mongo.db.transactions.update_one(
                {'_id': object_id},
                {
                    '$set': {
                        'date': _parse_date(request.form['date']) or transaction['date'],
                        'description': description,
                        'amount': float(request.form['amount']),
                        'category_id': new_category_id,
                        'notes': request.form.get('notes', ''),
                    }
                }
            )
            if new_category_id != 0:
                categorizer = AutoCategorizer(mongo)
                categorizer.learn_from_categorization(description, new_category_id)
                batch_count = categorizer.batch_categorize_similar(description, new_category_id)
                if batch_count:
                    flash(
                        f'Updated. {batch_count} similar transaction(s) also categorized.',
                        'success',
                    )
                else:
                    flash('Transaction updated.', 'success')
            else:
                flash('Transaction updated.', 'success')
    except (ValueError, KeyError) as e:  # pylint: disable=broad-exception-caught
        flash(f'Error: {e}', 'danger')
    return redirect(request.referrer or url_for('web.transactions'))


@web_bp.route('/transactions/<transaction_id>/delete', methods=['POST'])
def delete_transaction(transaction_id):
    """Delete a transaction by its MongoDB ObjectId string."""
    try:
        mongo.db.transactions.delete_one({'_id': ObjectId(transaction_id)})
        flash('Transaction deleted.', 'success')
    except (ValueError, KeyError) as e:  # pylint: disable=broad-exception-caught
        flash(f'Error: {e}', 'danger')
    return redirect(request.referrer or url_for('web.transactions'))


def _handle_upload_post(file) -> object:
    """
    Process a CSV upload POST request.

    Validates the file, account, and CSV content, then imports transactions
    and records the upload. Flashes a result message and returns a redirect.

    Args:
        file: The uploaded file object from request.files.

    Returns:
        A redirect response to the upload page.
    """
    if not allowed_file(file.filename):
        flash('Only CSV/TXT files are allowed.', 'danger')
        return redirect(url_for('web.upload'))
    try:
        selected_account_id = int(request.form.get('account_id', 1))
        selected_account = mongo.db.accounts.find_one({'id': selected_account_id})
        if not selected_account:
            flash('Selected account not found.', 'danger')
            return redirect(url_for('web.upload'))
        content = file.read().decode('utf-8')
        filename = secure_filename(file.filename)
        validation = CSVParser.validate_csv(content)
        if not validation['valid']:
            flash(f'Invalid CSV: {validation["error"]}', 'danger')
            return redirect(url_for('web.upload'))
        parse_result = CSVParser.parse_csv(content, filename)
        if not parse_result['row_count']:
            flash('No valid transactions found.', 'warning')
            return redirect(url_for('web.upload'))
        categorized, uncategorized = process_transactions(
            parse_result,
            filename,
            AutoCategorizer(mongo),
            account_id=selected_account_id,
            account_type=selected_account['type'],
        )[1:]
        month = (parse_result['transactions'][0]['date'].strftime('%Y-%m') if parse_result['transactions'] else '')
        mongo.db.uploads.insert_one({
            'filename': filename,
            'upload_date': datetime.now(UTC),
            'row_count': parse_result['row_count'],
            'month': month,
            'status': 'processed',
            'categorized_count': categorized,
            'uncategorized_count': uncategorized,
            'errors': parse_result['errors'],
            'account_id': selected_account_id,
        })
        flash(
            f'Imported {parse_result["row_count"]} transactions '
            f'({categorized} auto-categorized, {uncategorized} uncategorized).',
            'success'
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        current_app.logger.error('Upload error: %s', e)
        flash(f'Import failed: {e}', 'danger')
    return redirect(url_for('web.upload'))


# ── Upload ────────────────────────────────────────────────────────
@web_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    """Handle CSV upload (POST) and display upload history (GET)."""
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('web.upload'))
        return _handle_upload_post(file)

    upload_history = list(mongo.db.uploads.find().sort('upload_date', -1).limit(30))
    for upload_record in upload_history:
        upload_record['_id_str'] = str(upload_record['_id'])
        if isinstance(upload_record.get('upload_date'), datetime):
            upload_record['upload_date_str'] = upload_record['upload_date'].strftime('%b %d, %Y')
    all_accounts = list(mongo.db.accounts.find().sort('id', 1))
    return render_template('upload.html', uploads=upload_history, accounts=all_accounts)


# ── Accounts ──────────────────────────────────────────────────────
@web_bp.route('/accounts')
def accounts():
    """Render the accounts management page."""
    accounts_list = list(mongo.db.accounts.find().sort('id', 1))
    return render_template(
        'accounts.html',
        accounts=accounts_list,
        type_labels=ACCOUNT_TYPE_LABELS,
        account_types=ACCOUNT_TYPES,
    )


@web_bp.route('/accounts/add', methods=['POST'])
def add_account():
    """Create a new account from the modal form."""
    try:
        type_ = request.form.get('type', 'checking')
        if type_ not in ACCOUNT_TYPES:
            flash('Invalid account type.', 'danger')
            return redirect(url_for('web.accounts'))
        account = Account.create(
            account_id=Account.get_next_id(mongo),
            name=request.form['name'].strip(),
            type_=type_,
            institution=request.form.get('institution', '').strip(),
            color=request.form.get('color', '#42A5F5'),
            currency=request.form.get('currency', 'CAD'),
        )
        mongo.db.accounts.insert_one(account)
        flash(f'Account "{account["name"]}" created.', 'success')
    except DuplicateKeyError:
        flash('Account creation conflict. Please try again.', 'danger')
    except (ValueError, KeyError) as e:  # pylint: disable=broad-exception-caught
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('web.accounts'))


@web_bp.route('/accounts/<int:account_id>/edit', methods=['POST'])
def edit_account(account_id):
    """Update name, institution, color, and currency for an account."""
    account = mongo.db.accounts.find_one({'id': account_id})
    if not account:
        flash('Account not found.', 'danger')
        return redirect(url_for('web.accounts'))
    try:
        mongo.db.accounts.update_one(
            {'id': account_id},
            {
                '$set': {
                    'name': request.form['name'].strip(),
                    'institution': request.form.get('institution', '').strip(),
                    'color': request.form.get('color', '#42A5F5'),
                    'currency': request.form.get('currency', 'CAD'),
                }
            }
        )
        flash('Account updated.', 'success')
    except (ValueError, KeyError) as e:  # pylint: disable=broad-exception-caught
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('web.accounts'))


@web_bp.route('/accounts/<int:account_id>/delete', methods=['POST'])
def delete_account(account_id):
    """Delete an account if it has no associated transactions."""
    account = mongo.db.accounts.find_one({'id': account_id})
    if not account:
        flash('Account not found.', 'danger')
        return redirect(url_for('web.accounts'))
    count = Account.transaction_count(account_id, mongo)
    if count:
        flash(f'Cannot delete "{account["name"]}" - used by {count} transaction(s).', 'danger')
        return redirect(url_for('web.accounts'))
    mongo.db.accounts.delete_one({'id': account_id})
    flash(f'Account "{account["name"]}" deleted.', 'success')
    return redirect(url_for('web.accounts'))


# ── Categories ────────────────────────────────────────────────────
@web_bp.route('/categories')
def categories():
    """Render the categories management page."""
    categories_list = list(mongo.db.categories.find().sort('id', 1))
    return render_template('categories.html', categories=categories_list)


@web_bp.route('/categories/add', methods=['POST'])
def add_category():
    """Create a new category from the modal form."""
    try:
        name = request.form['name'].strip()
        if mongo.db.categories.find_one({'name': name}):
            flash(f'Category "{name}" already exists.', 'danger')
            return redirect(url_for('web.categories'))
        category = Category.create(
            category_id=Category.get_next_id(mongo),
            name=name,
            description=request.form.get('description', '').strip(),
            color=request.form['color'],
            monthly_limit=float(request.form.get('monthly_limit') or 0),
        )
        mongo.db.categories.insert_one(category)
        flash(f'Category "{name}" created.', 'success')
    except (ValueError, KeyError) as e:  # pylint: disable=broad-exception-caught
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('web.categories'))


@web_bp.route('/categories/<int:category_id>/edit', methods=['POST'])
def edit_category(category_id):
    """Update a category. System categories: only monthly_limit is editable."""
    category = mongo.db.categories.find_one({'id': category_id})
    if not category:
        flash('Category not found.', 'danger')
        return redirect(url_for('web.categories'))
    try:
        if category.get('is_system'):
            mongo.db.categories.update_one(
                {'id': category_id},
                {
                    '$set': {
                        'monthly_limit': float(request.form.get('monthly_limit') or 0),
                    }
                }
            )
        else:
            mongo.db.categories.update_one(
                {'id': category_id},
                {
                    '$set': {
                        'name': request.form['name'].strip(),
                        'description': request.form.get('description', '').strip(),
                        'color': request.form['color'],
                        'monthly_limit': float(request.form.get('monthly_limit') or 0),
                    }
                }
            )
        flash('Category updated.', 'success')
    except (ValueError, KeyError) as e:  # pylint: disable=broad-exception-caught
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('web.categories'))


@web_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
def delete_category(category_id):
    """Delete a category if it is not a system category and has no transactions."""
    category = mongo.db.categories.find_one({'id': category_id})
    if not category:
        flash('Category not found.', 'danger')
        return redirect(url_for('web.categories'))
    if category.get('is_system'):
        flash('System categories cannot be deleted.', 'danger')
        return redirect(url_for('web.categories'))
    count = mongo.db.transactions.count_documents({'category_id': category_id})
    if count:
        flash(f'Cannot delete "{category["name"]}" - used by {count} transaction(s).', 'danger')
        return redirect(url_for('web.categories'))
    mongo.db.categories.delete_one({'id': category_id})
    flash(f'Category "{category["name"]}" deleted.', 'success')
    return redirect(url_for('web.categories'))
