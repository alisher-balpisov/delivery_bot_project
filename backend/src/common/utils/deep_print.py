def deep_print(obj, depth=2):
    """Рекурсивный просмотр содержимого объекта."""
    if depth <= 0:
        return str(obj)
    if hasattr(obj, "__dict__"):
        return {k: deep_print(v, depth - 1) for k, v in vars(obj).items()}
    elif isinstance(obj, dict):
        return {k: deep_print(v, depth - 1) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [deep_print(v, depth - 1) for v in obj]
    else:
        return str(obj)
