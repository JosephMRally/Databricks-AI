# This method is to imitate Scalas datasets in PySpark.
# This is useful when we want to strongly type a dataframe, often in cases of
# reusable methods.
# 
# to use:
# Dataset(my_dataframe, “person”) # will throw an exception if it’s violated
def Dataset(df, schema:StructType, strict=true) -> Dataframe:
    # Emulates Scala’s Dataset
    if strict and len(schema.fieldNames()) != len(df.columns):
        raise Exception("not equal number of columns between the two")

    for field in schema.fields:
        col_name = field.name
        col_type = field.dataType
        col_null = field.nullable

        if col_name in df.columns:

           if not strict:
                 continue

            # check for existence
            if not (col_name in schema.fieldNames()):
                raise Exception(f"column missing: {col_name}")
            elif col_type != df.schema[col_name].dataType:
                raise Exception(
                    f"column type is incorrect for '{col_name}', expected '{col_type}', got '{df.schema[col_name].dataType}'. "
                )

            elif not col_null:
                null_count = df.filter(df[col_name].isNull()).count()
                if null_count > 0:
                    raise Exception("Null Constraint Violation")
        else:
            raise Exception("Schema Enforcement Failed")

    # reorder to match schema
    return df.select(*schema.fieldNames())

# long standing bug in PySpark is that loading a dataframe from a CSV
# file with a schema, it will apply all schema fields except metadata
# this will apply back the metadata field.
def fix_schema(schema:StructType) -> StructType:
    # fix the metadata field after StructType.fromJson
    # StructType.fromJson still has a bug in it where it will not load the metadata portion
    fields = []
    for field_data in struct:
        metadata = [k for k in s_json["fields"] if k["name"] == field_data.name][0]
        metadata = metadata["metadata"] if "metadata" in metadata else {}
        new_field = StructField(
            name=field_data.name,
            dataType=field_data.dataType,
            nullable=field_data.nullable,
            metadata=metadata
        )
        fields.append(new_field)
    return StructType(fields)

s_json = …  # our patient json from above
struct = StructType.fromJson(s_json)
struct = fix_schema(struct)


# Validate a dataframe against it's schema allowing for custom
# rules to be applied to data.
# These rules are similar to CONSTRAINT in SQL, but more robust
# since they are in PySpark.
def validate_dataframe(df, schema:StructType) -> None:
    if isinstance(schema, StructType):
        pass
    elif schema == None:
        schema = df.schema
     else:
        raise ValueError("parameter schema is of an invalid value")

    for field in schema.fields:
        col_name = field.name
        col_type = field.dataType
        col_null = field.nullable
        col_metadata = field.metadata
        # TODO: use a factory design pattern over if-elses 
         if "validation" in col_metadata:
             validation = col_metadata[“validation”]
      # do regex and see if it works on the value as a super simple check
             if “regex_match” in validation:
                   pattern = validation[“regex_match”] 
                   cnt = df.select(F.regexp_count(F.col(col_name), pattern)).collect()[0][0]
                   if cnt > 0:
                      raise Exception(“failed on regex”)
             if “PII” in col_metadata:
                  # TODO: confirm that the field is encrypted
             if “PK” in col_metadata:
                  # TODO: confirm that the row has an unique value
