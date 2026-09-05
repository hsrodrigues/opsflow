"""`/api/v1/products` — catálogo do que é transportado (usado pela
Programação para tirar a ambiguidade de `quantity` sem unidade declarada)."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.enums import ProductStatus
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=Page[ProductOut])
def list_products(
    request: Request,
    params: PageParams = Depends(),
    q: str | None = Query(default=None, description="Busca por nome ou SKU"),
    status: ProductStatus | None = None,
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("products.view")),
    db: Session = Depends(get_db),
) -> Page[ProductOut]:
    items, total = product_service.list_products(
        db, tenant_id, query=q, status=status, limit=params.page_size, offset=params.offset,
    )
    return Page.build([ProductOut.model_validate(item) for item in items], total=total, params=params)


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("products.manage")), db: Session = Depends(get_db),
) -> ProductOut:
    product = product_service.create_product(db, tenant_id, user, payload, _client_ip(request))
    return ProductOut.model_validate(product)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int, tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("products.view")), db: Session = Depends(get_db),
) -> ProductOut:
    return ProductOut.model_validate(product_service.get_product(db, tenant_id, product_id))


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int, payload: ProductUpdate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("products.manage")), db: Session = Depends(get_db),
) -> ProductOut:
    product = product_service.update_product(db, tenant_id, user, product_id, payload, _client_ip(request))
    return ProductOut.model_validate(product)


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("products.manage")), db: Session = Depends(get_db),
) -> None:
    product_service.delete_product(db, tenant_id, user, product_id, _client_ip(request))
