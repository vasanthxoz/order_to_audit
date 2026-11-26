from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from db import fetch_one, fetch_all, execute_query


class AppUser(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.full_name = row["full_name"]
        self.email = row["email"]
        self.phone = row.get("phone")
        self.password_hash = row["password_hash"]
        self.role_id = row["role_id"]
        self.role_name = row["role_name"]
        self._is_active = row["is_active"]

    @property
    def is_active(self):
        return self._is_active


def load_user_by_id(user_id):
    row = fetch_one(
        """
        SELECT u.*, r.name AS role_name
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s
        """,
        (int(user_id),),
    )
    return AppUser(row) if row else None


def authenticate_user(username, password):
    row = fetch_one(
        """
        SELECT u.*, r.name AS role_name
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.username = %s AND u.is_active = TRUE
        """,
        (username.strip(),),
    )
    if row and check_password_hash(row["password_hash"], password):
        return AppUser(row)
    return None


def list_users():
    return fetch_all(
        """
        SELECT u.id, u.username, u.full_name, u.email, u.phone, u.is_active, u.created_at, r.name AS role_name
        FROM users u
        JOIN roles r ON r.id = u.role_id
        ORDER BY u.id
        """
    )


def list_roles():
    return fetch_all("SELECT id, name, description FROM roles ORDER BY id")


def create_user(username, full_name, email, phone, password, role_id):
    pw_hash = generate_password_hash(password)
    return execute_query(
        """
        INSERT INTO users (username, full_name, email, phone, password_hash, role_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (username.strip(), full_name.strip(), email.strip(), (phone or "").strip(), pw_hash, int(role_id)),
        returning=True,
    )
