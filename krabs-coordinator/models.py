import os
from typing import Optional
from sqlalchemy import String, ForeignKey, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, selectinload
from dotenv import load_dotenv
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"), echo=True)

load_dotenv()

class Base(DeclarativeBase):
    pass

class Cluster(Base):
    __tablename__ = "clusters"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    ip_address: Mapped[str] = mapped_column(String(15), default="0.0.0.0")
    applications: Mapped[list["Application"]] = relationship(back_populates="cluster")
    telemetries: Mapped[list["Telemetry"]] = relationship(back_populates="cluster")

    # Novo método para serialização
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "ip_address": self.ip_address,
            "applications": [app.name for app in self.applications] # Lista simples de nomes
        }

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    config: Mapped[int] = mapped_column(default=0)
    port: Mapped[int] = mapped_column(default=8080)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"))
    cluster: Mapped["Cluster"] = relationship(back_populates="applications")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "config": self.config,
            "port": self.port,
            "cluster": self.cluster.name # Retorna apenas o nome do cluster
        }
    
class Telemetry(Base):
    __tablename__ = "telemetry"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(30))

    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"))
    cluster: Mapped["Cluster"] = relationship(back_populates="telemetries")

    # Novo método para serialização
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "cluster": self.cluster.name # Retorna apenas o nome do cluster
        }

class InfrastructureManager:
    def __init__(self, engine):
        self.engine = engine

    def list_clusters(self):
        with Session(self.engine) as session:
            # A MÁGICA ESTÁ AQUI: .options(selectinload(...))
            stmt = select(Cluster).options(selectinload(Cluster.applications))
            
            clusters = session.scalars(stmt).all()
            
            # Agora podemos converter para dict mesmo se a sessão fechar depois,
            # pois os dados de 'applications' já estão na memória.
            result = [c.to_dict() for c in clusters]
            
            return result
    
    def create_cluster(self, name: str, ip_address: str) -> Cluster:
        with Session(self.engine) as session:
            new_cluster = Cluster(name=name, ip_address=ip_address)
            session.add(new_cluster)
            session.commit()
            
            # Atualiza o objeto com o ID gerado pelo banco
            session.refresh(new_cluster) 
            
            # --- A CORREÇÃO ESTÁ AQUI ---
            # Acessamos a propriedade 'applications' para que o SQLAlchemy 
            # carregue a lista (vazia) na memória AGORA, enquanto a sessão está aberta.
            # Isso evita o "Lazy Load" fora da sessão.
            _ = new_cluster.applications 
            
            # Opcional: Se quiser ser explícito e evitar query desnecessária (já que é novo):
            # new_cluster.applications = [] 
            
            return new_cluster
        
    def delete_cluster(self, name: str) -> Optional[Cluster]:
        with Session(self.engine) as session:
            # 1. Primeiro, BUSCAMOS o objeto real (executando a query)
            stmt = select(Cluster).options(selectinload(Cluster.applications)).where(Cluster.name == name)
            
            # Usamos .scalar() para pegar um único resultado (ou None)
            cluster = session.scalar(stmt)

            # 2. Verificamos se ele foi encontrado
            if not cluster:
                return None  # Ou lançar uma exceção, dependendo da sua regra

            # 3. Agora sim, deletamos o objeto
            session.delete(cluster)
            session.commit()
            
            # O objeto 'cluster' ainda existe na memória do Python com os dados antigos,
            # mesmo tendo sido removido do banco.
            return cluster

    def list_telemetry(self):
        with Session(self.engine) as session:
            # A MÁGICA ESTÁ AQUI: .options(selectinload(...))
            stmt = select(Telemetry).options(selectinload(Telemetry.cluster)) # CORRECT
            
            telemetry = session.scalars(stmt).all()
            
            # Agora podemos converter para dict mesmo se a sessão fechar depois,
            # pois os dados de 'applications' já estão na memória.
            result = [t.to_dict() for t in telemetry]
            
            return result

    def create_telemetry(self, name: str, value: str, cluster_name: str) -> Telemetry:
        with Session(self.engine) as session:
            stmt = select(Cluster).where(Cluster.name == cluster_name)
            cluster = session.scalar(stmt)

            if not cluster:
                print(f"Erro: Cluster '{cluster_name}' não encontrado.")
                return None

            new_telemetry = Telemetry(name=name, value=value, cluster=cluster)
            session.add(new_telemetry)
            session.commit()
            session.refresh(new_telemetry)
            _ = new_telemetry.cluster
            
            return new_telemetry

    def deploy_application(self, name: str, cluster_name: str, port: int, config: int) -> Optional[Application]:
        with Session(self.engine) as session:
            # Busca o cluster pelo nome
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