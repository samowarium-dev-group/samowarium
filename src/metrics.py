from prometheus_client import Gauge, Counter

GATHER_METRIC_DELAY_SEC = 3 * 60  # 3 min

users_amount_metric = Gauge("users_amount", "Users", labelnames=["pswd", "autoread"])

# Logging
log_metric = Counter("log_info", "Logs metric", labelnames=["level"])

# Telegram
incoming_commands_metric = Counter(
    "incoming_command", "Incoming commands metric", labelnames=["command_name"]
)
sent_message_metric = Counter("sent_message", "Sent messages metric")

# Samoware
samoware_response_status_code_metric = Counter(
    "samoware_response_sc", "Samoware reponses status code metric", labelnames=["sc"]
)

# Domain
login_metric = Counter("login", "Login events metric", labelnames=["is_successful"])
relogin_metric = Counter(
    "relogin", "Relogin events metric", labelnames=["is_successful"]
)
revalidation_metric = Counter(
    "revalidation", "Revalidation events metric", labelnames=["is_successful"]
)
logout_metric = Counter("logout", "Logout events metric")
forced_logout_metric = Counter("forced_logout", "Forced logout events metric")
user_handler_error_metric = Counter(
    "user_handler_error", "Client handler error events metric", labelnames=["type"]
)
incoming_letter_metric = Counter("incoming_letter", "Incoming letter events metric")
