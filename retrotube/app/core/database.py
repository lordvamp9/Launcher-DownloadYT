"""Capa de persistencia local con SQLite + SQLAlchemy.

La base de datos almacena ÚNICAMENTE metadatos de los vídeos descargados y
las listas de reproducción locales del usuario. Nunca se guardan cookies,
tokens ni historial de sesión. Todas las consultas usan el ORM, por lo que
los parámetros viajan siempre parametrizados (sin interpolación de cadenas).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    delete,
    func,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from app.utils.security import database_path


class Base(DeclarativeBase):
    """Clase base declarativa de SQLAlchemy."""


def _utcnow() -> datetime:
    """Marca temporal en UTC (sin información de zona para SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Download(Base):
    """Metadatos de un vídeo descargado."""

    __tablename__ = "downloads"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    thumbnail_path: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    download_date: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    def as_dict(self) -> dict:
        """Representación serializable del registro."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "local_path": self.local_path,
            "thumbnail_path": self.thumbnail_path,
            "channel": self.channel,
            "duration": self.duration,
            "size_bytes": self.size_bytes,
            "download_date": self.download_date,
        }


class Playlist(Base):
    """Lista de reproducción local creada por el usuario."""

    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(9), default="#00AAFF")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    items: Mapped[list["PlaylistItem"]] = relationship(
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistItem.position",
    )


class PlaylistItem(Base):
    """Entrada de una lista de reproducción local."""

    __tablename__ = "playlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False
    )
    video_id: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    downloaded: Mapped[bool] = mapped_column(Boolean, default=False)

    playlist: Mapped[Playlist] = relationship(back_populates="items")


class Database:
    """Fachada sencilla sobre la sesión de SQLAlchemy."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or database_path()
        self._engine = create_engine(
            f"sqlite:///{self._path}", future=True, echo=False
        )
        self._Session: sessionmaker[Session] = sessionmaker(
            bind=self._engine, future=True, expire_on_commit=False
        )
        Base.metadata.create_all(self._engine)

    # ----- Descargas ----------------------------------------------------
    def upsert_download(self, data: dict) -> None:
        """Inserta o actualiza el registro de un vídeo descargado."""
        with self._Session() as session:
            existing = session.get(Download, data["id"])
            if existing is None:
                session.add(Download(**data))
            else:
                for key, value in data.items():
                    setattr(existing, key, value)
            session.commit()

    def list_downloads(
        self,
        channel: Optional[str] = None,
        order_by: str = "fecha",
    ) -> list[dict]:
        """Devuelve los vídeos descargados, opcionalmente filtrados por canal."""
        with self._Session() as session:
            stmt = select(Download)
            if channel:
                # Parámetro vinculado: nunca se interpola la entrada en el SQL.
                stmt = stmt.where(Download.channel == channel)
            if order_by == "tamaño":
                stmt = stmt.order_by(Download.size_bytes.desc())
            elif order_by == "canal":
                stmt = stmt.order_by(Download.channel.asc())
            else:
                stmt = stmt.order_by(Download.download_date.desc())
            return [row.as_dict() for row in session.scalars(stmt).all()]

    def get_download(self, video_id: str) -> Optional[dict]:
        """Recupera un registro de descarga por su ID de vídeo."""
        with self._Session() as session:
            row = session.get(Download, video_id)
            return row.as_dict() if row else None

    def delete_download(self, video_id: str) -> None:
        """Elimina el registro de un vídeo (no toca el archivo en disco)."""
        with self._Session() as session:
            session.execute(delete(Download).where(Download.id == video_id))
            session.commit()

    def stats(self) -> dict:
        """Estadísticas agregadas de la biblioteca descargada."""
        with self._Session() as session:
            total = session.scalar(select(func.count(Download.id))) or 0
            size = session.scalar(select(func.coalesce(
                func.sum(Download.size_bytes), 0))) or 0
            channels = session.scalar(
                select(func.count(func.distinct(Download.channel)))
            ) or 0
            return {
                "total_videos": int(total),
                "total_bytes": int(size),
                "total_gb": round(int(size) / (1024 ** 3), 2),
                "unique_channels": int(channels),
            }

    # ----- Listas de reproducción --------------------------------------
    def create_playlist(self, name: str, color: str = "#00AAFF") -> int:
        """Crea una lista local y devuelve su identificador."""
        with self._Session() as session:
            playlist = Playlist(name=name.strip() or "Sin nombre", color=color)
            session.add(playlist)
            session.commit()
            return playlist.id

    def list_playlists(self) -> list[dict]:
        """Devuelve todas las listas locales con su número de elementos."""
        with self._Session() as session:
            result: list[dict] = []
            for pl in session.scalars(select(Playlist)).all():
                result.append({
                    "id": pl.id,
                    "name": pl.name,
                    "color": pl.color,
                    "created_at": pl.created_at,
                    "count": len(pl.items),
                })
            return result

    def delete_playlist(self, playlist_id: int) -> None:
        """Elimina una lista local y todos sus elementos."""
        with self._Session() as session:
            playlist = session.get(Playlist, playlist_id)
            if playlist is not None:
                session.delete(playlist)
                session.commit()

    def add_to_playlist(self, playlist_id: int, video: dict) -> bool:
        """Añade un vídeo a una lista evitando duplicados.

        Devuelve ``True`` si se añadió y ``False`` si ya existía.
        """
        with self._Session() as session:
            playlist = session.get(Playlist, playlist_id)
            if playlist is None:
                return False
            if any(it.video_id == video["id"] for it in playlist.items):
                return False
            session.add(PlaylistItem(
                playlist_id=playlist_id,
                video_id=video["id"],
                title=video.get("title", ""),
                channel=video.get("channel", ""),
                url=video.get("url", ""),
                duration=int(video.get("duration", 0) or 0),
                position=len(playlist.items),
            ))
            session.commit()
            return True

    def playlist_items(self, playlist_id: int) -> list[dict]:
        """Devuelve los elementos de una lista ordenados por posición."""
        with self._Session() as session:
            playlist = session.get(Playlist, playlist_id)
            if playlist is None:
                return []
            return [{
                "id": it.id,
                "video_id": it.video_id,
                "title": it.title,
                "channel": it.channel,
                "url": it.url,
                "duration": it.duration,
                "position": it.position,
                "downloaded": it.downloaded,
            } for it in playlist.items]

    def remove_playlist_item(self, item_id: int) -> None:
        """Elimina un elemento concreto de una lista."""
        with self._Session() as session:
            session.execute(
                delete(PlaylistItem).where(PlaylistItem.id == item_id)
            )
            session.commit()

    def dispose(self) -> None:
        """Libera el pool de conexiones del motor."""
        self._engine.dispose()


if __name__ == "__main__":
    import tempfile

    tmp = Path(tempfile.gettempdir()) / "retrotube_demo.db"
    db = Database(tmp)
    db.upsert_download({
        "id": "dQw4w9WgXcQ",
        "title": "Demo de prueba",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "local_path": "C:/Videos/demo.mp4",
        "channel": "Canal Demo",
        "duration": 212,
        "size_bytes": 15_000_000,
    })
    print("Descargas:", db.list_downloads())
    print("Estadísticas:", db.stats())
    pid = db.create_playlist("Favoritos", "#33CCFF")
    db.add_to_playlist(pid, {"id": "dQw4w9WgXcQ", "title": "Demo de prueba"})
    print("Listas:", db.list_playlists())
    db.dispose()
    tmp.unlink(missing_ok=True)
