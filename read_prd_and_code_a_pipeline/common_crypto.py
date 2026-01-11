from cryptography.fernet import Fernet
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

"""
# This is an example of how to perform business logic on encrypted fields. 
# See the full article at: https://medium.com/@ultrarelativistic/data-isolation-and-governance-within-pyspark-dataframes-6bfb337c6f04
#
# Step 1. Create a method with the transformations on the encrypted fields
def business_logic(df):
  return (
    df
    .filter(col("ssn").isNotNull())
    .select("id", "ssn")
    )

# Step 2. pass a dataframe of encrypted data with the metadata specifying which fields are encrypted and the business logic like this
final_df = with_fernet(df, ["ssn"], business_logic)
"""

# Load once - do this in your notebook or job initialization
FERNET_KEY = dbutils.secrets.get(scope="crypto", key=f"{current_user}-fernet-main-key-2025")
fernet_singleton = Fernet(FERNET_KEY.encode())

def encrypt_fernet(plain_text):
    if plain_text is None:
        return None
    return cipher_suite.encrypt(plain_text.encode()).decode()

def decrypt_fernet(encrypted_text):
    if encrypted_text is None:
        return None
    return cipher_suite.decrypt(encrypted_text.encode()).decode()

def decrypt_columns(df: DataFrame, columns: list[str]) -> DataFrame:
    return df.transform(
        lambda d: d.select(
            *[
                decrypt_fernet(col(c)).alias(c) if c in columns else col(c)
                for c in d.columns
            ]
        )
    )

def encrypt_columns(df: DataFrame, columns: list[str]) -> DataFrame:
    return df.transform(
        lambda d: d.select(
            *[
                encrypt_fernet(col(c)).alias(c) if c in columns else col(c)
                for c in d.columns
            ]
        )
    )

def with_fernet(df: DataFrame,columns: list[str],fn: Callable[[DataFrame], DataFrame],
) -> DataFrame:
  encrypted_columns = [c for c in df.schema.metadata if "PII" in c or "PHI" in c or ("encrypted" in c and c["encrypted"])]
  return (
    df
    .transform(lambda d: decrypt_columns(d, encrypted_columns)
    .transform(fn)
    .transform(lambda d: encrypt_columns(d, encrypted_columns))
    )
  
