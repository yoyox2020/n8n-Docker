from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String, Text, DateTime, func

from app.database import Base

_VECTOR_DIM = 768  # nomic-embed-text menghasilkan 768 dimensi


class NodeEmbedding(Base):
    """
    Menyimpan vektor embedding setiap node n8n menggunakan pgvector.

    Kolom:
      node_type    - identifier unik node, misal: n8n-nodes-base.serviceNow
      display_name - nama tampilan: "ServiceNow"
      description  - deskripsi bilingual EN+ID yang dipakai saat embed
      embedding    - vektor Vector(768) — tipe native pgvector, bukan ARRAY(REAL)
                     Mendukung operator <=> (cosine), <-> (L2), <#> (inner product)
                     dan index HNSW/IVFFlat untuk pencarian cepat
      catalog_hash - MD5 dari catalog + versi embedding untuk deteksi perlu regenerasi
      updated_at   - kapan terakhir diperbarui
    """

    __tablename__ = "node_embeddings"

    node_type    = Column(String(256), primary_key=True)
    display_name = Column(String(256), nullable=True)
    description  = Column(Text, nullable=True)
    embedding    = Column(Vector(_VECTOR_DIM), nullable=False)
    catalog_hash = Column(String(32), nullable=True)
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
