"""Product service — business rules for o catálogo de produtos."""
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import AuditAction
from app.models.product import Product
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.audit_service import write_audit_log


def _as_dict(product: Product) -> dict:
    return {
        "name": product.name, "sku": product.sku,
        "unit_of_measure": product.unit_of_measure.value if hasattr(product.unit_of_measure, "value") else product.unit_of_measure,
        "status": product.status.value if hasattr(product.status, "value") else product.status,
    }


def list_products(
    db: Session, tenant_id: int, *, query: str | None, status: str | None, limit: int, offset: int,
) -> tuple[list[Product], int]:
    return ProductRepository(db, tenant_id).search(query=query, status=status, limit=limit, offset=offset)


def get_product(db: Session, tenant_id: int, product_id: int) -> Product:
    product = ProductRepository(db, tenant_id).get(product_id)
    if product is None:
        raise NotFoundError("Produto não encontrado.")
    return product


def create_product(
    db: Session, tenant_id: int, actor: User, payload: ProductCreate, ip_address: str | None,
) -> Product:
    product = Product(
        tenant_id=tenant_id, name=payload.name, sku=payload.sku, unit_of_measure=payload.unit_of_measure,
        default_weight_kg=payload.default_weight_kg, notes=payload.notes,
        created_by=actor.id, updated_by=actor.id,
    )
    ProductRepository(db, tenant_id).add(product)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.CREATE, table_name="products",
        record_id=str(product.id), ip_address=ip_address, new_value=_as_dict(product),
    )
    db.commit()
    db.refresh(product)
    return product


def update_product(
    db: Session, tenant_id: int, actor: User, product_id: int, payload: ProductUpdate, ip_address: str | None,
) -> Product:
    product = get_product(db, tenant_id, product_id)
    old_value = _as_dict(product)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    product.updated_by = actor.id
    db.flush()

    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.UPDATE, table_name="products",
        record_id=str(product.id), ip_address=ip_address, old_value=old_value, new_value=_as_dict(product),
    )
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, tenant_id: int, actor: User, product_id: int, ip_address: str | None) -> None:
    repo = ProductRepository(db, tenant_id)
    product = get_product(db, tenant_id, product_id)
    old_value = _as_dict(product)
    repo.soft_delete(product)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.DELETE, table_name="products",
        record_id=str(product_id), ip_address=ip_address, old_value=old_value,
    )
    db.commit()
