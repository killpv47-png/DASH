from . import onboarding, menu, workers, newworker, deploy, secrets, ops, storage, settings_h, help_h, ai_chat  # noqa: F401

# Order matters: menu (commands, /cancel, reply-keyboard) first, AI free-text catch-all last.
ROUTERS = [
    onboarding.router, menu.router, workers.router, newworker.router, deploy.router, secrets.router,
    storage.router, settings_h.router, help_h.router, ops.router, ai_chat.router,
]
