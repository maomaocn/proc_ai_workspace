import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.db.session import SessionFactory
from app.models.approval import ApprovalRule, MCPServerRecord, ToolPolicy
from app.models.identity import Department, User, UserRole
from app.models.knowledge import KnowledgeACL, KnowledgeCollection
from app.models.procurement import InventoryItem, Supplier, SupplierQuote

DEMO_PASSWORD = "DemoPass123!"
DEMO_USERS = {
    "employee": ("研发部", {"EMPLOYEE"}),
    "manager": ("研发部", {"EMPLOYEE", "APPROVER"}),
    "approver": ("财务部", {"EMPLOYEE", "APPROVER"}),
    "procurement": ("采购部", {"EMPLOYEE", "PROCUREMENT"}),
    "admin": ("信息技术部", {"EMPLOYEE", "ADMIN"}),
    "techadmin": ("信息技术部", {"TECH_ADMIN"}),
}
DEMO_APPROVAL_RULES = (
    (Decimal("0.00"), Decimal("10000.00"), 1, "APPROVER"),
    (Decimal("10000.01"), None, 1, "APPROVER"),
    (Decimal("10000.01"), None, 2, "APPROVER"),
)
DEMO_INVENTORY = {
    "LT-THINK-14": ("笔记本电脑", "ThinkBook 14 企业版", 25, Decimal("5799.00")),
    "LT-LAT-3450": ("笔记本电脑", "Latitude 3450 商务版", 8, Decimal("6299.00")),
    "MON-27-QHD": ("显示器", "27 英寸 QHD 办公显示器", 30, Decimal("1699.00")),
}
DEMO_SUPPLIERS = ("示例供应商·华东办公", "示例供应商·企业设备")
DEMO_QUOTES = (
    ("示例供应商·华东办公", "LT-THINK-14", Decimal("5680.00")),
    ("示例供应商·企业设备", "LT-THINK-14", Decimal("5920.00")),
    ("示例供应商·企业设备", "LT-LAT-3450", Decimal("6180.00")),
    ("示例供应商·华东办公", "MON-27-QHD", Decimal("1580.00")),
)
DEMO_QUOTED_AT = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
DEMO_TOOL_POLICIES = {
    "mcp.inventory.search": (["EMPLOYEE", "APPROVER", "PROCUREMENT", "ADMIN", "TECH_ADMIN"], 4),
    "mcp.supplier.quote": (["EMPLOYEE", "APPROVER", "PROCUREMENT", "ADMIN", "TECH_ADMIN"], 8),
}


async def seed_demo_data() -> None:
    async with SessionFactory() as session:
        departments: dict[str, Department] = {}
        users: dict[str, User] = {}
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
            users[username] = user

        await session.flush()
        collection = await session.scalar(
            select(KnowledgeCollection)
            .where(KnowledgeCollection.name == "企业采购制度")
            .options(selectinload(KnowledgeCollection.acl_entries))
        )
        if collection is None:
            collection = KnowledgeCollection(
                name="企业采购制度",
                visibility="INTERNAL",
                created_by=users["admin"].id,
                acl_entries=[],
            )
            session.add(collection)
            await session.flush()
        existing_grants = {
            (entry.principal_type, entry.principal_id, entry.permission)
            for entry in collection.acl_entries
        }
        employee_read = ("ROLE", "EMPLOYEE", "READ")
        if employee_read not in existing_grants:
            collection.acl_entries.append(
                KnowledgeACL(
                    principal_type=employee_read[0],
                    principal_id=employee_read[1],
                    permission=employee_read[2],
                )
            )

        inventory: dict[str, InventoryItem] = {}
        for sku, (category, model, available_qty, reference_price) in DEMO_INVENTORY.items():
            item = await session.scalar(select(InventoryItem).where(InventoryItem.sku == sku))
            if item is None:
                item = InventoryItem(
                    sku=sku,
                    category=category,
                    model=model,
                    available_qty=available_qty,
                    reference_price=reference_price,
                    active=True,
                )
                session.add(item)
                await session.flush()
            inventory[sku] = item

        suppliers: dict[str, Supplier] = {}
        for supplier_name in DEMO_SUPPLIERS:
            supplier = await session.scalar(select(Supplier).where(Supplier.name == supplier_name))
            if supplier is None:
                supplier = Supplier(name=supplier_name, active=True, demo_data=True)
                session.add(supplier)
                await session.flush()
            suppliers[supplier_name] = supplier

        for supplier_name, sku, unit_price in DEMO_QUOTES:
            supplier = suppliers[supplier_name]
            item = inventory[sku]
            quote = await session.scalar(
                select(SupplierQuote).where(
                    SupplierQuote.supplier_id == supplier.id,
                    SupplierQuote.inventory_item_id == item.id,
                    SupplierQuote.quoted_at == DEMO_QUOTED_AT,
                )
            )
            if quote is None:
                session.add(
                    SupplierQuote(
                        supplier_id=supplier.id,
                        inventory_item_id=item.id,
                        unit_price=unit_price,
                        currency="CNY",
                        quoted_at=DEMO_QUOTED_AT,
                        source_type="DEMO",
                    )
                )

        for min_amount, max_amount, stage, approver_role in DEMO_APPROVAL_RULES:
            rule = await session.scalar(
                select(ApprovalRule).where(
                    ApprovalRule.min_amount == min_amount,
                    ApprovalRule.max_amount == max_amount,
                    ApprovalRule.stage == stage,
                    ApprovalRule.approver_role == approver_role,
                )
            )
            if rule is None:
                session.add(
                    ApprovalRule(
                        min_amount=min_amount,
                        max_amount=max_amount,
                        stage=stage,
                        approver_role=approver_role,
                        active=True,
                    )
                )

        mcp_server = await session.scalar(
            select(MCPServerRecord).where(MCPServerRecord.name == "enterprise-ai-agent-hub-mcp")
        )
        if mcp_server is None:
            session.add(
                MCPServerRecord(
                    name="enterprise-ai-agent-hub-mcp",
                    transport="stdio",
                    config_ref="app.mcp.server",
                    enabled=True,
                    health_status="UNKNOWN",
                )
            )
        for tool_name, (allowed_roles, max_calls) in DEMO_TOOL_POLICIES.items():
            policy = await session.scalar(
                select(ToolPolicy).where(ToolPolicy.tool_name == tool_name)
            )
            if policy is None:
                session.add(
                    ToolPolicy(
                        tool_name=tool_name,
                        allowed_roles=allowed_roles,
                        read_only=True,
                        enabled=True,
                        max_calls_per_run=max_calls,
                    )
                )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
