from aiogram.fsm.state import State, StatesGroup


class Onboard(StatesGroup):
    lang = State()
    token = State()
    gk_email = State()
    gk_key = State()


class NewWorker(StatesGroup):
    name = State()
    template = State()


class Deploy(StatesGroup):
    name = State()          # worker name for a brand-new deploy
    code = State()          # waiting for .js/.zip/pasted code
    plan = State()          # reviewing the plan
    value = State()         # typing a var/secret value for a plan item
    link = State()          # typing a resource id / target for a plan item
    cron = State()          # typing cron expressions for the plan


class SecretFlow(StatesGroup):
    name = State()
    value = State()
    var_name = State()
    var_value = State()


class WorkerEdit(StatesGroup):
    compat = State()
    delete_confirm = State()


class OpsFlow(StatesGroup):
    cron = State()
    route = State()
    domain = State()
    test_path = State()


class StorageFlow(StatesGroup):
    create_name = State()
    kv_key = State()
    kv_put_key = State()
    kv_put_value = State()
    d1_sql = State()
    delete_confirm = State()


class AISetup(StatesGroup):
    base = State()
    key = State()
    model = State()
