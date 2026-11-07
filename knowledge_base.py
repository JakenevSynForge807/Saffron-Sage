import logging

import requests

from db import db
from vector_store import delete_documents, get_collection, sync_documents, upsert_documents

log = logging.getLogger(__name__)

HTTP_HEADERS = {"User-Agent": "SaffronSage/1.0 (student project)"}
KNOWLEDGE_TYPES = ["recipe", "nutrition"]
_knowledge_attempted = set()

def fetch_from_food_api(query):
    try:
        response = requests.get(
            "https://www.themealdb.com/api/json/v1/1/search.php",
            params={"s": query}, headers=HTTP_HEADERS, timeout=5,
        )
        response.raise_for_status()
        meals = response.json().get("meals") or []
    except (requests.RequestException, ValueError) as exc:
        # Free public APIs are often slow or down; that is expected, so one line is enough.
        log.warning("TheMealDB lookup failed for %r: %s", query, exc)
        return []

    results = []
    for meal in meals[:2]:
        instructions = (meal.get("strInstructions") or "N/A")[:300]
        text = (
            f"Reference recipe (general knowledge, not a marketplace listing): "
            f"{meal['strMeal']} is a {meal.get('strCategory') or 'food'} dish from "
            f"{meal.get('strArea') or 'unknown'} cuisine. Instructions summary: {instructions} "
            f"Tags: {meal.get('strTags') or 'None'}"
        )
        results.append({"id": f"mealdb_{meal['idMeal']}", "text": text})
    return results


def fetch_nutrition(food_name):
    try:
        response = requests.get(
            "https://world.openfoodfacts.org/cgi/search.pl",
            params={"search_terms": food_name, "search_simple": 1, "action": "process",
                    "json": 1, "page_size": 3},
            headers=HTTP_HEADERS, timeout=5,
        )
        response.raise_for_status()
        products = response.json().get("products", [])
    except (requests.RequestException, ValueError) as exc:
        # Free public APIs are often slow or down; that is expected, so one line is enough.
        log.warning("OpenFoodFacts lookup failed for %r: %s", food_name, exc)
        return []

    results = []
    for product in products[:3]:
        name = product.get("product_name")
        code = product.get("code")
        nutriments = product.get("nutriments", {})
        calories = nutriments.get("energy-kcal_100g")
        if not name or not code or calories is None:
            continue
        # These are packaged supermarket products, so say so: the model must not
        # present them as the nutrition of a seller's home-made dish.
        brand = product.get("brands") or "unknown brand"
        text = (
            f"Approximate nutrition of a similar packaged product ({name}, {brand}): "
            f"{calories} kcal, {nutriments.get('proteins_100g', 'N/A')}g protein, "
            f"{nutriments.get('fat_100g', 'N/A')}g fat per 100g. "
            f"Home-made dishes on the marketplace may differ."
        )
        results.append({"id": f"nutrition_{code}", "text": text})
    return results


def _dish_rows(dish_id=None):
    conn = db()
    try:
        query = """
            SELECT dishesTable.id, dishesTable.dishname AS name, dishesTable.dishprice AS price,
                   usersInfo.fullname AS seller
            FROM dishesTable
            JOIN usersInfo ON dishesTable.sellerid = usersInfo.id
        """
        if dish_id is not None:
            return conn.execute(query + " WHERE dishesTable.id = ?", (dish_id,)).fetchall()
        return conn.execute(query).fetchall()
    finally:
        conn.close()


def _dish_document(dish):
    text = (
        f"{dish['name']} is available on Saffron & Sage marketplace. "
        f"Seller: {dish['seller']}. Price: £{dish['price']:.2f}."
    )
    return f"dish_{dish['id']}", (text, {"type": "dish", "dish_id": dish["id"]})


def _knowledge_key(dish_name):
    return dish_name.strip().lower()


def fetch_and_store_dish_knowledge(dish_name):
    """Fetch recipe and nutrition facts once per dish name."""
    key = _knowledge_key(dish_name)
    if key in _knowledge_attempted:
        return
    existing = get_collection().get(where={"dish": key}, limit=1, include=[])
    if existing["ids"]:
        return
    # Remember the attempt so dishes the APIs know nothing about are not
    # looked up again on every sync (they are retried after a restart).
    _knowledge_attempted.add(key)
    docs = {}
    for item in fetch_from_food_api(dish_name):
        docs[item["id"]] = (item["text"], {"type": "recipe", "dish": key})
    for item in fetch_nutrition(dish_name):
        docs[item["id"]] = (item["text"], {"type": "nutrition", "dish": key})
    upsert_documents(docs)


def sync_dish(dish_id):
    """Called (in the background) after a seller adds a dish."""
    for dish in _dish_rows(dish_id):
        upsert_documents(dict([_dish_document(dish)]))
        fetch_and_store_dish_knowledge(dish["name"])


def remove_dish(dish_id):
    """Called (in the background) after a seller deletes a dish."""
    delete_documents([f"dish_{dish_id}"])


def sync_dishes_to_vector_store():
    dishes = _dish_rows()
    added, removed = sync_documents(dict(_dish_document(dish) for dish in dishes), where={"type": "dish"})
    log.info("Dishes synced: %s embedded, %s removed.", added, removed)

    current_names = {_knowledge_key(dish["name"]) for dish in dishes}
    knowledge = get_collection().get(where={"type": {"$in": KNOWLEDGE_TYPES}}, include=["metadatas"])
    orphaned = [doc_id for doc_id, meta in zip(knowledge["ids"], knowledge["metadatas"])
                if meta.get("dish") not in current_names]
    delete_documents(orphaned)

    for dish in dishes:
        fetch_and_store_dish_knowledge(dish["name"])


def sync_orders_knowledge():
    conn = db()
    try:
        popular = conn.execute("""
            SELECT dishesTable.id, dishesTable.dishname AS name, COUNT(*) AS order_count,
                   usersInfo.fullname AS seller
            FROM orderTable
            JOIN dishesTable ON orderTable.dishid = dishesTable.id
            JOIN usersInfo  ON dishesTable.sellerid = usersInfo.id
            WHERE orderTable.status != 'cancelled'
            GROUP BY dishesTable.id
            ORDER BY order_count DESC
            LIMIT 10
        """).fetchall()
    finally:
        conn.close()

    desired = {
        f"popular_{dish['id']}": (
            f"{dish['name']} by {dish['seller']} is one of the most popular dishes "
            f"with {dish['order_count']} orders.",
            {"type": "popular"},
        )
        for dish in popular
    }
    sync_documents(desired, where={"type": "popular"})


def sync_all():
    log.info("Syncing dishes...")
    sync_dishes_to_vector_store()
    log.info("Syncing order popularity...")
    sync_orders_knowledge()
    log.info("Vector store is ready.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_all()