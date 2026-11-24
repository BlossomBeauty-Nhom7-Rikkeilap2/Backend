"""
Script seed dong bo tai khoan mau cua Frontend vao CSDL Backend TiDB Cloud.
Cac tai khoan bao gom:
- admin (Doan Thi Minh Anh, Marketing Manager, password: Blossom@123)
- minhanh (Doan Thi Minh Anh, Marketing Staff, password: Staff@123)
- thuyduong (Nguyen Thuy Duong, Marketing Staff, password: Staff@123)
- manh (Doan Thi Minh Anh, Marketing Staff, password: Manh@2026)
- manager (Marketing Manager, password: Manager@123)
- staff1 (Marketing Staff, password: Staff@123)
"""
from datetime import datetime
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User

def seed_users():
    db = SessionLocal()
    try:
        users_to_seed = [
            {
                "username": "admin",
                "email": "admin@blossom.vn",
                "password": hash_password("Blossom@123"),
                "full_name": "Doan Thi Minh Anh",
                "role_id": 1,
                "status": "ACTIVE"
            },
            {
                "username": "minhanh",
                "email": "minhanh@blossom.vn",
                "password": hash_password("Staff@123"),
                "full_name": "Doan Thi Minh Anh",
                "role_id": 2,
                "status": "ACTIVE"
            },
            {
                "username": "thuyduong",
                "email": "thuyduong@blossom.vn",
                "password": hash_password("Staff@123"),
                "full_name": "Nguyen Thuy Duong",
                "role_id": 2,
                "status": "ACTIVE"
            },
            {
                "username": "manh",
                "email": "manh@blossom.vn",
                "password": hash_password("Manh@2026"),
                "full_name": "Doan Thi Minh Anh",
                "role_id": 2,
                "status": "ACTIVE"
            },
            {
                "username": "manager",
                "email": "manager@rikkeilab.vn",
                "password": hash_password("Manager@123"),
                "full_name": "Marketing Manager",
                "role_id": 1,
                "status": "ACTIVE"
            },
            {
                "username": "staff1",
                "email": "staff1@rikkeilab.vn",
                "password": hash_password("Staff@123"),
                "full_name": "Marketing Staff 1",
                "role_id": 2,
                "status": "ACTIVE"
            }
        ]

        for u_data in users_to_seed:
            existing = db.query(User).filter(
                (User.username == u_data["username"]) | (User.email == u_data["email"])
            ).first()

            if existing:
                existing.password_hash = u_data["password"]
                existing.status = u_data["status"]
                existing.full_name = u_data["full_name"]
                existing.role_id = u_data["role_id"]
                existing.failed_login_attempts = 0
                existing.locked_until = None
                print(f"Cap nhat tai khoan: {existing.username}")
            else:
                new_user = User(
                    username=u_data["username"],
                    email=u_data["email"],
                    password_hash=u_data["password"],
                    full_name=u_data["full_name"],
                    role_id=u_data["role_id"],
                    status=u_data["status"],
                    created_at=datetime.now()
                )
                db.add(new_user)
                print(f"Tao moi tai khoan: {u_data['username']}")

        db.commit()
        print("Dong bo tai khoan hoan tat!")
    except Exception as e:
        db.rollback()
        print("Loi khi seed tai khoan:", e)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_users()
