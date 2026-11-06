#!/usr/bin/env python3
"""products.py - small store inventory CLI backed by a JSON file (stdlib only)."""

import argparse
import json
import os
import re
import sys
import tempfile

PRICE_RE = re.compile(r"^[0-9]+(\.[0-9]{1,2})?$")
STORED_PRICE_RE = re.compile(r"^[0-9]+\.[0-9]{2}$")
DIGITS_RE = re.compile(r"^[0-9]+$")

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


def fail(message, code):
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def name_value(text):
    name = text.strip()
    if not name:
        raise argparse.ArgumentTypeError(
            "name must contain at least one non-whitespace character"
        )
    return name


def price_value(text):
    if not PRICE_RE.fullmatch(text):
        raise argparse.ArgumentTypeError(
            "price must be digits with an optional decimal point and 1-2 digits (e.g. 4.50)"
        )
    whole, _, frac = text.partition(".")
    return f"{int(whole)}.{(frac + '00')[:2]}"


def quantity_value(text):
    if not DIGITS_RE.fullmatch(text):
        raise argparse.ArgumentTypeError("quantity must be a nonnegative integer")
    return int(text)


def id_value(text):
    if not DIGITS_RE.fullmatch(text) or int(text) < 1:
        raise argparse.ArgumentTypeError("ID must be a positive integer")
    return int(text)


def validate_db(db, path):
    def bad(reason):
        fail(f"data file {path!r} violates schema: {reason}", EXIT_FAILURE)

    if not isinstance(db, dict) or set(db) != {"next_id", "products"}:
        bad("top level must be an object with exactly next_id and products")
    next_id = db["next_id"]
    products = db["products"]
    if isinstance(next_id, bool) or not isinstance(next_id, int) or next_id < 1:
        bad("next_id must be a positive integer")
    if not isinstance(products, list):
        bad("products must be an array")
    seen = set()
    for product in products:
        if (
            not isinstance(product, dict)
            or set(product) != {"id", "name", "price", "quantity"}
        ):
            bad("each product must have exactly id, name, price, quantity")
        pid = product["id"]
        if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
            bad("product id must be a positive integer")
        if pid in seen:
            bad(f"duplicate product id {pid}")
        seen.add(pid)
        name = product["name"]
        if not isinstance(name, str) or not name.strip():
            bad("product name must be a string with a non-whitespace character")
        price = product["price"]
        if not isinstance(price, str) or not STORED_PRICE_RE.fullmatch(price):
            bad("product price must be a string with exactly two decimals")
        quantity = product["quantity"]
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity < 0
        ):
            bad("product quantity must be a nonnegative integer")
    if seen and next_id <= max(seen):
        bad("next_id must be greater than every existing product id")


def load_db(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return {"next_id": 1, "products": []}
    except UnicodeDecodeError:
        fail(f"data file {path!r} is not valid UTF-8", EXIT_FAILURE)
    except OSError as exc:
        fail(f"cannot read data file {path!r}: {exc.strerror or exc}", EXIT_FAILURE)
    try:
        db = json.loads(raw)
    except json.JSONDecodeError:
        fail(f"data file {path!r} is not valid JSON", EXIT_FAILURE)
    validate_db(db, path)
    return db


def save_db(path, db):
    directory = os.path.dirname(os.path.abspath(path))
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            prefix=".products-", suffix=".tmp", dir=directory
        )
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(db, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
        tmp_path = None
    except OSError as exc:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        fail(f"cannot write data file {path!r}: {exc.strerror or exc}", EXIT_FAILURE)


def find_product(db, product_id):
    for product in db["products"]:
        if product["id"] == product_id:
            return product
    fail(f"product {product_id} not found", EXIT_FAILURE)


def cmd_add(args):
    db = load_db(args.file)
    product = {
        "id": db["next_id"],
        "name": args.name,
        "price": args.price,
        "quantity": args.quantity,
    }
    db["products"].append(product)
    db["next_id"] += 1
    save_db(args.file, db)
    print(json.dumps(product))


def cmd_list(args):
    db = load_db(args.file)
    products = sorted(db["products"], key=lambda p: p["id"])
    print(json.dumps(products))


def cmd_get(args):
    db = load_db(args.file)
    print(json.dumps(find_product(db, args.id)))


def cmd_update(args):
    db = load_db(args.file)
    product = find_product(db, args.id)
    if args.name is not None:
        product["name"] = args.name
    if args.price is not None:
        product["price"] = args.price
    if args.quantity is not None:
        product["quantity"] = args.quantity
    save_db(args.file, db)
    print(json.dumps(product))


def cmd_delete(args):
    db = load_db(args.file)
    find_product(db, args.id)
    db["products"] = [p for p in db["products"] if p["id"] != args.id]
    save_db(args.file, db)
    print(json.dumps({"deleted_id": args.id}))


def cmd_low_stock(args):
    db = load_db(args.file)
    products = sorted(
        (p for p in db["products"] if p["quantity"] <= args.threshold),
        key=lambda p: p["id"],
    )
    print(json.dumps(products))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="products.py",
        description="Small store product inventory stored in a JSON file.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        default="products.json",
        help="path to the JSON data file (default: products.json)",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    p = sub.add_parser("add", help="add a new product", allow_abbrev=False)
    p.add_argument("--name", required=True, type=name_value)
    p.add_argument("--price", required=True, type=price_value)
    p.add_argument("--quantity", required=True, type=quantity_value)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("list", help="print all products sorted by ID", allow_abbrev=False)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("get", help="print one product", allow_abbrev=False)
    p.add_argument("id", type=id_value)
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("update", help="update one or more fields of a product", allow_abbrev=False)
    p.add_argument("id", type=id_value)
    p.add_argument("--name", type=name_value)
    p.add_argument("--price", type=price_value)
    p.add_argument("--quantity", type=quantity_value)
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("delete", help="delete a product", allow_abbrev=False)
    p.add_argument("id", type=id_value)
    p.add_argument("--yes", action="store_true", required=True)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser(
        "low-stock",
        help="print products with quantity <= threshold, sorted by ID",
        allow_abbrev=False,
    )
    p.add_argument("--threshold", required=True, type=quantity_value)
    p.set_defaults(func=cmd_low_stock)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if (
        args.command == "update"
        and args.name is None
        and args.price is None
        and args.quantity is None
    ):
        parser.error("update requires at least one of --name, --price, --quantity")
    try:
        args.func(args)
    except Exception as exc:
        fail(str(exc) or exc.__class__.__name__, EXIT_FAILURE)


if __name__ == "__main__":
    main()
