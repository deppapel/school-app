<<<<<<< HEAD
import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///local.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
=======
import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///local.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
>>>>>>> 71d5ac3407a9428aa7ea493a322bf9d033f9ebf5
