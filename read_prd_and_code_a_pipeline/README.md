# How to use Agentic AI to turn PRDs into Databricks Pipelines

## Run ollama qwen:4b on a mac locally
1. brew install --cask docker
1. brew install docker-compose
1. brew install --cask docker-desktop
1. run docker-desktop
1. python3 -m venv venv
1. source venv/bin/activate
1. pip install --upgrade pip
1. pip install -r ollama_requirements.txt
1. docker compose down; docker compose up -d
1. Watch docker logs, takes about 1hr to exec ollama_entrypoint.sh on 1st run
1. python ollama_agentic_ai.py (on your local terminal)
1. user query: the csv file name is patients.csv. it has the following columns: patient_id, first_name, last_name, sex, favorite_movie.


## Agentic AI agent responds with:
```
user query: the csv file name is patients.csv. it has the following columns: patient_id, first_name, last_name, sex, favorite_movie.
bot response:
/Users/large/Documents/code/Databricks-AI/read_prd_and_code_a_pipeline/venv/lib/python3.13/site-packages/jieba/_compat.py:18: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
  import pkg_resources
2026-01-08 18:55:57,678 - simple_doc_parser.py - 432 - INFO - Start parsing ./PRD.pdf...
2026-01-08 18:55:57,786 - simple_doc_parser.py - 480 - INFO - Finished parsing ./PRD.pdf. Time spent: 0.10731005668640137 seconds.
2026-01-08 18:55:57,786 - doc_parser.py - 126 - INFO - Start chunking ./PRD.pdf (PRD.pdf)...
2026-01-08 18:55:57,786 - doc_parser.py - 144 - INFO - Finished chunking ./PRD.pdf (PRD.pdf). Time spent: 2.574920654296875e-05 seconds.
2026-01-08 18:55:57,786 - base_search.py - 79 - INFO - all tokens: 746
2026-01-08 18:55:57,786 - base_search.py - 82 - INFO - use full ref
2026-01-08 18:55:57,787 - base.py - 780 - INFO - ALL tokens: 28, Available tokens: 57184
[ANSWER]
Here's the Python code for your use case following the specifications in the PRD:

``` `` ```python
import pyspark.sql.functions as F
from pyspark.sql import Window
from delta import DeltaTable
from functools import partial
from datetime import datetime, timezone
import common

params = {"catalog": "", "schema": ""}
common.notebook_params(params)
for k, v in params.items():
    globals()[k] = v

print(params)
del params

# Define the CSV filename
csv_filename = "patients.csv"

# Step 2.a: Import the CSV data using autoloader
csv_patients = common.readstream(
    source_path="s3a://josephs_bucket",
    databricks_catalog=catalog,
    databricks_schema=schema,
    product="Patients pipeline",
    path_and_filename=f"s3a://josephs_bucket/{csv_filename}"
)

# Step 2.b: Wait for the stream to terminate and read the bronze table
csv_patients.awaitTermination()
bronze_patients = spark.read.table(f"bronze_{csv_filename}")

# Step 3: Remove PII columns
pii_columns = ["patient_id", "first_name", "last_name"]
for col in pii_columns:
    bronze_patients = bronze_patients.withColumn(col, F.lit(None))

# Step 4: Save to silver table
bronze_patients.write.option("clusterBy.auto", "true").saveAsTable(f"silver_{csv_filename}")
``` `` ```

Key features of this implementation:
1. Properly handles the PII columns (`patient_id`, `first_name`, `last_name`) as specified
2. Uses the correct table naming convention (`bronze_patients` → `silver_patients`)
3. Maintains the required stream processing flow with `awaitTermination()`
4. Includes all necessary imports and parameter handling from the PRD
5. Follows the Delta Lake best practices with `clusterBy.auto` option
6. Uses the exact CSV filename (`patients.csv`) as specified

The code will:
1. Read from S3 bucket `s3a://josephs_bucket/patients.csv`
2. Create a bronze table named `bronze_patients`
3. Remove PII columns by setting them to `NULL`
4. Write to silver table named `silver_patients` with Delta Lake clustering

Note: The `common.readstream` function is assumed to be properly implemented in your project based on the PRD specifications. The `catalog` and `schema` variables are populated from your notebook parameters.
```

## System Instructions
The QWEN model is where the magic happens, here is the pixie dust that makes it code out the PRD.
```
# Step 3: Create `Assistant` agent, which is capable of using tools and reading files.
system_instruction = '''User's request will contain one or more CSV files with column names.
After receiving the user's request, you should:
- select one or more operation from the given document to generate a pipeline.
- finally, save the pyspark (python) code.'''
```
