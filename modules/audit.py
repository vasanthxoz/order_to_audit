from db import fetch_all


def log_audit(cur, user_id, username, action, entity_type, entity_id=None, details="", ip_address=None):
    """Record an audit log entry inside the active transaction."""
    cur.execute(
        """
        INSERT INTO audit_logs (user_id, username, action, entity_type, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, username, action, entity_type, entity_id, details, ip_address),
    )


def get_audit_logs(limit=200, entity_type=None):
    if entity_type:
        return fetch_all(
            """
            SELECT * FROM audit_logs
            WHERE entity_type = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (entity_type, limit),
        )
    return fetch_all(
        """
        SELECT * FROM audit_logs
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        (limit,),
    )
