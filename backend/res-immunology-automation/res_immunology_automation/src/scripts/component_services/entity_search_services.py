
from typing import Dict, List
from duckdb import DuckDBPyConnection
from pandas import DataFrame
import os
import duckdb
from fastapi import HTTPException

db_file_path = "/app/database/entity_search.db"

# To query the phenotype id and name
primary_phenotype_query = """
SELECT
   id,
   name,
   CASE
       WHEN id ILIKE (? || '%') THEN 'id: ' || id
       WHEN dbXRefs_text ILIKE ('%' || ? || '%') THEN 'dbXRef: ' || dbXRefs_text
       WHEN name ILIKE ? THEN 'name: ' || name
       WHEN name ILIKE (? || '%') THEN 'name: ' || name
       WHEN name ILIKE ('%' || ' ' || ? || '%') THEN 'name: ' || name
       ELSE NULL
   END AS matched_column
FROM
   phenotypes
WHERE
   id ILIKE (? || '%') OR
   dbXRefs_text ILIKE ('%' || ? || '%') OR
   name ILIKE ? OR
   name ILIKE (? || '%') OR
   name ILIKE ('%' || ' ' || ? || '%')
ORDER BY
   CASE
       WHEN name ILIKE ? THEN 1
       WHEN name ILIKE (? || '%') THEN 2
       WHEN name ILIKE ('%' || ' ' || ? || '%') THEN 3
       WHEN id ILIKE (? || '%') THEN 4
       WHEN dbXRefs_text ILIKE ('%' || ? || '%') THEN 5
       ELSE 6
   END
"""

# To query synonyms
secondary_phenotype_query = """
SELECT
   id,
   name,
   CASE
       WHEN synonyms_text ILIKE (? || '%') OR synonyms_text ILIKE ('%' || ' ' || ? || '%') THEN 'synonyms: ' || synonyms_text
       ELSE NULL
   END AS matched_column
FROM
   phenotypes
WHERE
   synonyms_text ILIKE (? || '%') OR synonyms_text ILIKE ('%' || ' ' || ? || '%')
"""

# Full text search query
fts_phenotype_query = """
WITH fts_results AS (
    SELECT 
        id, 
        name,
        synonyms_text,
        fts_main_phenotypes.match_bm25(id, ?, conjunctive := 1, fields := 'name') AS name_score,
        fts_main_phenotypes.match_bm25(id, ?, conjunctive := 1, fields := 'synonyms_text') AS synonym_score
    FROM phenotypes
)
SELECT id, name, matched_column
FROM (
    SELECT 
        id,
        name,
        'name: ' || name AS matched_column,
        name_score AS score
    FROM fts_results
    WHERE name_score IS NOT NULL
    UNION
    SELECT 
        id,
        name,
        'synonyms: ' || synonyms_text AS matched_column,
        synonym_score AS score
    FROM fts_results
    WHERE synonym_score IS NOT NULL
) AS all_matches
ORDER BY 
    CASE 
        WHEN matched_column ILIKE 'name:%' THEN 1
        WHEN matched_column ILIKE 'synonyms:%' THEN 2
    END,
    score DESC
"""

# catchall query
substring_query = """
SELECT
   id,
   name,
   CASE
       WHEN name ILIKE ('%' || ? || '%') THEN 'name: ' || name
       WHEN synonyms_text ILIKE ('%' || ? || '%') THEN 'synonyms: ' || synonyms_text
       ELSE NULL
   END AS matched_column
FROM
   phenotypes
WHERE
   name ILIKE ('%' || ? || '%') OR
   synonyms_text ILIKE ('%' || ? || '%')
ORDER BY
   CASE
       WHEN name ILIKE ('%' || ? || '%') THEN 1
       WHEN synonyms_text ILIKE ('%' || ? || '%') THEN 2
       ELSE 3
   END
"""

def get_db_connection() -> DuckDBPyConnection: 
    if not db_file_path:
        raise HTTPException(status_code=500, detail="Database path is not set")
    conn = duckdb.connect(db_file_path, read_only=True)
    try:
        yield conn
    finally:
        conn.close()


def lexical_phenotype_search(search_string: str, conn: DuckDBPyConnection) -> DataFrame:
   """
   Query the database for phenotypes lexically matching the search term with a result limit.
  
   Parameters:
       search_term (str): The search term for filtering phenotypes.
       limit (int): Maximum number of results to return.
       conn (DuckDBPyConnection): The database connection.


   Returns:
       List[Dict]: Query results as a list of dictionaries.
   """
   query = f"({primary_phenotype_query}) UNION ALL ({fts_phenotype_query}) UNION ALL ({secondary_phenotype_query}) UNION ALL ({substring_query})"
   results = conn.execute(query, (search_string, ) * query.count('?')).df()
   results.drop_duplicates(subset = ['id', 'name'], keep = 'first', inplace = True)
   if results.empty:
    return DataFrame()
   return results
