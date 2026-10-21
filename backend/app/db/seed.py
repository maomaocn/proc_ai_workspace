import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.db.session import SessionFactory
from app.models.identity import Department, User, UserRole

DEMO_PASSWORD = "DemoPass123!"
DEMO_USERS = {
    "employee": ("研发部", {"EMPLOYEE"}),
    "approver": ("财务部", {"EMPLOYEE", "APPROVER"}),
    "procurement": ("采购部", {"EMPLOYEE", "PROCUREMENT"}),
    "admin": ("信息技术部", {"EMPLOYEE", "ADMIN"}),
    "techadmin": ("信息技术部", {"TECH_ADMIN"}),
}


async def seed_demo_data() -> None:
    async with SessionFactory() as session:
        departments: dict[str, Department] = {}
        for department_name in sorted({item[0] for item in DEMO_USERS.values()}):
            department = await session.scalar(
                select(Department).where(Department.name == department_name)
            )
            if department is None:
                department = Department(name=department_name)
                session.add(department)
                await session.flush()
            departments[department_name] = department

        for username, (department_name, roles) in DEMO_USERS.items():
            user = await session.scalar(
                select(User)
                .where(User.username == username)
                .options(selectinload(User.role_assignments))
            )
            if user is None:
                user = User(
                    username=username,
                    password_hash=hash_password(DEMO_PASSWORD),
                    department=departments[department_name],
                    role_assignments=[],
                )
                session.add(user)
                await session.flush()
                existing_roles: set[str] = set()
            else:
                existing_roles = user.roles
            for role in sorted(roles - existing_roles):
                user.role_assignments.append(UserRole(role=role))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
