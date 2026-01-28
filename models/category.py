"""
Category model.
Handles category data validation and helper methods.
"""
from datetime import datetime


class Category:
    """
    Category model for budget categorization.

    Schema:
        id: int - Auto-incrementing category ID (1, 2, 3...)
        name: str - Category name
        description: str - Category description
        color: str - Hex color code (e.g., #4CAF50)
        monthly_limit: float - Monthly spending limit
        created_date: datetime - When category was created
    """

    @staticmethod
    def get_next_id(mongo):
        """
        Get the next auto-incrementing ID for a new category.

        Args:
            mongo: Flask-PyMongo instance

        Returns:
            int: Next available category ID
        """
        # Find the highest existing ID
        highest = mongo.db.categories.find_one(sort=[('id', -1)])
        if highest and 'id' in highest:
            return highest['id'] + 1
        return 1  # Start at 1 for user-created categories (0 is reserved for Uncategorized)

    @staticmethod
    def create(category_id, name, description, color, monthly_limit=0.0):
        """
        Create a new category document.

        Args:
            category_id: int - Category ID (use get_next_id() to generate)
            name: str - Category name
            description: str - Category description
            color: str - Hex color code
            monthly_limit: float - Monthly spending limit

        Returns:
            dict: Category document ready for MongoDB insertion
        """
        # Validate ID (0 is valid for Uncategorized)
        if not isinstance(category_id, int) or category_id < 0:
            raise ValueError("category_id must be a non-negative integer")

        # Validate color format
        if not Category.validate_color(color):
            raise ValueError(f"Invalid color format: {color}. Expected hex format like #4CAF50")

        # Validate monthly limit
        try:
            monthly_limit = float(monthly_limit)
            if monthly_limit < 0:
                raise ValueError("monthly_limit cannot be negative")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid monthly_limit: {monthly_limit}") from exc

        return {
            'id': category_id,
            'name': str(name).strip(),
            'description': str(description).strip(),
            'color': str(color).upper(),
            'monthly_limit': monthly_limit,
            'created_date': datetime.utcnow()
        }

    @staticmethod
    def validate_color(color):
        """
        Validate hex color format.

        Args:
            color: str - Color string to validate

        Returns:
            bool: True if valid hex color
        """
        if not isinstance(color, str):
            return False

        color = color.strip()

        # Check format: #RRGGBB
        if not color.startswith('#'):
            return False

        if len(color) != 7:
            return False

        # Check if all characters after # are hex digits
        try:
            int(color[1:], 16)
            return True
        except ValueError:
            return False

    @staticmethod
    def validate(category):
        """
        Validate a category document.

        Args:
            category: dict - Category document

        Returns:
            bool: True if valid

        Raises:
            ValueError: If validation fails
        """
        required_fields = ['id', 'name', 'description', 'color', 'monthly_limit']

        for field in required_fields:
            if field not in category:
                raise ValueError(f"Missing required field: {field}")

        if not isinstance(category['id'], int) or category['id'] < 0:
            raise ValueError("id must be a non-negative integer")

        if not category['name'].strip():
            raise ValueError("name cannot be empty")

        if not Category.validate_color(category['color']):
            raise ValueError(f"Invalid color format: {category['color']}")

        if not isinstance(category['monthly_limit'], (int, float)) or category['monthly_limit'] < 0:
            raise ValueError("monthly_limit must be a non-negative number")

        return True

    @staticmethod
    def to_json(category):
        """
        Convert category to JSON-serializable format.

        Args:
            category: dict - Category document from MongoDB

        Returns:
            dict: JSON-serializable category
        """
        result = category.copy()

        # Convert ObjectId to string
        if '_id' in result:
            result['_id'] = str(result['_id'])

        # Convert datetime to ISO format string
        if 'created_date' in result and isinstance(result['created_date'], datetime):
            result['created_date'] = result['created_date'].isoformat()

        return result

    @staticmethod
    def update(category_id, **updates):
        """
        Create update document for MongoDB.
        Allows updating: name, description, color, monthly_limit.
        The id field cannot be changed.

        Args:
            category_id: int - Category ID
            **updates: Keyword arguments for fields to update

        Returns:
            dict: MongoDB update document
        """
        # Validate category_id is provided
        if not category_id:
            raise ValueError("category_id is required for update")

        # Explicitly prevent updating the id field
        if 'id' in updates:
            raise ValueError("Cannot update 'id' field - category IDs are immutable")

        allowed_fields = {'name', 'description', 'color', 'monthly_limit'}
        update_doc = {}

        for field, value in updates.items():
            if field not in allowed_fields:
                raise ValueError(f"Cannot update field: {field}")

            # Validate name if updating
            if field == 'name':
                name = str(value).strip()
                if not name:
                    raise ValueError("name cannot be empty")
                update_doc[field] = name
                continue

            # Validate color if updating
            if field == 'color' and not Category.validate_color(value):
                raise ValueError(f"Invalid color format: {value}")

            # Validate monthly_limit if updating
            if field == 'monthly_limit':
                try:
                    value = float(value)
                    if value < 0:
                        raise ValueError("monthly_limit cannot be negative")
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Invalid monthly_limit: {value}") from exc

            update_doc[field] = value

        return {'$set': update_doc} if update_doc else {}
