# products.py

A small command-line inventory tool for a store, written in Python 3 using only the standard library. Each invocation performs exactly one operation (`add`, `list`, `get`, `update`, `delete`, `low-stock`) against a JSON data file and exits. It never prompts for input, prints only JSON to stdout on success, and writes failures to stderr.

Data is stored as UTF-8 JSON:

```json
{"next_id": 2, "products": [{"id": 1, "name": "Notebook", "price": "4.50", "quantity": 10}]}
```

- IDs start at 1, are auto-assigned, never change on update, and are never reused after deletion.
- Prices are stored and printed as strings with exactly two decimals (input `4.5` is saved as `"4.50"`).
- Missing file is treated as an empty store. Read-only commands never create or rewrite the file; the first successful `add` creates it.
- Saves are atomic (temp file + `os.replace`), so a failed command never alters the file or consumes an ID.

## How to run

```bash
python3 products.py [--file PATH] COMMAND [OPTIONS]
```

- `--file PATH` must come **before** the command and selects the JSON data file. Default is `products.json` in the current working directory.
- Works with Python 3 only; no third-party packages required.

**Exit codes:** `0` success (including help and empty results) · `1` product ID not found, invalid stored data, or file read/write failure · `2` invalid syntax, missing arguments, or invalid input values. Flag abbreviations (e.g. `--quan`) are rejected; only ASCII digits are accepted in numbers.

## Commands

| Command | Purpose | Required options / notes |
|---|---|---|
| `add --name NAME --price PRICE --quantity QTY` | Add a product and print it as a JSON object. | All three flags required. Name must contain a non-whitespace character (trimmed); price is nonnegative with at most 2 decimals; quantity is a nonnegative integer. |
| `list` | Print a JSON array of all products sorted by ID. | Prints `[]` if the store is empty. |
| `get ID` | Print one product as a JSON object. | `ID` must be a positive integer; exit 1 if not found. |
| `update ID [--name] [--price] [--quantity]` | Change only the supplied fields and print the updated product. | Requires at least one field flag; ID is never changed. |
| `delete ID --yes` | Delete a product and print `{"deleted_id": ID}`. | `--yes` is required; exit 1 if the ID doesn't exist. |
| `low-stock --threshold N` | Print a JSON array of products with quantity ≤ N, sorted by ID. | `N` must be a nonnegative integer; prints `[]` if nothing matches. |

`--help` and `COMMAND --help` print usage, exit 0, and never read or change the data file.

## Low-stock feature

### Who it helps and why

`low-stock` is for store owners and staff who need to spot items that have fallen to or below a reorder point before they run out. Instead of reading the whole `list` output and eyeballing quantities, they can run one command at the end of the day, or just before placing a purchase order, and get exactly the products that need restocking, sorted by ID so the output is stable and easy to diff or feed into another script. Because the output is plain JSON, it can be pasted into a report or piped into other tools (`jq`, a spreadsheet, an ordering script) without any cleanup.

### Syntax

```bash
python3 products.py [--file PATH] low-stock --threshold N
```

### Inputs

- `--threshold N` (required): a nonnegative integer, ASCII digits only (`0`, `5`, `20`). Negative numbers, fractions, signs, or anything non-numeric exit with code 2 and print an error to stderr.
- `--file PATH` (optional, before the command): selects the data file; defaults to `products.json`.

### Expected outputs

- On success: a JSON array of products with `quantity <= N`, sorted by ID ascending, exit 0. The command is read-only — it never creates or rewrites the data file, so running it against a missing file simply prints `[]`.
- If no product is at or below the threshold: `[]`, exit 0.

### Runnable example

```bash
python3 products.py add --name "Pen"  --price 2.00  --quantity 5
python3 products.py add --name "Bag"  --price 10.00 --quantity 20
python3 products.py add --name "Desk" --price 40.00 --quantity 50

python3 products.py low-stock --threshold 20
# [{"id": 1, "name": "Pen", "price": "2.00", "quantity": 5}, {"id": 2, "name": "Bag", "price": "10.00", "quantity": 20}]

python3 products.py low-stock --threshold 0
# []   (empty-result edge case: nothing is at or below 0)
```

A missing data file behaves the same way and is left uncreated:

```bash
python3 products.py --file new-store.json low-stock --threshold 99
# []
```
