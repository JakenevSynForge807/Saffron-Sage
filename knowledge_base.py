from vector_store import add_to_vector_store
from db import db
import requests

def fetch_from_food_api(query):
    try:
        url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={query}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if not data["meals"]:
            return []

        results = []
        for meal in data["meals"][:5]:  # limit to 5
            text = f"""
        {meal['strMeal']} is a {meal['strCategory']} dish from {meal['strArea']} cuisine.
        Instructions summary: {meal['strInstructions'][:300] if meal['strInstructions'] else 'N/A'}
        Tags: {meal['strTags'] or 'None'}"""
            results.append({
                "id": f"mealdb_{meal['idMeal']}",
                "text": text.strip()
            })
        return results
    except:
        return []
    
def fetch_nutrition(food_name):
    try:
        url = f"https://world.openfoodfacts.org/cgi/search.pl"
        params = {
            "search_terms": food_name,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 3
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        results = []
        for product in data.get("products", [])[:3]:
            name     = product.get("product_name", "Unknown")
            calories = product.get("nutriments", {}).get("energy-kcal_100g", "N/A")
            protein  = product.get("nutriments", {}).get("proteins_100g", "N/A")
            fat      = product.get("nutriments", {}).get("fat_100g", "N/A")

            if name and name != "Unknown":
                text = f"{name}: approximately {calories} kcal per 100g, {protein}g protein, {fat}g fat."
                results.append({
                    "id": f"nutrition_{name[:30].replace(' ', '_')}",
                    "text": text
                })
        return results
    except:
        return []
    
def sync_dishes_to_vector_store(dish_id=None):
    conn    = db()
    query = """
        SELECT dishesTable.id, dishesTable.dishname AS name, dishesTable.dishprice AS price,
                   usersInfo.fullname AS seller
        FROM dishesTable
        JOIN usersInfo ON dishesTable.sellerid = usersInfo.id
    """
    if dish_id is not None:
        query += " WHERE dishesTable.id = ?"
        dishes = conn.execute(query, (dish_id,)).fetchall()
    else:
        dishes = conn.execute(query).fetchall()
    conn.close()

    for dish in dishes:
        text = f"""
        {dish['name']} is available on Saffron & Sage marketplace.
        Seller: {dish['seller']}
        Price: £{dish['price']}
        """
        add_to_vector_store(
            docid=f"dish_{dish['id']}",
            text=text.strip(),
            metadata={"type": "dish", "dish_id": dish["id"]}
        )

        fetch_and_store_dish_knowledge(dish["name"])

    print(f"Synced {len(dishes)} dishes!")

def fetch_and_store_dish_knowledge(dish_name):
    """
    When a dish is added, fetch real knowledge about it
    from free APIs and store in vector DB
    """
    meal_results = fetch_from_food_api(dish_name)
    for item in meal_results:
        add_to_vector_store(
            docid=item["id"],
            text=item["text"],
            metadata={"type": "recipe", "dish": dish_name}
        )

    nutrition_results = fetch_nutrition(dish_name)
    for item in nutrition_results:
        add_to_vector_store(
            docid=item["id"],
            text=item["text"],
            metadata={"type": "nutrition", "dish": dish_name}
        )

def sync_orders_knowledge():
    conn    = db()
    popular = conn.execute("""
        SELECT dishesTable.dishname AS name, COUNT(*) as order_count,
                   usersInfo.fullname AS seller
        FROM orderTable
        JOIN dishesTable ON orderTable.dishid = dishesTable.id
        JOIN usersInfo  ON dishesTable.sellerid = usersInfo.id
        GROUP BY dishesTable.id
        LIMIT 10
    """).fetchall()
    conn.close()

    for dish in popular:
        text = f"{dish['name']} by {dish['seller']} is one of the most popular dishes with {dish['order_count']} orders."
        add_to_vector_store(
            docid=f"popular_{dish['name'][:30].replace(' ', '_')}",
            text=text,
            metadata={"type": "popular"}
        )

def sync_all():
    print("Syncing dishes...")
    sync_dishes_to_vector_store()

    print("Syncing order popularity...")
    sync_orders_knowledge()

    print("Done! Vector store is ready.")

if __name__ == "__main__":
    sync_all()