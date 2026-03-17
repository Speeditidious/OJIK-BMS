"""pgvector-based document retrieval for chatbot RAG."""
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_embedding(text_content: str, openai_client: Any) -> list[float]:
    """
    Generate an embedding vector for the given text using OpenAI.

    Args:
        text_content: The text to embed.
        openai_client: An initialized OpenAI async client.

    Returns:
        A list of floats representing the embedding vector (dimension: 1536).
    """
    response = await openai_client.embeddings.create(
        input=text_content,
        model="text-embedding-3-small",
    )
    return response.data[0].embedding


async def retrieve_relevant_documents(
    query_embedding: list[float],
    db: AsyncSession,
    top_k: int = 5,
    category: str | None = None,
) -> list[dict]:
    """
    Retrieve the most relevant documents using cosine similarity search with pgvector.

    Args:
        query_embedding: The query embedding vector.
        db: Async database session.
        top_k: Number of top results to return.
        category: Optional category filter.

    Returns:
        List of document dicts with id, title, content, and similarity score.
    """
    embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

    category_filter = ""
    if category:
        category_filter = f"AND category = '{category}'"

    sql = text(f"""
        SELECT
            id::text,
            category,
            title,
            content,
            chunk_index,
            1 - (embedding <=> :embedding::vector) AS similarity
        FROM chatbot_documents
        WHERE embedding IS NOT NULL
        {category_filter}
        ORDER BY embedding <=> :embedding::vector
        LIMIT :top_k
    """)

    result = await db.execute(
        sql,
        {"embedding": embedding_str, "top_k": top_k},
    )
    rows = result.fetchall()

    return [
        {
            "id": row.id,
            "category": row.category,
            "title": row.title,
            "content": row.content,
            "chunk_index": row.chunk_index,
            "similarity": float(row.similarity),
        }
        for row in rows
    ]


def format_context_from_documents(documents: list[dict]) -> str:
    """Format retrieved documents into a context string for the LLM prompt."""
    if not documents:
        return ""

    context_parts = []
    for i, doc in enumerate(documents, 1):
        title = doc.get("title", "Untitled")
        content = doc.get("content", "")
        similarity = doc.get("similarity", 0.0)

        context_parts.append(
            f"[문서 {i}] {title} (관련도: {similarity:.2f})\n{content}"
        )

    return "\n\n---\n\n".join(context_parts)
