from datetime import datetime, date
import uuid
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Date, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv
import os

load_dotenv()  # Load biến môi trường từ file .env

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AuthCode(Base):
    __tablename__ = "auth_codes_exams_generator"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(32), unique=True, nullable=False)
    school_id = Column(String(8), nullable=False)
    expiry_date = Column(Date, nullable=False)
    max_uses = Column(Integer, default=0)
    used_count = Column(Integer, default=0)
    created_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    @staticmethod
    def generate_code(school_id: str, expiry_date: date) -> str:
        import string, random
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(random.choices(chars, k=16))
        date_part = expiry_date.strftime("%m%d")
        return f"{school_id}-{date_part}-{random_part}"

    @staticmethod
    def create_code(school_id: str, expiry_date: date, max_uses: int = 0, created_by: str = "admin") -> "AuthCode":
        db = SessionLocal()
        try:
            code = AuthCode(
                code=AuthCode.generate_code(school_id, expiry_date),
                school_id=school_id,
                expiry_date=expiry_date,
                max_uses=max_uses,
                created_by=created_by
            )
            db.add(code)
            db.commit()
            db.refresh(code)
            return code
        finally:
            db.close()

    @staticmethod
    def validate_code(code: str) -> tuple:
        db = SessionLocal()
        try:
            auth_code = db.query(AuthCode).filter(AuthCode.code == code).first()
            if not auth_code:
                return False, "Mã không hợp lệ", None
            if not auth_code.is_active:
                return False, "Mã đã bị vô hiệu hóa", None
            if auth_code.expiry_date < date.today():
                return False, "Mã đã hết hạn", None
            if auth_code.max_uses > 0 and auth_code.used_count >= auth_code.max_uses:
                return False, "Mã đã hết số lần sử dụng", None

            auth_code.used_count += 1
            db.commit()
            return True, "Xác thực thành công", auth_code.id  # 👈 Trả kèm ID để log sau
        finally:
            db.close()


class CodeUsageLog(Base):
    __tablename__ = "code_usage_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code_id = Column(String(36), nullable=False)
    used_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))
    user_agent = Column(String(200))

    @staticmethod
    def log_usage(code_id: str, ip_address: str = None, user_agent: str = None):
        db = SessionLocal()
        try:
            log = CodeUsageLog(
                code_id=code_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(log)
            db.commit()
        finally:
            db.close()

# Create all tables
Base.metadata.create_all(bind=engine)

def create_initial_codes():
    from datetime import timedelta
    expiry = date.today() + timedelta(days=30)
    AuthCode.create_code("THPT", expiry, max_uses=100)

if __name__ == "__main__":
    create_initial_codes()
