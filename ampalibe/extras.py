from ._cmd import Cmd


funcs = {
    "command": {},
    "action": {},
    "event": {},
    "before": None,
    "after": None,
}


def analyse(data):
    """
    Function analyzing data received from Facebook
    The data received are of type Json .
    """

    for event in data["entry"]:
        messaging = event["messaging"]

        for message in messaging:

            sender_id = message["sender"]["id"]

            if message.get("message"):

                if message["message"].get("attachments"):
                    # Get file name
                    data = message["message"].get("attachments")
                    # creation de l'objet cmd personalisé
                    atts = list(map(lambda dt: dt["payload"]["url"], data))
                    cmd = Cmd(atts[0])
                    cmd.set_atts(atts)
                    cmd.webhook = "attachments"
                    return sender_id, cmd, message
                elif message["message"].get("quick_reply"):
                    # if the response is a quick reply
                    return (
                        sender_id,
                        Cmd(message["message"]["quick_reply"].get("payload")),
                        message,
                    )
                elif message["message"].get("text"):
                    # if the response is a simple text
                    return (
                        sender_id,
                        Cmd(message["message"].get("text")),
                        message,
                    )

            if message.get("postback"):
                recipient_id = sender_id
                pst_payload = Cmd(message["postback"]["payload"])
                pst_payload.webhook = "postback"
                return recipient_id, pst_payload, message

            if message.get("read"):
                watermark = Cmd(message["read"]["watermark"])
                watermark.webhook = "read"
                return sender_id, watermark, message

            if message.get("delivery"):
                watermark = Cmd(message["delivery"]["watermark"])
                watermark.webhook = "delivery"
                return sender_id, watermark, message

            if message.get("reaction"):
                reaction = Cmd(message["reaction"]["reaction"])
                reaction.webhook = "reaction"
                return sender_id, reaction, message

            if message.get("optin"):
                optin = Cmd(message["optin"]["payload"])
                optin.webhook = "optin"
                if message["optin"].get("type") == "one_time_notif_req":
                    optin.token = message["optin"]["one_time_notif_token"]
                elif message["optin"].get("type") == "notification_messages":
                    optin.token = message["optin"]["notification_messages_token"]
                return sender_id, optin, message

    return None, Cmd(""), None


def command(*args, **kwargs):
    """
    A decorator that registers the function as the route
        of a processing per command sent.
    """

    def call_fn(function):
        funcs["command"][args[0]] = function

    return call_fn


def action(*args, **kwargs):
    """
    A decorator that registers the function as the route
        of a defined action handler.
    """

    def call_fn(function):
        funcs["action"][args[0]] = function

    return call_fn


def event(*args, **kwargs):
    """
    A decorator that registers the function as the route
        of a defined event handler.
    """

    def call_fn(function):
        funcs["event"][args[0]] = function

    return call_fn


def before_receive(*args, **kwargs):
    """
    A decorator that run the function before
        running apropriate function
    """

    def call_fn(function):
        funcs["before"] = function

    return call_fn


def after_receive(*args, **kwargs):
    """
    A decorator that run the function after
        running apropriate function
    """

    def call_fn(function):
        funcs["after"] = function

    return call_fn


def before_run(func, **kwargs):
    res = None
    if funcs["before"] and hasattr(funcs["before"], "__call__"):
        if funcs["before"](**kwargs):
            res = func(**kwargs)
    else:
        res = func(**kwargs)

    if funcs["after"] and hasattr(funcs["after"], "__call__"):
        kwargs["res"] = res
        funcs["after"](**kwargs)

    return res
