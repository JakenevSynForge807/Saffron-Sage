import os
from dotenv import load_dotenv
from flask import current_app, jsonify, redirect, render_template, request, session, url_for
from google import genai
from google.genai import types

from db import db as get_db
from db import ensure_chat_tables
from guardrails import is_topic_allowed, sanitise_input
from vector_store import search_vector_store

load_dotenv()

genai_client = None
MODEL_NAME = "gemini-3.8-flash"


def get_genai_client():
    global genai_client
    if genai_client is None:
        genai_client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=60000),
        )
    return genai_client


def get_user_context(conn):
    role = session.get("role")
    name = session.get("fullname", "there")
    user_id = session.get("id")

    if role == "seller":
        dishes = conn.execute(
            "SELECT dishname, dishprice FROM dishesTable WHERE sellerid = ? ORDER BY dishname",
            (user_id,),
        ).fetchall()
        orders = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(CASE WHEN orderTable.status = 'pending' THEN 1 ELSE 0 END), 0) AS pending,
                   COALESCE(SUM(CASE WHEN orderTable.status = 'completed' THEN 1 ELSE 0 END), 0) AS completed
            FROM orderTable
            JOIN dishesTable ON orderTable.dishid = dishesTable.id
            WHERE dishesTable.sellerid = ?
            """,
            (user_id,),
        ).fetchone()
        dishes_list = "\n".join(
            f"- {dish['dishname']}: £{dish['dishprice']:.2f}" for dish in dishes
        ) or "No dishes listed."
        return f"""
        SELLER CONTEXT for {name}:
        Dishes listed: {dishes_list}
        Order Summary: Total Orders: {orders['total']}, Pending: {orders['pending']}, Completed: {orders['completed']}
        """

    my_orders = conn.execute(
        """
        SELECT dishesTable.dishname, orderTable.status, orderTable.quantity
        FROM orderTable
        JOIN dishesTable ON orderTable.dishid = dishesTable.id
        WHERE orderTable.buyerid = ?
        ORDER BY orderTable.id DESC
        LIMIT 5
        """,
        (user_id,),
    ).fetchall()
    all_dishes = conn.execute(
        """
        SELECT dishesTable.dishname, dishesTable.dishprice,
               usersInfo.fullname AS seller
        FROM dishesTable
        JOIN usersInfo ON dishesTable.sellerid = usersInfo.id
        ORDER BY dishesTable.dishname
        """
    ).fetchall()
    order_history = "\n".join(
        f"- {order['dishname']} (Quantity: {order['quantity']}) - Status: {order['status']}"
        for order in my_orders
    ) or "No orders placed."
    available_dishes = "\n".join(
        f"- {dish['dishname']} by {dish['seller']}: £{dish['dishprice']:.2f}"
        for dish in all_dishes
    ) or "No dishes available."
    return f"""
        BUYER CONTEXT for {name}:
        Recent Orders: {order_history}
        Available Dishes: {available_dishes}
        """


def build_prompt(user_question, user_context, rag_context, role):
    return f"""
    You are a helpful assistant for Saffron & Sage, a food marketplace. You will help {'seller manage food business' if role == 'seller' else 'buyer find and order food'}
    Strict Rules:
    - Only answer questions related to food, dishes, recipes, nutrition, and marketplace inquiries.
    - For a greeting or brief conversational opener, respond warmly and invite a food or marketplace question.
    - If the question is off-topic, respond with "I'm sorry, I can only help with food-related questions and marketplace inquiries."
    - If the question is about a dish, provide information from the knowledge base and vector store
    - Never make information up about a dish. Only use the information provided in the knowledge base and vector store.
    - If the question is about a dish that is not in the knowledge base, respond with "I'm sorry, I don't have information about that dish."
    - If you don't know something, say honestly
    - Keep answers concise and practical, max 3-4 sentences
    - Be warm and friendly in your tone

    Knowledge Base:
    {chr(10).join(rag_context) if rag_context else "No relevant knowledge found."}

    User Data:
    {user_context}

    User Question:
    {user_question}

    Answer in a helpful, grounded way based on the information provided above.
    """


def _is_json_request():
    return "application/json" in request.headers.get("Accept", "")


def _page_context(conn, user_id, chat, error=None, question=""):
    chats = conn.execute(
        "SELECT * FROM ai_chats WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    messages = (
        conn.execute(
            "SELECT role, content FROM ai_messages WHERE chat_id = ? ORDER BY id",
            (chat["id"],),
        ).fetchall()
        if chat else []
    )
    return render_template(
        "ai_assistant.html",
        chats=chats,
        active_chat=chat,
        messages=messages,
        error=error,
        question=question,
    )


def assistant():
    conn = get_db()
    try:
        ensure_chat_tables(conn)
        user_id = session["id"]
        chat_id = (
            request.args.get("chat_id", type=int)
            if request.method == "GET"
            else request.form.get("chat_id", type=int)
        )
        if chat_id:
            chat = conn.execute(
                "SELECT * FROM ai_chats WHERE id = ? AND user_id = ?",
                (chat_id, user_id),
            ).fetchone()
        else:
            chat = conn.execute(
                "SELECT * FROM ai_chats WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
                (user_id,),
            ).fetchone()

        if request.method == "POST":
            if chat is None:
                return jsonify(error="This chat no longer exists."), 404

            raw_question = request.form.get("question", "")
            question = sanitise_input(raw_question)
            if not question or len(raw_question) > 2000:
                error = "Please enter a question between 1 and 2,000 characters."
                if _is_json_request():
                    return jsonify(error=error), 400
                return _page_context(conn, user_id, chat, error, raw_question)

            allowed, status = is_topic_allowed(question)
            if not allowed:
                answer = status
            else:
                try:
                    rag_context = search_vector_store(question, n_results=5)
                    user_context = get_user_context(conn)
                    prompt = build_prompt(question, user_context, rag_context, session.get("role"))
                    response = get_genai_client().models.generate_content(
                        model=MODEL_NAME,
                        contents=prompt,
                    )
                    answer = response.text
                    if not answer:
                        raise RuntimeError("The assistant returned an empty response.")
                except Exception:
                    current_app.logger.exception("Unable to generate an assistant response.")
                    error = "Sorry, I could not process that right now. Please try again later."
                    if _is_json_request():
                        return jsonify(error=error), 503
                    return _page_context(conn, user_id, chat, error, question)

            title = question[:45]
            conn.execute(
                "INSERT INTO ai_messages (chat_id, role, content) VALUES (?, 'user', ?)",
                (chat["id"], question),
            )
            conn.execute(
                "INSERT INTO ai_messages (chat_id, role, content) VALUES (?, 'assistant', ?)",
                (chat["id"], answer),
            )
            conn.execute(
                "UPDATE ai_chats SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, chat["id"]),
            )
            conn.commit()
            if _is_json_request():
                return jsonify(answer=answer, title=title)
            return redirect(url_for("main.ai_assistant", chat_id=chat["id"]))

        return _page_context(conn, user_id, chat)
    finally:
        conn.close()
