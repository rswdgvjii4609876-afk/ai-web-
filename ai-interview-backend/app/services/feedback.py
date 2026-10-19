def serialize_feedback(item, *, admin=False):
    data = {name: getattr(item, name) for name in (
        "id", "category", "title", "content", "status", "reply", "created_at", "updated_at"
    )}
    if admin:
        data.update(user_id=item.user_id, replied_by=item.replied_by)
    return data


def feedback_response(data):
    return {"code": 200, "message": "Success", "data": data}
