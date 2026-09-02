import sys

from railway_telegram_publish_webhook import telegram_publish_webhook as _impl

sys.modules[__name__] = _impl
