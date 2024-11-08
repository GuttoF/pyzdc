import json
import logging
from pathlib import Path
from typing import Dict

import duckdb
import unidecode

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

db_path = Path(__file__).resolve().parents[1] / "data" / "db" / "db.db"
json_dir = Path(__file__).resolve().parents[1] / "json"
json_paths = {
    "english": json_dir / "columns_translated_english.json",
    "portuguese": json_dir / "columns_translated_portuguese.json",
}


def load_json(language: str = "english") -> Dict[str, str]:
    """
    Load a JSON file containing column mappings based on the specified language.

    Args:
        language (str): The language for which to load the column mappings.
                        Supported values are 'english' and 'portuguese'.
                        Defaults to 'english'.

    Returns:
        Dict[str, str]: A dictionary containing the column mappings.

    Raises:
        ValueError: If the specified language is not supported.
        FileNotFoundError: If the JSON file for the specified language is not found.
        json.JSONDecodeError: If there is an error decoding the JSON file.
        Exception: For any other unexpected errors.
    """
    if language not in json_paths:
        raise ValueError(
            "Language not supported. Please choose 'english' or 'portuguese'."
        )

    json_path = json_paths[language]

    try:
        with open(json_path, "r") as file:
            columns_mapping = json.load(file)
        logging.info(f"Column mapping for '{language}' loaded successfully.")
        return dict(columns_mapping)
    except FileNotFoundError:
        logging.error(f"JSON file for '{language}' not found in {json_path}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON file: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise


def rename_db_columns(
    db_path: Path, table_name: str = "sinan", language: str = "english"
) -> None:
    """
    Renames columns in a DuckDB table based on a JSON mapping and removes
    accents from column names.

    Args:
        db_path (Path): The path to the DuckDB database file.
        table_name (str, optional): The name of the table to rename columns in.
                                    Defaults to "sinan".
        language (str, optional): The language to use for loading the JSON mapping.
                                  Defaults to "english".

    Raises:
        FileNotFoundError: If the database file does not exist at the specified path.
        Exception: If there is an error during the renaming process, the transaction
                   is rolled back and the error is raised.

    Notes:
        - The function first removes accents from existing column names.
        - Then, it renames columns based on the provided JSON mapping.
        - If any columns in the JSON mapping are not found in the database,
          a warning is logged.
    """
    if not db_path.exists():
        logging.error(f"Database not found at {db_path}")
        raise FileNotFoundError(f"Database not found at {db_path}")

    column_mapping = load_json(language)

    try:
        conn = duckdb.connect(str(db_path))

        conn.begin()

        existing_columns = {
            col[0]: unidecode.unidecode(col[0])
            for col in conn.execute(f"DESCRIBE {table_name}").fetchall()
        }

        unmapped_columns = []

        for col, normalized_col in existing_columns.items():
            if col != normalized_col:
                conn.execute(
                    f'ALTER TABLE {table_name} RENAME COLUMN "{col}" '
                    f'TO "{normalized_col}"'
                )
                logging.info(
                    f"Removed accents from column '{col}' to '{normalized_col}'"
                )

        for old_name, new_name in column_mapping.items():
            normalized_old_name = unidecode.unidecode(old_name)
            if normalized_old_name in existing_columns.values():
                conn.execute(
                    f'ALTER TABLE {table_name} RENAME COLUMN "{normalized_old_name}" '
                    f'TO "{new_name}"'
                )
            else:
                unmapped_columns.append(old_name)

        conn.commit()
        conn.close()

        if unmapped_columns:
            logging.warning(
                "The following columns were not found in the JSON mapping or database "
                "and were not renamed:"
            )
            for col in unmapped_columns:
                logging.warning(f" - {col}")
        else:
            logging.info("All columns renamed successfully.")

    except Exception as e:
        logging.error(f"Error renaming columns in DuckDB: {e}")
        if conn:
            conn.rollback()
        raise


if __name__ == "__main__":
    rename_db_columns(db_path, "sinan")
