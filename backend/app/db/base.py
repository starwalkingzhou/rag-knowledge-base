"""SQLAlchemy 2.0 声明式基类。所有 ORM 模型都继承 Base。"""

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass