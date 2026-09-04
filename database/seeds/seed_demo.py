"""Seed de dados demonstrativos (seção 38).

Cria uma empresa demo completa — tenant, licença, usuário admin, transportadoras,
veículos, motoristas, rotas, uma programação com operações em andamento e
ocorrências — para permitir explorar o sistema de ponta a ponta sem precisar
cadastrar tudo manualmente.

Idempotente: rodar mais de uma vez não duplica dados (identifica a empresa
demo pelo CNPJ fixo e não recria nada se ela já existir).

Uso:
    python database/seeds/seed_demo.py

A senha do usuário admin vem de `SEED_ADMIN_PASSWORD` (.env); se omitida, uma
senha aleatória é gerada e impressa **uma única vez** no terminal — nunca é
gravada em log ou arquivo, e nunca fica hardcoded no código-fonte.
"""
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    Carrier,
    Driver,
    License,
    Location,
    Occurrence,
    OccurrenceType,
    Operation,
    Plan,
    Role,
    Route,
    Schedule,
    ScheduleItem,
    StatusHistory,
    Tenant,
    User,
    Vehicle,
    VehicleType,
)
from app.models.enums import (  # noqa: E402
    CarrierStatus,
    DriverStatus,
    LicenseStatus,
    OccurrenceSeverity,
    OccurrenceStatus,
    ScheduleStatus,
    UserStatus,
    VehicleStatus,
)

DEMO_TENANT_CNPJ = "11.222.333/0001-81"
UTC_NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _get_or_create_tenant(db: Session) -> tuple[Tenant, bool]:
    existing = db.query(Tenant).filter(Tenant.cnpj == DEMO_TENANT_CNPJ).one_or_none()
    if existing is not None:
        return existing, False
    tenant = Tenant(legal_name="OpsFlow Demo Transportes Ltda", trade_name="OpsFlow Demo", cnpj=DEMO_TENANT_CNPJ)
    db.add(tenant)
    db.flush()
    return tenant, True


def _resolve_admin_password() -> str:
    settings = get_settings()
    if settings.seed_admin_password:
        return settings.seed_admin_password
    generated = secrets.token_urlsafe(12)
    print(f"[seed_demo] Senha gerada para o admin (anote agora, não será exibida novamente): {generated}")
    return generated


def _create_admin_user(db: Session, tenant: Tenant) -> User:
    settings = get_settings()
    admin_email = settings.seed_admin_email or "admin@opsflow.local"
    admin_role = db.query(Role).filter(Role.code == "ADMIN_EMPRESA").one()
    user = User(
        tenant_id=tenant.id,
        email=admin_email,
        password_hash=hash_password(_resolve_admin_password()),
        full_name="Administrador Demo",
        status=UserStatus.ATIVO,
    )
    user.roles.append(admin_role)
    db.add(user)
    db.flush()
    return user


def _create_license(db: Session, tenant: Tenant) -> License:
    plan = db.query(Plan).filter(Plan.code == "PROFESSIONAL").one()
    license_ = License(
        tenant_id=tenant.id,
        plan_id=plan.id,
        license_key=secrets.token_hex(16),
        status=LicenseStatus.TRIAL,
        issued_at=UTC_NOW,
        expires_at=UTC_NOW + timedelta(days=30),
    )
    db.add(license_)
    return license_


def _create_carriers(db: Session, tenant: Tenant) -> list[Carrier]:
    carriers = [
        Carrier(
            tenant_id=tenant.id, legal_name="Rápido Log Transportes Ltda", trade_name="Rápido Log",
            cnpj="22.333.444/0001-11", contact_name="Carlos Mendes", phone="(11) 3456-7890",
            email="contato@rapidolog.com.br", status=CarrierStatus.ATIVO,
        ),
        Carrier(
            tenant_id=tenant.id, legal_name="Trans Sul Cargas Ltda", trade_name="Trans Sul",
            cnpj="33.444.555/0001-22", contact_name="Fernanda Souza", phone="(51) 3222-4455",
            email="contato@transsul.com.br", status=CarrierStatus.ATIVO,
        ),
    ]
    db.add_all(carriers)
    db.flush()
    return carriers


def _create_vehicle_types(db: Session, tenant: Tenant) -> dict[str, VehicleType]:
    types = {
        "truck": VehicleType(tenant_id=tenant.id, name="Caminhão Truck"),
        "carreta": VehicleType(tenant_id=tenant.id, name="Carreta"),
        "van": VehicleType(tenant_id=tenant.id, name="Van de Carga"),
    }
    db.add_all(types.values())
    db.flush()
    return types


def _create_drivers(db: Session, tenant: Tenant, carriers: list[Carrier]) -> list[Driver]:
    drivers = [
        Driver(
            tenant_id=tenant.id, full_name="João da Silva", cpf="123.456.789-01", cnh_number="01234567890",
            cnh_category="E", cnh_expiry=date.today() + timedelta(days=10), phone="(11) 98888-1111",
            carrier_id=carriers[0].id, status=DriverStatus.ATIVO,
        ),
        Driver(
            tenant_id=tenant.id, full_name="Maria Oliveira", cpf="234.567.890-12", cnh_number="12345678901",
            cnh_category="D", cnh_expiry=date.today() + timedelta(days=180), phone="(11) 98888-2222",
            carrier_id=carriers[0].id, status=DriverStatus.ATIVO,
        ),
        Driver(
            tenant_id=tenant.id, full_name="Pedro Santos", cpf="345.678.901-23", cnh_number="23456789012",
            cnh_category="E", cnh_expiry=date.today() + timedelta(days=365), phone="(51) 98888-3333",
            carrier_id=carriers[1].id, status=DriverStatus.ATIVO,
        ),
        Driver(
            tenant_id=tenant.id, full_name="Ana Costa", cpf="456.789.012-34", cnh_number="34567890123",
            cnh_category="D", cnh_expiry=date.today() + timedelta(days=45), phone="(51) 98888-4444",
            carrier_id=carriers[1].id, status=DriverStatus.ATIVO,
        ),
    ]
    db.add_all(drivers)
    db.flush()
    return drivers


def _create_vehicles(
    db: Session, tenant: Tenant, vehicle_types: dict[str, VehicleType], carriers: list[Carrier],
    drivers: list[Driver],
) -> list[Vehicle]:
    vehicles = [
        Vehicle(
            tenant_id=tenant.id, plate="ABC1D23", vehicle_type_id=vehicle_types["truck"].id,
            brand="Volvo", model="FH 540", year=2021, carrier_id=carriers[0].id, capacity=15000,
            status=VehicleStatus.EM_OPERACAO, current_driver_id=drivers[0].id,
        ),
        Vehicle(
            tenant_id=tenant.id, plate="DEF2E34", vehicle_type_id=vehicle_types["carreta"].id,
            brand="Scania", model="R450", year=2020, carrier_id=carriers[0].id, capacity=25000,
            status=VehicleStatus.DISPONIVEL, current_driver_id=drivers[1].id,
        ),
        Vehicle(
            tenant_id=tenant.id, plate="GHI3F45", vehicle_type_id=vehicle_types["truck"].id,
            brand="Mercedes-Benz", model="Actros", year=2019, carrier_id=carriers[1].id, capacity=14000,
            status=VehicleStatus.EM_OPERACAO, current_driver_id=drivers[2].id,
        ),
        Vehicle(
            tenant_id=tenant.id, plate="JKL4G56", vehicle_type_id=vehicle_types["van"].id,
            brand="Fiat", model="Ducato", year=2022, carrier_id=carriers[1].id, capacity=1500,
            status=VehicleStatus.DISPONIVEL, current_driver_id=drivers[3].id,
        ),
        Vehicle(
            tenant_id=tenant.id, plate="MNO5H67", vehicle_type_id=vehicle_types["carreta"].id,
            brand="Volvo", model="FH 460", year=2018, carrier_id=carriers[0].id, capacity=24000,
            status=VehicleStatus.EM_MANUTENCAO,
        ),
    ]
    db.add_all(vehicles)
    db.flush()
    return vehicles


def _create_routes(db: Session, tenant: Tenant) -> list[Route]:
    origin = Location(tenant_id=tenant.id, name="CD São Paulo", city="São Paulo", state="SP")
    destination_a = Location(tenant_id=tenant.id, name="CD Campinas", city="Campinas", state="SP")
    destination_b = Location(tenant_id=tenant.id, name="CD Porto Alegre", city="Porto Alegre", state="RS")
    db.add_all([origin, destination_a, destination_b])
    db.flush()

    routes = [
        Route(
            tenant_id=tenant.id, name="São Paulo → Campinas", origin_location_id=origin.id,
            destination_location_id=destination_a.id, distance_km=99, estimated_time_minutes=90,
            operation_type="ENTREGA",
        ),
        Route(
            tenant_id=tenant.id, name="São Paulo → Porto Alegre", origin_location_id=origin.id,
            destination_location_id=destination_b.id, distance_km=1109, estimated_time_minutes=900,
            operation_type="TRANSFERENCIA",
        ),
    ]
    db.add_all(routes)
    db.flush()
    return routes


def _create_operational_data(
    db: Session, tenant: Tenant, admin_user: User, carriers: list[Carrier], vehicles: list[Vehicle],
    drivers: list[Driver], routes: list[Route],
) -> None:
    schedule = Schedule(tenant_id=tenant.id, schedule_date=date.today(), shift="MANHA", created_by=admin_user.id)
    db.add(schedule)
    db.flush()

    item_specs = [
        (routes[0], carriers[0], vehicles[0], drivers[0], ScheduleStatus.EM_OPERACAO, "10231"),
        (routes[0], carriers[1], vehicles[2], drivers[2], ScheduleStatus.ATRASADO, "10232"),
        (routes[1], carriers[0], vehicles[1], drivers[1], ScheduleStatus.PROGRAMADO, "10233"),
    ]
    for route, carrier, vehicle, driver, status, operation_number in item_specs:
        item = ScheduleItem(
            tenant_id=tenant.id, schedule_id=schedule.id, route_id=route.id, carrier_id=carrier.id,
            vehicle_id=vehicle.id, driver_id=driver.id, scheduled_at=datetime.combine(date.today(), datetime.min.time()),
            cargo_description="Carga geral paletizada", quantity=1, status=status, created_by=admin_user.id,
        )
        db.add(item)
        db.flush()

        if status == ScheduleStatus.PROGRAMADO:
            continue  # ainda não virou operação (seção 13: só ao sair de PROGRAMADO)

        operation = Operation(
            tenant_id=tenant.id, schedule_item_id=item.id, operation_number=operation_number, status=status,
            started_at=UTC_NOW - timedelta(hours=1), created_by=admin_user.id,
        )
        db.add(operation)
        db.flush()
        db.add(
            StatusHistory(
                tenant_id=tenant.id, operation_id=operation.id, previous_status=ScheduleStatus.PROGRAMADO,
                new_status=status, changed_by=admin_user.id, changed_at=UTC_NOW - timedelta(minutes=30),
            )
        )

        if status == ScheduleStatus.ATRASADO:
            occurrence_type = db.query(OccurrenceType).filter(
                OccurrenceType.tenant_id == tenant.id, OccurrenceType.name == "Atraso"
            ).one_or_none()
            if occurrence_type is None:
                occurrence_type = OccurrenceType(tenant_id=tenant.id, name="Atraso")
                db.add(occurrence_type)
                db.flush()
            db.add(
                Occurrence(
                    tenant_id=tenant.id, occurrence_type_id=occurrence_type.id, operation_id=operation.id,
                    vehicle_id=vehicle.id, driver_id=driver.id, responsible_user_id=admin_user.id,
                    description="Atraso por trânsito intenso na rodovia de acesso.",
                    severity=OccurrenceSeverity.MEDIA, status=OccurrenceStatus.ABERTA, occurred_at=UTC_NOW,
                    created_by=admin_user.id,
                )
            )


def main() -> None:
    db = SessionLocal()
    try:
        tenant, created = _get_or_create_tenant(db)
        if not created:
            print(f"[seed_demo] Empresa demo já existe (tenant_id={tenant.id}); nada a fazer.")
            return

        _create_license(db, tenant)
        admin_user = _create_admin_user(db, tenant)
        carriers = _create_carriers(db, tenant)
        vehicle_types = _create_vehicle_types(db, tenant)
        drivers = _create_drivers(db, tenant, carriers)
        vehicles = _create_vehicles(db, tenant, vehicle_types, carriers, drivers)
        routes = _create_routes(db, tenant)
        _create_operational_data(db, tenant, admin_user, carriers, vehicles, drivers, routes)

        db.commit()
        print(f"[seed_demo] Empresa demo criada com sucesso (tenant_id={tenant.id}).")
        print(f"[seed_demo] Login: {admin_user.email}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
