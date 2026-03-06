"""Web blueprint - server-side rendered pages with Jinja2."""
import json
from datetime import datetime, timezone
from bson import ObjectId
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app)
from werkzeug.utils import secure_filename

from models.transaction import Transaction
from models.category import Category
from utils.db import mongo
from utils.csv_parser import CSVParser
from utils.categorization import AutoCategorizer
from utils.aggregations import Aggregations

web_bp = Blueprint('web', __name__)

PAGE_SIZE = 50
MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        return None


# ── Dashboard ─────────────────────────────────────────────────────
@web_bp.route('/dashboard')
def dashboard():
    now = datetime.now()

    pipeline = [
        {'$group': {'_id': {'year': {'$year': '$date'}, 'month': {'$month': '$date'}}}},
        {'$sort': {'_id.year': -1, '_id.month': -1}},
    ]
    periods = [{'year': p['_id']['year'], 'month': p['_id']['month']}
               for p in mongo.db.transactions.aggregate(pipeline)]

    year = int(request.args.get('year', now.year))
    if request.args.get('month'):
        month = int(request.args.get('month'))
    else:
        ym = [p['month'] for p in periods if p['year'] == year]
        if ym:
            month = max(ym)
        elif periods:
            year = periods[0]['year']
            month = periods[0]['month']
        else:
            month = now.month

    start_date, end_date = Aggregations.get_date_range(year, month=month)
    stats         = Aggregations.get_summary_stats(mongo, start_date, end_date)
    uncat_count   = mongo.db.transactions.count_documents({'category_id': 0})
    category_data = Aggregations.aggregate_by_category(mongo, start_date, end_date)
    budget_status = Aggregations.calculate_budget_status(mongo, year, month)
    trend_data    = Aggregations.get_spending_trend(mongo, year, months=6)
    top_merchants = Aggregations.get_top_merchants(mongo, start_date, end_date, limit=10)

    years  = sorted({p['year'] for p in periods}, reverse=True) or [now.year]
    months = sorted({p['month'] for p in periods if p['year'] == year}, reverse=True)
    if not months:
        months = [month]

    return render_template('dashboard.html',
        year=year, month=month,
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


# ── Transactions ──────────────────────────────────────────────────
@web_bp.route('/transactions')
def transactions():
    start_s = request.args.get('start_date', '')
    end_s   = request.args.get('end_date', '')
    cat_s   = request.args.get('category_id', '')
    sort    = request.args.get('sort', 'date')
    order   = request.args.get('order', 'desc')
    page    = max(1, int(request.args.get('page', 1) or 1))

    query  = {}
    date_q = {}
    d = _parse_date(start_s)
    if d:
        date_q['$gte'] = d
    d = _parse_date(end_s)
    if d:
        date_q['$lte'] = d.replace(hour=23, minute=59, second=59)
    if date_q:
        query['date'] = date_q
    if cat_s != '':
        try:
            query['category_id'] = int(cat_s)
        except ValueError:
            pass

    if sort not in ('date', 'amount', 'description'):
        sort = 'date'
    sort_dir = -1 if order == 'desc' else 1
    offset   = (page - 1) * PAGE_SIZE

    txns  = list(mongo.db.transactions.find(query).sort(sort, sort_dir).skip(offset).limit(PAGE_SIZE))
    total = mongo.db.transactions.count_documents(query)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    cats    = list(mongo.db.categories.find().sort('name', 1))
    cat_map = {c['id']: c for c in cats}

    for t in txns:
        t['_id_str']  = str(t['_id'])
        t['date_str'] = t['date'].strftime('%Y-%m-%d') if isinstance(t['date'], datetime) else ''
        t['date_fmt'] = t['date'].strftime('%b %d, %Y') if isinstance(t['date'], datetime) else ''
        t['category'] = cat_map.get(t.get('category_id', 0), {'name': 'Uncategorized', 'color': '#9E9E9E'})

    page_range = list(range(max(1, page - 2), min(total_pages + 1, page + 3)))
    today      = datetime.now().strftime('%Y-%m-%d')

    return render_template('transactions.html',
        transactions=txns,
        categories=cats,
        total=total,
        page=page,
        total_pages=total_pages,
        page_range=page_range,
        start_date=start_s,
        end_date=end_s,
        category_id=cat_s,
        sort=sort,
        order=order,
        today=today,
    )


@web_bp.route('/transactions/add', methods=['POST'])
def add_transaction():
    try:
        txn = Transaction.create(
            date=request.form['date'],
            description=request.form['description'],
            amount=float(request.form['amount']),
            category_id=int(request.form.get('category_id', 0)),
            notes=request.form.get('notes', ''),
        )
        mongo.db.transactions.insert_one(txn)
        flash('Transaction added.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(request.referrer or url_for('web.transactions'))


@web_bp.route('/transactions/<tid>/edit', methods=['POST'])
def edit_transaction(tid):
    try:
        oid = ObjectId(tid)
        txn = mongo.db.transactions.find_one({'_id': oid})
        if not txn:
            flash('Transaction not found.', 'danger')
        else:
            desc       = request.form['description'].strip()
            new_cat_id = int(request.form.get('category_id', 0))
            mongo.db.transactions.update_one({'_id': oid}, {'$set': {
                'date':        _parse_date(request.form['date']) or txn['date'],
                'description': desc,
                'amount':      float(request.form['amount']),
                'category_id': new_cat_id,
                'notes':       request.form.get('notes', ''),
            }})
            # Learn and batch-categorize if category was manually set
            if new_cat_id != 0:
                categorizer = AutoCategorizer(mongo)
                categorizer.learn_from_categorization(desc, new_cat_id)
                batch = categorizer.batch_categorize_similar(desc, new_cat_id)
                if batch:
                    flash(f'Updated. {batch} similar transaction(s) also categorized.', 'success')
                else:
                    flash('Transaction updated.', 'success')
            else:
                flash('Transaction updated.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(request.referrer or url_for('web.transactions'))


@web_bp.route('/transactions/<tid>/delete', methods=['POST'])
def delete_transaction(tid):
    try:
        mongo.db.transactions.delete_one({'_id': ObjectId(tid)})
        flash('Transaction deleted.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(request.referrer or url_for('web.transactions'))


# ── Upload ────────────────────────────────────────────────────────
@web_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('web.upload'))
        if file.filename.rsplit('.', 1)[-1].lower() not in {'csv', 'txt'}:
            flash('Only CSV/TXT files are allowed.', 'danger')
            return redirect(url_for('web.upload'))
        try:
            content  = file.read().decode('utf-8')
            filename = secure_filename(file.filename)

            validation = CSVParser.validate_csv(content)
            if not validation['valid']:
                flash(f'Invalid CSV: {validation["error"]}', 'danger')
                return redirect(url_for('web.upload'))

            parse_result = CSVParser.parse_csv(content, filename)
            if not parse_result['row_count']:
                flash('No valid transactions found.', 'warning')
                return redirect(url_for('web.upload'))

            categorizer   = AutoCategorizer(mongo)
            categorized   = 0
            uncategorized = 0

            for row in parse_result['transactions']:
                cat = categorizer.categorize(row['description'], row['amount'])
                txn = Transaction.create(
                    date=row['date'],
                    description=row['description'],
                    amount=row['amount'],
                    category_id=cat['category_id'],
                    source_file=filename,
                    auto_categorized=(cat['match_type'] != 'none'),
                    confidence=cat['confidence'],
                )
                mongo.db.transactions.insert_one(txn)
                if cat['match_type'] != 'none':
                    categorized += 1
                else:
                    uncategorized += 1

            month = (parse_result['transactions'][0]['date'].strftime('%Y-%m')
                     if parse_result['transactions'] else '')
            mongo.db.uploads.insert_one({
                'filename':            filename,
                'upload_date':         datetime.now(timezone.utc),
                'row_count':           parse_result['row_count'],
                'month':               month,
                'status':              'processed',
                'categorized_count':   categorized,
                'uncategorized_count': uncategorized,
                'errors':              parse_result['errors'],
            })
            flash(
                f'Imported {parse_result["row_count"]} transactions '
                f'({categorized} auto-categorized, {uncategorized} uncategorized).',
                'success'
            )
        except Exception as e:
            current_app.logger.error(f'Upload error: {e}')
            flash(f'Import failed: {e}', 'danger')
        return redirect(url_for('web.upload'))

    # GET
    uploads_list = list(mongo.db.uploads.find().sort('upload_date', -1).limit(30))
    for u in uploads_list:
        u['_id_str'] = str(u['_id'])
        if isinstance(u.get('upload_date'), datetime):
            u['upload_date_str'] = u['upload_date'].strftime('%b %d, %Y')
    return render_template('upload.html', uploads=uploads_list)


# ── Categories ────────────────────────────────────────────────────
@web_bp.route('/categories')
def categories():
    cats = list(mongo.db.categories.find().sort('id', 1))
    return render_template('categories.html', categories=cats)


@web_bp.route('/categories/add', methods=['POST'])
def add_category():
    try:
        name = request.form['name'].strip()
        if mongo.db.categories.find_one({'name': name}):
            flash(f'Category "{name}" already exists.', 'danger')
            return redirect(url_for('web.categories'))
        cat = Category.create(
            category_id=Category.get_next_id(mongo),
            name=name,
            description=request.form.get('description', '').strip(),
            color=request.form['color'],
            monthly_limit=float(request.form.get('monthly_limit') or 0),
        )
        mongo.db.categories.insert_one(cat)
        flash(f'Category "{name}" created.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('web.categories'))


@web_bp.route('/categories/<int:cat_id>/edit', methods=['POST'])
def edit_category(cat_id):
    cat = mongo.db.categories.find_one({'id': cat_id})
    if not cat:
        flash('Category not found.', 'danger')
        return redirect(url_for('web.categories'))
    if cat.get('is_system'):
        flash('System categories cannot be edited.', 'danger')
        return redirect(url_for('web.categories'))
    try:
        mongo.db.categories.update_one({'id': cat_id}, {'$set': {
            'name':          request.form['name'].strip(),
            'description':   request.form.get('description', '').strip(),
            'color':         request.form['color'],
            'monthly_limit': float(request.form.get('monthly_limit') or 0),
        }})
        flash('Category updated.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('web.categories'))


@web_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
def delete_category(cat_id):
    cat = mongo.db.categories.find_one({'id': cat_id})
    if not cat:
        flash('Category not found.', 'danger')
        return redirect(url_for('web.categories'))
    if cat.get('is_system'):
        flash('System categories cannot be deleted.', 'danger')
        return redirect(url_for('web.categories'))
    count = mongo.db.transactions.count_documents({'category_id': cat_id})
    if count:
        flash(f'Cannot delete "{cat["name"]}" — used by {count} transaction(s).', 'danger')
        return redirect(url_for('web.categories'))
    mongo.db.categories.delete_one({'id': cat_id})
    flash(f'Category "{cat["name"]}" deleted.', 'success')
    return redirect(url_for('web.categories'))
