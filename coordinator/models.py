import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib import request
from sqlalchemy import String, ForeignKey, select, func, desc
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, selectinload
from sqlalchemy import create_engine

from dotenv import load_dotenv
load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"), echo=True)

class Base(DeclarativeBase):
    pass

class Cluster(Base):
    __tablename__ = "clusters"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    ip_address: Mapped[str] = mapped_column(String(15), default="0.0.0.0")
    cores: Mapped[int] = mapped_column(default=4)
    
    applications: Mapped[list["Application"]] = relationship(back_populates="cluster")
    components: Mapped[list["Component"]] = relationship(back_populates="cluster")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "ip_address": self.ip_address,
            "cores": self.cores,
            "applications": [app.to_dict() for app in self.applications] if self.applications else [],
            "components": [comp.to_dict() for comp in self.components] if self.components else []
        }

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    config: Mapped[int] = mapped_column(default=0)
    port: Mapped[int] = mapped_column(default=8080)
    last_latency_check: Mapped[float] = mapped_column(default=0.0)
    last_latency_counter: Mapped[int] = mapped_column(default=0)

    num_replicas: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    
    components: Mapped[list["Component"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"))
    cluster: Mapped["Cluster"] = relationship(back_populates="applications")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "config": self.config,
            "port": self.port,
            "last_latency_check": self.last_latency_check,
            "last_latency_counter": self.last_latency_counter,
            "status": self.status,
            "cluster": self.cluster.name if self.cluster else None,
            "components": [comp.to_dict() for comp in self.components] if self.components else [],
            "num_replicas": self.num_replicas
        }
    
class Component(Base):
    __tablename__ = "components"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    port: Mapped[int] = mapped_column(default=30300)

    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    application: Mapped["Application"] = relationship(back_populates="components")

    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"))
    cluster: Mapped["Cluster"] = relationship(back_populates="components")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "port": self.port,
            "application_id": self.application_id,
            "cluster_id": self.cluster_id
        }
    
class Telemetry(Base):
    __tablename__ = "telemetry"
    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(30))
    value: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "target": self.target,
            "type": self.type,
            "value": self.value,
            "created_at": self.created_at.timestamp()
        }

class InfrastructureManager:
    def __init__(self, engine):
        self.engine = engine

    def update_application(self, name: str, num_replicas: int, config: int,
                           last_latency_check: float, last_latency_counter: int) -> Optional[Application]:
        with Session(self.engine) as session:
            stmt = select(Application).where(Application.name == name)
            app = session.scalar(stmt)

            if not app:
                print(f"Erro: Aplicação '{name}' não encontrada.")
                return None

            app.num_replicas = num_replicas
            app.config = config
            if last_latency_check is not None:
                app.last_latency_check = last_latency_check
            if last_latency_counter is not None:
                app.last_latency_counter = last_latency_counter
            session.commit()
            session.refresh(app)
            _ = app.cluster
            _ = app.components
            return app

    def list_clusters(self):
        with Session(self.engine) as session:
            stmt = select(Cluster).options(selectinload(Cluster.applications))
            clusters = session.scalars(stmt).all()
            result = [c.to_dict() for c in clusters]
            return result
    
    def create_cluster(self, name: str, ip_address: str, cores: int) -> Cluster:
        with Session(self.engine) as session:
            new_cluster = Cluster(name=name, ip_address=ip_address, cores=cores)
            session.add(new_cluster)
            session.commit()
            session.refresh(new_cluster) 
            _ = new_cluster.applications
            _ = new_cluster.components
            return new_cluster
        
    def delete_cluster(self, name: str) -> Optional[Cluster]:
        with Session(self.engine) as session:
            stmt = select(Cluster).options(selectinload(Cluster.applications)).where(Cluster.name == name)
            cluster = session.scalar(stmt)

            if not cluster:
                return None  

            session.delete(cluster)
            session.commit()
            return cluster

    def list_telemetry(self, target: Optional[str] = None, telemetry_type: Optional[str] = None, minutes: Optional[int] = None):
        with Session(self.engine) as session:
            stmt = select(Telemetry)
            
            if target:
                stmt = stmt.where(Telemetry.target == target)
            
            if telemetry_type:
                stmt = stmt.where(Telemetry.type == telemetry_type)
            
            if minutes:
                cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
                stmt = stmt.where(Telemetry.created_at >= cutoff_time)
            
            stmt = stmt.order_by(desc(Telemetry.created_at))
            
            telemetry = session.scalars(stmt).all()
            result = [t.to_dict() for t in telemetry]
            return result

    def create_telemetry(self, target: str, value: str, telemetry_type: str) -> Telemetry:
        with Session(self.engine) as session:
            new_telemetry = Telemetry(target=target, value=value, type=telemetry_type)
            session.add(new_telemetry)
            session.commit()
            session.refresh(new_telemetry)            
            return new_telemetry

    def deploy_application(self, name: str, cluster_name: str, port: int, config: int) -> Optional[Application]:
        with Session(self.engine) as session:
            stmt = select(Cluster).where(Cluster.name == cluster_name)
            cluster = session.scalar(stmt)
            
            if not cluster:
                print(f"Erro: Cluster '{cluster_name}' não encontrado.")
                return None

            new_app = Application(name=name, status="deploying", cluster=cluster, port=port, config=config)
            session.add(new_app)
            session.commit()
            session.refresh(new_app)
            _ = new_app.cluster
            _ = new_app.components
            return new_app
        
    def create_component(self, name: str, cluster_name: str, app_name: str, port: int) -> Optional[Component]:
        with Session(self.engine) as session:
            stmt = select(Cluster).where(Cluster.name == cluster_name)
            cluster = session.scalar(stmt)
            
            if not cluster:
                print(f"Erro: Cluster '{cluster_name}' não encontrado.")
                return None
            
            stmt = select(Application).where(Application.name == app_name)
            app = session.scalar(stmt)

            if not app:
                print(f"Erro: Aplicação '{app_name}' não encontrada no cluster '{cluster_name}'.")
                return None

            new_component = Component(name=name, port=port, application=app, cluster=cluster)
            session.add(new_component)
            session.commit()
            session.refresh(new_component)
            _ = new_component.application
            return new_component
        
    def delete_component(self, name: str) -> Optional[Component]:
        with Session(self.engine) as session:
            stmt = select(Component).where(Component.name == name)
            component = session.scalar(stmt)

            if not component:
                return None  

            session.delete(component)
            session.commit()
            return component