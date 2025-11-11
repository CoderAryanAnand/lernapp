# Import Flask modules for routing, request handling, and session management
from flask import Blueprint, render_template, request, jsonify, session
from datetime import datetime, timedelta
import os, json

# Import application models and utilities
from ..models import Settings, User, ToDoCategory, ToDoItem
from ..utils import login_required, csrf_protect
from ..extensions import db

# Define the blueprint for ToDo-related API routes
todo_bp = Blueprint(
    "todo", __name__, template_folder="../templates", static_folder="../static"
)

@todo_bp.route("/categories", methods=["POST"])
@csrf_protect
@login_required
def create_category(user):
    """
    API endpoint to create a new to-do category for the logged-in user.

    Returns:
        JSON: The newly created category with its ID and status code 201.
    """
    data = request.json
    name = data.get("name")
    
    if not name:
        return jsonify({"message": "Category name is required"}), 400
    
    new_category = ToDoCategory(
        user_id=user.id,
        name=name
    )
    db.session.add(new_category)
    db.session.commit()
    
    return jsonify({
        "message": "Category created",
        "category": {
            "id": new_category.id,
            "name": new_category.name,
            "items": []
        }
    }), 201

@todo_bp.route("/categories/<int:category_id>", methods=["DELETE"])
@csrf_protect
@login_required
def delete_category(user, category_id):
    """
    API endpoint to delete a to-do category and all its items.

    Args:
        category_id (int): The ID of the category to delete.

    Returns:
        JSON: A success message and status code 200, or a 404 error.
    """
    category = ToDoCategory.query.get(category_id)
    
    if not category or category.user_id != user.id:
        return jsonify({"message": "Category not found or unauthorized"}), 404
    
    db.session.delete(category)
    db.session.commit()
    
    return jsonify({"message": "Category deleted"}), 200

@todo_bp.route("/categories/<int:category_id>/items", methods=["POST"])
@csrf_protect
@login_required
def create_todo_item(user, category_id):
    """
    API endpoint to create a new to-do item within a category.

    Args:
        category_id (int): The ID of the category to add the item to.

    Returns:
        JSON: The newly created item with its ID and status code 201.
    """
    category = ToDoCategory.query.get(category_id)
    
    if not category or category.user_id != user.id:
        return jsonify({"message": "Category not found or unauthorized"}), 404
    
    data = request.json
    description = data.get("description")
    
    if not description:
        return jsonify({"message": "Description is required"}), 400
    
    new_item = ToDoItem(
        category_id=category_id,
        description=description
    )
    db.session.add(new_item)
    db.session.commit()
    
    return jsonify({
        "message": "Item created",
        "item": {
            "id": new_item.id,
            "description": new_item.description
        }
    }), 201

@todo_bp.route("/items/<int:item_id>", methods=["DELETE"])
@csrf_protect
@login_required
def delete_todo_item(user, item_id):
    """
    API endpoint to delete a to-do item.

    Args:
        item_id (int): The ID of the item to delete.

    Returns:
        JSON: A success message and status code 200, or a 404 error.
    """
    item = ToDoItem.query.get(item_id)
    
    if not item:
        return jsonify({"message": "Item not found"}), 404
    
    # Verify user owns this item through the category
    category = ToDoCategory.query.get(item.category_id)
    if not category or category.user_id != user.id:
        return jsonify({"message": "Unauthorized"}), 404
    
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({"message": "Item deleted"}), 200
