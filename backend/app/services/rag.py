from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate

from app.core.config import settings
from app.services.embeddings import get_embedding_function

# Prompt em português, focado em suporte empresarial
SYSTEM_PROMPT = PromptTemplate(
    input_variables=["context", "question", "chat_history"],
    template="""Você é o assistente de suporte da empresa {company_name}.
Responda de forma clara, objetiva e profissional, baseando-se APENAS no contexto fornecido abaixo.

Se a informação não estiver no contexto, diga educadamente que não encontrou essa informação
nos documentos disponíveis e sugira que o usuário entre em contato com o suporte humano.

Contexto dos documentos:
{context}

Histórico da conversa:
{chat_history}

Pergunta do usuário: {question}

Resposta:""".replace("{company_name}", settings.company_name),
)


def get_rag_chain(session_memory: ConversationBufferWindowMemory) -> ConversationalRetrievalChain:
    """
    Monta a chain RAG com:
    - Retriever: ChromaDB (top-k chunks por similaridade)
    - LLM: Gemini Flash (rápido e gratuito)
    - Memória: janela de 5 turnos de conversa
    """
    llm = ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.2,       # Respostas mais factuais para suporte
        convert_system_message_to_human=True,
    )

    vector_store = Chroma(
        persist_directory=settings.chroma_persist_dir,
        embedding_function=get_embedding_function(),
        collection_name="supportbot_docs",
    )

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": settings.retriever_k},
    )

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=session_memory,
        combine_docs_chain_kwargs={"prompt": SYSTEM_PROMPT},
        return_source_documents=True,
        verbose=False,
    )

    return chain


def ask(question: str, session_memory: ConversationBufferWindowMemory) -> dict:
    """
    Recebe a pergunta, recupera contexto relevante e gera resposta com Gemini.
    Retorna a resposta e as fontes utilizadas.
    """
    chain = get_rag_chain(session_memory)
    result = chain.invoke({"question": question})

    # Extrai fontes únicas usadas na resposta
    sources = []
    seen = set()
    for doc in result.get("source_documents", []):
        src = doc.metadata.get("source", "desconhecido")
        if src not in seen:
            seen.add(src)
            sources.append({
                "source": src,
                "type": doc.metadata.get("type", "?"),
                "page": doc.metadata.get("page"),
            })

    return {
        "answer": result["answer"],
        "sources": sources,
    }
