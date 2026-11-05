import os

# Ensure default in-memory or SQLite database during pytest runs to prevent connection to external Docker hosts
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_suite.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
os.environ.setdefault("RATE_LIMIT_LOGIN", "50/minute")
os.environ.setdefault("RATE_LIMIT_REGISTER", "50/hour")
os.environ.setdefault("RATE_LIMIT_READ", "120/minute")
os.environ.setdefault("RATE_LIMIT_WRITE", "50/minute")
os.environ.setdefault("RATE_LIMIT_FAIL_OPEN", "true")

