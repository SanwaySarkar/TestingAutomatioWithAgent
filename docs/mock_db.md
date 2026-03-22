# Mock Database Documentation

## Overview

The `mock_db.py` file simulates an external database for lookup operations in the ETL pipeline. It provides deterministic values for database key lookups based on ISIN (International Securities Identification Number) codes, enabling the system to function without requiring a real database connection.

## Purpose

This mock database serves several important functions:
- Enables offline development and testing
- Provides consistent, predictable lookup values
- Demonstrates the database integration pattern
- Allows validation of DB lookup functionality
- Facilitates reproducible test scenarios

## Data Structure

The mock database uses a dictionary with tuple keys:
- Key format: `(isin, key)` where `isin` is a string and `key` is a database key name
- Value format: String representation of numeric values

## Sample Data

### ISINs
The database includes 5 sample ISIN codes:
- INF000A1
- INF000B2
- INF000C3
- INF000D4
- INF000E5

### Database Keys
15 sample database keys with numeric suffixes:
- KEY_7, KEY_12, KEY_17, KEY_22, KEY_27
- KEY_32, KEY_37, KEY_42, KEY_47, KEY_52
- KEY_57, KEY_62, KEY_67, KEY_72, KEY_77
- KEY_82, KEY_87, KEY_92

### Value Generation
Values are generated deterministically using the formula:
```
base_value = {1000.0, 2000.0, 3000.0, 4000.0, 5000.0} (based on ISIN)
value = base_value + key_number * 10.5
```

This ensures each (ISIN, key) combination has a unique, predictable value.

## Functions

### `db_lookup(isin, key)`
Main function for retrieving database values.

**Parameters:**
- `isin` (str): International Securities Identification Number
- `key` (str): Database key name (e.g., "KEY_12")

**Returns:**
- String representation of the numeric value if found
- "N/A" if the (isin, key) combination doesn't exist

### `get_all_keys()`
Returns a list of all database key names.

**Returns:**
- List of strings representing all available database keys

## Usage in ETL Pipeline

The mock database integrates with the ETL pipeline through:
1. **DBMappingAgent**: Resolves all database lookups for input rows
2. **Rule Interpreter**: Identifies rules requiring database lookups
3. **Output Mapping**: Incorporates database values into output rows
4. **Runtime Validation**: Validates database-derived output values

## Example Usage

```python
from mock_db import db_lookup

# Lookup a value
value = db_lookup("INF000A1", "KEY_12")
print(value)  # Outputs: "1126.0000"

# Handle missing values
missing = db_lookup("UNKNOWN", "KEY_999")
print(missing)  # Outputs: "N/A"
```

## Extending for Production

To replace the mock database with a real database:

1. Modify the `db_lookup` function to connect to your database
2. Replace the dictionary-based lookup with SQL queries
3. Add proper connection management and error handling
4. Implement caching if needed for performance
5. Add authentication and security measures

Example production implementation:
```python
def db_lookup(isin, key):
    """Production version connecting to real database."""
    try:
        # Connect to database
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Execute query
        cursor.execute("SELECT value FROM db_table WHERE isin=? AND key=?", (isin, key))
        result = cursor.fetchone()
        
        # Return result or N/A
        return str(result[0]) if result else "N/A"
    except Exception as e:
        print(f"Database error: {e}")
        return "N/A"
```

## Testing Benefits

The deterministic nature of the mock database enables:
- Reproducible test scenarios
- Consistent validation of ETL processes
- Easy identification of calculation errors
- Verification of database integration without external dependencies
- Performance testing without network latency

## Data Consistency

All values are generated with 4-decimal precision to match the ETL pipeline's arithmetic engine, ensuring consistency between calculated and database-derived values.