import os
from datetime import datetime, timedelta, timezone
from typing import Optional
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

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "ip_address": self.ip_address,
            "applications": [app.name for app in self.applications]
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
            "num_replicas": self.num_replicas
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
            return app

    def list_clusters(self):
        with Session(self.engine) as session:
            stmt = select(Cluster).options(selectinload(Cluster.applications))
            clusters = session.scalars(stmt).all()
            result = [c.to_dict() for c in clusters]
            return result
    
    def create_cluster(self, name: str, ip_address: str) -> Cluster:
        with Session(self.engine) as session:
            new_cluster = Cluster(name=name, ip_address=ip_address)
            session.add(new_cluster)
            session.commit()
            session.refresh(new_cluster) 
            _ = new_cluster.applications 
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
            return new_app