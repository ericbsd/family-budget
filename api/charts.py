"""
Chart API Blueprint
Provides aggregated data for visualizations.
"""
from datetime import datetime

from flask import Blueprint, request, current_app
from pymongo.errors import PyMongoError

from utils.aggregations import Aggregations
from utils.db import mongo
from utils.responses import error_response, success_response

charts_bp = Blueprint('charts', __name__)


def _parse_query_params() -> tuple:
    """
    Parse and validate common query parameters for top_merchants.

    Returns:
        tuple: (limit, year, month, error_response) where error is None if valid
    """
    # Parse and validate limit
    try:
        limit = int(request.args.get('limit', 10))
        if limit < 1 or limit > 100:
            return None, None, None, error_response(
                'INVALID_PARAMETER',
                'limit must be between 1 and 100',
            )
    except ValueError:
        return None, None, None, error_response(
            'INVALID_PARAMETER',
            'limit must be an integer',
        )

    # Parse and validate year
    year = request.args.get('year')
    if year:
        try:
            year = int(year)
        except ValueError:
            return None, None, None, error_response(
                'INVALID_PARAMETER',
                'year must be an integer',
            )
    else:
        year = datetime.now().year

    # Parse and validate month
    month = request.args.get('month')
    if month:
        try:
            month = int(month)
            if not 1 <= month <= 12:
                return None, None, None, error_response(
                    'INVALID_MONTH',
                    'Month must be between 1 and 12',
                )
        except ValueError:
            return None, None, None, error_response(
                'INVALID_PARAMETER',
                'month must be an integer',
            )

    return limit, year, month, None


@charts_bp.route('/charts/monthly/<int:year>/<int:month>', methods=['GET'])
def monthly_chart(year: int, month: int) -> tuple:
    """
    Get monthly spending breakdown by category.

    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)

    Returns:
        JSON response with category breakdown
    """
    try:
        if not 1 <= month <= 12:
            return error_response('INVALID_MONTH', 'Month must be between 1 and 12')

        start_date, end_date = Aggregations.get_date_range(year, month=month)
        data = Aggregations.aggregate_by_category(mongo, start_date, end_date)

        return success_response(
            data=data,
            count=len(data),
            year=year,
            month=month,
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error('Database error getting monthly chart: %s', e)
        return error_response('DATABASE_ERROR', 'Failed to retrieve chart data', 500)


@charts_bp.route('/charts/quarterly/<int:year>/<int:quarter>', methods=['GET'])
def quarterly_chart(year: int, quarter: int) -> tuple:
    """
    Get quarterly spending breakdown.

    Args:
        year: Year (e.g., 2024)
        quarter: Quarter (1-4)

    Returns:
        JSON response with category breakdown
    """
    try:
        if not 1 <= quarter <= 4:
            return error_response('INVALID_QUARTER', 'Quarter must be between 1 and 4')

        start_date, end_date = Aggregations.get_date_range(year, quarter=quarter)
        data = Aggregations.aggregate_by_category(mongo, start_date, end_date)

        return success_response(
            data=data,
            count=len(data),
            year=year,
            quarter=quarter,
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error('Database error getting quarterly chart: %s', e)
        return error_response('DATABASE_ERROR', 'Failed to retrieve chart data', 500)


@charts_bp.route('/charts/annual/<int:year>', methods=['GET'])
def annual_chart(year: int) -> tuple:
    """
    Get annual spending breakdown.

    Args:
        year: Year (e.g., 2024)

    Returns:
        JSON response with category breakdown
    """
    try:
        start_date, end_date = Aggregations.get_date_range(year)
        data = Aggregations.aggregate_by_category(mongo, start_date, end_date)

        return success_response(
            data=data,
            count=len(data),
            year=year,
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error('Database error getting annual chart: %s', e)
        return error_response('DATABASE_ERROR', 'Failed to retrieve chart data', 500)


@charts_bp.route('/charts/periods', methods=['GET'])
def available_periods() -> tuple:
    """
    Return distinct year-month combinations that have transaction data.

    Returns:
        JSON response with the list of available periods
    """
    try:
        pipeline = [
            {'$group': {'_id': {'year': {'$year': '$date'}, 'month': {'$month': '$date'}}}},
            {'$sort': {'_id.year': -1, '_id.month': -1}},
        ]
        results = list(mongo.db.transactions.aggregate(pipeline))
        periods = [{'year': r['_id']['year'], 'month': r['_id']['month']} for r in results]
        return success_response(data=periods, count=len(periods))
    except PyMongoError as e:
        current_app.logger.error('Database error getting periods: %s', e)
        return error_response('DATABASE_ERROR', 'Failed to retrieve periods', 500)


@charts_bp.route('/budget/status/<int:year>/<int:month>', methods=['GET'])
def budget_status(year: int, month: int) -> tuple:
    """
    Get budget status (spent vs. limit) for each category.

    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)

    Returns:
        JSON response with budget status per category
    """
    try:
        if not 1 <= month <= 12:
            return error_response('INVALID_MONTH', 'Month must be between 1 and 12')

        data = Aggregations.calculate_budget_status(mongo, year, month)

        return success_response(
            data=data,
            count=len(data),
            year=year,
            month=month,
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error('Database error getting budget status: %s', e)
        return error_response('DATABASE_ERROR', 'Failed to retrieve budget data', 500)


@charts_bp.route('/charts/trend', methods=['GET'])
def spending_trend() -> tuple:
    """
    Get spending trend over time.

    Query parameters:
        year: Year to end trend at (default: current year)
        months: Number of months to include (default: 12)

    Returns:
        JSON response with trend data
    """
    try:
        try:
            year = int(request.args.get('year', datetime.now().year))
            months = int(request.args.get('months', 12))
        except ValueError:
            return error_response('INVALID_PARAMETER', 'year and months must be integers')

        if months < 1 or months > 36:
            return error_response('INVALID_PARAMETER', 'months must be between 1 and 36')

        data = Aggregations.get_spending_trend(mongo, year, months)

        return success_response(
            data=data,
            count=len(data),
            year=year,
            months=months,
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error('Database error getting spending trend: %s', e)
        return error_response('DATABASE_ERROR', 'Failed to retrieve trend data', 500)


@charts_bp.route('/charts/top-merchants', methods=['GET'])
def top_merchants() -> tuple:
    """
    Get top merchants by spending.

    Query parameters:
        limit: Number of merchants to return (default: 10)
        year: Optional year filter (default: current year)
        month: Optional month filter (requires year, returns month data; without month returns annual)

    Returns:
        JSON response with top merchants
    """
    try:
        limit, year, month, error = _parse_query_params()
        if error:
            return error

        if month:
            start_date, end_date = Aggregations.get_date_range(year, month=month)
        else:
            start_date, end_date = Aggregations.get_date_range(year)

        data = Aggregations.get_top_merchants(mongo, start_date, end_date, limit)

        return success_response(
            data=data,
            count=len(data),
            limit=limit,
            year=year,
            month=month,
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error('Database error getting top merchants: %s', e)
        return error_response('DATABASE_ERROR', 'Failed to retrieve merchant data', 500)
