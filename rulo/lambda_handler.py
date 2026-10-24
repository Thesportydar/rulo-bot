from rulo.__main__ import main


def handler(event, context):
    """Invocado por EventBridge Scheduler. Para probar: {"args": ["--dry-run"]}."""
    code = main(list((event or {}).get("args", [])))
    return {"exit_code": code}
