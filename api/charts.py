"""
Charts API Blueprint
Provides aggregated data for visualizations.
"""
from flask import Blueprint, request, current_app
from pymongo.errors import PyMongoError

from utils.aggregations import Aggregations
from utils.db import mongo
from utils.responses import error_response, success_response

charts_bp = Blueprint('charts', __name__)


def _parse_query_params():
    """
    Parse and validate common query parameters for top_merchants.

    Returns:
        tuple: (limit, year, month, error_response) where error is None if valid
    """
    from datetime import datetime

    # Parse and validate limit
    try:
        limit = int(request.args.get('limit', 10))
        if limit < 1 or limit > 100:
            return None, None, None, error_response('INVALID_PARAMETER',
                                                    'limit must be between 1 and 100')
    except ValueError:
        return None, None, None, error_response('INVALID_PARAMETER', 'limit must be an integer')

    # Parse and validate year
    year = request.args.get('year')
    if year:
        try:
            year = int(year)
        except ValueError:
            return None, None, None, error_response('INVALID_PARAMETER', 'year must be an integer')
    else:
        year = datetime.now().year

    # Parse and validate month
    month = request.args.get('month')
    if month:
        try:
            month = int(month)
            if not 1 <= month <= 12:
                return None, None, None, error_response('INVALID_MONTH',
                                                        'Month must be between 1 and 12')
        except ValueError:
            return None, None, None, error_response('INVALID_PARAMETER',
                                                    'month must be an integer')

    return limit, year, month, None


@charts_bp.route('/charts/monthly/<int:year>/<int:month>', methods=['GET'])
def monthly_chart(year, month):
    """
    Get monthly spending breakdown by category.

    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)

    Returns:
        JSON response with category breakdown
    """
    try:
        # Validate month
        if not 1 <= month <= 12:
            return error_response('INVALID_MONTH', 'Month must be between 1 and 12')

        # Get date range for the month
        start_date, end_date = Aggregations.get_date_range(year, month=month)

        # Get spending data
        data = Aggregations.aggregate_by_category(mongo, start_date, end_date)

        return success_response(
            data=data,
            count=len(data),
            year=year,
            month=month
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error getting monthly chart: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve chart data', 500)


@charts_bp.route('/charts/quarterly/<int:year>/<int:quarter>', methods=['GET'])
def quarterly_chart(year, quarter):
    """
    Get quarterly spending breakdown.

    Args:
        year: Year (e.g., 2024)
        quarter: Quarter (1-4)

    Returns:
        JSON response with category breakdown
    """
    try:
        # Validate quarter
        if not 1 <= quarter <= 4:
            return error_response('INVALID_QUARTER', 'Quarter must be between 1 and 4')

        # Get date range for the quarter
        start_date, end_date = Aggregations.get_date_range(year, quarter=quarter)

        # Get spending data
        data = Aggregations.aggregate_by_category(mongo, start_date, end_date)

        return success_response(
            data=data,
            count=len(data),
            year=year,
            quarter=quarter
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error getting quarterly chart: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve chart data', 500)


@charts_bp.route('/charts/annual/<int:year>', methods=['GET'])
def annual_chart(year):
    """
    Get annual spending breakdown.

    Args:
        year: Year (e.g., 2024)

    Returns:
        JSON response with category breakdown
    """
    try:
        # Get date range for the year
        start_date, end_date = Aggregations.get_date_range(year)

        # Get spending data
        data = Aggregations.aggregate_by_category(mongo, start_date, end_date)

        return success_response(
            data=data,
            count=len(data),
            year=year
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error getting annual chart: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve chart data', 500)


@charts_bp.route('/budget/status/<int:year>/<int:month>', methods=['GET'])
def budget_status(year, month):
    """
    Get budget status (spent vs limit) for each category.

    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)

    Returns:
        JSON response with budget status per category
    """
    try:
        # Validate month
        if not 1 <= month <= 12:
            return error_response('INVALID_MONTH', 'Month must be between 1 and 12')

        # Get budget status data
        data = Aggregations.calculate_budget_status(mongo, year, month)

        return success_response(
            data=data,
            count=len(data),
            year=year,
            month=month
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error getting budget status: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve budget data', 500)


@charts_bp.route('/charts/trend', methods=['GET'])
def spending_trend():
    """
    Get spending trend over time.

    Query parameters:
        year: Year to end trend at (default: current year)
        months: Number of months to include (default: 12)

    Returns:
        JSON response with trend data
    """
    try:
        # Get query parameters
        from datetime import datetime

        try:
            year = int(request.args.get('year', datetime.now().year))
            months = int(request.args.get('months', 12))
        except ValueError:
            return error_response('INVALID_PARAMETER', 'year and months must be integers')

        # Validate months
        if months < 1 or months > 36:
            return error_response('INVALID_PARAMETER', 'months must be between 1 and 36')

        # Get trend data
        data = Aggregations.get_spending_trend(mongo, year, months)

        return success_response(
            data=data,
            count=len(data),
            year=year,
            months=months
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error getting spending trend: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve trend data', 500)


@charts_bp.route('/charts/top-merchants', methods=['GET'])
def top_merchants():
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
        # Parse and validate query parameters
        limit, year, month, error = _parse_query_params()
        if error:
            return error

        # Get date range
        if month:
            start_date, end_date = Aggregations.get_date_range(year, month=month)
        else:
            start_date, end_date = Aggregations.get_date_range(year)

        # Get top merchants data
        data = Aggregations.get_top_merchants(mongo, start_date, end_date, limit)

        return success_response(
            data=data,
            count=len(data),
            limit=limit,
            year=year,
            month=month
        )

    except ValueError as e:
        return error_response('VALIDATION_ERROR', str(e))
    except PyMongoError as e:
        current_app.logger.error(f"Database error getting top merchants: {str(e)}")
        return error_response('DATABASE_ERROR', 'Failed to retrieve merchant data', 500)
