import requests
import json
import logging
import threading
import os
from tqdm import tqdm
from pathlib import Path
from multiprocessing.dummy import Pool as ThreadPool

lock = threading.Lock()

OUTPUT_FILE = "db.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10; rv:33.0) Gecko/20100101 Firefox/33.0"
HAS_SUBCATEGORIES = "hasSubcategories"
SUBCATEGORIES = "subcategories"
CATEGORIES = "categories"
IS_REDIRECTED = "isRedirected"
REDIRECT_ID = "redirectCategoryId"
ID = "id"
NAME = "name"
KEY = "key"
PRODUCT_GROUPS = "productGroups"
TYPE = "type"
DEFAULT_TYPE = "default_type"
ELEMENTS = "elements"
COMMERCIAL_COMPONENTS = "commercialComponents"
PRODUCT_GROUP_TYPE = "productGroupType"

class Category:
  def __init__(self, idd: str, key: str, name: str) -> None:
    self.idd = idd
    self.key = key
    self.name = name

  def __str__(self) -> str:
    return f"Category (id={self.idd}, key={self.key}, name={self.name})"


# TODO: Create Product class with valuable fields


# Processes products and returns them by type
def process_products(data: dict) -> list:
  output = []
  for product_group in data.get(PRODUCT_GROUPS, []):
    product_group_type = product_group.get(TYPE, DEFAULT_TYPE)
    for element in product_group.get(ELEMENTS, []):
      for product in element.get(COMMERCIAL_COMPONENTS, []):
        product[PRODUCT_GROUP_TYPE] = product_group_type
        output.append(product)
  return output


# Returns products json, receies category_id
def get_products(category: Category) -> dict:
  url = f"https://www.zara.com/mx/es/category/{category.idd}/products"
  res = requests.get(url, headers={"User-Agent": USER_AGENT})
  if not res.ok:
    logging.error(f"When fetching products returned not ok request: {res.text}")
    return {}
  data = json.loads(res.text)
  return process_products(data)


# Recursively grab every category id
def search_categories(categories: list, out: list):
  if len(categories) <= 0:
    return
  for category in categories:
    has_subcategories = category.get(HAS_SUBCATEGORIES, False)
    if has_subcategories:
      search_categories(category[SUBCATEGORIES], out)
    else:
      is_redirected = category.get(IS_REDIRECTED)
      out.append(
        Category(
          category.get(REDIRECT_ID if is_redirected else ID),
          category.get(NAME),
          category.get(KEY))) 


# Returns every Category{id, name, key}
def get_categories() -> list[dict]:
  url = f" https://www.zara.com/mx/es/categories"
  res = requests.get(url, headers={"User-Agent": USER_AGENT})
  if not res.ok:
    logging.error(f"When fetching categories returned not ok request: {res.text}")
    return {}
  data = json.loads(res.text)
  categories = data.get(CATEGORIES, data.get(SUBCATEGORIES, []))
  out = []
  search_categories(categories, out)
  return out


def build_db() -> dict:
  categories = get_categories()
  logging.info(f"Building Zara database with {len(categories)} categories.")
  db = {}

  def process_category(category):
    products = get_products(category)
    with lock:
      nonlocal db
      db[category.key] = products

  with ThreadPool(os.cpu_count()) as pool:
    pool.map(process_category, categories)

  return db


def write_to_file(db: dict) -> None:
  with open(Path(OUTPUT_FILE), "w") as f:
    f.write(json.dumps(db))
  

def setup_logger(level=logging.DEBUG) -> None:
  logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=level)


if __name__ == "__main__":
  setup_logger(logging.DEBUG)  # Change ERROR to DEBUG for debugging purposes
  db = build_db()
  write_to_file(db)